from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from huggingface_hub import HfApi, hf_hub_download

from udise.indicator_registry import (
    ALL_INDICATORS,
    CODEBOOK_REQUIRED_COLUMNS,
    SECONDARY_INDICATORS,
    TERTIARY_INDICATORS,
    Indicator,
    validate_registry,
)

GROUPS = (
    ("A0", "Muslim"),
    ("B0", "General baseline"),
    ("C0", "Scheduled Caste baseline"),
    ("D0", "Scheduled Tribe baseline"),
    ("E0", "Other Backward Class baseline"),
)
GROUP_ITEM = {
    "A0": (2, 5),
    "B0": (1, 1),
    "C0": (1, 2),
    "D0": (1, 3),
    "E0": (1, 4),
}
STAGES = (
    ("primary", "Primary", (1, 2, 3, 4, 5)),
    ("upper_primary", "Upper primary", (6, 7, 8)),
    ("secondary", "Secondary", (9, 10)),
    ("higher_secondary", "Higher secondary", (11, 12)),
)
BANDS = (
    (0, "0%"),
    (1, ">0-5%"),
    (2, ">5-10%"),
    (3, ">10-20%"),
    (4, ">20-30%"),
    (5, ">30-40%"),
    (6, ">40-50%"),
    (7, ">50-75%"),
    (8, ">75-100%"),
)
REMOTE_DATABASE = "processed/2024_25/database/udise_2024_25.duckdb"
REMOTE_SCHOOL_INDICATORS = "processed/2024_25/analysis/school_indicator_base.parquet"

PRIMARY_SUMMARY_COLUMNS = {
    "profile_1": (
        "lowclass", "highclass", "avg_instr_days",
        "same_sch_b", "same_sch_g", "other_sch_b", "other_sch_g",
        "anganwadi_ecce_b", "anganwadi_ecce_g",
    ),
    "profile_2": (
        "acad_inspections", "crc_coordinator", "block_level_officers",
        "district_officers", "smc_smdc_meetings",
        "grants_receipt", "grants_expenditure",
    ),
    "facility": (
        "no_building_blocks", "pucca_building_blocks", "total_class_rooms",
        "other_rooms", "classrooms_in_good_condition",
        "classrooms_needs_minor_repair", "classrooms_needs_major_repair",
        "total_boys_toilet", "total_boys_func_toilet",
        "total_girls_toilet", "total_girls_func_toilet",
        "total_boys_cwsn_toilet", "func_boys_cwsn_friendly",
        "total_girls_cwsn_toilet", "func_girls_cwsn_friendly",
        "urinal_boys", "urinal_girls", "laptop", "tablet", "desktop",
        "digiboard", "teachdev_tot", "server_tot", "smart_class_tv_tot",
        "projector", "printer",
    ),
    "teacher": (
        "total_tch", "male", "female", "transgender",
        "gen_tch", "sc_tch", "st_tch", "obc_tch",
        "regular", "contract", "part_time", "below_graduate", "graduate",
        "post_graduate_and_above", "trained_comp", "trained_cwsn",
        "teacher_involve_non_training_assignment",
    ),
}

KEY_MODEL_OUTCOMES = (
    "ends_before_class10",
    "ends_before_class12",
    "no_functional_girls_toilet",
    "no_functional_water_source",
    "no_functional_electricity",
    "no_library",
    "no_internet",
    "student_teacher_ratio",
    "str_above_30",
    "no_female_teacher",
    "grant_per_student",
    "over_age_share",
    "access_deprivation_index",
    "infrastructure_deprivation_index",
    "wash_deprivation_index",
    "digital_deprivation_index",
    "teacher_capacity_deprivation_index",
    "governance_response_deficit_index",
    "gendered_school_disadvantage_index",
    "educational_resource_deficit_index",
    "institutional_neglect_index",
    "overall_multidimensional_deprivation_index",
    "compound_vulnerability_deprivation_index",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/comprehensive_a0"))
    parser.add_argument("--database-path", type=Path)
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    parser.add_argument("--upload-school-indicators", action="store_true")
    return parser.parse_args()


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def query_dicts(connection: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, Any]]:
    cursor = connection.execute(query)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def class_total_expression(classes: Iterable[int], suffixes: tuple[str, ...] = ("b", "g")) -> str:
    return " + ".join(
        f"COALESCE(c{class_number}_{suffix}, 0)"
        for class_number in classes
        for suffix in suffixes
    )


def all_class_expression(suffixes: tuple[str, ...] = ("b", "g")) -> str:
    return class_total_expression(range(1, 13), suffixes)


def band_case(share: str) -> str:
    return f"""
        CASE
            WHEN {share} = 0 THEN 0
            WHEN {share} <= 0.05 THEN 1
            WHEN {share} <= 0.10 THEN 2
            WHEN {share} <= 0.20 THEN 3
            WHEN {share} <= 0.30 THEN 4
            WHEN {share} <= 0.40 THEN 5
            WHEN {share} <= 0.50 THEN 6
            WHEN {share} <= 0.75 THEN 7
            ELSE 8
        END
    """


def band_label_case(order_column: str = "band_order") -> str:
    clauses = " ".join(
        f"WHEN {order_column} = {order} THEN {sql_string(label)}"
        for order, label in BANDS
    )
    return f"CASE {clauses} END"


def interaction_band_case(share: str) -> str:
    return f"""
        CASE
            WHEN {share} = 0 THEN 0
            WHEN {share} <= 0.10 THEN 1
            WHEN {share} <= 0.25 THEN 2
            WHEN {share} <= 0.50 THEN 3
            ELSE 4
        END
    """


def interaction_band_label(order: int) -> str:
    return {0: "0%", 1: ">0-10%", 2: ">10-25%", 3: ">25-50%", 4: ">50%"}[order]


def download_database(args: argparse.Namespace, work_dir: Path) -> Path:
    if args.database_path:
        return args.database_path
    if not args.dataset_repo:
        raise RuntimeError("HF_DATASET_REPO is not configured")
    if not args.token:
        raise RuntimeError("HF_TOKEN is not configured")
    return Path(
        hf_hub_download(
            repo_id=args.dataset_repo,
            filename=REMOTE_DATABASE,
            repo_type="dataset",
            token=args.token,
            local_dir=work_dir,
        )
    )


def create_social_composition(connection: duckdb.DuckDBPyConnection) -> None:
    all_students = all_class_expression()
    boys = all_class_expression(("b",))
    girls = all_class_expression(("g",))
    stage_select = ",\n".join(
        f"{class_total_expression(classes)} AS {stage}_students"
        for stage, _, classes in STAGES
    )
    stage_boys = ",\n".join(
        f"{class_total_expression(classes, ('b',))} AS {stage}_boys"
        for stage, _, classes in STAGES
    )
    stage_girls = ",\n".join(
        f"{class_total_expression(classes, ('g',))} AS {stage}_girls"
        for stage, _, classes in STAGES
    )
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE enrolment_components AS
        SELECT pseudocode, item_group, item_id,
               {all_students} AS all_students,
               {boys} AS boys,
               {girls} AS girls,
               {stage_select},
               {stage_boys},
               {stage_girls}
        FROM raw_enrolment_1
        """
    )

    pivot_terms: list[str] = []
    for code, (item_group, item_id) in GROUP_ITEM.items():
        prefix = code.lower()
        pivot_terms.extend([
            f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN all_students ELSE 0 END) AS {prefix}_students",
            f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN boys ELSE 0 END) AS {prefix}_boys",
            f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN girls ELSE 0 END) AS {prefix}_girls",
        ])
        for stage, _, _ in STAGES:
            pivot_terms.extend([
                f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN {stage}_students ELSE 0 END) AS {prefix}_{stage}",
                f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN {stage}_boys ELSE 0 END) AS {prefix}_{stage}_boys",
                f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN {stage}_girls ELSE 0 END) AS {prefix}_{stage}_girls",
            ])

    religion_terms = {
        "christian_students": (2, 6), "sikh_students": (2, 7),
        "buddhist_students": (2, 8), "parsi_students": (2, 9),
        "jain_students": (2, 10),
    }
    for name, (item_group, item_id) in religion_terms.items():
        pivot_terms.append(
            f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN all_students ELSE 0 END) AS {name}"
        )
    pivot_terms.extend([
        "SUM(CASE WHEN item_group=3 AND item_id=13 THEN all_students ELSE 0 END) AS bpl_students",
        "SUM(CASE WHEN item_group=10 AND item_id=32 THEN all_students ELSE 0 END) AS ews_students",
        "SUM(CASE WHEN item_group=5 AND item_id=0 THEN all_students ELSE 0 END) AS repeater_students",
        "SUM(CASE WHEN item_group=4 THEN all_students ELSE 0 END) AS cwsn_students",
    ])
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE social_composition_raw AS
        SELECT pseudocode, {", ".join(pivot_terms)}
        FROM enrolment_components
        GROUP BY pseudocode
        """
    )
    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE social_composition AS
        SELECT *,
            b0_students + c0_students + d0_students + e0_students AS total_students,
            b0_boys + c0_boys + d0_boys + e0_boys AS total_boys,
            b0_girls + c0_girls + d0_girls + e0_girls AS total_girls,
            a0_students / NULLIF(b0_students + c0_students + d0_students + e0_students, 0) AS a0_share,
            b0_students / NULLIF(b0_students + c0_students + d0_students + e0_students, 0) AS b0_share,
            c0_students / NULLIF(b0_students + c0_students + d0_students + e0_students, 0) AS c0_share,
            d0_students / NULLIF(b0_students + c0_students + d0_students + e0_students, 0) AS d0_share,
            e0_students / NULLIF(b0_students + c0_students + d0_students + e0_students, 0) AS e0_share,
            a0_girls / NULLIF(a0_students, 0) AS a0_girls_share,
            (b0_students + c0_students + d0_students + e0_students)
              - (a0_students + christian_students + sikh_students + buddhist_students
                 + parsi_students + jain_students) AS religion_residual_students
        FROM social_composition_raw
        """
    )


def create_age_grade_table(connection: duckdb.DuckDBPyConnection) -> None:
    total_terms: list[str] = []
    over_terms: list[str] = []
    under_terms: list[str] = []
    on_terms: list[str] = []
    for class_number in range(1, 13):
        count = f"(COALESCE(c{class_number}_b, 0) + COALESCE(c{class_number}_g, 0))"
        nominal_age = class_number + 5
        total_terms.append(count)
        over_terms.append(f"CASE WHEN item_id > {nominal_age + 1} THEN {count} ELSE 0 END")
        under_terms.append(f"CASE WHEN item_id < {nominal_age - 1} THEN {count} ELSE 0 END")
        on_terms.append(f"CASE WHEN item_id BETWEEN {nominal_age - 1} AND {nominal_age + 1} THEN {count} ELSE 0 END")
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE age_grade_environment AS
        SELECT pseudocode,
               SUM({" + ".join(total_terms)}) AS age_class_students,
               SUM({" + ".join(over_terms)}) AS over_age_students,
               SUM({" + ".join(under_terms)}) AS under_age_students,
               SUM({" + ".join(on_terms)}) AS on_age_students
        FROM raw_enrolment_2
        WHERE item_group = 8
        GROUP BY pseudocode
        """
    )


def create_indicator_tables(connection: duckdb.DuckDBPyConnection) -> None:
    create_social_composition(connection)
    create_age_grade_table(connection)
    secondary_select = ",\n".join(
        f"({item.expression}) AS {sql_identifier(item.code)}"
        for item in SECONDARY_INDICATORS
    )
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE school_secondary AS
        SELECT m.*, s.* EXCLUDE (pseudocode),
               a.age_class_students, a.over_age_students,
               a.under_age_students, a.on_age_students,
               {secondary_select}
        FROM school_master_base AS m
        INNER JOIN social_composition AS s USING (pseudocode)
        LEFT JOIN age_grade_environment AS a USING (pseudocode)
        WHERE s.total_students > 0
        """
    )

    initial_codes = {
        "access_deprivation_index", "infrastructure_deprivation_index",
        "wash_deprivation_index", "digital_deprivation_index",
        "teacher_capacity_deprivation_index", "governance_response_deficit_index",
        "welfare_support_deficit_index", "inclusion_failure_index",
        "gendered_school_disadvantage_index",
    }
    initial = [item for item in TERTIARY_INDICATORS if item.code in initial_codes]
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE school_domains AS
        SELECT *, {", ".join(f'({item.expression}) AS {sql_identifier(item.code)}' for item in initial)}
        FROM school_secondary
        """
    )

    middle_codes = {
        "educational_resource_deficit_index", "institutional_need_index",
        "overall_multidimensional_deprivation_index",
    }
    middle = [item for item in TERTIARY_INDICATORS if item.code in middle_codes]
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE school_tertiary_middle AS
        SELECT *, {", ".join(f'({item.expression}) AS {sql_identifier(item.code)}' for item in middle)}
        FROM school_domains
        """
    )
    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE school_vulnerability_ranks AS
        SELECT *,
            CASE WHEN bpl_share IS NOT NULL THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY bpl_share) END AS bpl_percentile,
            CASE WHEN ews_share IS NOT NULL THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY ews_share) END AS ews_percentile,
            CASE WHEN repeater_share IS NOT NULL THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY repeater_share) END AS repeater_percentile,
            CASE WHEN cwsn_share IS NOT NULL THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY cwsn_share) END AS cwsn_percentile
        FROM school_tertiary_middle
        """
    )
    remaining_codes = {"institutional_neglect_index", "vulnerability_context_index"}
    remaining = [item for item in TERTIARY_INDICATORS if item.code in remaining_codes]
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE school_tertiary_pre_final AS
        SELECT *, {", ".join(f'({item.expression}) AS {sql_identifier(item.code)}' for item in remaining)}
        FROM school_vulnerability_ranks
        """
    )
    compound = next(item for item in TERTIARY_INDICATORS if item.code == "compound_vulnerability_deprivation_index")
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE school_indicator_base AS
        SELECT *, ({compound.expression}) AS {sql_identifier(compound.code)}
        FROM school_tertiary_pre_final
        """
    )

    selected_columns = [
        "pseudocode", "state", "district", "block", "rural_urban",
        "school_category", "school_type", "managment", "lowclass", "highclass",
        "minority_school", "shift_school", "resi_school",
        "total_students", "total_boys", "total_girls",
    ]
    for code, _ in GROUPS:
        prefix = code.lower()
        selected_columns.extend([f"{prefix}_students", f"{prefix}_boys", f"{prefix}_girls", f"{prefix}_share"])
    selected_columns.extend(item.code for item in ALL_INDICATORS)
    selected = ", ".join(sql_identifier(column) for column in selected_columns)
    unions: list[str] = []
    for code, label in GROUPS:
        prefix = code.lower()
        unions.append(
            f"""
            SELECT {selected},
                   {sql_string(code)} AS group_code,
                   {sql_string(label)} AS group_label,
                   {prefix}_students AS group_students,
                   {prefix}_boys AS group_boys,
                   {prefix}_girls AS group_girls,
                   {prefix}_share AS group_share,
                   {band_case(f'{prefix}_share')} AS band_order
            FROM school_indicator_base
            """
        )
    connection.execute("CREATE OR REPLACE TEMP VIEW group_school_long AS " + " UNION ALL ".join(unions))


def display_multiplier(item: Indicator) -> float:
    if item.kind == "binary_adverse":
        return 100.0
    if item.level == "tertiary":
        return 1.0
    if item.code.endswith("_share") or item.code.endswith("_rate"):
        return 100.0
    return 1.0


def display_unit(item: Indicator) -> str:
    if item.kind == "binary_adverse":
        return "percent exposed"
    if item.level == "tertiary":
        return "index 0-100"
    if item.code.endswith("_share") or item.code.endswith("_rate"):
        return "percent"
    if "per_100" in item.code:
        return "per 100 students"
    if item.code == "student_teacher_ratio":
        return "students per teacher"
    if item.code == "students_per_classroom":
        return "students per classroom"
    if "grant" in item.code or "expenditure" in item.code:
        return "rupees per student" if "per_student" in item.code else "ratio"
    return "raw value"


def weighted_expression(item: Indicator, weight: str) -> str:
    code = sql_identifier(item.code)
    return (
        f"SUM(CASE WHEN {code} IS NOT NULL THEN {weight} * CAST({code} AS DOUBLE) END) "
        f"/ NULLIF(SUM(CASE WHEN {code} IS NOT NULL THEN {weight} END), 0)"
    )


def group_exposure_rows(connection: duckdb.DuckDBPyConnection, group_fields: tuple[str, ...], indicators: tuple[Indicator, ...] = ALL_INDICATORS, where: str = "group_students > 0") -> list[dict[str, Any]]:
    fields = ", ".join(group_fields)
    aggregates = []
    for item in indicators:
        weight = "group_girls" if item.weight == "girls" else "group_students"
        aggregates.append(f"{weighted_expression(item, weight)} AS {sql_identifier(item.code)}")
    wide = query_dicts(
        connection,
        f"""
        SELECT {fields}, SUM(group_students)::BIGINT AS group_students,
               SUM(group_girls)::BIGINT AS group_girls,
               {", ".join(aggregates)}
        FROM group_school_long
        WHERE {where}
        GROUP BY {fields}
        ORDER BY {fields}
        """,
    )
    rows: list[dict[str, Any]] = []
    for record in wide:
        base = {field: record[field] for field in group_fields}
        for item in indicators:
            value = record.get(item.code)
            rows.append({
                **base,
                "group_students": record["group_students"],
                "group_girls": record["group_girls"],
                "indicator_code": item.code,
                "indicator_level": item.level,
                "domain": item.domain,
                "indicator_label": item.label,
                "kind": item.kind,
                "direction": item.direction,
                "raw_value": value,
                "display_value": float(value) * display_multiplier(item) if value is not None else None,
                "unit": display_unit(item),
            })
    return rows


def concentration_gradient_rows(connection: duckdb.DuckDBPyConnection, indicators: tuple[Indicator, ...] = ALL_INDICATORS) -> list[dict[str, Any]]:
    aggregates: list[str] = []
    for item in indicators:
        code = sql_identifier(item.code)
        weight = "group_girls" if item.weight == "girls" else "group_students"
        aggregates.append(f"AVG(CAST({code} AS DOUBLE)) AS school_{item.code}")
        aggregates.append(f"{weighted_expression(item, weight)} AS weighted_{item.code}")
    wide = query_dicts(
        connection,
        f"""
        SELECT group_code, group_label, band_order,
               {band_label_case('band_order')} AS band,
               COUNT(*)::BIGINT AS schools,
               SUM(group_students)::BIGINT AS group_students,
               {", ".join(aggregates)}
        FROM group_school_long
        GROUP BY group_code, group_label, band_order
        ORDER BY group_code, band_order
        """,
    )
    rows: list[dict[str, Any]] = []
    for record in wide:
        for item in indicators:
            for estimand in ("school", "weighted"):
                value = record.get(f"{estimand}_{item.code}")
                rows.append({
                    "group_code": record["group_code"],
                    "group_label": record["group_label"],
                    "band_order": record["band_order"],
                    "band": record["band"],
                    "schools": record["schools"],
                    "group_students": record["group_students"],
                    "estimand": "equal-school mean" if estimand == "school" else "group-student-weighted mean",
                    "indicator_code": item.code,
                    "indicator_level": item.level,
                    "domain": item.domain,
                    "indicator_label": item.label,
                    "direction": item.direction,
                    "raw_value": value,
                    "display_value": float(value) * display_multiplier(item) if value is not None else None,
                    "unit": display_unit(item),
                })
    return rows


def baseline_gap_rows(exposure_rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    grouped: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in exposure_rows:
        group_key = tuple(row.get(key) for key in keys) + (row["indicator_code"],)
        grouped[group_key][row["group_code"]] = row
    output: list[dict[str, Any]] = []
    for group_key, by_code in grouped.items():
        if "A0" not in by_code:
            continue
        a0 = by_code["A0"]
        for baseline_code in ("B0", "C0", "D0", "E0"):
            baseline = by_code.get(baseline_code)
            if not baseline:
                continue
            a0_value = a0["raw_value"]
            baseline_value = baseline["raw_value"]
            if a0_value is None or baseline_value is None:
                gap = None
            elif a0["direction"] == "higher_better":
                gap = baseline_value - a0_value
            else:
                gap = a0_value - baseline_value
            row = {key: group_key[index] for index, key in enumerate(keys)}
            row.update({
                "baseline_code": baseline_code,
                "baseline_label": baseline["group_label"],
                "indicator_code": a0["indicator_code"],
                "indicator_level": a0["indicator_level"],
                "domain": a0["domain"],
                "indicator_label": a0["indicator_label"],
                "direction": a0["direction"],
                "a0_raw_value": a0_value,
                "baseline_raw_value": baseline_value,
                "standardised_deprivation_gap_raw": gap,
                "standardised_deprivation_gap_display": gap * display_multiplier(registry[a0["indicator_code"]]) if gap is not None else None,
                "unit": a0["unit"],
            })
            output.append(row)
    return output


def pairwise_gap_rows(exposure_rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    grouped: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in exposure_rows:
        group_key = tuple(row.get(key) for key in keys) + (row["indicator_code"],)
        grouped[group_key][row["group_code"]] = row
    output: list[dict[str, Any]] = []
    codes = [code for code, _ in GROUPS]
    for group_key, by_code in grouped.items():
        for left_index, left in enumerate(codes):
            for right in codes[left_index + 1:]:
                if left not in by_code or right not in by_code:
                    continue
                left_row = by_code[left]
                right_row = by_code[right]
                left_value = left_row["raw_value"]
                right_value = right_row["raw_value"]
                difference = left_value - right_value if left_value is not None and right_value is not None else None
                row = {key: group_key[index] for index, key in enumerate(keys)}
                row.update({
                    "left_group": left,
                    "right_group": right,
                    "indicator_code": left_row["indicator_code"],
                    "domain": left_row["domain"],
                    "indicator_label": left_row["indicator_label"],
                    "left_raw_value": left_value,
                    "right_raw_value": right_value,
                    "raw_difference_left_minus_right": difference,
                    "display_difference": difference * display_multiplier(registry[left_row["indicator_code"]]) if difference is not None else None,
                    "unit": left_row["unit"],
                })
                output.append(row)
    return output


def group_totals(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return query_dicts(
        connection,
        """
        SELECT group_code, group_label,
               SUM(group_students)::BIGINT AS students,
               SUM(group_boys)::BIGINT AS boys,
               SUM(group_girls)::BIGINT AS girls,
               SUM(group_students) * 100.0 / NULLIF(SUM(total_students), 0) AS national_share_percent,
               SUM((group_students > 0)::INTEGER)::BIGINT AS schools_with_group,
               COUNT(*)::BIGINT AS schools
        FROM group_school_long
        GROUP BY group_code, group_label
        ORDER BY group_code
        """,
    )


def stage_rows(connection: duckdb.DuckDBPyConnection, geographic: bool = False) -> list[dict[str, Any]]:
    geography = "state," if geographic else ""
    rows: list[dict[str, Any]] = []
    for stage_order, (stage, stage_label, _) in enumerate(STAGES):
        columns = ", ".join(f"SUM({code.lower()}_{stage}) AS {code.lower()}" for code, _ in GROUPS)
        records = query_dicts(
            connection,
            f"""
            SELECT {geography} {columns}
            FROM social_composition s
            {"JOIN raw_profile_1 p USING (pseudocode)" if geographic else ""}
            {"GROUP BY state" if geographic else ""}
            """,
        )
        for record in records:
            total = sum(int(record[code.lower()] or 0) for code, _ in GROUPS[1:])
            for code, label in GROUPS:
                students = int(record[code.lower()] or 0)
                result = {
                    "stage_order": stage_order, "stage": stage_label,
                    "group_code": code, "group_label": label,
                    "students": students,
                    "share_percent": students * 100.0 / total if total else None,
                }
                if geographic:
                    result["state"] = record["state"]
                rows.append(result)
    return rows


def concentration_distribution(connection: duckdb.DuckDBPyConnection, by_state: bool = False) -> list[dict[str, Any]]:
    geography = "state," if by_state else ""
    partition = "state, group_code" if by_state else "group_code"
    group = "state, group_code, group_label, band_order" if by_state else "group_code, group_label, band_order"
    return query_dicts(
        connection,
        f"""
        SELECT {geography} group_code, group_label, band_order,
               {band_label_case('band_order')} AS band,
               COUNT(*)::BIGINT AS schools,
               SUM(group_students)::BIGINT AS group_students,
               COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY {partition}) AS school_share_percent,
               SUM(group_students) * 100.0 / NULLIF(SUM(SUM(group_students)) OVER (PARTITION BY {partition}), 0) AS group_student_share_percent
        FROM group_school_long
        GROUP BY {group}
        ORDER BY {geography} group_code, band_order
        """,
    )


def primary_source_inventory(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    table_map = {
        "profile_1": "raw_profile_1", "profile_2": "raw_profile_2",
        "facility": "raw_facility", "enrolment_1": "raw_enrolment_1",
        "enrolment_2": "raw_enrolment_2", "teacher": "raw_teacher",
    }
    codebook = {column for column, _ in CODEBOOK_REQUIRED_COLUMNS}
    for source_name, table_name in table_map.items():
        for ordinal, record in enumerate(connection.execute(f"DESCRIBE {table_name}").fetchall(), start=1):
            column = record[0]
            qualified = f"{source_name}.{column}"
            rows.append({
                "source_table": source_name, "ordinal": ordinal,
                "column": column, "data_type": record[1], "nullable": record[2],
                "primary_indicator": True,
                "codebook_required": qualified in codebook,
                "analysis_role": "school identifier" if column == "pseudocode" else "directly recorded parameter",
            })
    return rows


def primary_numeric_summary(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, columns in PRIMARY_SUMMARY_COLUMNS.items():
        table = f"raw_{source}"
        for column in columns:
            quoted = sql_identifier(column)
            record = connection.execute(
                f"""
                SELECT COUNT(*) AS rows, COUNT({quoted}) AS nonmissing,
                       MIN(CAST({quoted} AS DOUBLE)) AS minimum,
                       QUANTILE_CONT(CAST({quoted} AS DOUBLE), 0.10) AS p10,
                       MEDIAN(CAST({quoted} AS DOUBLE)) AS median,
                       AVG(CAST({quoted} AS DOUBLE)) AS mean,
                       QUANTILE_CONT(CAST({quoted} AS DOUBLE), 0.90) AS p90,
                       MAX(CAST({quoted} AS DOUBLE)) AS maximum
                FROM {table}
                """
            ).fetchone()
            rows.append({
                "source_table": source, "column": column,
                "rows": record[0], "nonmissing": record[1],
                "missing": record[0] - record[1], "minimum": record[2],
                "p10": record[3], "median": record[4], "mean": record[5],
                "p90": record[6], "maximum": record[7],
            })
    return rows


def codebook_audit(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for qualified, description in CODEBOOK_REQUIRED_COLUMNS:
        source, column = qualified.split(".", 1)
        table = f"raw_{source}"
        query = f"""
            SELECT CAST(t.{sql_identifier(column)} AS VARCHAR) AS raw_code,
                   COUNT(*)::BIGINT AS schools,
                   SUM(s.a0_students)::BIGINT AS a0_students,
                   SUM(s.b0_students)::BIGINT AS b0_students,
                   SUM(s.c0_students)::BIGINT AS c0_students,
                   SUM(s.d0_students)::BIGINT AS d0_students,
                   SUM(s.e0_students)::BIGINT AS e0_students,
                   SUM(s.total_students)::BIGINT AS total_students,
                   SUM(s.a0_students) * 100.0 / NULLIF(SUM(s.total_students), 0) AS muslim_share_percent
            FROM {table} t
            LEFT JOIN social_composition s USING (pseudocode)
            GROUP BY t.{sql_identifier(column)}
            ORDER BY TRY_CAST(t.{sql_identifier(column)} AS DOUBLE), raw_code
        """
        for record in query_dicts(connection, query):
            rows.append({
                "source_table": source, "column": column,
                "description": description, **record,
                "interpretation_status": "raw code only; UDISE DCF required",
            })
    return rows


def teacher_representation(connection: duckdb.DuckDBPyConnection, by_state: bool = False) -> list[dict[str, Any]]:
    geography = "state," if by_state else ""
    join = "JOIN raw_profile_1 p USING (pseudocode)" if by_state else ""
    group_by = "GROUP BY state" if by_state else ""
    records = query_dicts(
        connection,
        f"""
        SELECT {geography}
               SUM(gen_tch)::DOUBLE AS b0_teachers,
               SUM(sc_tch)::DOUBLE AS c0_teachers,
               SUM(st_tch)::DOUBLE AS d0_teachers,
               SUM(obc_tch)::DOUBLE AS e0_teachers,
               SUM(total_tch)::DOUBLE AS total_teachers,
               SUM(s.b0_students)::DOUBLE AS b0_students,
               SUM(s.c0_students)::DOUBLE AS c0_students,
               SUM(s.d0_students)::DOUBLE AS d0_students,
               SUM(s.e0_students)::DOUBLE AS e0_students,
               SUM(s.total_students)::DOUBLE AS total_students
        FROM raw_teacher t
        JOIN social_composition s USING (pseudocode)
        {join}
        {group_by}
        """,
    )
    rows: list[dict[str, Any]] = []
    for record in records:
        for code, label in GROUPS[1:]:
            prefix = code.lower()
            teacher_share = record[f"{prefix}_teachers"] / record["total_teachers"] if record["total_teachers"] else None
            student_share = record[f"{prefix}_students"] / record["total_students"] if record["total_students"] else None
            row = {
                "group_code": code, "group_label": label,
                "teacher_share_percent": teacher_share * 100 if teacher_share is not None else None,
                "student_share_percent": student_share * 100 if student_share is not None else None,
                "teacher_minus_student_percentage_points": (teacher_share - student_share) * 100 if teacher_share is not None and student_share is not None else None,
            }
            if by_state:
                row["state"] = record["state"]
            rows.append(row)
    return rows


def gender_exposure_rows(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    indicators = tuple(item for item in ALL_INDICATORS if item.code in {
        "ends_before_class10", "ends_before_class12", "no_functional_girls_toilet",
        "girls_toilets_per_100_girls", "no_female_teacher", "female_teacher_share",
        "no_functional_water_source", "gendered_school_disadvantage_index",
    })
    rows: list[dict[str, Any]] = []
    for gender, weight in (("girls", "group_girls"), ("boys", "group_boys")):
        aggregates = [f"{weighted_expression(item, weight)} AS {sql_identifier(item.code)}" for item in indicators]
        wide = query_dicts(
            connection,
            f"""
            SELECT group_code, group_label, SUM({weight})::BIGINT AS gender_students,
                   {", ".join(aggregates)}
            FROM group_school_long
            WHERE {weight} > 0
            GROUP BY group_code, group_label
            ORDER BY group_code
            """,
        )
        for record in wide:
            for item in indicators:
                value = record[item.code]
                rows.append({
                    "gender": gender, "group_code": record["group_code"],
                    "group_label": record["group_label"],
                    "gender_students": record["gender_students"],
                    "indicator_code": item.code, "indicator_label": item.label,
                    "domain": item.domain, "raw_value": value,
                    "display_value": value * display_multiplier(item) if value is not None else None,
                    "unit": display_unit(item),
                })
    return rows


def interaction_grids(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    selected = tuple(item for item in ALL_INDICATORS if item.level == "tertiary" or item.code in {
        "ends_before_class10", "ends_before_class12", "student_teacher_ratio",
        "no_internet", "no_functional_girls_toilet", "grant_per_student",
    })
    rows: list[dict[str, Any]] = []
    for baseline_code in ("B0", "C0", "D0", "E0"):
        baseline_share = f"{baseline_code.lower()}_share"
        aggregates = [f"AVG({sql_identifier(item.code)}) AS school_{item.code}" for item in selected]
        aggregates += [
            f"SUM(a0_students * {sql_identifier(item.code)}) / NULLIF(SUM(a0_students), 0) AS a0_weighted_{item.code}"
            for item in selected
        ]
        wide = query_dicts(
            connection,
            f"""
            WITH banded AS (
                SELECT *, {interaction_band_case('a0_share')} AS a0_band,
                       {interaction_band_case(baseline_share)} AS baseline_band
                FROM school_indicator_base
            )
            SELECT a0_band, baseline_band, COUNT(*)::BIGINT AS schools,
                   SUM(a0_students)::BIGINT AS muslim_students,
                   {", ".join(aggregates)}
            FROM banded
            GROUP BY a0_band, baseline_band
            ORDER BY a0_band, baseline_band
            """,
        )
        for record in wide:
            for item in selected:
                for estimand in ("school", "a0_weighted"):
                    value = record[f"{estimand}_{item.code}"]
                    rows.append({
                        "baseline_code": baseline_code,
                        "a0_band_order": record["a0_band"],
                        "a0_band": interaction_band_label(record["a0_band"]),
                        "baseline_band_order": record["baseline_band"],
                        "baseline_band": interaction_band_label(record["baseline_band"]),
                        "schools": record["schools"], "muslim_students": record["muslim_students"],
                        "estimand": "equal-school mean" if estimand == "school" else "Muslim-student-weighted mean",
                        "indicator_code": item.code, "indicator_label": item.label,
                        "domain": item.domain, "raw_value": value,
                        "display_value": value * display_multiplier(item) if value is not None else None,
                        "unit": display_unit(item),
                    })
    return rows


def fixed_effect_slopes(connection: duckdb.DuckDBPyConnection, outcomes: tuple[str, ...] = KEY_MODEL_OUTCOMES) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    rows: list[dict[str, Any]] = []
    for outcome in outcomes:
        item = registry[outcome]
        for level, partition in (("state_fixed_effect", "state"), ("district_fixed_effect", "state, district")):
            record = connection.execute(
                f"""
                WITH demeaned AS (
                    SELECT a0_share - AVG(a0_share) OVER (PARTITION BY {partition}) AS x,
                           {sql_identifier(outcome)} - AVG({sql_identifier(outcome)}) OVER (PARTITION BY {partition}) AS y
                    FROM school_indicator_base
                    WHERE a0_share IS NOT NULL AND {sql_identifier(outcome)} IS NOT NULL
                )
                SELECT COUNT(*)::BIGINT AS observations,
                       SUM(x * y) / NULLIF(SUM(x * x), 0) AS slope,
                       CORR(x, y) AS within_correlation
                FROM demeaned
                """
            ).fetchone()
            rows.append({
                "model": level, "indicator_code": outcome,
                "indicator_label": item.label, "domain": item.domain,
                "observations": record[0], "slope_per_unit_a0_share": record[1],
                "slope_per_10_percentage_point_a0_increase": record[1] * 0.10 * display_multiplier(item) if record[1] is not None else None,
                "within_correlation": record[2], "unit": display_unit(item),
                "interpretation": "Positive means worse conditions as Muslim share rises" if item.direction == "higher_worse" else "Negative means worse conditions as Muslim share rises",
            })
    return rows


def state_profiles(state_exposures: list[dict[str, Any]], state_stages: list[dict[str, Any]], state_distribution: list[dict[str, Any]]) -> list[dict[str, Any]]:
    a0_exposure = {(row["state"], row["indicator_code"]): row for row in state_exposures if row["group_code"] == "A0"}
    stage_lookup = {(row["state"], row["stage"]): row for row in state_stages if row["group_code"] == "A0"}
    concentration_lookup: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for row in state_distribution:
        if row["group_code"] == "A0":
            concentration_lookup[row["state"]][row["band_order"]] = row
    states = sorted({row["state"] for row in state_exposures})
    selected = [
        "ends_before_class10", "ends_before_class12", "student_teacher_ratio",
        "str_above_30", "no_female_teacher", "no_functional_girls_toilet",
        "no_functional_water_source", "no_functional_electricity", "no_library",
        "no_internet", "grant_per_student", "overall_multidimensional_deprivation_index",
        "institutional_neglect_index",
    ]
    rows: list[dict[str, Any]] = []
    for state in states:
        profile: dict[str, Any] = {"state": state}
        for stage in ("Primary", "Upper primary", "Secondary", "Higher secondary"):
            row = stage_lookup.get((state, stage))
            profile[f"a0_{stage.lower().replace(' ', '_')}_share_percent"] = row["share_percent"] if row else None
        primary = profile.get("a0_primary_share_percent")
        higher = profile.get("a0_higher_secondary_share_percent")
        profile["a0_primary_to_higher_secondary_representation_change_pp"] = higher - primary if higher is not None and primary is not None else None
        bands = concentration_lookup.get(state, {})
        profile["a0_students_in_majority_schools_percent"] = sum(bands[order]["group_student_share_percent"] for order in (7, 8) if order in bands)
        profile["a0_students_in_supermajority_schools_percent"] = bands[8]["group_student_share_percent"] if 8 in bands else None
        for code in selected:
            row = a0_exposure.get((state, code))
            profile[code] = row["display_value"] if row else None
        rows.append(profile)
    return rows


def district_profiles(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    selected = tuple(item for item in ALL_INDICATORS if item.code in {
        "ends_before_class10", "ends_before_class12", "str_above_30", "no_female_teacher",
        "no_functional_girls_toilet", "no_functional_water_source", "no_functional_electricity",
        "no_library", "no_internet", "grant_per_student",
        "overall_multidimensional_deprivation_index", "institutional_neglect_index",
    })
    aggregates = [
        f"SUM(a0_students * {sql_identifier(item.code)}) / NULLIF(SUM(a0_students), 0) AS {sql_identifier(item.code)}"
        for item in selected
    ]
    rows = query_dicts(
        connection,
        f"""
        SELECT state, district, COUNT(*)::BIGINT AS schools,
               SUM(total_students)::BIGINT AS total_students,
               SUM(a0_students)::BIGINT AS muslim_students,
               SUM(a0_students) * 100.0 / NULLIF(SUM(total_students), 0) AS muslim_share_percent,
               SUM((a0_students > 0)::INTEGER)::BIGINT AS schools_with_muslim_students,
               {", ".join(aggregates)}
        FROM school_indicator_base
        GROUP BY state, district
        ORDER BY state, district
        """,
    )
    registry = {item.code: item for item in selected}
    for row in rows:
        for code, item in registry.items():
            if row[code] is not None:
                row[code] *= display_multiplier(item)
    return rows


def structural_evidence_profile(national_gaps: list[dict[str, Any]], slopes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gap_lookup = {(row["baseline_code"], row["indicator_code"]): row for row in national_gaps}
    slope_lookup = {(row["model"], row["indicator_code"]): row for row in slopes}
    rows: list[dict[str, Any]] = []
    for code in KEY_MODEL_OUTCOMES:
        item = next(item for item in ALL_INDICATORS if item.code == code)
        b0_gap = gap_lookup.get(("B0", code))
        state_slope = slope_lookup.get(("state_fixed_effect", code))
        district_slope = slope_lookup.get(("district_fixed_effect", code))
        raw_adverse = bool(b0_gap and b0_gap["standardised_deprivation_gap_display"] is not None and b0_gap["standardised_deprivation_gap_display"] > 0)
        state_adverse = False
        district_adverse = False
        for model_row, target in ((state_slope, "state"), (district_slope, "district")):
            if model_row and model_row["slope_per_10_percentage_point_a0_increase"] is not None:
                adverse = model_row["slope_per_10_percentage_point_a0_increase"] > 0 if item.direction == "higher_worse" else model_row["slope_per_10_percentage_point_a0_increase"] < 0
                if target == "state":
                    state_adverse = adverse
                else:
                    district_adverse = adverse
        evidence_count = sum((raw_adverse, state_adverse, district_adverse))
        rows.append({
            "indicator_code": code, "indicator_label": item.label, "domain": item.domain,
            "a0_worse_than_b0_raw": raw_adverse,
            "adverse_within_state_association": state_adverse,
            "adverse_within_district_association": district_adverse,
            "evidence_components_met": evidence_count,
            "evidence_classification": "three-layer consistent pattern" if evidence_count == 3 else "two-layer pattern" if evidence_count == 2 else "one-layer signal" if evidence_count == 1 else "no adverse pattern in these tests",
            "limitation": "Descriptive and fixed-effect associations do not by themselves prove discrimination or intent.",
        })
    return rows


def indicator_catalog_rows(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in primary_source_inventory(connection):
        rows.append({
            "indicator_code": f"primary.{item['source_table']}.{item['column']}",
            "indicator_level": "primary", "domain": item["source_table"],
            "indicator_label": item["column"], "formula": "directly recorded source parameter",
            "kind": "direct", "direction": "not assigned at primary level",
            "weight": "not applicable", "applicability": "as recorded",
            "source_columns": f"{item['source_table']}.{item['column']}",
            "interpretation": "Direct UDISE+ parameter.",
            "limitation": "Requires the UDISE DCF before categorical labels can be assigned." if item["codebook_required"] else "",
            "supported": True,
        })
    for item in ALL_INDICATORS:
        row = item.as_row()
        row.update({
            "indicator_code": item.code, "indicator_level": item.level,
            "formula": item.expression, "source_columns": row["sources"],
        })
        rows.append(row)
    return rows


def save_bar_chart(rows: list[dict[str, Any]], title: str, ylabel: str, output: Path) -> None:
    ordered = sorted(rows, key=lambda row: row["group_code"])
    fig, ax = plt.subplots(figsize=(9, 5.7))
    values = [row["display_value"] if row["display_value"] is not None else np.nan for row in ordered]
    bars = ax.bar([row["group_code"] for row in ordered], values)
    if bars:
        bars[0].set_hatch("//")
        bars[0].set_linewidth(1.8)
        bars[0].set_edgecolor("black")
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("A0 is Muslim enrolment; B0-E0 are comparison baselines")
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar, value in zip(bars, values, strict=True):
        if np.isfinite(value):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.1f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=190, bbox_inches="tight")
    plt.close(fig)


def save_gradient_chart(rows: list[dict[str, Any]], item: Indicator, output: Path) -> None:
    selected = [row for row in rows if row["indicator_code"] == item.code and row["estimand"] == "group-student-weighted mean"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        grouped[row["group_code"]].append(row)
    fig, ax = plt.subplots(figsize=(10, 6))
    for code, label in GROUPS:
        group_rows = sorted(grouped[code], key=lambda row: row["band_order"])
        ax.plot([row["band"] for row in group_rows], [row["display_value"] for row in group_rows], marker="o", linewidth=3.0 if code == "A0" else 1.2, alpha=1.0 if code == "A0" else 0.68, label=f"{code} {label}")
    ax.set_title(f"{item.label} across school-composition bands", loc="left", fontweight="bold")
    ax.set_ylabel(display_unit(item))
    ax.set_xlabel("Group share of school enrolment")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_domain_gap_heatmaps(gaps: list[dict[str, Any]], output_dir: Path) -> None:
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in gaps:
        by_domain[row["domain"]].append(row)
    baselines = ["B0", "C0", "D0", "E0"]
    registry = {item.code: item for item in ALL_INDICATORS}
    for domain, rows in by_domain.items():
        indicators = sorted({row["indicator_code"] for row in rows}, key=lambda code: registry[code].label)
        if not indicators:
            continue
        matrix = np.full((len(indicators), len(baselines)), np.nan)
        for row in rows:
            matrix[indicators.index(row["indicator_code"]), baselines.index(row["baseline_code"])] = row["standardised_deprivation_gap_display"] if row["standardised_deprivation_gap_display"] is not None else np.nan
        fig, ax = plt.subplots(figsize=(8, max(4, 0.32 * len(indicators) + 1.8)))
        image = ax.imshow(matrix, aspect="auto", cmap="coolwarm")
        ax.set_xticks(range(len(baselines)))
        ax.set_xticklabels([f"A0 vs {code}" for code in baselines])
        ax.set_yticks(range(len(indicators)))
        ax.set_yticklabels([registry[code].label for code in indicators], fontsize=7)
        ax.set_title(f"Standardised Muslim disadvantage gaps in {domain.replace('_', ' ')}", loc="left", fontweight="bold")
        fig.colorbar(image, ax=ax, label="Positive means worse A0 condition")
        fig.tight_layout()
        output_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_dir / f"{domain}_a0_baseline_gap_heatmap.png", dpi=180, bbox_inches="tight")
        plt.close(fig)


def save_state_ranking(profiles: list[dict[str, Any]], column: str, title: str, output: Path) -> None:
    rows = [row for row in profiles if row.get(column) is not None]
    rows.sort(key=lambda row: row[column])
    fig, ax = plt.subplots(figsize=(10, max(7, len(rows) * 0.25)))
    ax.barh([row["state"] for row in rows], [row[column] for row in rows])
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_xlabel(column.replace("_", " "))
    ax.grid(axis="x", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_report(totals: list[dict[str, Any]], exposures: list[dict[str, Any]], gaps: list[dict[str, Any]], slopes: list[dict[str, Any]], catalog_count: int) -> str:
    totals_by_code = {row["group_code"]: row for row in totals}
    exposure_lookup = {(row["group_code"], row["indicator_code"]): row for row in exposures}
    gap_lookup = {(row["baseline_code"], row["indicator_code"]): row for row in gaps}
    a0 = totals_by_code["A0"]
    key = (
        "ends_before_class10", "ends_before_class12", "str_above_30",
        "no_female_teacher", "no_functional_girls_toilet",
        "no_functional_water_source", "no_functional_electricity",
        "no_library", "no_internet", "overall_multidimensional_deprivation_index",
        "institutional_neglect_index",
    )
    lines = [
        "# Comprehensive A0-centred UDISE+ 2024-25 analysis", "",
        "## Scope", "",
        f"The run catalogues {catalog_count:,} primary, secondary and tertiary indicators. A0 Muslim students are the substantive population. B0 General, C0 Scheduled Caste, D0 Scheduled Tribe and E0 Other Backward Class are comparison baselines.", "",
        "## Muslim enrolment", "",
        f"Muslim enrolment in Classes 1-12: {int(a0['students']):,}.",
        f"Muslim share of reconciled enrolment: {a0['national_share_percent']:.2f}%.",
        f"Schools reporting at least one Muslim student: {int(a0['schools_with_group']):,}.", "",
        "## Selected national Muslim exposure measures", "",
        "| Indicator | A0 value | A0-B0 standardised disadvantage gap |", "|---|---:|---:|",
    ]
    for code in key:
        exposure = exposure_lookup.get(("A0", code))
        gap = gap_lookup.get(("B0", code))
        if exposure:
            gap_value = f"{gap['standardised_deprivation_gap_display']:.2f}" if gap and gap["standardised_deprivation_gap_display"] is not None else "n/a"
            lines.append(f"| {exposure['indicator_label']} | {exposure['display_value']:.2f} {exposure['unit']} | {gap_value} |")
    lines.extend([
        "", "## Structural interpretation boundary", "",
        "The outputs measure school concentration, student-weighted exposure, baseline gaps, within-state and within-district associations, domain indices and interaction patterns. They can support a conclusion that the evidence is consistent with structural educational disadvantage when adverse A0 patterns persist across these layers. They do not directly measure discriminatory intent, household circumstances, attendance, learning outcomes or individual Muslim caste status.", "",
        "Fields whose meanings depend on the UDISE DCF are preserved as raw codes and excluded from label-dependent conclusions until the codebook is supplied.", "",
        f"Fixed-effect association rows produced: {len(slopes):,}.", "",
    ])
    return "\n".join(lines)


def export_school_indicator_parquet(connection: duckdb.DuckDBPyConnection, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    connection.execute(f"COPY school_indicator_base TO {sql_string(str(output_path))} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)")


def upload_school_indicator(repo_id: str, token: str, parquet_path: Path) -> None:
    HfApi(token=token).upload_file(
        path_or_fileobj=str(parquet_path), path_in_repo=REMOTE_SCHOOL_INDICATORS,
        repo_id=repo_id, repo_type="dataset",
        commit_message="Add comprehensive UDISE 2024-25 school indicator table",
    )


def main() -> int:
    validate_registry()
    args = parse_args()
    output = args.output
    tables_dir = output / "tables"
    figures_dir = output / "figures"
    work_dir = output / "work"
    for directory in (tables_dir, figures_dir, work_dir):
        directory.mkdir(parents=True, exist_ok=True)

    database_path = download_database(args, work_dir)
    connection = duckdb.connect(str(database_path), read_only=True)
    connection.execute("PRAGMA threads=4")
    connection.execute("PRAGMA memory_limit='11GB'")
    connection.execute(f"PRAGMA temp_directory={sql_string(str(work_dir / 'duckdb_temp'))}")
    try:
        create_indicator_tables(connection)
        catalog = indicator_catalog_rows(connection)
        primary_summary = primary_numeric_summary(connection)
        dcf_audit = codebook_audit(connection)
        totals = group_totals(connection)
        national_stages = stage_rows(connection)
        state_stages = stage_rows(connection, geographic=True)
        national_distribution = concentration_distribution(connection)
        state_distribution = concentration_distribution(connection, by_state=True)
        national_exposures = group_exposure_rows(connection, ("group_code", "group_label"))
        national_gaps = baseline_gap_rows(national_exposures, keys=())
        pairwise_gaps = pairwise_gap_rows(national_exposures, keys=())
        gradients = concentration_gradient_rows(connection)
        gender_exposures = gender_exposure_rows(connection)
        teacher_representation_national = teacher_representation(connection)
        teacher_representation_state = teacher_representation(connection, by_state=True)
        interactions = interaction_grids(connection)
        slopes = fixed_effect_slopes(connection)
        state_exposures = group_exposure_rows(connection, ("state", "group_code", "group_label"))
        state_gaps = baseline_gap_rows(state_exposures, keys=("state",))
        profiles = state_profiles(state_exposures, state_stages, state_distribution)
        districts = district_profiles(connection)
        evidence = structural_evidence_profile(national_gaps, slopes)

        outputs = {
            "indicator_catalog.csv": catalog,
            "primary_numeric_summary.csv": primary_summary,
            "dcf_raw_code_audit.csv": dcf_audit,
            "national_group_totals.csv": totals,
            "national_stage_representation.csv": national_stages,
            "state_stage_representation.csv": state_stages,
            "national_concentration_distribution.csv": national_distribution,
            "state_concentration_distribution.csv": state_distribution,
            "national_group_exposures_all_indicators.csv": national_exposures,
            "national_a0_baseline_gaps_all_indicators.csv": national_gaps,
            "national_all_pairwise_gaps.csv": pairwise_gaps,
            "national_concentration_gradients_all_indicators.csv": gradients,
            "national_gender_exposures.csv": gender_exposures,
            "national_teacher_social_category_representation.csv": teacher_representation_national,
            "state_teacher_social_category_representation.csv": teacher_representation_state,
            "a0_baseline_interaction_grids.csv": interactions,
            "fixed_effect_a0_associations.csv": slopes,
            "state_group_exposures_all_indicators.csv": state_exposures,
            "state_a0_baseline_gaps_all_indicators.csv": state_gaps,
            "state_a0_profiles.csv": profiles,
            "district_a0_profiles.csv": districts,
            "structural_evidence_profile.csv": evidence,
        }
        for filename, rows in outputs.items():
            write_csv(tables_dir / filename, rows)

        manifest = {
            "indicator_catalog_rows": len(catalog),
            "secondary_indicators": len(SECONDARY_INDICATORS),
            "tertiary_indicators": len(TERTIARY_INDICATORS),
            "national_exposure_rows": len(national_exposures),
            "national_gap_rows": len(national_gaps),
            "gradient_rows": len(gradients),
            "state_exposure_rows": len(state_exposures),
            "state_gap_rows": len(state_gaps),
            "district_profiles": len(districts),
        }
        write_json(output / "analysis_manifest.json", manifest)

        exposures_by_indicator: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in national_exposures:
            exposures_by_indicator[row["indicator_code"]].append(row)
        for item in ALL_INDICATORS:
            safe_domain = item.domain.replace("/", "_")
            save_bar_chart(exposures_by_indicator[item.code], f"{item.label}: Muslim exposure and comparison baselines", display_unit(item), figures_dir / "exposures" / safe_domain / f"{item.code}.png")
            save_gradient_chart(gradients, item, figures_dir / "gradients" / safe_domain / f"{item.code}.png")
        save_domain_gap_heatmaps(national_gaps, figures_dir / "gap_heatmaps")
        save_state_ranking(profiles, "overall_multidimensional_deprivation_index", "Muslim-student exposure to multidimensional school deprivation by state", figures_dir / "state_rankings" / "overall_deprivation.png")
        save_state_ranking(profiles, "institutional_neglect_index", "Muslim-student exposure to institutional neglect interaction by state", figures_dir / "state_rankings" / "institutional_neglect.png")
        save_state_ranking(profiles, "a0_primary_to_higher_secondary_representation_change_pp", "Change in Muslim representation from primary to higher secondary by state", figures_dir / "state_rankings" / "stage_representation_change.png")

        school_parquet = work_dir / "school_indicator_base.parquet"
        export_school_indicator_parquet(connection, school_parquet)
        if args.upload_school_indicators:
            if not args.dataset_repo or not args.token:
                raise RuntimeError("Dataset repository and token required for upload")
            upload_school_indicator(args.dataset_repo, args.token, school_parquet)

        report = build_report(totals, national_exposures, national_gaps, slopes, len(catalog))
        (output / "comprehensive_a0_report.md").write_text(report, encoding="utf-8")
        if summary_path := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary_path).open("a", encoding="utf-8") as handle:
                handle.write(report)
        school_parquet.unlink(missing_ok=True)
        shutil.rmtree(work_dir, ignore_errors=True)
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
