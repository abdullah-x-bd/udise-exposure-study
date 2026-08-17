from __future__ import annotations

import os
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from common import add_shares, bh_qvalues, build_panel, fit_wls_clustered, muslim_bin, write_json, write_rows

OUT = Path("studies/muslim_government_school_equity/outputs/need_inspection")


def _prepare(panel: Path, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    q = str(panel).replace("'", "''")
    df = con.execute(f"""
        SELECT academic_year,pseudocode,state,district,rural_urban,management,school_category,lowclass,highclass,
               is_state_local_government,is_core_government,enrol_c1_12,boys_c1_12,girls_c1_12,
               general_c1_12,sc_c1_12,st_c1_12,obc_c1_12,muslim_c1_12,christian_c1_12,sikh_c1_12,buddhist_c1_12,parsi_c1_12,jain_c1_12,
               total_classrooms,classrooms_major_repair,boys_func_toilets,girls_func_toilets,water_functional,electricity_functional,
               academic_inspections,crc_visits,block_visits,district_state_visits
        FROM read_parquet('{q}') WHERE enrol_c1_12 IS NOT NULL
    """).df()
    df = add_shares(df, primary=False)
    years = {y: i for i, y in enumerate(sorted(df.academic_year.unique()))}
    df["year_index"] = df.academic_year.map(years)
    df = df.sort_values(["pseudocode", "year_index"]).reset_index(drop=True)

    girls = pd.to_numeric(df["girls_c1_12"], errors="coerce")
    boys = pd.to_numeric(df["boys_c1_12"], errors="coerce")
    gf = pd.to_numeric(df["girls_func_toilets"], errors="coerce")
    bf = pd.to_numeric(df["boys_func_toilets"], errors="coerce")
    major = pd.to_numeric(df["classrooms_major_repair"], errors="coerce")
    rooms = pd.to_numeric(df["total_classrooms"], errors="coerce")
    water = pd.to_numeric(df["water_functional"], errors="coerce")
    elec = pd.to_numeric(df["electricity_functional"], errors="coerce")

    components = pd.DataFrame(index=df.index)
    components["need_girls_toilet"] = np.where((girls > 0) & gf.notna(), (gf <= 0).astype(float), np.nan)
    components["need_boys_toilet"] = np.where((boys > 0) & bf.notna(), (bf <= 0).astype(float), np.nan)
    components["need_water"] = np.where(water.notna(), (water <= 0).astype(float), np.nan)
    components["need_electricity"] = np.where(elec.notna(), (elec <= 0).astype(float), np.nan)
    components["need_major_repair"] = np.where((rooms > 0) & major.notna(), (major > 0).astype(float), np.nan)
    for col in components:
        df[col] = components[col]
    df["need_components_observed"] = components.notna().sum(axis=1)
    df["need_index"] = components.mean(axis=1, skipna=True).where(df["need_components_observed"] >= 3)

    for col in ("academic_inspections", "crc_visits", "block_visits", "district_state_visits"):
        x = pd.to_numeric(df[col], errors="coerce")
        x = x.where(x >= 0)
        cap = x.quantile(0.995) if x.notna().any() else np.nan
        if np.isfinite(cap):
            x = x.clip(upper=cap)
        df[f"log_{col}"] = np.log1p(x)
        df[f"any_{col}"] = np.where(x.notna(), (x > 0).astype(float), np.nan)

    raw_counts = df[["academic_inspections", "crc_visits", "block_visits", "district_state_visits"]].apply(pd.to_numeric, errors="coerce").where(lambda z: z >= 0)
    df["total_visits"] = raw_counts.sum(axis=1, min_count=1)
    df["senior_visits"] = raw_counts[["block_visits", "district_state_visits"]].sum(axis=1, min_count=1)
    for col in ("total_visits", "senior_visits"):
        x = pd.to_numeric(df[col], errors="coerce")
        cap = x.quantile(0.995) if x.notna().any() else np.nan
        if np.isfinite(cap):
            x = x.clip(upper=cap)
        df[f"log_{col}"] = np.log1p(x)
        df[f"any_{col}"] = np.where(x.notna(), (x > 0).astype(float), np.nan)

    earliest = (
        df.loc[df["muslim_share"].notna(), ["pseudocode", "year_index", "muslim_share", "sc_share", "st_share", "obc_share", "rural_urban", "management"]]
        .sort_values(["pseudocode", "year_index"]).drop_duplicates("pseudocode")
        .rename(columns={
            "muslim_share":"base_muslim", "sc_share":"base_sc", "st_share":"base_st", "obc_share":"base_obc",
            "rural_urban":"base_rural", "management":"base_management",
        })
    )
    df = df.merge(earliest.drop(columns="year_index"), on="pseudocode", how="left")

    outcome_cols = (
        "log_academic_inspections", "log_crc_visits", "log_block_visits", "log_district_state_visits",
        "log_total_visits", "log_senior_visits", "any_academic_inspections", "any_block_visits",
        "any_district_state_visits", "any_senior_visits",
    )
    for col in outcome_cols:
        df[f"next_{col}"] = df.groupby("pseudocode")[col].shift(-1)
    df["next_year_index"] = df.groupby("pseudocode")["year_index"].shift(-1)
    df["next_is_state_local_government"] = df.groupby("pseudocode")["is_state_local_government"].shift(-1)
    valid_followup = df["next_year_index"].eq(df["year_index"] + 1) & df["next_is_state_local_government"].eq(1)
    for col in outcome_cols:
        df.loc[~valid_followup, f"next_{col}"] = np.nan
    return df


def _fit(d: pd.DataFrame, outcome: str, cluster: str = "state", lag_exposure: bool = False) -> dict | None:
    x = d.copy()
    need = pd.to_numeric(x["need_index"], errors="coerce").to_numpy(float)
    if lag_exposure:
        m = pd.to_numeric(x["muslim_share"], errors="coerce").to_numpy(float)
        sc = pd.to_numeric(x["sc_share"], errors="coerce").to_numpy(float)
        st = pd.to_numeric(x["st_share"], errors="coerce").to_numpy(float)
        obc = pd.to_numeric(x["obc_share"], errors="coerce").to_numpy(float)
        exposure_name = "contemporaneous_composition"
    else:
        m = pd.to_numeric(x["base_muslim"], errors="coerce").to_numpy(float)
        sc = pd.to_numeric(x["base_sc"], errors="coerce").to_numpy(float)
        st = pd.to_numeric(x["base_st"], errors="coerce").to_numpy(float)
        obc = pd.to_numeric(x["base_obc"], errors="coerce").to_numpy(float)
        exposure_name = "frozen_baseline_composition"
    enrol = np.log1p(pd.to_numeric(x["enrol_c1_12"], errors="coerce").to_numpy(float))
    rural = pd.to_numeric(x["base_rural"], errors="coerce").to_numpy(float)
    observed = pd.to_numeric(x["need_components_observed"], errors="coerce").to_numpy(float)
    mgmt = pd.to_numeric(x["base_management"], errors="coerce")

    cols = [need, need*m, need*sc, need*st, need*obc, enrol, need*rural, observed]
    names = ["need", "need_x_muslim", "need_x_sc", "need_x_st", "need_x_obc", "log_enrolment", "need_x_rural", "need_components_observed"]
    finite = mgmt.dropna()
    if len(finite):
        base = finite.min()
        for code in sorted(v for v in finite.unique() if v != base):
            dum = (mgmt.to_numpy(float) == code).astype(float)
            cols.append(need*dum)
            names.append(f"need_x_management_{int(code)}")
    X = np.column_stack(cols)
    school = x["pseudocode"].astype(str).to_numpy(object)
    district_year = (x["district"].astype(str) + "|" + x["academic_year"].astype(str)).to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(x[outcome], errors="coerce").to_numpy(float), X, np.ones(len(x)),
            x[cluster].to_numpy(object), absorb_groups=[school, district_year], names=names,
        )
    except RuntimeError:
        return None
    key = "need_x_muslim"
    return {
        "outcome": outcome, "exposure": exposure_name, "cluster": cluster,
        "n": fit["n"], "clusters": fit["clusters"],
        "need_coef": fit["coef"]["need"], "need_p": fit["p"]["need"],
        "need_x_muslim": fit["coef"][key], "need_x_muslim_se": fit["se"][key],
        "need_x_muslim_p": fit["p"][key], "ci_low": fit["ci_low"][key], "ci_high": fit["ci_high"][key],
        "need_x_sc": fit["coef"]["need_x_sc"], "need_x_st": fit["coef"]["need_x_st"], "need_x_obc": fit["coef"]["need_x_obc"],
    }


def main() -> None:
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix="muslim_equity_inspection_") as td:
        root = Path(td)
        panel, reports = build_panel(con, repo, token, root/"work", root/"panel", teacher=False, facility=True, profile2=True)
        df = _prepare(panel, con)
        sample = df.loc[(df["is_state_local_government"] == 1) & df["need_index"].notna() & df["base_muslim"].notna()].copy()
        core = sample.loc[sample["is_core_government"] == 1].copy()

        sample.groupby("academic_year").agg(rows=("pseudocode","size"), schools=("pseudocode","nunique"), mean_need=("need_index","mean"), mean_base_muslim=("base_muslim","mean"), states=("state","nunique"), districts=("district","nunique")).reset_index().to_csv(OUT/"sample_counts.csv", index=False)

        outcomes = (
            "next_log_total_visits", "next_log_senior_visits", "next_log_academic_inspections", "next_log_crc_visits",
            "next_log_block_visits", "next_log_district_state_visits", "next_any_senior_visits",
            "next_any_academic_inspections", "next_any_block_visits", "next_any_district_state_visits",
        )
        rows = []
        for outcome in outcomes:
            ans = _fit(sample, outcome, "state", False)
            if ans:
                rows.append({"universe":"main_1_2_3_6_89_90", "spec":"primary", **ans})
            ans = _fit(sample, outcome, "district", False)
            if ans:
                rows.append({"universe":"main_1_2_3_6_89_90", "spec":"district_cluster", **ans})
            ans = _fit(sample, outcome, "state", True)
            if ans:
                rows.append({"universe":"main_1_2_3_6_89_90", "spec":"contemporaneous_exposure", **ans})
            ans = _fit(core, outcome, "state", False) if len(core) else None
            if ans:
                rows.append({"universe":"core_1_2_3", "spec":"government_universe_robustness", **ans})
        primary_ix = [i for i, r in enumerate(rows) if r["spec"] == "primary"]
        qs = bh_qvalues([rows[i]["need_x_muslim_p"] for i in primary_ix])
        for i, q in zip(primary_ix, qs):
            rows[i]["need_x_muslim_q"] = q
        write_rows(OUT/"need_inspection_models.csv", rows)

        sample["muslim_bin"] = muslim_bin(sample["base_muslim"])
        high_need = sample.loc[sample["need_index"] >= 0.5].copy()
        bin_rows = []
        for label, d in high_need.groupby("muslim_bin", observed=True):
            bin_rows.append({
                "muslim_bin": str(label), "school_years": len(d), "schools": d.pseudocode.nunique(), "states": d.state.nunique(),
                "mean_need": float(d.need_index.mean()),
                "mean_next_total_log_visits": float(pd.to_numeric(d.next_log_total_visits, errors="coerce").mean()),
                "mean_next_senior_log_visits": float(pd.to_numeric(d.next_log_senior_visits, errors="coerce").mean()),
                "next_any_senior_visit_rate": float(pd.to_numeric(d.next_any_senior_visits, errors="coerce").mean()),
            })
        write_rows(OUT/"five_pp_high_need_response.csv", bin_rows)
        write_json(OUT/"source_validation.json", reports)

        primary = [r for r in rows if r["spec"] == "primary" and r["universe"] == "main_1_2_3_6_89_90"]
        lines = ["# Need-to-inspection national experiment", "", f"Eligible government school-years with a valid need index: {len(sample):,}.", "", "The key coefficient is the interaction between documented current need and frozen baseline Muslim share after absorbing school and district-by-year fixed effects. Following-year outcomes are censored if the school leaves the State/local-government universe."]
        for r in primary:
            qv = r.get("need_x_muslim_q", float("nan"))
            lines.append(f"- {r['outcome']}: need x Muslim = {r['need_x_muslim']:+.4f} (95% CI {r['ci_low']:+.4f} to {r['ci_high']:+.4f}), p={r['need_x_muslim_p']:.4g}, q={qv:.4g}, n={r['n']:,}")
        (OUT/"RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)
    con.close()


if __name__ == "__main__":
    main()
