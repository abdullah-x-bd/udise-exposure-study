from __future__ import annotations

import os
import tempfile
from pathlib import Path

import duckdb

from common import build_panel, lit, write_json

OUT = Path("studies/muslim_government_school_equity/outputs/baseline")


def main() -> None:
    repo = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=4")
    con.execute("PRAGMA memory_limit='10GB'")

    with tempfile.TemporaryDirectory(prefix="muslim_equity_baseline_") as td:
        root = Path(td)
        panel, reports = build_panel(
            con, repo, token, root / "work", root / "panel",
            teacher=True, facility=True, profile2=True,
        )
        p = lit(str(panel))
        annual = con.execute(f"""
            SELECT academic_year,
                   COUNT(*) FILTER (WHERE is_state_local_government=1 AND enrol_c1_12>0) AS schools,
                   SUM(enrol_c1_12) FILTER (WHERE is_state_local_government=1 AND enrol_c1_12>0) AS students,
                   SUM(muslim_c1_12) FILTER (WHERE is_state_local_government=1 AND enrol_c1_12>0) AS muslim_students,
                   AVG(muslim_c1_12/enrol_c1_12) FILTER (WHERE is_state_local_government=1 AND enrol_c1_12>0) AS mean_school_muslim_share,
                   (SUM(muslim_c1_12) FILTER (WHERE is_state_local_government=1 AND enrol_c1_12>0)) /
                   NULLIF((SUM(enrol_c1_12) FILTER (WHERE is_state_local_government=1 AND enrol_c1_12>0)),0)
                   AS student_weighted_muslim_share
            FROM read_parquet({p})
            GROUP BY 1 ORDER BY 1
        """).df()
        annual.to_csv(OUT / "annual_universe.csv", index=False)

        bins = con.execute(f"""
            WITH g AS (
              SELECT *,
                     LEAST(19, GREATEST(0, FLOOR(20.0*muslim_c1_12/NULLIF(enrol_c1_12,0))))::INTEGER AS bin_id,
                     CASE WHEN girls_c1_12>0 THEN CASE WHEN girls_func_toilets>0 THEN 1 ELSE 0 END END AS girls_toilet_ok,
                     CASE WHEN boys_c1_12>0 THEN CASE WHEN boys_func_toilets>0 THEN 1 ELSE 0 END END AS boys_toilet_ok,
                     CASE WHEN classrooms_major_repair>0 THEN 1 ELSE 0 END AS major_repair_any
              FROM read_parquet({p})
              WHERE is_state_local_government=1 AND enrol_c1_12>0
            )
            SELECT academic_year, bin_id,
                   bin_id*5 AS muslim_share_low_pct,
                   CASE WHEN bin_id=19 THEN 100 ELSE (bin_id+1)*5 END AS muslim_share_high_pct,
                   COUNT(*) AS schools,
                   SUM(enrol_c1_12) AS students,
                   SUM(muslim_c1_12) AS muslim_students,
                   AVG(total_teachers) AS mean_total_teachers,
                   AVG(girls_toilet_ok) AS girls_functional_toilet_rate,
                   AVG(boys_toilet_ok) AS boys_functional_toilet_rate,
                   AVG(water_functional) AS functional_water_rate,
                   AVG(electricity_functional) AS functional_electricity_rate,
                   AVG(major_repair_any) AS major_repair_rate,
                   AVG(academic_inspections) AS mean_academic_inspections,
                   AVG(crc_visits) AS mean_crc_visits,
                   AVG(block_visits) AS mean_block_visits,
                   AVG(district_state_visits) AS mean_district_state_visits
            FROM g GROUP BY 1,2 ORDER BY 1,2
        """).df()
        bins.to_csv(OUT / "muslim_share_5pp_baseline.csv", index=False)

        latest = con.execute(f"""
            WITH g AS (
              SELECT *, muslim_c1_12/NULLIF(enrol_c1_12,0) AS muslim_share,
                     general_c1_12/NULLIF(enrol_c1_12,0) AS general_share,
                     sc_c1_12/NULLIF(enrol_c1_12,0) AS sc_share,
                     st_c1_12/NULLIF(enrol_c1_12,0) AS st_share,
                     obc_c1_12/NULLIF(enrol_c1_12,0) AS obc_share,
                     GREATEST(0, enrol_c1_12-muslim_c1_12-christian_c1_12-sikh_c1_12-buddhist_c1_12-parsi_c1_12-jain_c1_12)/NULLIF(enrol_c1_12,0) AS religion_residual_share
              FROM read_parquet({p})
              WHERE academic_year='2025-26' AND is_state_local_government=1 AND enrol_c1_12>0
            )
            SELECT COUNT(*) AS schools,
                   AVG(muslim_share) AS mean_muslim_share,
                   AVG(religion_residual_share) AS mean_religion_residual_share,
                   AVG(general_share) AS mean_general_share,
                   AVG(sc_share) AS mean_sc_share,
                   AVG(st_share) AS mean_st_share,
                   AVG(obc_share) AS mean_obc_share,
                   CORR(muslim_share,general_share) AS corr_muslim_general,
                   CORR(muslim_share,sc_share) AS corr_muslim_sc,
                   CORR(muslim_share,st_share) AS corr_muslim_st,
                   CORR(muslim_share,obc_share) AS corr_muslim_obc
            FROM g
        """).df()
        latest.to_csv(OUT / "latest_composition_summary.csv", index=False)
        write_json(OUT / "source_validation.json", reports)

    con.close()
    print(annual.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
