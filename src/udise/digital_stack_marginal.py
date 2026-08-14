from __future__ import annotations

import csv
import os
from pathlib import Path

import duckdb
from huggingface_hub import hf_hub_download

REMOTE_DB = "processed/2024_25/database/udise_2024_25.duckdb"


def main() -> None:
    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    db = hf_hub_download(repo_id=repo_id, repo_type="dataset", filename=REMOTE_DB, token=token)
    con = duckdb.connect(db, read_only=True)
    out = Path("outputs/bharatnet_dpi")
    out.mkdir(parents=True, exist_ok=True)

    con.execute("""
        CREATE OR REPLACE TEMP VIEW stack_school AS
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
        SELECT p.pseudocode, e.students,
               CASE WHEN f.electricity_availability=1 THEN 1 ELSE 0 END AS electricity,
               CASE WHEN COALESCE(f.desktop,0)+COALESCE(f.laptop,0)+COALESCE(f.tablet,0)>0 THEN 1 ELSE 0 END AS device,
               CASE WHEN f.internet=1 THEN 1 ELSE 0 END AS internet,
               CASE WHEN t.trained_comp>0 THEN 1 ELSE 0 END AS trained
        FROM raw_profile_1 p
        JOIN raw_facility f USING(pseudocode)
        JOIN raw_teacher t USING(pseudocode)
        LEFT JOIN e USING(pseudocode)
        WHERE p.rural_urban=1
    """)

    cur = con.execute("""
        SELECT missing_count, COUNT(*) AS schools, SUM(students) AS students,
               COUNT(*) * 1.0 / SUM(COUNT(*)) OVER () AS school_share,
               SUM(students) * 1.0 / SUM(SUM(students)) OVER () AS student_share
        FROM (
            SELECT *, (1-electricity)+(1-device)+(1-internet)+(1-trained) AS missing_count
            FROM stack_school
        )
        GROUP BY 1 ORDER BY 1
    """)
    cols = [d[0] for d in cur.description]
    gap_rows = [dict(zip(cols,row,strict=True)) for row in cur.fetchall()]

    cur = con.execute("""
        SELECT missing_input, COUNT(*) AS schools, SUM(students) AS students
        FROM (
            SELECT *, CASE
                WHEN electricity=0 AND device=1 AND internet=1 AND trained=1 THEN 'functional electricity'
                WHEN electricity=1 AND device=0 AND internet=1 AND trained=1 THEN 'computing device'
                WHEN electricity=1 AND device=1 AND internet=0 AND trained=1 THEN 'internet connectivity'
                WHEN electricity=1 AND device=1 AND internet=1 AND trained=0 THEN 'computer-trained teacher'
            END AS missing_input
            FROM stack_school
        )
        WHERE missing_input IS NOT NULL
        GROUP BY 1 ORDER BY schools DESC
    """)
    cols2 = [d[0] for d in cur.description]
    marginal = [dict(zip(cols2,row,strict=True)) for row in cur.fetchall()]
    total_one = sum(int(r['schools']) for r in marginal)
    total_students_one = sum(int(r['students'] or 0) for r in marginal)
    for r in marginal:
        r['share_of_one_gap_schools'] = int(r['schools']) / total_one if total_one else None
        r['share_of_one_gap_students'] = int(r['students'] or 0) / total_students_one if total_students_one else None

    for filename, rows in (("rural_missing_input_count.csv", gap_rows), ("rural_one_input_away.csv", marginal)):
        with (out/filename).open('w', newline='', encoding='utf-8') as f:
            fields = list(rows[0]) if rows else []
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

    print('Missing-count distribution:', gap_rows)
    print('Exactly one input away:', marginal)


if __name__ == '__main__':
    main()
