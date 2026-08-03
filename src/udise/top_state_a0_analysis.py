from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any

import duckdb
from huggingface_hub import hf_hub_download

REMOTE_CHECKPOINT = "processed/2024_25/analysis/school_indicator_base.parquet"
TOP_STATES = ("BIHAR", "UTTAR PRADESH", "JHARKHAND", "UTTARAKHAND", "ASSAM")
GROUPS = (
    ("A0", "Muslim"),
    ("B0", "General baseline"),
    ("C0", "Scheduled Caste baseline"),
    ("D0", "Scheduled Tribe baseline"),
    ("E0", "Other Backward Class baseline"),
)
BANDS = {
    0: "0%", 1: ">0-5%", 2: ">5-10%", 3: ">10-20%", 4: ">20-30%",
    5: ">30-40%", 6: ">40-50%", 7: ">50-75%", 8: ">75-100%",
}
INDICATORS = (
    ("ends_before_class10", "School ends before Class 10", "Access", "percent exposed", 100.0, "students"),
    ("ends_before_class12", "School ends before Class 12", "Access", "percent exposed", 100.0, "students"),
    ("str_above_30", "Student-teacher ratio above 30", "Crowding", "percent exposed", 100.0, "students"),
    ("student_teacher_ratio", "Students per teacher", "Crowding", "students per teacher", 1.0, "students"),
    ("students_per_classroom", "Students per instructional classroom", "Crowding", "students per classroom", 1.0, "students"),
    ("no_library", "No library", "Learning resources", "percent exposed", 100.0, "students"),
    ("no_reading_corner", "No reading corner", "Learning resources", "percent exposed", 100.0, "students"),
    ("no_internet", "No internet access", "Digital resources", "percent exposed", 100.0, "students"),
    ("no_core_digital_device", "No laptop, tablet or desktop", "Digital resources", "percent exposed", 100.0, "students"),
    ("no_primary_teacher", "No primary-grade teacher", "Teacher capacity", "percent exposed", 100.0, "students"),
    ("no_female_teacher", "No female teacher", "Teacher capacity", "percent exposed", 100.0, "girls"),
    ("over_age_share", "School-level over-age enrolment share", "Age-grade distortion", "percent", 100.0, "students"),
    ("institutional_neglect_index", "Institutional neglect interaction index", "Structural disadvantage", "index 0-100", 1.0, "students"),
    ("overall_multidimensional_deprivation_index", "Overall multidimensional school deprivation", "Structural disadvantage", "index 0-100", 1.0, "students"),
)


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/top_five_states"))
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    parser.add_argument("--school-indicator-path", type=Path)
    return parser.parse_args()


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def query(connection: duckdb.DuckDBPyConnection, statement: str) -> list[dict[str, Any]]:
    cursor = connection.execute(statement)
    fields = [item[0] for item in cursor.description]
    return [dict(zip(fields, row, strict=True)) for row in cursor.fetchall()]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def band_case(share: str) -> str:
    return f"""CASE WHEN {share}=0 THEN 0 WHEN {share}<=0.05 THEN 1
        WHEN {share}<=0.10 THEN 2 WHEN {share}<=0.20 THEN 3
        WHEN {share}<=0.30 THEN 4 WHEN {share}<=0.40 THEN 5
        WHEN {share}<=0.50 THEN 6 WHEN {share}<=0.75 THEN 7 ELSE 8 END"""


def weighted(prefix: str, code: str, weight_kind: str) -> str:
    weight = f"{prefix}_{weight_kind}"
    return (
        f"SUM(CASE WHEN {code} IS NOT NULL THEN {weight}*{code} ELSE 0 END)"
        f"/NULLIF(SUM(CASE WHEN {code} IS NOT NULL THEN {weight} ELSE 0 END),0)"
    )


def checkpoint(options: argparse.Namespace, work: Path) -> Path:
    if options.school_indicator_path:
        return options.school_indicator_path
    if not options.dataset_repo or not options.token:
        raise RuntimeError("HF_DATASET_REPO and HF_TOKEN are required")
    return Path(hf_hub_download(
        repo_id=options.dataset_repo,
        filename=REMOTE_CHECKPOINT,
        repo_type="dataset",
        token=options.token,
        local_dir=work,
    ))


def state_exposures(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    state_sql = ",".join(sql_string(state) for state in TOP_STATES)
    for group_code, group_label in GROUPS:
        prefix = group_code.lower()
        terms = ",".join(
            f"{weighted(prefix, code, weight)} AS {code}"
            for code, _, _, _, _, weight in INDICATORS
        )
        wide = query(connection, f"""
            SELECT state,SUM({prefix}_students) AS group_students,
                   SUM({prefix}_girls) AS group_girls,{terms}
            FROM school_indicator_base WHERE state IN ({state_sql}) GROUP BY state
        """)
        for record in wide:
            for code, label, domain, unit, scale, _ in INDICATORS:
                raw = record.get(code)
                rows.append({
                    "state": record["state"], "group_code": group_code,
                    "group_label": group_label, "group_students": record["group_students"],
                    "group_girls": record["group_girls"], "indicator_code": code,
                    "indicator_label": label, "domain": domain, "raw_value": raw,
                    "display_value": raw*scale if raw is not None and math.isfinite(raw) else None,
                    "unit": unit,
                })
    return rows


def concentration_gradients(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    state_sql = ",".join(sql_string(state) for state in TOP_STATES)
    for group_code, group_label in GROUPS:
        prefix = group_code.lower()
        terms: list[str] = []
        for code, _, _, _, _, weight_kind in INDICATORS:
            weight = f"{prefix}_{weight_kind}"
            terms.extend([
                f"AVG({code}) AS {code}__school",
                f"SUM(CASE WHEN {code} IS NOT NULL THEN {weight}*{code} ELSE 0 END)"
                f"/NULLIF(SUM(CASE WHEN {code} IS NOT NULL THEN {weight} ELSE 0 END),0) AS {code}__weighted",
            ])
        wide = query(connection, f"""
            SELECT state,{band_case(f'{prefix}_share')} AS band_order,
                   COUNT(*) AS schools,SUM({prefix}_students) AS group_students,{','.join(terms)}
            FROM school_indicator_base
            WHERE state IN ({state_sql}) AND {prefix}_share IS NOT NULL
            GROUP BY state,band_order ORDER BY state,band_order
        """)
        for record in wide:
            order = int(record["band_order"])
            for code, label, domain, unit, scale, _ in INDICATORS:
                for estimand, suffix in (("equal-school mean", "school"), ("group-student-weighted mean", "weighted")):
                    raw = record.get(f"{code}__{suffix}")
                    rows.append({
                        "state": record["state"], "group_code": group_code,
                        "group_label": group_label, "band_order": order, "band": BANDS[order],
                        "schools": record["schools"], "group_students": record["group_students"],
                        "estimand": estimand, "indicator_code": code, "indicator_label": label,
                        "domain": domain, "raw_value": raw,
                        "display_value": raw*scale if raw is not None and math.isfinite(raw) else None,
                        "unit": unit,
                    })
    return rows


def baseline_gaps(exposures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {(r["state"],r["group_code"],r["indicator_code"]):r for r in exposures}
    rows: list[dict[str, Any]] = []
    for state in TOP_STATES:
        for baseline_code, baseline_label in GROUPS[1:]:
            for code, label, domain, unit, _, _ in INDICATORS:
                a0 = lookup[(state,"A0",code)]["display_value"]
                base = lookup[(state,baseline_code,code)]["display_value"]
                rows.append({
                    "state":state,"baseline_code":baseline_code,"baseline_label":baseline_label,
                    "indicator_code":code,"indicator_label":label,"domain":domain,
                    "a0_value":a0,"baseline_value":base,
                    "a0_disadvantage_gap":a0-base if a0 is not None and base is not None else None,
                    "unit":unit,
                })
    return rows


def a0_band_changes(gradients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {(r["state"],r["indicator_code"],r["band_order"]):r for r in gradients
              if r["group_code"]=="A0" and r["estimand"]=="group-student-weighted mean"}
    rows: list[dict[str, Any]] = []
    for state in TOP_STATES:
        for code, label, domain, unit, _, _ in INDICATORS:
            low = lookup.get((state,code,1),{}).get("display_value")
            high = lookup.get((state,code,8),{}).get("display_value")
            rows.append({
                "state":state,"indicator_code":code,"indicator_label":label,"domain":domain,
                "a0_value_above_0_to_5_percent":low,"a0_value_above_75_percent":high,
                "change_above_75_minus_above_0_to_5":high-low if low is not None and high is not None else None,
                "unit":unit,
            })
    return rows


def main() -> int:
    options = args()
    output = options.output
    work = output/"work"
    work.mkdir(parents=True,exist_ok=True)
    try:
        parquet = checkpoint(options,work)
        temp = work/"duckdb_temp"; temp.mkdir(exist_ok=True)
        connection = duckdb.connect(str(work/"analysis.duckdb"))
        connection.execute("SET threads=2")
        connection.execute("SET memory_limit='4GB'")
        connection.execute("SET preserve_insertion_order=false")
        connection.execute(f"SET temp_directory={sql_string(str(temp))}")
        connection.execute("CREATE VIEW school_indicator_base AS SELECT * FROM read_parquet("+sql_string(str(parquet))+")")
        try:
            exposures = state_exposures(connection)
            gradients = concentration_gradients(connection)
        finally:
            connection.close()
        tables = output/"tables"
        write_csv(tables/"top_five_state_group_exposures.csv",exposures)
        write_csv(tables/"top_five_state_a0_baseline_gaps.csv",baseline_gaps(exposures))
        write_csv(tables/"top_five_state_all_group_concentration_gradients.csv",gradients)
        write_csv(tables/"top_five_state_a0_band_changes.csv",a0_band_changes(gradients))
        (output/"analysis_manifest.json").write_text(json.dumps({
            "states":TOP_STATES,"groups":[g[0] for g in GROUPS],"bands":BANDS,
            "indicators":[i[0] for i in INDICATORS],"gradient_rows":len(gradients)
        },indent=2),encoding="utf-8")
    finally:
        shutil.rmtree(work,ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
