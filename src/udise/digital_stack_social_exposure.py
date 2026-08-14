from __future__ import annotations

import csv
import os
from pathlib import Path

import duckdb
from huggingface_hub import hf_hub_download

REMOTE_DB = "processed/2024_25/database/udise_2024_25.duckdb"
GROUPS = {
    "A0_Muslim": (2, 5),
    "B0_General": (1, 1),
    "C0_SC": (1, 2),
    "D0_ST": (1, 3),
    "E0_OBC": (1, 4),
}


def class_total(prefix: str = "") -> str:
    return "+".join(f"COALESCE({prefix}c{c}_{sex},0)" for c in range(1,13) for sex in ("b","g"))


def main() -> None:
    repo_id = os.environ["HF_DATASET_REPO"]
    token = os.environ["HF_TOKEN"]
    db = hf_hub_download(repo_id=repo_id, repo_type="dataset", filename=REMOTE_DB, token=token)
    con = duckdb.connect(db, read_only=True)
    out = Path("outputs/bharatnet_dpi")
    out.mkdir(parents=True, exist_ok=True)

    union_parts = []
    total_expr = class_total()
    for label, (item_group, item_id) in GROUPS.items():
        union_parts.append(f"""
            SELECT pseudocode, '{label}' AS group_name, {total_expr} AS group_students
            FROM raw_enrolment_1
            WHERE item_group={item_group} AND item_id={item_id}
        """)
    group_sql = " UNION ALL ".join(union_parts)

    query = f"""
        WITH groups AS ({group_sql}),
        school AS (
            SELECT p.pseudocode,
                   CASE WHEN f.electricity_availability=1 THEN 1 ELSE 0 END AS electricity,
                   CASE WHEN COALESCE(f.desktop,0)+COALESCE(f.laptop,0)+COALESCE(f.tablet,0)>0 THEN 1 ELSE 0 END AS device,
                   CASE WHEN f.internet=1 THEN 1 ELSE 0 END AS internet,
                   CASE WHEN t.trained_comp>0 THEN 1 ELSE 0 END AS trained,
                   CASE
                       WHEN f.electricity_availability<>1 THEN 0
                       WHEN COALESCE(f.desktop,0)+COALESCE(f.laptop,0)+COALESCE(f.tablet,0)=0 THEN 1
                       WHEN f.internet<>1 THEN 2
                       WHEN t.trained_comp<=0 THEN 3
                       ELSE 4 END AS stack_level
            FROM raw_profile_1 p
            JOIN raw_facility f USING(pseudocode)
            JOIN raw_teacher t USING(pseudocode)
            WHERE p.rural_urban=1
        )
        SELECT g.group_name, s.stack_level,
               SUM(g.group_students) AS group_students,
               SUM(g.group_students) * 1.0 / SUM(SUM(g.group_students)) OVER (PARTITION BY g.group_name) AS exposure_share
        FROM groups g JOIN school s USING(pseudocode)
        GROUP BY 1,2 ORDER BY 1,2
    """
    cur = con.execute(query)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    with (out / "rural_digital_stack_social_exposure.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader(); w.writerows(rows)
    print(rows)


if __name__ == "__main__":
    main()
