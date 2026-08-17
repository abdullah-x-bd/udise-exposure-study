from __future__ import annotations

import csv
import json
import math
import os
import re
import runpy
import shutil
from pathlib import Path
from typing import Iterable

import duckdb
import numpy as np
import pandas as pd

_CSG = runpy.run_path(
    "studies/composite_school_grant/scripts/03_build_panel.py",
    run_name="muslim_equity_csg_helpers",
)

YEARS = _CSG["YEARS"]
extract_archive = _CSG["extract_archive"]
csv_source = _CSG["csv_source"]
source_columns = _CSG["source_columns"]
qid = _CSG["qid"]
lit = _CSG["lit"]
ref = _CSG["ref"]
nref = _CSG["nref"]

MAIN_GOV_CODES = (1, 2, 3, 6, 89, 90)
CORE_GOV_CODES = (1, 2, 3)
RTE_CUTOFFS = (60.5, 90.5, 120.5)
MUSLIM_BINS = np.arange(0.0, 1.000001, 0.05)


def ident(cols: dict[str, str]) -> str:
    value = cols.get("pseudocode") or cols.get("psuedocode")
    if not value:
        raise RuntimeError("school identifier missing")
    return value


def first_ref(cols: dict[str, str], names: Iterable[str], alias: str | None = None) -> str | None:
    for name in names:
        value = ref(cols, name, alias)
        if value:
            return value
    return None


def first_num(cols: dict[str, str], names: Iterable[str], alias: str | None = None) -> str:
    value = first_ref(cols, names, alias)
    if not value:
        return "NULL"
    return f"TRY_CAST(NULLIF(TRIM(CAST({value} AS VARCHAR)), '') AS DOUBLE)"


def first_str(cols: dict[str, str], names: Iterable[str], alias: str | None = None) -> str:
    value = first_ref(cols, names, alias)
    if not value:
        return "NULL"
    return f"NULLIF(TRIM(CAST({value} AS VARCHAR)), '')"


def class_sum(cols: dict[str, str], start: int, end: int, sex: str | None = None) -> str:
    sexes = (sex,) if sex else ("b", "g")
    terms: list[str] = []
    for grade in range(start, end + 1):
        for s in sexes:
            key = f"c{grade}_{s}"
            if key in cols:
                terms.append(f"COALESCE({nref(cols, key)},0)")
    if not terms:
        raise RuntimeError(f"no class columns found for grades {start}-{end}, sex={sex}")
    return " + ".join(terms)


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def enrolment_filters(
    con: duckdb.DuckDBPyConnection,
    src: str,
    cols: dict[str, str],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return exact SQL filters for social and religion rows across schema vintages."""
    if "item_group" in cols and "item_id" in cols:
        ig = nref(cols, "item_group")
        ii = nref(cols, "item_id")
        filters = {
            "general": f"({ig}=1 AND {ii}=1)",
            "sc": f"({ig}=1 AND {ii}=2)",
            "st": f"({ig}=1 AND {ii}=3)",
            "obc": f"({ig}=1 AND {ii}=4)",
            "muslim": f"({ig}=2 AND {ii}=5)",
            "christian": f"({ig}=2 AND {ii}=6)",
            "sikh": f"({ig}=2 AND {ii}=7)",
            "buddhist": f"({ig}=2 AND {ii}=8)",
            "parsi": f"({ig}=2 AND {ii}=9)",
            "jain": f"({ig}=2 AND {ii}=10)",
        }
        return filters, {k: [] for k in filters}

    desc = first_ref(cols, ("item_desc", "item_description", "item_name"))
    if not desc:
        raise RuntimeError("early enrolment schema has no item_group/item_id or item_desc")
    raw_values = [
        str(r[0]).strip()
        for r in con.execute(
            f"SELECT DISTINCT {desc} FROM {src} WHERE {desc} IS NOT NULL"
        ).fetchall()
        if r[0] is not None
    ]
    buckets: dict[str, list[str]] = {
        "general": [], "sc": [], "st": [], "obc": [],
        "muslim": [], "christian": [], "sikh": [], "buddhist": [], "parsi": [], "jain": [],
    }
    for raw in raw_values:
        n = _normalize_label(raw)
        target = None
        if n in {"general", "gen"} or n.startswith("general "):
            target = "general"
        elif n in {"sc", "scheduled caste"} or "scheduled caste" in n:
            target = "sc"
        elif n in {"st", "scheduled tribe"} or "scheduled tribe" in n:
            target = "st"
        elif n in {"obc", "other backward class", "other backward classes"} or "other backward" in n:
            target = "obc"
        elif "muslim" in n:
            target = "muslim"
        elif "christian" in n:
            target = "christian"
        elif re.search(r"(^| )sikh($| )", n):
            target = "sikh"
        elif "buddh" in n:
            target = "buddhist"
        elif "parsi" in n or "zoroastr" in n:
            target = "parsi"
        elif "jain" in n:
            target = "jain"
        if target:
            buckets[target].append(raw)

    missing = [k for k, v in buckets.items() if not v]
    if missing:
        raise RuntimeError(f"could not identify early enrolment labels for {missing}; labels={raw_values[:80]}")
    filters = {
        k: f"TRIM(CAST({desc} AS VARCHAR)) IN ({','.join(lit(x) for x in sorted(set(v)))})"
        for k, v in buckets.items()
    }
    return filters, {k: sorted(set(v)) for k, v in buckets.items()}


def _case_sum(condition: str, expr: str) -> str:
    return f"SUM(CASE WHEN {condition} THEN ({expr}) ELSE 0 END)"


def _yes_no_from_sources(cols: dict[str, str], functional: bool = True, alias: str = "f") -> str:
    early_key = "drinking_water_functional" if functional else "drinking_water_available"
    early = first_ref(cols, (early_key,), alias)
    if early:
        x = f"TRY_CAST(NULLIF(TRIM(CAST({early} AS VARCHAR)), '') AS DOUBLE)"
        return f"CASE WHEN {x}=1 THEN 1 WHEN {x}=2 THEN 0 ELSE NULL END"
    suffix = "_fun_yn" if functional else "_yn"
    bases = ("hand_pump", "well_prot", "tap", "othsrc", "well_unprot", "pack_water")
    vals = []
    for base in bases:
        r = first_ref(cols, (base + suffix,), alias)
        if r:
            vals.append(f"TRY_CAST(NULLIF(TRIM(CAST({r} AS VARCHAR)), '') AS DOUBLE)")
    if not vals:
        return "NULL"
    any_yes = " OR ".join(f"({x}=1)" for x in vals)
    all_no_or_missing = " AND ".join(f"({x}=2 OR {x} IS NULL)" for x in vals)
    return f"CASE WHEN {any_yes} THEN 1 WHEN {all_no_or_missing} THEN 0 ELSE NULL END"


def _binary_yes(cols: dict[str, str], names: Iterable[str], alias: str) -> str:
    r = first_ref(cols, names, alias)
    if not r:
        return "NULL"
    x = f"TRY_CAST(NULLIF(TRIM(CAST({r} AS VARCHAR)), '') AS DOUBLE)"
    return f"CASE WHEN {x}=1 THEN 1 WHEN {x}=2 THEN 0 ELSE NULL END"


def _electricity_ok(cols: dict[str, str], alias: str = "f") -> str:
    r = first_ref(cols, ("electricity_availability", "electricity"), alias)
    if not r:
        return "NULL"
    x = f"TRY_CAST(NULLIF(TRIM(CAST({r} AS VARCHAR)), '') AS DOUBLE)"
    return f"CASE WHEN {x}=1 THEN 1 WHEN {x} IN (2,3) THEN 0 ELSE NULL END"


def build_panel(
    con: duckdb.DuckDBPyConnection,
    repo_id: str,
    token: str,
    work: Path,
    output_dir: Path,
    *,
    teacher: bool,
    facility: bool,
    profile2: bool,
) -> tuple[Path, list[dict]]:
    """Build a temporary harmonised school-year panel. Never upload this panel as an artifact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict] = []
    year_paths: list[Path] = []

    for year in YEARS:
        print(f"BUILD {year}", flush=True)
        tables = ["profile_1", "enrolment_1"]
        if teacher:
            tables.append("teacher")
        if facility:
            tables.append("facility")
        if profile2:
            tables.append("profile_2")

        paths = {t: extract_archive(repo_id, token, year, t, work) for t in tables}
        src = {t: csv_source(paths[t]) for t in tables}
        cols = {t: source_columns(con, src[t]) for t in tables}
        ids = {t: ident(cols[t]) for t in tables}

        p1 = src["profile_1"]
        pc = cols["profile_1"]
        n_rows, n_ids = con.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT CAST({qid(ids['profile_1'])} AS VARCHAR)) FROM {p1}"
        ).fetchone()
        if int(n_rows) != int(n_ids):
            raise RuntimeError(f"{year} profile_1 contains duplicate school identifiers: rows={n_rows}, ids={n_ids}")

        ec = cols["enrolment_1"]
        filters, early_labels = enrolment_filters(con, src["enrolment_1"], ec)
        p15 = class_sum(ec, 1, 5)
        p15_b = class_sum(ec, 1, 5, "b")
        p15_g = class_sum(ec, 1, 5, "g")
        c112 = class_sum(ec, 1, 12)
        c112_b = class_sum(ec, 1, 12, "b")
        c112_g = class_sum(ec, 1, 12, "g")
        social = ("general", "sc", "st", "obc")
        minority = ("muslim", "christian", "sikh", "buddhist", "parsi", "jain")
        social_cond = " OR ".join(f"({filters[k]})" for k in social)

        enrol_cols = [
            f"CAST({qid(ids['enrolment_1'])} AS VARCHAR) AS pseudocode",
            f"{_case_sum(social_cond, p15)} AS enrol_primary",
            f"{_case_sum(social_cond, p15_b)} AS boys_primary",
            f"{_case_sum(social_cond, p15_g)} AS girls_primary",
            f"{_case_sum(social_cond, c112)} AS enrol_c1_12",
            f"{_case_sum(social_cond, c112_b)} AS boys_c1_12",
            f"{_case_sum(social_cond, c112_g)} AS girls_c1_12",
        ]
        for group in social + minority:
            enrol_cols.append(f"{_case_sum(filters[group], p15)} AS {group}_primary")
            enrol_cols.append(f"{_case_sum(filters[group], c112)} AS {group}_c1_12")

        con.execute(
            "CREATE OR REPLACE TEMP TABLE enr AS SELECT "
            + ",".join(enrol_cols)
            + f" FROM {src['enrolment_1']} GROUP BY 1"
        )

        joins = []
        select_extra = []
        if teacher:
            tc = cols["teacher"]
            tid = qid(ids["teacher"])
            joins.append(f"LEFT JOIN {src['teacher']} t ON CAST(p.{qid(ids['profile_1'])} AS VARCHAR)=CAST(t.{tid} AS VARCHAR)")
            primary_terms = [
                first_num(tc, ("class_taught_pr",), "t"),
                first_num(tc, ("class_taught_pr_upr",), "t"),
                first_num(tc, ("class_taught_pr_and_pre_pri", "class_taught_pr_and_pre_primary"), "t"),
            ]
            primary_terms = [x for x in primary_terms if x != "NULL"]
            primary_expr = " + ".join(f"COALESCE({x},0)" for x in primary_terms) if primary_terms else "NULL"
            select_extra += [
                f"{first_num(tc, ('total_tch','total_teacher','total_teachers'), 't')} AS total_teachers",
                f"{primary_expr} AS primary_serving_teachers",
                f"{first_num(tc, ('regular',), 't')} AS regular_teachers",
                f"{first_num(tc, ('contract',), 't')} AS contract_teachers",
                f"{first_num(tc, ('part_time',), 't')} AS part_time_teachers",
                f"{first_num(tc, ('female',), 't')} AS female_teachers",
                f"{first_num(tc, ('graduate',), 't')} AS graduate_teachers",
                f"{first_num(tc, ('post_graduate_and_above',), 't')} AS postgraduate_teachers",
                f"{first_num(tc, ('bed_equivalent',), 't')} AS bed_teachers",
            ]
        else:
            select_extra += [f"NULL AS {x}" for x in (
                "total_teachers", "primary_serving_teachers", "regular_teachers", "contract_teachers",
                "part_time_teachers", "female_teachers", "graduate_teachers", "postgraduate_teachers", "bed_teachers"
            )]

        if facility:
            fc = cols["facility"]
            fid = qid(ids["facility"])
            joins.append(f"LEFT JOIN {src['facility']} f ON CAST(p.{qid(ids['profile_1'])} AS VARCHAR)=CAST(f.{fid} AS VARCHAR)")
            select_extra += [
                f"{first_num(fc, ('total_class_rooms','total_classrooms'), 'f')} AS total_classrooms",
                f"{first_num(fc, ('classrooms_in_good_condition',), 'f')} AS classrooms_good",
                f"{first_num(fc, ('classrooms_needs_major_repair',), 'f')} AS classrooms_major_repair",
                f"{first_num(fc, ('classrooms_needs_minor_repair',), 'f')} AS classrooms_minor_repair",
                f"{first_num(fc, ('total_boys_toilet',), 'f')} AS boys_toilets",
                f"{first_num(fc, ('total_boys_func_toilet',), 'f')} AS boys_func_toilets",
                f"{first_num(fc, ('total_girls_toilet',), 'f')} AS girls_toilets",
                f"{first_num(fc, ('total_girls_func_toilet',), 'f')} AS girls_func_toilets",
                f"{_yes_no_from_sources(fc, True, 'f')} AS water_functional",
                f"{_electricity_ok(fc, 'f')} AS electricity_functional",
            ]
        else:
            select_extra += [f"NULL AS {x}" for x in (
                "total_classrooms", "classrooms_good", "classrooms_major_repair", "classrooms_minor_repair",
                "boys_toilets", "boys_func_toilets", "girls_toilets", "girls_func_toilets",
                "water_functional", "electricity_functional"
            )]

        if profile2:
            p2c = cols["profile_2"]
            p2id = qid(ids["profile_2"])
            joins.append(f"LEFT JOIN {src['profile_2']} p2 ON CAST(p.{qid(ids['profile_1'])} AS VARCHAR)=CAST(p2.{p2id} AS VARCHAR)")
            select_extra += [
                f"{first_num(p2c, ('acad_inspections',), 'p2')} AS academic_inspections",
                f"{first_num(p2c, ('crc_coordinator',), 'p2')} AS crc_visits",
                f"{first_num(p2c, ('block_level_officers',), 'p2')} AS block_visits",
                f"{first_num(p2c, ('district_officers',), 'p2')} AS district_state_visits",
            ]
        else:
            select_extra += [f"NULL AS {x}" for x in (
                "academic_inspections", "crc_visits", "block_visits", "district_state_visits"
            )]

        mgmt = first_num(pc, ("managment", "management"), "p")
        select_sql = f"""
            SELECT
                {lit(year)} AS academic_year,
                CAST(p.{qid(ids['profile_1'])} AS VARCHAR) AS pseudocode,
                {first_str(pc, ('state','state_id','state_code','state_cd'), 'p')} AS state,
                {first_str(pc, ('district','district_id','district_code','district_cd'), 'p')} AS district,
                {first_str(pc, ('block','block_id','block_code','block_cd'), 'p')} AS block,
                {first_num(pc, ('rural_urban','ruralurban'), 'p')} AS rural_urban,
                {first_num(pc, ('school_category','sch_category'), 'p')} AS school_category,
                {first_num(pc, ('school_type',), 'p')} AS school_type,
                {first_num(pc, ('lowclass','lowest_class'), 'p')} AS lowclass,
                {first_num(pc, ('highclass','highest_class'), 'p')} AS highclass,
                {mgmt} AS management,
                CASE WHEN {mgmt} IN ({','.join(map(str, MAIN_GOV_CODES))}) THEN 1 ELSE 0 END AS is_state_local_government,
                CASE WHEN {mgmt} IN ({','.join(map(str, CORE_GOV_CODES))}) THEN 1 ELSE 0 END AS is_core_government,
                e.* EXCLUDE(pseudocode),
                {','.join(select_extra)}
            FROM {p1} p
            LEFT JOIN enr e ON CAST(p.{qid(ids['profile_1'])} AS VARCHAR)=e.pseudocode
            {' '.join(joins)}
        """
        year_path = output_dir / f"{year}.parquet"
        con.execute(
            f"COPY ({select_sql}) TO {lit(str(year_path))} "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
        )
        row = con.execute(
            f"SELECT COUNT(*), COUNT(*) FILTER (WHERE is_state_local_government=1), "
            f"COUNT(*) FILTER (WHERE enrol_c1_12 IS NOT NULL) FROM read_parquet({lit(str(year_path))})"
        ).fetchone()
        reports.append({
            "year": year,
            "rows": int(row[0]),
            "state_local_government_rows": int(row[1]),
            "rows_with_enrolment": int(row[2]),
            "early_labels": early_labels,
            "columns": {t: sorted(cols[t].keys()) for t in tables},
        })
        year_paths.append(year_path)
        shutil.rmtree(work / year, ignore_errors=True)

    panel_path = output_dir / "school_year_panel.parquet"
    path_sql = "[" + ",".join(lit(str(p)) for p in year_paths) + "]"
    con.execute(
        f"COPY (SELECT * FROM read_parquet({path_sql}, union_by_name=true)) TO {lit(str(panel_path))} "
        "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
    )
    return panel_path, reports


def add_shares(df: pd.DataFrame, primary: bool = False) -> pd.DataFrame:
    suffix = "primary" if primary else "c1_12"
    denom = pd.to_numeric(df[f"enrol_{'primary' if primary else 'c1_12'}"], errors="coerce")
    denom = denom.where(denom > 0)
    for g in ("general", "sc", "st", "obc", "muslim", "christian", "sikh", "buddhist", "parsi", "jain"):
        x = pd.to_numeric(df[f"{g}_{suffix}"], errors="coerce")
        df[f"{g}_share"] = (x / denom).clip(lower=0, upper=1)
    minorities = sum(pd.to_numeric(df[f"{g}_{suffix}"], errors="coerce").fillna(0) for g in ("muslim", "christian", "sikh", "buddhist", "parsi", "jain"))
    df["religion_residual"] = (denom - minorities).clip(lower=0)
    df["religion_residual_share"] = (df["religion_residual"] / denom).clip(lower=0, upper=1)
    general = pd.to_numeric(df[f"general_{suffix}"], errors="coerce")
    n = denom
    h = df["religion_residual"]
    df["residual_general_intersection_lb"] = np.maximum(0, h + general - n)
    df["residual_general_intersection_ub"] = np.minimum(h, general)
    df["residual_general_share_lb"] = (df["residual_general_intersection_lb"] / n).clip(0, 1)
    df["residual_general_share_ub"] = (df["residual_general_intersection_ub"] / n).clip(0, 1)
    return df


def muslim_bin(series: pd.Series) -> pd.Categorical:
    edges = list(MUSLIM_BINS)
    labels = [f"{int(100*edges[i])}-{int(100*edges[i+1])}%" for i in range(len(edges)-1)]
    x = pd.to_numeric(series, errors="coerce").clip(0, 1)
    return pd.cut(x, bins=edges, labels=labels, include_lowest=True, right=True)


def required_primary_teachers(enrolment: pd.Series) -> pd.Series:
    """RTE Schedule teacher bands used only through 200 pupils; >200 is left missing here."""
    n = pd.to_numeric(enrolment, errors="coerce")
    out = pd.Series(np.nan, index=n.index, dtype=float)
    out[(n >= 1) & (n <= 60)] = 2
    out[(n >= 61) & (n <= 90)] = 3
    out[(n >= 91) & (n <= 120)] = 4
    out[(n >= 121) & (n <= 150)] = 5
    return out


def bh_qvalues(pvalues: Iterable[float]) -> np.ndarray:
    p = np.asarray(list(pvalues), dtype=float)
    q = np.full(len(p), np.nan)
    ok = np.isfinite(p)
    vals = p[ok]
    if not len(vals):
        return q
    order = np.argsort(vals)
    ranked = vals[order]
    adj = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = np.empty_like(vals)
    out[order] = np.minimum(adj, 1.0)
    q[np.where(ok)[0]] = out
    return q


def _weighted_group_means(z: np.ndarray, w: np.ndarray, groups: np.ndarray) -> np.ndarray:
    codes, _ = pd.factorize(groups, sort=False)
    k = int(codes.max()) + 1 if len(codes) else 0
    if k <= 0:
        return np.zeros_like(z)
    denom = np.bincount(codes, weights=w, minlength=k)
    ans = np.empty_like(z, dtype=float)
    for j in range(z.shape[1]):
        numer = np.bincount(codes, weights=w * z[:, j], minlength=k)
        means = np.divide(numer, denom, out=np.zeros_like(numer), where=denom > 0)
        ans[:, j] = means[codes]
    return ans


def absorb(z: np.ndarray, w: np.ndarray, groups: list[np.ndarray], max_iter: int = 100, tol: float = 1e-9) -> np.ndarray:
    out = np.asarray(z, dtype=float).copy()
    if not groups:
        return out
    for _ in range(max_iter):
        before = out.copy()
        for g in groups:
            out -= _weighted_group_means(out, w, np.asarray(g, dtype=object))
        if np.nanmax(np.abs(out - before)) < tol:
            break
    return out


def fit_wls_clustered(
    y: np.ndarray,
    X: np.ndarray,
    weights: np.ndarray,
    cluster: np.ndarray,
    *,
    absorb_groups: list[np.ndarray] | None = None,
    names: list[str] | None = None,
) -> dict:
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    w = np.asarray(weights, dtype=float)
    cl = np.asarray(cluster, dtype=object)
    mask = np.isfinite(y) & np.isfinite(w) & (w > 0) & pd.Series(cl).notna().to_numpy()
    mask &= np.all(np.isfinite(X), axis=1)
    y, X, w, cl = y[mask], X[mask], w[mask], cl[mask]
    groups = [np.asarray(g, dtype=object)[mask] for g in (absorb_groups or [])]
    if len(y) <= X.shape[1] + 20:
        raise RuntimeError(f"insufficient observations for model: n={len(y)}, k={X.shape[1]}")
    z = np.column_stack([y, X])
    z = absorb(z, w, groups)
    ya, Xa = z[:, 0], z[:, 1:]
    sw = np.sqrt(w)
    Xw, yw = Xa * sw[:, None], ya * sw
    bread_inv = np.linalg.pinv(Xw.T @ Xw)
    beta = bread_inv @ (Xw.T @ yw)
    resid = ya - Xa @ beta
    meat = np.zeros((Xa.shape[1], Xa.shape[1]), dtype=float)
    unique = pd.unique(cl)
    for g in unique:
        ix = np.where(cl == g)[0]
        score = Xa[ix].T @ (w[ix] * resid[ix])
        meat += np.outer(score, score)
    G, N, K = len(unique), len(y), Xa.shape[1]
    vcov = bread_inv @ meat @ bread_inv
    if G > 1 and N > K:
        vcov *= (G / (G - 1)) * ((N - 1) / (N - K))
    se = np.sqrt(np.maximum(np.diag(vcov), 0))
    zstat = np.divide(beta, se, out=np.full_like(beta, np.nan), where=se > 0)
    p = np.array([math.erfc(abs(v) / math.sqrt(2)) if np.isfinite(v) else np.nan for v in zstat])
    names = names or [f"x{i}" for i in range(X.shape[1])]
    return {
        "n": int(N), "clusters": int(G),
        "coef": dict(zip(names, map(float, beta))),
        "se": dict(zip(names, map(float, se))),
        "p": dict(zip(names, map(float, p))),
        "ci_low": dict(zip(names, map(float, beta - 1.96 * se))),
        "ci_high": dict(zip(names, map(float, beta + 1.96 * se))),
    }


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
