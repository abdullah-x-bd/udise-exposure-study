from __future__ import annotations

import os
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from common import bh_qvalues, build_panel, fit_wls_clustered, muslim_bin, write_json, write_rows

OUT = Path("studies/muslim_government_school_equity/outputs/failure_to_repair")
FAILURES = ("girls_toilet", "boys_toilet", "water", "electricity", "major_repair")
YEARS = ("2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26")


def _prepare_events(panel: Path, con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    q = str(panel).replace("'", "''")
    year_case = "CASE academic_year " + " ".join(f"WHEN '{y}' THEN {i}" for i, y in enumerate(YEARS)) + " END"
    status_cols = {
        "girls_toilet": "CASE WHEN girls_c1_12>0 AND girls_func_toilets IS NOT NULL THEN CAST(girls_func_toilets>0 AS DOUBLE) END",
        "boys_toilet": "CASE WHEN boys_c1_12>0 AND boys_func_toilets IS NOT NULL THEN CAST(boys_func_toilets>0 AS DOUBLE) END",
        "water": "CASE WHEN water_functional IS NOT NULL THEN CAST(water_functional>0 AS DOUBLE) END",
        "electricity": "CASE WHEN electricity_functional IS NOT NULL THEN CAST(electricity_functional>0 AS DOUBLE) END",
        "major_repair": "CASE WHEN total_classrooms>0 AND classrooms_major_repair IS NOT NULL THEN CAST(classrooms_major_repair<=0 AS DOUBLE) END",
    }
    base_status = ",\n".join(f"{expr} AS {name}_ok" for name, expr in status_cols.items())
    lag_status = ",\n".join(
        f"LAG({name}_ok) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_{name}_ok, "
        f"LEAD({name}_ok,1) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lead1_{name}_ok, "
        f"LEAD({name}_ok,2) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lead2_{name}_ok, "
        f"LEAD({name}_ok,3) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lead3_{name}_ok"
        for name in FAILURES
    )
    unions = []
    for name in FAILURES:
        stock = {
            "girls_toilet": "lag_girls_toilets",
            "boys_toilet": "lag_boys_toilets",
            "major_repair": "lag_total_classrooms",
            "water": "0",
            "electricity": "0",
        }[name]
        unions.append(f"""
            SELECT *, '{name}' AS failure_type, {stock} AS baseline_stock,
                   CASE
                     WHEN lead1_year_index=year_index+1 AND lead1_is_gov=1 AND lead1_{name}_ok=1 THEN 1.0
                     WHEN lead1_year_index=year_index+1 AND lead1_is_gov=1 AND lead1_{name}_ok=0 THEN 0.0
                   END AS repair_by_1,
                   CASE
                     WHEN lead1_year_index=year_index+1 AND lead1_is_gov=1 AND lead1_{name}_ok=1 THEN 1.0
                     WHEN lead2_year_index=year_index+2 AND lead2_is_gov=1 AND lead2_{name}_ok=1 THEN 1.0
                     WHEN lead1_year_index=year_index+1 AND lead2_year_index=year_index+2
                          AND lead1_is_gov=1 AND lead2_is_gov=1
                          AND lead1_{name}_ok=0 AND lead2_{name}_ok=0 THEN 0.0
                   END AS repair_by_2,
                   CASE
                     WHEN lead1_year_index=year_index+1 AND lead1_is_gov=1 AND lead1_{name}_ok=1 THEN 1.0
                     WHEN lead2_year_index=year_index+2 AND lead2_is_gov=1 AND lead2_{name}_ok=1 THEN 1.0
                     WHEN lead3_year_index=year_index+3 AND lead3_is_gov=1 AND lead3_{name}_ok=1 THEN 1.0
                     WHEN lead1_year_index=year_index+1 AND lead2_year_index=year_index+2 AND lead3_year_index=year_index+3
                          AND lead1_is_gov=1 AND lead2_is_gov=1 AND lead3_is_gov=1
                          AND lead1_{name}_ok=0 AND lead2_{name}_ok=0 AND lead3_{name}_ok=0 THEN 0.0
                   END AS repair_by_3
            FROM w
            WHERE is_state_local_government=1 AND lag_is_gov=1
              AND lag_year_index=year_index-1
              AND lag_{name}_ok=1 AND {name}_ok=0
              AND lag_muslim_share IS NOT NULL
              AND state IS NOT NULL AND district IS NOT NULL
        """)
    union_sql = " UNION ALL ".join(unions)
    return con.execute(f"""
        WITH base AS (
          SELECT *, {year_case} AS year_index,
                 muslim_c1_12/NULLIF(enrol_c1_12,0) AS muslim_share,
                 sc_c1_12/NULLIF(enrol_c1_12,0) AS sc_share,
                 st_c1_12/NULLIF(enrol_c1_12,0) AS st_share,
                 obc_c1_12/NULLIF(enrol_c1_12,0) AS obc_share,
                 {base_status}
          FROM read_parquet('{q}')
          WHERE enrol_c1_12 IS NOT NULL
        ), w0 AS (
          SELECT *,
                 LAG(year_index) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_year_index,
                 LEAD(year_index,1) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lead1_year_index,
                 LEAD(year_index,2) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lead2_year_index,
                 LEAD(year_index,3) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lead3_year_index,
                 LAG(is_state_local_government) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_is_gov,
                 LEAD(is_state_local_government,1) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lead1_is_gov,
                 LEAD(is_state_local_government,2) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lead2_is_gov,
                 LEAD(is_state_local_government,3) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lead3_is_gov,
                 LAG(muslim_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_muslim_share,
                 LAG(sc_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_sc_share,
                 LAG(st_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_st_share,
                 LAG(obc_share) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_obc_share,
                 LAG(enrol_c1_12) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_enrol_c1_12,
                 LAG(rural_urban) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_rural_urban,
                 LAG(management) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_management,
                 LAG(girls_toilets) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_girls_toilets,
                 LAG(boys_toilets) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_boys_toilets,
                 LAG(total_classrooms) OVER (PARTITION BY pseudocode ORDER BY year_index) AS lag_total_classrooms,
                 ARG_MIN(muslim_share, year_index) OVER (PARTITION BY pseudocode) AS frozen_muslim_share,
                 {lag_status}
          FROM base
        ), w AS (SELECT * FROM w0)
        {union_sql}
    """).df()


def _fit(ev: pd.DataFrame, outcome: str, exposure: str, cluster: str = "state") -> dict | None:
    d = ev.copy()
    m = pd.to_numeric(d[exposure], errors="coerce").to_numpy(float)
    sc = pd.to_numeric(d["lag_sc_share"], errors="coerce").to_numpy(float)
    st = pd.to_numeric(d["lag_st_share"], errors="coerce").to_numpy(float)
    obc = pd.to_numeric(d["lag_obc_share"], errors="coerce").to_numpy(float)
    logn = np.log1p(pd.to_numeric(d["lag_enrol_c1_12"], errors="coerce").to_numpy(float))
    rural = pd.to_numeric(d["lag_rural_urban"], errors="coerce").to_numpy(float)
    stock = np.log1p(pd.to_numeric(d["baseline_stock"], errors="coerce").fillna(0).to_numpy(float))
    mgmt = pd.to_numeric(d["lag_management"], errors="coerce")
    cols = [m, sc, st, obc, logn, rural, stock]
    names = ["muslim_share", "lag_sc_share", "lag_st_share", "lag_obc_share", "log_enrolment", "rural_urban", "log_baseline_stock"]
    finite = mgmt.dropna()
    if len(finite):
        base = finite.min()
        for code in sorted(v for v in finite.unique() if v != base):
            cols.append((mgmt.to_numpy(float) == code).astype(float)); names.append(f"management_{int(code)}")
    X = np.column_stack(cols)
    district_onset = (d["district"].astype(str) + "|" + d["academic_year"].astype(str)).to_numpy(object)
    try:
        fit = fit_wls_clustered(
            pd.to_numeric(d[outcome], errors="coerce").to_numpy(float), X, np.ones(len(d)),
            d[cluster].to_numpy(object), absorb_groups=[district_onset], names=names,
        )
    except RuntimeError:
        return None
    key = "muslim_share"
    return {
        "n": fit["n"], "clusters": fit["clusters"], "cluster": cluster,
        "coef_muslim_share": fit["coef"][key], "se_muslim_share": fit["se"][key],
        "p_muslim_share": fit["p"][key], "ci_low": fit["ci_low"][key], "ci_high": fit["ci_high"][key],
    }


def main() -> None:
    repo, token = os.environ["HF_DATASET_REPO"], os.environ["HF_TOKEN"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(); con.execute("PRAGMA threads=4"); con.execute("PRAGMA memory_limit='10GB'")
    with tempfile.TemporaryDirectory(prefix="muslim_equity_repair_") as td:
        root = Path(td)
        panel, reports = build_panel(con, repo, token, root/"work", root/"panel", teacher=False, facility=True, profile2=False)
        all_events = _prepare_events(panel, con)
        all_events.groupby(["academic_year", "failure_type"]).agg(
            events=("pseudocode","size"), schools=("pseudocode","nunique"), states=("state","nunique"), districts=("district","nunique"),
            mean_pre_failure_muslim_share=("lag_muslim_share","mean")
        ).reset_index().to_csv(OUT/"event_counts.csv", index=False)

        rows = []
        for failure, ev in all_events.groupby("failure_type"):
            for h in (1, 2, 3):
                outcome = f"repair_by_{h}"
                ans = _fit(ev, outcome, "lag_muslim_share", "state")
                if ans: rows.append({"failure_type":failure,"horizon_years":h,"exposure":"lag_muslim_share","universe":"main_1_2_3_6_89_90","spec":"primary",**ans})
                ans = _fit(ev, outcome, "lag_muslim_share", "district")
                if ans: rows.append({"failure_type":failure,"horizon_years":h,"exposure":"lag_muslim_share","universe":"main_1_2_3_6_89_90","spec":"district_cluster",**ans})
                ans = _fit(ev, outcome, "frozen_muslim_share", "state")
                if ans: rows.append({"failure_type":failure,"horizon_years":h,"exposure":"frozen_muslim_share","universe":"main_1_2_3_6_89_90","spec":"frozen_exposure",**ans})
                core = ev.loc[ev["is_core_government"] == 1].copy()
                ans = _fit(core, outcome, "lag_muslim_share", "state") if len(core) else None
                if ans: rows.append({"failure_type":failure,"horizon_years":h,"exposure":"lag_muslim_share","universe":"core_1_2_3","spec":"government_universe_robustness",**ans})

        primary_ix = [i for i, r in enumerate(rows) if r["spec"] == "primary"]
        qvals = bh_qvalues([rows[i]["p_muslim_share"] for i in primary_ix])
        for i, qv in zip(primary_ix, qvals): rows[i]["primary_family_q"] = qv
        write_rows(OUT/"repair_models.csv", rows)

        all_events["muslim_bin"] = muslim_bin(all_events["lag_muslim_share"])
        bin_rows = []
        for (failure, label), d in all_events.groupby(["failure_type", "muslim_bin"], observed=True):
            row = {"failure_type":failure,"muslim_bin":str(label),"events":len(d),"states":d.state.nunique(),"districts":d.district.nunique()}
            for h in (1,2,3):
                y = pd.to_numeric(d[f"repair_by_{h}"], errors="coerce")
                row[f"repair_rate_{h}y"] = float(y.mean()) if y.notna().any() else None
                row[f"observed_{h}y"] = int(y.notna().sum())
            bin_rows.append(row)
        write_rows(OUT/"five_pp_repair_rates.csv", bin_rows)
        write_json(OUT/"source_validation.json", reports)

        primary = [r for r in rows if r["spec"] == "primary"]
        lines = ["# Failure-to-repair national experiment", "", f"Incident documented failures: {len(all_events):,}.", "", "The coefficient is the conditional change in restoration probability associated with moving pre-failure Muslim share from 0 to 100 percent. Follow-up is censored if the school leaves the State/local-government universe."]
        for r in primary:
            qv = r.get("primary_family_q", float("nan"))
            lines.append(f"- {r['failure_type']} within {r['horizon_years']}y: {r['coef_muslim_share']:+.4f} (95% CI {r['ci_low']:+.4f} to {r['ci_high']:+.4f}), p={r['p_muslim_share']:.4g}, q={qv:.4g}, n={r['n']:,}")
        (OUT/"RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)
    con.close()


if __name__ == "__main__":
    main()
