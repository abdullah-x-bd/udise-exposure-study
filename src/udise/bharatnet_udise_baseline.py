from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import duckdb
from huggingface_hub import hf_hub_download

REMOTE_DB = "processed/2024_25/database/udise_2024_25.duckdb"
RAW_TABLES = ("raw_profile_1", "raw_profile_2", "raw_facility", "raw_teacher", "raw_enrolment_1")


def rows_as_dicts(con: duckdb.DuckDBPyConnection, query: str):
    cur = con.execute(query)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    db_path = hf_hub_download(repo_id=repo_id, repo_type="dataset", filename=REMOTE_DB, token=token)
    con = duckdb.connect(db_path, read_only=True)
    out = Path("outputs/bharatnet_dpi")
    out.mkdir(parents=True, exist_ok=True)

    schema = {table: rows_as_dicts(con, f"PRAGMA table_info('{table}')") for table in RAW_TABLES}
    (out / "udise_schema.json").write_text(json.dumps(schema, indent=2, default=str), encoding="utf-8")

    frequencies = {}
    for table, column in (
        ("raw_profile_1", "rural_urban"),
        ("raw_profile_1", "managment"),
        ("raw_facility", "internet"),
        ("raw_facility", "electricity_availability"),
        ("raw_facility", "comp_ict_lab_yn"),
        ("raw_facility", "ict_lab_yn"),
    ):
        frequencies[f"{table}.{column}"] = rows_as_dicts(
            con,
            f"SELECT {column} AS value, COUNT(*) AS schools FROM {table} GROUP BY 1 ORDER BY 1"
        )
    (out / "udise_code_frequencies.json").write_text(json.dumps(frequencies, indent=2, default=str), encoding="utf-8")

    con.execute("""
        CREATE OR REPLACE TEMP VIEW bn_school AS
        WITH e AS (
            SELECT pseudocode,
                   SUM(CASE WHEN item_group=1 AND item_id IN (1,2,3,4)
                            THEN COALESCE(c1_b,0)+COALESCE(c1_g,0)+COALESCE(c2_b,0)+COALESCE(c2_g,0)+
                                 COALESCE(c3_b,0)+COALESCE(c3_g,0)+COALESCE(c4_b,0)+COALESCE(c4_g,0)+
                                 COALESCE(c5_b,0)+COALESCE(c5_g,0)+COALESCE(c6_b,0)+COALESCE(c6_g,0)+
                                 COALESCE(c7_b,0)+COALESCE(c7_g,0)+COALESCE(c8_b,0)+COALESCE(c8_g,0)+
                                 COALESCE(c9_b,0)+COALESCE(c9_g,0)+COALESCE(c10_b,0)+COALESCE(c10_g,0)+
                                 COALESCE(c11_b,0)+COALESCE(c11_g,0)+COALESCE(c12_b,0)+COALESCE(c12_g,0)
                            ELSE 0 END) AS students
            FROM raw_enrolment_1 GROUP BY 1
        )
        SELECT p.pseudocode, p.state, p.district, p.block, p.rural_urban, p.managment,
               p.lgd_vill_name, p.lgd_vill_panchayat_name, p.lgd_block_name,
               p.lowclass, p.highclass,
               e.students,
               CASE WHEN f.internet=1 THEN 1 WHEN f.internet=2 THEN 0 ELSE NULL END AS has_internet,
               CASE WHEN f.electricity_availability=1 THEN 1 WHEN f.electricity_availability IN (2,3) THEN 0 ELSE NULL END AS functional_electricity,
               CASE WHEN COALESCE(f.desktop,0)+COALESCE(f.laptop,0)+COALESCE(f.tablet,0)>0 THEN 1 ELSE 0 END AS any_device,
               CASE WHEN t.trained_comp>0 THEN 1 ELSE 0 END AS trained_teacher,
               CASE WHEN f.comp_ict_lab_yn=1 OR f.ict_lab_yn=1 THEN 1
                    WHEN f.comp_ict_lab_yn=2 AND f.ict_lab_yn=2 THEN 0 ELSE NULL END AS has_ict_lab,
               COALESCE(f.desktop,0)+COALESCE(f.laptop,0)+COALESCE(f.tablet,0) AS device_count
        FROM raw_profile_1 p
        JOIN raw_facility f USING (pseudocode)
        JOIN raw_teacher t USING (pseudocode)
        LEFT JOIN e USING (pseudocode)
    """)

    national = rows_as_dicts(con, """
        SELECT COUNT(*) AS schools,
               SUM(CASE WHEN rural_urban=1 THEN 1 ELSE 0 END) AS rural_code1_schools,
               AVG(has_internet) AS internet_rate,
               AVG(functional_electricity) AS functional_electricity_rate,
               AVG(any_device) AS any_computing_device_rate,
               AVG(trained_teacher) AS computer_trained_teacher_rate,
               AVG(has_ict_lab) AS ict_lab_rate,
               SUM(students) AS students
        FROM bn_school
    """)
    (out / "national_digital_baseline.json").write_text(json.dumps(national, indent=2, default=str), encoding="utf-8")

    rural = rows_as_dicts(con, """
        SELECT COUNT(*) AS schools,
               AVG(has_internet) AS internet_rate,
               AVG(functional_electricity) AS functional_electricity_rate,
               AVG(any_device) AS any_computing_device_rate,
               AVG(trained_teacher) AS computer_trained_teacher_rate,
               AVG(has_ict_lab) AS ict_lab_rate,
               AVG(CASE WHEN functional_electricity=1 AND any_device=1 AND has_internet=1 AND trained_teacher=1 THEN 1.0 ELSE 0.0 END) AS complete_stack_rate,
               SUM(students) AS students,
               SUM(CASE WHEN functional_electricity=1 AND any_device=1 AND has_internet=1 AND trained_teacher=1 THEN students ELSE 0 END) / NULLIF(SUM(students),0) AS student_weighted_complete_stack_rate
        FROM bn_school WHERE rural_urban=1
    """)
    (out / "rural_digital_baseline.json").write_text(json.dumps(rural, indent=2, default=str), encoding="utf-8")

    stack = rows_as_dicts(con, """
        WITH s AS (
            SELECT *, CASE
                WHEN functional_electricity<>1 THEN 0
                WHEN any_device<>1 THEN 1
                WHEN has_internet<>1 THEN 2
                WHEN trained_teacher<>1 THEN 3
                ELSE 4 END AS stack_level
            FROM bn_school WHERE rural_urban=1
        )
        SELECT stack_level,
               CASE stack_level
                   WHEN 0 THEN 'No functional electricity'
                   WHEN 1 THEN 'Electricity, but no computing device'
                   WHEN 2 THEN 'Electricity + device, but no internet'
                   WHEN 3 THEN 'Electricity + device + internet, but no computer-trained teacher'
                   WHEN 4 THEN 'Complete digital capability stack'
               END AS bottleneck,
               COUNT(*) AS schools,
               COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS school_share,
               SUM(students) AS students,
               SUM(students) * 1.0 / SUM(SUM(students)) OVER () AS student_share
        FROM s GROUP BY 1,2 ORDER BY 1
    """)
    write_csv(out / "rural_digital_capability_stack.csv", stack)

    complementarity = rows_as_dicts(con, """
        SELECT functional_electricity, any_device, trained_teacher,
               COUNT(*) AS schools,
               AVG(has_internet) AS internet_rate,
               SUM(students) AS students
        FROM bn_school
        WHERE rural_urban=1 AND has_internet IS NOT NULL
        GROUP BY 1,2,3 ORDER BY 1,2,3
    """)
    write_csv(out / "rural_complementarity_cells.csv", complementarity)

    district = rows_as_dicts(con, """
        SELECT state, district,
               COUNT(*) AS schools,
               AVG(has_internet) AS internet_rate,
               AVG(functional_electricity) AS functional_electricity_rate,
               AVG(any_device) AS any_computing_device_rate,
               AVG(trained_teacher) AS computer_trained_teacher_rate,
               AVG(has_ict_lab) AS ict_lab_rate,
               AVG(CASE WHEN functional_electricity=1 AND any_device=1 AND has_internet=1 AND trained_teacher=1 THEN 1.0 ELSE 0.0 END) AS complete_stack_rate,
               SUM(students) AS students
        FROM bn_school WHERE rural_urban=1
        GROUP BY 1,2 HAVING COUNT(*) >= 10 ORDER BY 1,2
    """)
    write_csv(out / "district_rural_digital_baseline.csv", district)

    panchayat_coverage = rows_as_dicts(con, """
        SELECT COUNT(*) AS schools,
               SUM(CASE WHEN lgd_vill_panchayat_name IS NOT NULL AND TRIM(lgd_vill_panchayat_name)<>'' THEN 1 ELSE 0 END) AS schools_with_gp_name,
               COUNT(DISTINCT CASE WHEN lgd_vill_panchayat_name IS NOT NULL AND TRIM(lgd_vill_panchayat_name)<>''
                                   THEN CAST(state AS VARCHAR) || '|' || CAST(district AS VARCHAR) || '|' || lgd_vill_panchayat_name END) AS distinct_named_gps
        FROM bn_school WHERE rural_urban=1
    """)
    (out / "panchayat_linkage_coverage.json").write_text(json.dumps(panchayat_coverage, indent=2, default=str), encoding="utf-8")

    print("National baseline:", json.dumps(national, indent=2, default=str))
    print("Rural baseline:", json.dumps(rural, indent=2, default=str))
    print("Digital stack:", json.dumps(stack, indent=2, default=str))
    print("Panchayat linkage:", json.dumps(panchayat_coverage, indent=2, default=str))


if __name__ == "__main__":
    main()
