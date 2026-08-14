from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import duckdb
from huggingface_hub import hf_hub_download

REMOTE_DB = "processed/2024_25/database/udise_2024_25.duckdb"


def rows_as_dicts(con: duckdb.DuckDBPyConnection, query: str):
    cur = con.execute(query)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
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

    schema = {}
    for table in ("profile_1", "profile_2", "facility", "teacher", "enrolment_1"):
        schema[table] = rows_as_dicts(con, f"PRAGMA table_info('{table}')")
    (out / "udise_schema.json").write_text(json.dumps(schema, indent=2, default=str), encoding="utf-8")

    frequencies = {}
    for table, column in (
        ("profile_1", "rural_urban"),
        ("profile_1", "managment"),
        ("facility", "internet"),
        ("facility", "electricity_availability"),
        ("facility", "comp_ict_lab_yn"),
        ("facility", "ict_lab_yn"),
    ):
        frequencies[f"{table}.{column}"] = rows_as_dicts(
            con,
            f"SELECT {column} AS value, COUNT(*) AS schools FROM {table} GROUP BY 1 ORDER BY 1"
        )
    (out / "udise_code_frequencies.json").write_text(json.dumps(frequencies, indent=2, default=str), encoding="utf-8")

    national = rows_as_dicts(con, """
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
            FROM enrolment_1 GROUP BY 1
        )
        SELECT
            COUNT(*) AS schools,
            SUM(CASE WHEN p.rural_urban=1 THEN 1 ELSE 0 END) AS rural_code1_schools,
            AVG(CASE WHEN f.internet=1 THEN 1.0 WHEN f.internet=2 THEN 0.0 END) AS internet_rate,
            AVG(CASE WHEN f.electricity_availability=1 THEN 1.0 WHEN f.electricity_availability IN (2,3) THEN 0.0 END) AS functional_electricity_rate,
            AVG(CASE WHEN COALESCE(f.desktop,0)+COALESCE(f.laptop,0)+COALESCE(f.tablet,0)>0 THEN 1.0 ELSE 0.0 END) AS any_computing_device_rate,
            AVG(CASE WHEN t.trained_comp>0 THEN 1.0 ELSE 0.0 END) AS computer_trained_teacher_rate,
            SUM(e.students) AS students
        FROM profile_1 p
        JOIN facility f USING (pseudocode)
        JOIN teacher t USING (pseudocode)
        LEFT JOIN e USING (pseudocode)
    """)
    (out / "national_digital_baseline.json").write_text(json.dumps(national, indent=2, default=str), encoding="utf-8")

    district = rows_as_dicts(con, """
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
            FROM enrolment_1 GROUP BY 1
        )
        SELECT p.state, p.district,
               COUNT(*) AS schools,
               AVG(CASE WHEN f.internet=1 THEN 1.0 WHEN f.internet=2 THEN 0.0 END) AS internet_rate,
               AVG(CASE WHEN f.electricity_availability=1 THEN 1.0 WHEN f.electricity_availability IN (2,3) THEN 0.0 END) AS functional_electricity_rate,
               AVG(CASE WHEN COALESCE(f.desktop,0)+COALESCE(f.laptop,0)+COALESCE(f.tablet,0)>0 THEN 1.0 ELSE 0.0 END) AS any_computing_device_rate,
               AVG(CASE WHEN t.trained_comp>0 THEN 1.0 ELSE 0.0 END) AS computer_trained_teacher_rate,
               SUM(e.students) AS students
        FROM profile_1 p
        JOIN facility f USING (pseudocode)
        JOIN teacher t USING (pseudocode)
        LEFT JOIN e USING (pseudocode)
        WHERE p.rural_urban=1
        GROUP BY 1,2
        HAVING COUNT(*) >= 10
        ORDER BY 1,2
    """)
    write_csv(out / "district_rural_digital_baseline.csv", district)

    panchayat_coverage = rows_as_dicts(con, """
        SELECT
            COUNT(*) AS schools,
            SUM(CASE WHEN lgd_vill_panchayat_name IS NOT NULL AND TRIM(lgd_vill_panchayat_name)<>'' THEN 1 ELSE 0 END) AS schools_with_gp_name,
            COUNT(DISTINCT CASE WHEN lgd_vill_panchayat_name IS NOT NULL AND TRIM(lgd_vill_panchayat_name)<>''
                                THEN state || '|' || district || '|' || lgd_vill_panchayat_name END) AS distinct_named_gps
        FROM profile_1
        WHERE rural_urban=1
    """)
    (out / "panchayat_linkage_coverage.json").write_text(json.dumps(panchayat_coverage, indent=2, default=str), encoding="utf-8")

    print("National baseline:", json.dumps(national, indent=2, default=str))
    print("Panchayat linkage:", json.dumps(panchayat_coverage, indent=2, default=str))


if __name__ == "__main__":
    main()
