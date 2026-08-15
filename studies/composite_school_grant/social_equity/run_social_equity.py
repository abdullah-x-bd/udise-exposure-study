from __future__ import annotations

"""Comprehensive social-equity extension for the Composite School Grant study.

The script deliberately separates three government-school universes:
  * core_state_local: management codes 1,2,3 (the original confirmatory sample)
  * broad_state: 1,2,3,6,89,90 (verified State/UT-government management categories)
  * all_udise_government: broad_state plus the principal Central-government codes

Government-aided, partially aided and private schools are never included.

Primary causal object: heterogeneity in the correctly timed 250/251 CSG financial
first stage, not raw cross-sectional grant differences.  Social category and religion
are treated as separate marginal classifications; they are never subtracted jointly.
"""

import csv
import json
import math
import os
import re
import runpy
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

PANEL = runpy.run_path(
    "studies/composite_school_grant/scripts/03_build_panel.py",
    run_name="csg_social_equity_panel_lib",
)

YEARS = PANEL["YEARS"]
extract_archive = PANEL["extract_archive"]
csv_source = PANEL["csv_source"]
source_columns = PANEL["source_columns"]
qid = PANEL["qid"]
lit = PANEL["lit"]
ref = PANEL["ref"]
nref = PANEL["nref"]

# The four post-2018 cohorts for which the +3 UDISE reporting round is usable.
PRIMARY_ASSIGNMENT_YEARS = ["2019-20", "2020-21", "2021-22", "2022-23"]
CUTOFF = 250.5
BW = 30

CORE_STATE_LOCAL = {1, 2, 3}
BROAD_STATE = {1, 2, 3, 6, 89, 90}
CENTRAL = {92, 93, 94, 95, 96, 101}
AMBIGUOUS_GOV = {91}  # Ministry of Labour in UDISE master; never in primary CSG universe.
ALL_UDISE_GOVERNMENT = BROAD_STATE | CENTRAL

UNIVERSES = {
    "core_state_local": CORE_STATE_LOCAL,
    "broad_state": BROAD_STATE,
    "all_udise_government": ALL_UDISE_GOVERNMENT,
}

SOCIAL_IDS = {
    "general": (1, 1),
    "sc": (1, 2),
    "st": (1, 3),
    "obc": (1, 4),
}
RELIGION_IDS = {
    "muslim": (2, 5),
    "christian": (2, 6),
    "sikh": (2, 7),
    "buddhist": (2, 8),
    "parsi": (2, 9),
    "jain": (2, 10),
}
GROUPS = list(SOCIAL_IDS) + list(RELIGION_IDS) + ["non_listed_minority_religion"]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=float), encoding="utf-8")


def school_id(cols: dict[str, str]) -> str:
    x = cols.get("pseudocode") or cols.get("psuedocode")
    if not x:
        raise RuntimeError("school identifier not found")
    return x


def class_total_expr(cols: dict[str, str], max_class: int = 12) -> str:
    terms = [
        f"COALESCE({nref(cols, f'c{k}_{sex}')},0)"
        for k in range(1, max_class + 1)
        for sex in ("b", "g")
        if f"c{k}_{sex}" in cols
    ]
    if not terms:
        raise RuntimeError("class-level enrolment columns not found")
    return " + ".join(terms)


def norm_label(x: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(x).lower()).strip()


def early_group_label_map(con: duckdb.DuckDBPyConnection, src: str, cols: dict[str, str]) -> dict[str, str]:
    d = ref(cols, "item_desc")
    if not d:
        raise RuntimeError("early enrolment table has neither item_group/item_id nor item_desc")
    vals = [str(r[0]).strip() for r in con.execute(
        f"SELECT DISTINCT TRIM(CAST({d} AS VARCHAR)) FROM {src} WHERE {d} IS NOT NULL"
    ).fetchall() if r[0] is not None]
    out: dict[str, str] = {}
    for raw in vals:
        n = norm_label(raw)
        if n in {"general", "gen"} or "general" in n:
            out.setdefault("general", raw)
        elif n in {"sc", "scheduled caste"} or "scheduled caste" in n:
            out.setdefault("sc", raw)
        elif n in {"st", "scheduled tribe"} or "scheduled tribe" in n:
            out.setdefault("st", raw)
        elif n in {"obc", "other backward class", "other backward classes"} or "other backward" in n:
            out.setdefault("obc", raw)
        elif "muslim" in n:
            out.setdefault("muslim", raw)
        elif "christian" in n:
            out.setdefault("christian", raw)
        elif n == "sikh" or " sikh" in (" " + n):
            out.setdefault("sikh", raw)
        elif "buddh" in n:
            out.setdefault("buddhist", raw)
        elif "parsi" in n or "zoroastr" in n:
            out.setdefault("parsi", raw)
        elif "jain" in n:
            out.setdefault("jain", raw)
    missing_social = [g for g in SOCIAL_IDS if g not in out]
    if missing_social:
        raise RuntimeError(f"could not identify required social-category labels: {missing_social}; labels={vals[:80]}")
    return out


def build_composition_year(
    con: duckdb.DuckDBPyConnection,
    repo: str,
    token: str,
    year: str,
    work: Path,
    outdir: Path,
) -> tuple[Path, dict]:
    en_paths = extract_archive(repo, token, year, "enrolment_1", work)
    p_paths = extract_archive(repo, token, year, "profile_1", work)
    en = csv_source(en_paths)
    p = csv_source(p_paths)
    ec = source_columns(con, en)
    pc = source_columns(con, p)
    ei = school_id(ec)
    pi = school_id(pc)
    csum = class_total_expr(ec, 12)

    label_map: dict[str, str] = {}
    if "item_group" not in ec or "item_id" not in ec:
        label_map = early_group_label_map(con, en, ec)

    def group_select(name: str) -> str:
        if "item_group" in ec and "item_id" in ec:
            ig, ii = (SOCIAL_IDS | RELIGION_IDS)[name]
            cond = f"{nref(ec,'item_group')}={ig} AND {nref(ec,'item_id')}={ii}"
        else:
            raw = label_map.get(name)
            if raw is None:
                return f"CAST({qid(ei)} AS VARCHAR) pseudocode, 0.0 AS {name}_n"
            cond = f"TRIM(CAST({ref(ec,'item_desc')} AS VARCHAR))={lit(raw)}"
        return f"CAST({qid(ei)} AS VARCHAR) pseudocode, SUM(CASE WHEN {cond} THEN ({csum}) ELSE 0 END) AS {name}_n"

    # Aggregate every margin in one pass. For early schemas religious labels may be absent;
    # those groups remain zero and are explicitly reported by validation diagnostics.
    agg_terms = []
    for name in list(SOCIAL_IDS) + list(RELIGION_IDS):
        if "item_group" in ec and "item_id" in ec:
            ig, ii = (SOCIAL_IDS | RELIGION_IDS)[name]
            agg_terms.append(f"SUM(CASE WHEN {nref(ec,'item_group')}={ig} AND {nref(ec,'item_id')}={ii} THEN ({csum}) ELSE 0 END) AS {name}_n")
        else:
            raw = label_map.get(name)
            if raw is None:
                agg_terms.append(f"0.0 AS {name}_n")
            else:
                agg_terms.append(f"SUM(CASE WHEN TRIM(CAST({ref(ec,'item_desc')} AS VARCHAR))={lit(raw)} THEN ({csum}) ELSE 0 END) AS {name}_n")

    # Total enrolment is the mutually exclusive social-category margin only.
    if "item_group" in ec and "item_id" in ec:
        total_cond = f"{nref(ec,'item_group')}=1 AND {nref(ec,'item_id')} IN (1,2,3,4)"
    else:
        social_raw = [label_map[g] for g in SOCIAL_IDS]
        total_cond = f"TRIM(CAST({ref(ec,'item_desc')} AS VARCHAR)) IN ({','.join(lit(x) for x in social_raw)})"

    mgmt = nref(pc, "managment", "p")
    state = ref(pc, "state", "p") or "NULL"
    district = ref(pc, "district", "p") or "NULL"
    rural = nref(pc, "rural_urban", "p")
    category = nref(pc, "school_category", "p")

    tmp = outdir / "composition" / f"{year}.parquet"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE social_{year.replace('-','_')} AS
        SELECT CAST({qid(ei)} AS VARCHAR) pseudocode,
               SUM(CASE WHEN {total_cond} THEN ({csum}) ELSE 0 END) AS enrol,
               {','.join(agg_terms)}
        FROM {en}
        GROUP BY 1
    """)
    tname = f"social_{year.replace('-','_')}"
    religion_sum = " + ".join(f"COALESCE(s.{g}_n,0)" for g in RELIGION_IDS)
    share_terms = [f"CASE WHEN s.enrol>0 THEN s.{g}_n/s.enrol END AS {g}_share" for g in list(SOCIAL_IDS)+list(RELIGION_IDS)]
    share_terms.append(f"CASE WHEN s.enrol>0 THEN GREATEST(0,s.enrol-({religion_sum}))/s.enrol END AS non_listed_minority_religion_share")
    con.execute(f"""
        COPY (
            SELECT {lit(year)} academic_year,
                   CAST(p.{qid(pi)} AS VARCHAR) pseudocode,
                   CAST({state} AS VARCHAR) state,
                   CAST({district} AS VARCHAR) district,
                   {rural} rural_urban,
                   {category} school_category,
                   {mgmt} management,
                   s.enrol,
                   {','.join('s.'+g+'_n' for g in list(SOCIAL_IDS)+list(RELIGION_IDS))},
                   {','.join(share_terms)}
            FROM {p} p
            JOIN {tname} s ON CAST(p.{qid(pi)} AS VARCHAR)=s.pseudocode
            WHERE s.enrol>0
        ) TO {lit(str(tmp))} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
    """)

    q = con.execute(f"""
        SELECT COUNT(*) n,
               AVG(ABS((general_n+sc_n+st_n+obc_n)-enrol)) mean_social_sum_error,
               MAX(ABS((general_n+sc_n+st_n+obc_n)-enrol)) max_social_sum_error,
               AVG(CASE WHEN muslim_share>0 THEN 1.0 ELSE 0.0 END) muslim_positive_share,
               AVG(CASE WHEN christian_share>0 THEN 1.0 ELSE 0.0 END) christian_positive_share,
               AVG(CASE WHEN sikh_share>0 THEN 1.0 ELSE 0.0 END) sikh_positive_share
        FROM read_parquet({lit(str(tmp))})
    """).fetchone()
    diag = {
        "year": year,
        "schools": int(q[0]),
        "mean_social_sum_error": q[1],
        "max_social_sum_error": q[2],
        "muslim_positive_school_share": q[3],
        "christian_positive_school_share": q[4],
        "sikh_positive_school_share": q[5],
        "early_label_map": label_map,
    }
    return tmp, diag


def load_financial_year(
    con: duckdb.DuckDBPyConnection,
    repo: str,
    token: str,
    year: str,
    work: Path,
    outdir: Path,
) -> Path:
    paths = extract_archive(repo, token, year, "profile_2", work)
    s = csv_source(paths)
    c = source_columns(con, s)
    sid = school_id(c)
    p = outdir / "finance" / f"{year}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"""
        COPY (
          SELECT CAST({qid(sid)} AS VARCHAR) pseudocode,
                 {nref(c,'grants_receipt')} receipt,
                 {nref(c,'grants_expenditure')} expenditure
          FROM {s}
        ) TO {lit(str(p))} (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    return p


def government_universe(management: pd.Series, codes: set[int]) -> pd.Series:
    x = pd.to_numeric(management, errors="coerce")
    return x.isin(codes)


def cluster_fit(X: np.ndarray, y: np.ndarray, w: np.ndarray, clusters: np.ndarray, cov_type: str = "cluster"):
    keep = np.isfinite(y) & np.isfinite(w) & (w > 0) & np.all(np.isfinite(X), axis=1)
    X, y, w, clusters = X[keep], y[keep], w[keep], clusters[keep]
    if len(y) < X.shape[1] + 50:
        return None
    model = sm.WLS(y, X, weights=w)
    if cov_type == "cluster" and len(pd.unique(clusters)) >= 8:
        return model.fit(cov_type="cluster", cov_kwds={"groups": clusters, "use_correction": True})
    return model.fit(cov_type="HC3")


def weighted_demean(df: pd.DataFrame, cols: list[str], fe: str, wcol: str) -> pd.DataFrame:
    d = df.copy()
    w = d[wcol].to_numpy(float)
    for c in cols:
        x = d[c].to_numpy(float)
        wx = pd.Series(w*x, index=d.index).groupby(d[fe]).transform("sum").to_numpy(float)
        sw = pd.Series(w, index=d.index).groupby(d[fe]).transform("sum").to_numpy(float)
        d[c] = x - np.divide(wx, sw, out=np.zeros_like(wx), where=sw>0)
    return d


def rd_interaction(df: pd.DataFrame, share_col: str, fe_level: str, adjusted: bool) -> dict | None:
    d = df.copy()
    d = d[np.isfinite(d["receipt"]) & np.isfinite(d[share_col]) & np.isfinite(d["enrol"])]
    d = d[np.abs(d.enrol - CUTOFF) <= BW].copy()
    if len(d) < 1200:
        return None
    d["T"] = (d.enrol >= CUTOFF).astype(float)
    d["z"] = d.enrol - CUTOFF
    d["w"] = np.maximum(0, 1 - np.abs(d.z)/BW)
    d["S"] = d[share_col].astype(float)
    d["Tz"] = d.T * 0  # overwritten below to avoid attribute ambiguity
    d["Tz"] = d["T"] * d["z"]
    d["TS"] = d["T"] * d["S"]
    d["zS"] = d["z"] * d["S"]
    d["TzS"] = d["T"] * d["z"] * d["S"]
    d["y"] = (d.receipt >= 75000).astype(float)
    if fe_level == "state_year":
        d["fe"] = d.state.astype(str) + "|" + d.assignment_year.astype(str)
    elif fe_level == "district_year":
        d["fe"] = d.state.astype(str) + "|" + d.district.astype(str) + "|" + d.assignment_year.astype(str)
    elif fe_level == "year":
        d["fe"] = d.assignment_year.astype(str)
    else:
        raise ValueError(fe_level)
    cols = ["y", "T", "z", "Tz", "S", "TS", "zS", "TzS"]
    if adjusted:
        # Covariates are used only for precision/robustness, not as eligibility definitions.
        for base in ("rural_urban", "school_category", "management"):
            vals = pd.to_numeric(d[base], errors="coerce").fillna(-999).astype(int)
            cats = sorted(vals.unique())
            for c in cats[1:]:
                name = f"cv_{base}_{c}"
                d[name] = (vals == c).astype(float)
                cols.append(name)
    d = weighted_demean(d, cols, "fe", "w")
    Xcols = ["T", "z", "Tz", "S", "TS", "zS", "TzS"] + [c for c in cols if c.startswith("cv_")]
    fit = cluster_fit(d[Xcols].to_numpy(float), d.y.to_numpy(float), d.w.to_numpy(float), d.state.astype(str).to_numpy())
    if fit is None:
        return None
    j = Xcols.index("TS")
    coef = float(fit.params[j])
    se = float(fit.bse[j])
    p = float(fit.pvalues[j])
    return {
        "n": int(fit.nobs),
        "clusters": int(d.state.nunique()),
        "interaction_per_10pp": coef * 0.10,
        "se_per_10pp": se * 0.10,
        "p": p,
        "ci_low_per_10pp": (coef - 1.96*se)*0.10,
        "ci_high_per_10pp": (coef + 1.96*se)*0.10,
        "fe": fe_level,
        "adjusted": adjusted,
    }


def rd_level_in_bin(df: pd.DataFrame, share_col: str, bin_index: int, fe_level: str = "state_year") -> dict | None:
    d = df[np.isfinite(df[share_col]) & np.isfinite(df.receipt)].copy()
    b = np.minimum((d[share_col].clip(0,1) * 20).astype(int), 19)
    d = d[b == bin_index]
    d = d[np.abs(d.enrol - CUTOFF) <= BW].copy()
    if len(d) < 350 or (d.enrol < CUTOFF).sum() < 100 or (d.enrol >= CUTOFF).sum() < 100:
        return None
    d["T"] = (d.enrol >= CUTOFF).astype(float)
    d["z"] = d.enrol - CUTOFF
    d["Tz"] = d.T * 0
    d["Tz"] = d["T"] * d["z"]
    d["y"] = (d.receipt >= 75000).astype(float)
    d["w"] = np.maximum(0, 1 - np.abs(d.z)/BW)
    if fe_level == "state_year":
        d["fe"] = d.state.astype(str) + "|" + d.assignment_year.astype(str)
    else:
        d["fe"] = d.assignment_year.astype(str)
    cols = ["y", "T", "z", "Tz"]
    d = weighted_demean(d, cols, "fe", "w")
    fit = cluster_fit(d[["T","z","Tz"]].to_numpy(float), d.y.to_numpy(float), d.w.to_numpy(float), d.state.astype(str).to_numpy())
    if fit is None:
        return None
    tau, se, p = float(fit.params[0]), float(fit.bse[0]), float(fit.pvalues[0])
    return {
        "bin": bin_index,
        "share_low": bin_index*0.05,
        "share_high": (bin_index+1)*0.05,
        "n": int(fit.nobs),
        "states": int(d.state.nunique()),
        "tau": tau,
        "se": se,
        "p": p,
        "ci_low": tau-1.96*se,
        "ci_high": tau+1.96*se,
    }


def fidelity_amount(enrol: pd.Series) -> pd.Series:
    # High-confidence portion of the schedule that is stable over the study period.
    e = pd.to_numeric(enrol, errors="coerce")
    out = pd.Series(np.nan, index=e.index, dtype=float)
    out[(e >= 101) & (e <= 250)] = 50000
    out[(e >= 251) & (e <= 1000)] = 75000
    out[e > 1000] = 100000
    return out


def fidelity_gradient(df: pd.DataFrame, share_col: str, outcome: str, fe_level: str) -> dict | None:
    d = df.copy()
    d["entitlement"] = fidelity_amount(d.enrol)
    d = d[np.isfinite(d.entitlement) & np.isfinite(d.receipt) & np.isfinite(d[share_col])].copy()
    if len(d) < 3000:
        return None
    d["reported_meets_nominal_band"] = (d.receipt >= d.entitlement).astype(float)
    d["reported_exact_nominal_band"] = np.isclose(d.receipt, d.entitlement).astype(float)
    d["reported_shortfall_share"] = np.maximum(d.entitlement-d.receipt,0)/d.entitlement
    d["reported_receipt_ratio_c2"] = np.clip(d.receipt/d.entitlement,0,2)
    d["S"] = d[share_col].astype(float)
    d["high_band"] = (d.enrol >= 251).astype(float)
    d["log_enrol"] = np.log(d.enrol.astype(float))
    d["w"] = 1.0
    if fe_level == "state_year":
        d["fe"] = d.state.astype(str) + "|" + d.assignment_year.astype(str)
    elif fe_level == "district_year":
        d["fe"] = d.state.astype(str) + "|" + d.district.astype(str) + "|" + d.assignment_year.astype(str)
    else:
        d["fe"] = d.assignment_year.astype(str)
    ycol = outcome
    cols = [ycol, "S", "high_band", "log_enrol"]
    # Add management, rural and school-category controls.
    for base in ("management", "rural_urban", "school_category"):
        vals = pd.to_numeric(d[base], errors="coerce").fillna(-999).astype(int)
        cats = sorted(vals.unique())
        for c in cats[1:]:
            name = f"cv_{base}_{c}"
            d[name] = (vals == c).astype(float)
            cols.append(name)
    d = weighted_demean(d, cols, "fe", "w")
    Xcols = ["S", "high_band", "log_enrol"] + [c for c in cols if c.startswith("cv_")]
    fit = cluster_fit(d[Xcols].to_numpy(float), d[ycol].to_numpy(float), d.w.to_numpy(float), d.state.astype(str).to_numpy())
    if fit is None:
        return None
    coef, se, p = float(fit.params[0]), float(fit.bse[0]), float(fit.pvalues[0])
    return {
        "outcome": outcome,
        "fe": fe_level,
        "n": int(fit.nobs),
        "states": int(d.state.nunique()),
        "gradient_per_10pp": coef*0.10,
        "se_per_10pp": se*0.10,
        "p": p,
        "ci_low_per_10pp": (coef-1.96*se)*0.10,
        "ci_high_per_10pp": (coef+1.96*se)*0.10,
    }


def state_descriptive_gradients(df: pd.DataFrame, share_col: str) -> list[dict]:
    out = []
    for state, d in df.groupby("state"):
        d = d[np.isfinite(d[share_col]) & np.isfinite(d.receipt)].copy()
        d = d[np.abs(d.enrol-CUTOFF) <= BW]
        if len(d) < 500 or (d.enrol<CUTOFF).sum()<150 or (d.enrol>=CUTOFF).sum()<150:
            continue
        d["T"] = (d.enrol>=CUTOFF).astype(float)
        d["z"] = d.enrol-CUTOFF
        d["S"] = d[share_col]
        d["Tz"] = d["T"]*d["z"]
        d["TS"] = d["T"]*d["S"]
        d["zS"] = d["z"]*d["S"]
        d["TzS"] = d["T"]*d["z"]*d["S"]
        d["y"] = (d.receipt>=75000).astype(float)
        d["w"] = np.maximum(0,1-np.abs(d.z)/BW)
        year_dummies = pd.get_dummies(d.assignment_year.astype(str), drop_first=True, dtype=float)
        X = np.column_stack([d[c].to_numpy(float) for c in ["T","z","Tz","S","TS","zS","TzS"]] + [year_dummies.to_numpy(float)])
        fit = cluster_fit(X,d.y.to_numpy(float),d.w.to_numpy(float),d.assignment_year.astype(str).to_numpy(),cov_type="hc")
        if fit is None:
            continue
        j=4
        out.append({"state":state,"n":int(fit.nobs),"interaction_per_10pp":float(fit.params[j])*0.10,"se_per_10pp":float(fit.bse[j])*0.10,"p":float(fit.pvalues[j])})
    return out


def first_difference_panel(df: pd.DataFrame, share_col: str) -> dict | None:
    d = df[["pseudocode","assignment_year","state",share_col,"reported_receipt_ratio_c2"]].dropna().copy()
    order = {y:i for i,y in enumerate(PRIMARY_ASSIGNMENT_YEARS)}
    d["yi"] = d.assignment_year.map(order)
    d = d.sort_values(["pseudocode","yi"])
    d["prev_yi"] = d.groupby("pseudocode").yi.shift(1)
    d["dS"] = d[share_col] - d.groupby("pseudocode")[share_col].shift(1)
    d["dY"] = d.reported_receipt_ratio_c2 - d.groupby("pseudocode").reported_receipt_ratio_c2.shift(1)
    d = d[(d.yi-d.prev_yi)==1].dropna(subset=["dS","dY"])
    if len(d)<3000 or d.dS.std()<1e-6:
        return None
    pair = d.prev_yi.astype(int).astype(str)+"_"+d.yi.astype(int).astype(str)
    pdum = pd.get_dummies(pair,drop_first=True,dtype=float)
    X=np.column_stack([d.dS.to_numpy(float),pdum.to_numpy(float)])
    fit=sm.OLS(d.dY.to_numpy(float),X).fit(cov_type="cluster",cov_kwds={"groups":d.state.astype(str).to_numpy()})
    return {"n_changes":int(fit.nobs),"schools":int(d.pseudocode.nunique()),"gradient_per_10pp_change":float(fit.params[0])*0.10,"se_per_10pp_change":float(fit.bse[0])*0.10,"p":float(fit.pvalues[0])}


def main() -> None:
    repo = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    out = Path("studies/composite_school_grant/outputs/social_equity")
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")

    composition_paths: dict[str,Path] = {}
    finance_paths: dict[str,Path] = {}
    diagnostics=[]
    needed_composition = sorted(set(["2018-19"] + PRIMARY_ASSIGNMENT_YEARS), key=YEARS.index)
    needed_finance = [YEARS[YEARS.index(y)+3] for y in PRIMARY_ASSIGNMENT_YEARS]

    with tempfile.TemporaryDirectory(prefix="csg_social_equity_") as td:
        work=Path(td)
        for y in needed_composition:
            print("COMPOSITION",y,flush=True)
            p,diag=build_composition_year(con,repo,token,y,work,out)
            composition_paths[y]=p;diagnostics.append(diag)
            shutil.rmtree(work/y,ignore_errors=True)
        for y in needed_finance:
            print("FINANCE",y,flush=True)
            finance_paths[y]=load_financial_year(con,repo,token,y,work,out)
            shutil.rmtree(work/y,ignore_errors=True)

    dump_json(out/"composition_validation.json",diagnostics)

    # Management counts before choosing the analytic universe.
    management_rows=[]
    for y,p in composition_paths.items():
        rows=con.execute(f"SELECT management,COUNT(*) n FROM read_parquet({lit(str(p))}) GROUP BY 1 ORDER BY 1").fetchall()
        for m,n in rows:
            management_rows.append({"assignment_year":y,"management":m,"schools":int(n)})
    write_csv(out/"management_counts.csv",management_rows)

    # Build the four correctly timed assignment->financial-report cohorts.
    cohorts=[]
    for ay in PRIMARY_ASSIGNMENT_YEARS:
        ry=YEARS[YEARS.index(ay)+3]
        cp=composition_paths[ay];fp=finance_paths[ry]
        prev=YEARS[YEARS.index(ay)-1]
        pp=composition_paths.get(prev)
        prev_join=""
        prev_cols=",".join(f"pr.{g}_share AS prev_{g}_share" for g in GROUPS)
        if pp:
            prev_join=f"LEFT JOIN read_parquet({lit(str(pp))}) pr ON a.pseudocode=pr.pseudocode"
        else:
            prev_cols=",".join(f"NULL::DOUBLE AS prev_{g}_share" for g in GROUPS)
        cohort=out/"cohorts"/f"{ay}.parquet";cohort.parent.mkdir(parents=True,exist_ok=True)
        con.execute(f"""
            COPY (
              SELECT a.*, {lit(ay)} assignment_year, {lit(ry)} report_year,
                     f.receipt,f.expenditure,{prev_cols}
              FROM read_parquet({lit(str(cp))}) a
              LEFT JOIN read_parquet({lit(str(fp))}) f USING(pseudocode)
              {prev_join}
            ) TO {lit(str(cohort))} (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        cohorts.append(cohort)
    pooled=out/"social_funding_panel.parquet"
    con.execute(f"COPY (SELECT * FROM read_parquet([{','.join(lit(str(p)) for p in cohorts)}],union_by_name=true)) TO {lit(str(pooled))} (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 100000)")

    all_df=con.execute(f"SELECT * FROM read_parquet({lit(str(pooled))})").df()

    universe_counts=[]; interaction_rows=[]; bin_rows=[]; fidelity_rows=[]; state_rows=[]; fd_rows=[]
    for uname,codes in UNIVERSES.items():
        df=all_df[government_universe(all_df.management,codes)].copy()
        universe_counts.append({"universe":uname,"school_year_rows":len(df),"unique_schools":int(df.pseudocode.nunique()),"management_codes":','.join(map(str,sorted(codes)))})

        # Main heterogeneous RD. Same-vintage composition plus predetermined prior-year composition.
        for g in GROUPS:
            for source,col in [("assignment",f"{g}_share"),("predetermined_previous_year",f"prev_{g}_share")]:
                for fe in ("year","state_year","district_year"):
                    for adj in (False,True):
                        r=rd_interaction(df,col,fe,adj)
                        if r: interaction_rows.append({"universe":uname,"group":g,"composition_source":source,**r})
            # 5-percentage-point visualisation bins use assignment-vintage shares.
            for b in range(20):
                r=rd_level_in_bin(df,f"{g}_share",b)
                if r: bin_rows.append({"universe":uname,"group":g,**r})

        # Whole-universe descriptive fidelity gradients. Restrict to the stable >=101 schedule.
        df["entitlement"]=fidelity_amount(df.enrol)
        df["reported_meets_nominal_band"]=(df.receipt>=df.entitlement).astype(float)
        df["reported_exact_nominal_band"]=np.isclose(df.receipt,df.entitlement).astype(float)
        df["reported_shortfall_share"]=np.maximum(df.entitlement-df.receipt,0)/df.entitlement
        df["reported_receipt_ratio_c2"]=np.clip(df.receipt/df.entitlement,0,2)
        for g in GROUPS:
            for outcome in ("reported_meets_nominal_band","reported_exact_nominal_band","reported_shortfall_share","reported_receipt_ratio_c2"):
                for fe in ("state_year","district_year"):
                    r=fidelity_gradient(df,f"{g}_share",outcome,fe)
                    if r:fidelity_rows.append({"universe":uname,"group":g,**r})
            if uname=="broad_state":
                for r in state_descriptive_gradients(df,f"{g}_share"):
                    state_rows.append({"group":g,**r})
                r=first_difference_panel(df,f"{g}_share")
                if r:fd_rows.append({"group":g,**r})

    # FDR within each model family.
    for rows,name in [(interaction_rows,"interaction"),(fidelity_rows,"fidelity"),(state_rows,"state")]:
        by=defaultdict(list)
        for i,r in enumerate(rows):
            key=tuple((k,r.get(k)) for k in ("universe","composition_source","fe","adjusted","outcome") if k in r)
            if r.get("p") is not None and math.isfinite(float(r["p"])):by[key].append(i)
        for idxs in by.values():
            ps=[rows[i]["p"] for i in idxs]
            q=multipletests(ps,method="fdr_bh")[1]
            for i,qq in zip(idxs,q):rows[i]["q_bh"]=float(qq)

    write_csv(out/"universe_counts.csv",universe_counts)
    write_csv(out/"rd_social_interactions.csv",interaction_rows)
    write_csv(out/"rd_5pp_bins.csv",bin_rows)
    write_csv(out/"whole_universe_fidelity_gradients.csv",fidelity_rows)
    write_csv(out/"state_social_gradients.csv",state_rows)
    write_csv(out/"school_first_difference_gradients.csv",fd_rows)

    # Concise machine-generated report focusing on the pre-specified primary model:
    # broad_state, previous-year composition, state-year FE, adjusted.
    primary=[r for r in interaction_rows if r["universe"]=="broad_state" and r["composition_source"]=="predetermined_previous_year" and r["fe"]=="state_year" and r["adjusted"]]
    lines=["# CSG social-equity results","","Primary heterogeneous-RD model: broad verified State/UT government universe, +/-30 around 250/251, correctly aligned +3 UDISE financial field, previous-year social composition, state-by-year fixed effects, covariate-adjusted, state-clustered inference.",""]
    for r in sorted(primary,key=lambda x:x["group"]):
        lines.append(f"- {r['group']}: change in the threshold first stage per +10 percentage points = {100*r['interaction_per_10pp']:+.2f} pp (95% CI {100*r['ci_low_per_10pp']:+.2f} to {100*r['ci_high_per_10pp']:+.2f}), p={r['p']:.4g}, q={r.get('q_bh',float('nan')):.4g}, n={r['n']}")
    lines += ["","Interpretation guardrails:","- Religion and caste/social category are separate marginal classifications. No Hindu-General or upper-caste-Hindu residual is constructed.","- Whole-universe fidelity measures compare UDISE-reported amounts with nominal formula bands and are descriptive because the UDISE financial field can contain timing/accounting effects.","- The heterogeneous RD asks whether the formula-induced discontinuity itself changes with social composition; it does not by itself identify discrimination.","- State-specific coefficients are exploratory; state-by-year and district-by-year fixed-effect pooled models are the primary geographic decompositions."]
    (out/"RESULTS.md").write_text("\n".join(lines),encoding="utf-8")
    print("\n".join(lines),flush=True)
    con.close()


if __name__ == "__main__":
    main()
