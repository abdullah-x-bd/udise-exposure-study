from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from common import RTE_CUTOFFS, bh_qvalues, build_panel, fit_wls_clustered, muslim_bin, write_json, write_rows

OUT = Path("studies/muslim_government_school_equity/outputs/rte_staffing")
BANDWIDTHS = (15.0, 20.0, 30.0)
FAKE_CUTOFFS = (75.5, 105.5, 135.5)


def _prepare(panel: Path, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Use DuckDB windows before materialising the narrow RTE sample in pandas."""
    q = str(panel).replace("'", "''")
    year_case = "CASE academic_year " + " ".join(
        f"WHEN '{y}' THEN {i}" for i, y in enumerate(
            ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
        )
    ) + " END"
    return con.execute(f"""
        WITH base AS (
          SELECT *,
                 {year_case} AS year_index,
                 muslim_primary/NULLIF(enrol_primary,0) AS muslim_share,
                 sc_primary/NULLIF(enrol_primary,0) AS sc_share,
                 st_primary/NULLIF(enrol_primary,0) AS st_share,
                 obc_primary/NULLIF(enrol_primary,0) AS obc_share,
                 general_primary/NULLIF(enrol_primary,0) AS general_share
          FROM read_parquet('{q}')
          WHERE enrol_primary IS NOT NULL
        ), w AS (
          SELECT *,
                 LAG(year_index) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_year_index,
                 LAG(muslim_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS raw_lag_muslim_share,
                 LAG(sc_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS raw_lag_sc_share,
                 LAG(st_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS raw_lag_st_share,
                 LAG(obc_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS raw_lag_obc_share,
                 LAG(general_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS raw_lag_general_share,
                 LEAD(year_index) OVER (PARTITION BY pseudocode ORDER BY year_index) AS next_year_index,
                 LEAD(total_teachers) OVER (PARTITION BY pseudocode ORDER BY year_index) AS raw_next_total_teachers,
                 ARG_MIN(muslim_share, year_index) OVER (PARTITION BY pseudocode) AS frozen_muslim_share,
                 ARG_MIN(sc_share, year_index) OVER (PARTITION BY pseudocode) AS frozen_sc_share,
                 ARG_MIN(st_share, year_index) OVER (PARTITION BY pseudocode) AS frozen_st_share,
                 ARG_MIN(obc_share, year_index) OVER (PARTITION BY pseudocode) AS frozen_obc_share
          FROM base
        )
        SELECT academic_year,pseudocode,state,district,rural_urban,management,school_category,
               lowclass,highclass,is_state_local_government,is_core_government,enrol_primary,
               total_teachers,primary_serving_teachers,regular_teachers,contract_teachers,female_teachers,
               CASE WHEN lag_year_index=year_index-1 THEN raw_lag_muslim_share END AS lag_muslim_share,
               CASE WHEN lag_year_index=year_index-1 THEN raw_lag_sc_share END AS lag_sc_share,
               CASE WHEN lag_year_index=year_index-1 THEN raw_lag_st_share END AS lag_st_share,
               CASE WHEN lag_year_index=year_index-1 THEN raw_lag_obc_share END AS lag_obc_share,
               CASE WHEN lag_year_index=year_index-1 THEN raw_lag_general_share END AS lag_general_share,
               frozen_muslim_share,frozen_sc_share,frozen_st_share,frozen_obc_share,
               CASE WHEN next_year_index=year_index+1 THEN raw_next_total_teachers END AS next_total_teachers,
               CASE
                 WHEN enrol_primary BETWEEN 1 AND 60 THEN 2
                 WHEN enrol_primary BETWEEN 61 AND 90 THEN 3
                 WHEN enrol_primary BETWEEN 91 AND 120 THEN 4
                 WHEN enrol_primary BETWEEN 121 AND 150 THEN 5
                 ELSE NULL
               END AS required_teachers,
               CASE
                 WHEN total_teachers IS NULL THEN NULL
                 WHEN enrol_primary BETWEEN 1 AND 60 THEN CAST(total_teachers>=2 AS DOUBLE)
                 WHEN enrol_primary BETWEEN 61 AND 90 THEN CAST(total_teachers>=3 AS DOUBLE)
                 WHEN enrol_primary BETWEEN 91 AND 120 THEN CAST(total_teachers>=4 AS DOUBLE)
                 WHEN enrol_primary BETWEEN 121 AND 150 THEN CAST(total_teachers>=5 AS DOUBLE)
                 ELSE NULL
               END AS meets_norm
        FROM w
        WHERE is_state_local_government=1
          AND lowclass=1 AND highclass=5
          AND enrol_primary BETWEEN 30 AND 151
          AND state IS NOT NULL AND district IS NOT NULL
    """).df()


def _design(d: pd.DataFrame, cutoff: float, exposure: str, bw: float) -> tuple[np.ndarray, list[str], np.ndarray]:
    r = pd.to_numeric(d["enrol_primary"], errors="coerce").to_numpy(float) - cutoff
    t = (r >= 0).astype(float)
    m = pd.to_numeric(d[exposure], errors="coerce").to_numpy(float)
    sc = pd.to_numeric(d["lag_sc_share"], errors="coerce").to_numpy(float)
    st = pd.to_numeric(d["lag_st_share"], errors="coerce").to_numpy(float)
    obc = pd.to_numeric(d["lag_obc_share"], errors="coerce").to_numpy(float)
    rural = pd.to_numeric(d["rural_urban"], errors="coerce").to_numpy(float)
    mgmt = pd.to_numeric(d["management"], errors="coerce")
    cols = [t, r, t*r, m, t*m, r*m, t*r*m, sc, st, obc, rural]
    names = [
        "above", "running", "above_running", "muslim_share", "above_muslim_share",
        "running_muslim_share", "above_running_muslim_share", "lag_sc_share", "lag_st_share",
        "lag_obc_share", "rural_urban",
    ]
    finite = mgmt.dropna()
    if len(finite):
        base = finite.min()
        for code in sorted(v for v in finite.unique() if v != base):
            cols.append((mgmt.to_numpy(float) == code).astype(float))
            names.append(f"management_{int(code)}")
    X = np.column_stack(cols)
    weights = np.maximum(0.0, 1.0 - np.abs(r) / bw)
    return X, names, weights


def _fit_one(sample: pd.DataFrame, *, cutoff: float, bw: float, outcome: str, exposure: str,
             cluster_col: str = "state", donut: bool = False) -> dict | None:
    d = sample.copy()
    r = pd.to_numeric(d["enrol_primary"], errors="coerce") - cutoff
    d = d.loc[r.abs() <= bw].copy()
    if donut:
        d = d.loc[~pd.to_numeric(d["enrol_primary"], errors="coerce").isin([math.floor(cutoff), math.ceil(cutoff)])].copy()
    if len(d) < 500:
        return None
    X, names, weights = _design(d, cutoff, exposure, bw)
    district_year = (d["district"].astype(str) + "|" + d["academic_year"].astype(str)).to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(d[outcome], errors="coerce").to_numpy(float), X, weights,
            d[cluster_col].to_numpy(object), absorb_groups=[district_year], names=names,
        )
    except RuntimeError:
        return None
    key = "above_muslim_share"
    return {
        "cutoff": cutoff, "bandwidth": bw, "outcome": outcome, "exposure": exposure,
        "cluster": cluster_col, "donut": int(donut), "n": fit["n"], "clusters": fit["clusters"],
        "base_jump": fit["coef"]["above"], "base_jump_se": fit["se"]["above"], "base_jump_p": fit["p"]["above"],
        "muslim_interaction": fit["coef"][key], "muslim_interaction_se": fit["se"][key],
        "muslim_interaction_p": fit["p"][key], "muslim_interaction_ci_low": fit["ci_low"][key],
        "muslim_interaction_ci_high": fit["ci_high"][key],
    }


def _stacked_fit(sample: pd.DataFrame, outcome: str, exposure: str, bw: float = 10.0) -> dict | None:
    """Non-overlapping narrow stacks around the three genuine cutoffs."""
    frames = []
    for cutoff in RTE_CUTOFFS:
        x = sample.copy()
        x["cutoff"] = cutoff
        x["running_stack"] = pd.to_numeric(x["enrol_primary"], errors="coerce") - cutoff
        frames.append(x.loc[x["running_stack"].abs() <= bw].copy())
    d = pd.concat(frames, ignore_index=True)
    if len(d) < 1000:
        return None
    r = d["running_stack"].to_numpy(float)
    t = (r >= 0).astype(float)
    m = pd.to_numeric(d[exposure], errors="coerce").to_numpy(float)
    sc = pd.to_numeric(d["lag_sc_share"], errors="coerce").to_numpy(float)
    st = pd.to_numeric(d["lag_st_share"], errors="coerce").to_numpy(float)
    obc = pd.to_numeric(d["lag_obc_share"], errors="coerce").to_numpy(float)
    rural = pd.to_numeric(d["rural_urban"], errors="coerce").to_numpy(float)
    X = np.column_stack([t, r, t*r, m, t*m, r*m, t*r*m, sc, st, obc, rural])
    names = [
        "above", "running", "above_running", "muslim_share", "above_muslim_share",
        "running_muslim_share", "above_running_muslim_share", "lag_sc_share", "lag_st_share", "lag_obc_share", "rural_urban",
    ]
    weights = np.maximum(0.0, 1.0 - np.abs(r)/bw)
    district_year = (d["district"].astype(str) + "|" + d["academic_year"].astype(str)).to_numpy(object)
    cutoff_year = (d["cutoff"].astype(str) + "|" + d["academic_year"].astype(str)).to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(d[outcome], errors="coerce").to_numpy(float), X, weights,
            d["state"].to_numpy(object), absorb_groups=[district_year, cutoff_year], names=names,
        )
    except RuntimeError:
        return None
    key = "above_muslim_share"
    return {
        "cutoff": "stacked", "bandwidth": bw, "outcome": outcome, "exposure": exposure,
        "cluster": "state", "donut": 0, "n": fit["n"], "clusters": fit["clusters"],
        "base_jump": fit["coef"]["above"], "base_jump_se": fit["se"]["above"], "base_jump_p": fit["p"]["above"],
        "muslim_interaction": fit["coef"][key], "muslim_interaction_se": fit["se"][key],
        "muslim_interaction_p": fit["p"][key], "muslim_interaction_ci_low": fit["ci_low"][key],
        "muslim_interaction_ci_high": fit["ci_high"][key],
    }


def _simple_rd(d: pd.DataFrame, cutoff: float, bw: float, outcome: str) -> dict | None:
    x = d.copy()
    r0 = pd.to_numeric(x["enrol_primary"], errors="coerce") - cutoff
    x = x.loc[r0.abs() <= bw].copy()
    r = pd.to_numeric(x["enrol_primary"], errors="coerce").to_numpy(float) - cutoff
    t = (r >= 0).astype(float)
    X = np.column_stack([t, r, t*r])
    w = np.maximum(0.0, 1.0 - np.abs(r)/bw)
    dy = (x["district"].astype(str) + "|" + x["academic_year"].astype(str)).to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(x[outcome], errors="coerce").to_numpy(float), X, w,
            x["state"].to_numpy(object), absorb_groups=[dy], names=["above", "running", "above_running"],
        )
    except RuntimeError:
        return None
    return {"cutoff": cutoff, "outcome": outcome, "n": fit["n"], "jump": fit["coef"]["above"], "se": fit["se"]["above"], "p": fit["p"]["above"]}


def main() -> None:
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix="muslim_equity_rte_") as td:
        root = Path(td)
        panel, reports = build_panel(con, repo, token, root/"work", root/"panel", teacher=True, facility=False, profile2=False)
        df = _prepare(panel, con)
        sample = df.loc[df["lag_muslim_share"].notna()].copy()
        core_sample = sample.loc[sample["is_core_government"] == 1].copy()

        sample.groupby("academic_year", dropna=False).agg(
            schools=("pseudocode", "nunique"), rows=("pseudocode", "size"),
            mean_muslim_share=("lag_muslim_share", "mean"), states=("state", "nunique"), districts=("district", "nunique"),
        ).reset_index().to_csv(OUT/"sample_counts.csv", index=False)

        rows: list[dict] = []
        outcomes = ("total_teachers", "meets_norm", "primary_serving_teachers", "regular_teachers", "contract_teachers", "female_teachers", "next_total_teachers")
        for outcome in outcomes:
            for cutoff in RTE_CUTOFFS:
                for bw in BANDWIDTHS:
                    ans = _fit_one(sample, cutoff=cutoff, bw=bw, outcome=outcome, exposure="lag_muslim_share")
                    if ans:
                        ans.update(universe="main_1_2_3_6_89_90", spec="primary" if bw == 20 else "bandwidth_robustness")
                        rows.append(ans)
                for kwargs, spec in [
                    ({"donut": True}, "donut"),
                    ({"cluster_col": "district"}, "district_cluster"),
                ]:
                    ans = _fit_one(sample, cutoff=cutoff, bw=20, outcome=outcome, exposure="lag_muslim_share", **kwargs)
                    if ans:
                        ans.update(universe="main_1_2_3_6_89_90", spec=spec); rows.append(ans)
                ans = _fit_one(core_sample, cutoff=cutoff, bw=20, outcome=outcome, exposure="lag_muslim_share")
                if ans:
                    ans.update(universe="core_1_2_3", spec="government_universe_robustness"); rows.append(ans)
                ans = _fit_one(sample, cutoff=cutoff, bw=20, outcome=outcome, exposure="frozen_muslim_share")
                if ans:
                    ans.update(universe="main_1_2_3_6_89_90", spec="frozen_exposure"); rows.append(ans)
            pooled = _stacked_fit(sample, outcome, "lag_muslim_share", 10)
            if pooled:
                pooled.update(universe="main_1_2_3_6_89_90", spec="stacked_narrow_supplement"); rows.append(pooled)

        primary_ix = [i for i, r in enumerate(rows) if r["spec"] == "primary" and r["outcome"] in ("total_teachers", "meets_norm")]
        primary_q = bh_qvalues([rows[i]["muslim_interaction_p"] for i in primary_ix])
        for i, qv in zip(primary_ix, primary_q): rows[i]["primary_family_q"] = qv
        write_rows(OUT/"rte_staffing_models.csv", rows)

        placebo_rows = []
        for cutoff in FAKE_CUTOFFS:
            ans = _fit_one(sample, cutoff=cutoff, bw=15, outcome="total_teachers", exposure="lag_muslim_share")
            if ans: placebo_rows.append(ans)
        write_rows(OUT/"fake_cutoffs.csv", placebo_rows)

        balance_rows = []
        for cutoff in RTE_CUTOFFS:
            for outcome in ("lag_muslim_share", "lag_sc_share", "lag_st_share", "lag_obc_share", "rural_urban"):
                ans = _simple_rd(sample, cutoff, 20, outcome)
                if ans: balance_rows.append(ans)
        qbal = bh_qvalues([r["p"] for r in balance_rows])
        for row, qv in zip(balance_rows, qbal): row["q"] = qv
        write_rows(OUT/"predetermined_balance.csv", balance_rows)

        density_rows = []
        for year, yy in sample.groupby("academic_year"):
            exact = pd.to_numeric(yy["enrol_primary"], errors="coerce").value_counts()
            nseries = pd.to_numeric(yy["enrol_primary"], errors="coerce")
            for cutoff in RTE_CUTOFFS:
                left, right = math.floor(cutoff), math.ceil(cutoff)
                density_rows.append({
                    "academic_year": year, "cutoff": cutoff,
                    "n_exact_left": int(exact.get(left, 0)), "n_exact_right": int(exact.get(right, 0)),
                    "right_left_ratio": float(exact.get(right, 0))/float(exact.get(left, 0)) if exact.get(left, 0) else None,
                    "n_window_left": int(((nseries >= left-10) & (nseries <= left)).sum()),
                    "n_window_right": int(((nseries >= right) & (nseries <= right+10)).sum()),
                })
        write_rows(OUT/"density_masspoint_diagnostics.csv", density_rows)

        sample["muslim_bin"] = muslim_bin(sample["lag_muslim_share"])
        binned_rows = []
        for label, dd in sample.groupby("muslim_bin", observed=True):
            if len(dd) < 800 or dd["state"].nunique() < 5: continue
            for cutoff in RTE_CUTOFFS:
                ans = _simple_rd(dd, cutoff, 20, "total_teachers")
                if ans:
                    ans.update(muslim_bin=str(label), states=int(dd["state"].nunique())); binned_rows.append(ans)
        write_rows(OUT/"five_pp_bin_staffing_jumps.csv", binned_rows)
        write_json(OUT/"source_validation.json", reports)

        headline = [r for r in rows if r["spec"] == "primary" and r["outcome"] in ("total_teachers", "meets_norm")]
        lines = ["# RTE staffing national experiment", "", f"Eligible local RTE school-years in analysis support: {len(sample):,}.", "", "Primary coefficients use the pre-specified +/-20-pupil local window, district-by-year fixed effects, predetermined social-composition controls and State-clustered inference."]
        for r in headline:
            qv = r.get("primary_family_q")
            lines.append(
                f"- cutoff {r['cutoff']}, {r['outcome']}: entitlement x Muslim-share interaction {r['muslim_interaction']:+.4f} "
                f"(95% CI {r['muslim_interaction_ci_low']:+.4f} to {r['muslim_interaction_ci_high']:+.4f}), "
                f"p={r['muslim_interaction_p']:.4g}, q={qv:.4g} if qv is not None else 'NA', n={r['n']:,}."
            )
        (OUT/"RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)
    con.close()


if __name__ == "__main__":
    main()
