from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Any

import duckdb

from udise.comprehensive_a0_analysis import (
    GROUPS,
    band_case,
    codebook_audit,
    concentration_distribution,
    create_social_composition,
    download_database,
    group_totals,
    primary_numeric_summary,
    primary_source_inventory,
    stage_rows,
    teacher_representation,
    write_csv,
)
from udise.national_a0_analysis import (
    save_a0_distribution_chart,
    save_stage_chart,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/source_composition"))
    parser.add_argument("--database-path", type=Path)
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    return parser.parse_args()


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def create_group_view(connection: duckdb.DuckDBPyConnection) -> None:
    unions: list[str] = []
    for code, label in GROUPS:
        prefix = code.lower()
        unions.append(
            f"""
            SELECT p.state, p.district, p.block, s.pseudocode,
                   s.total_students, s.total_boys, s.total_girls,
                   s.{prefix}_students AS group_students,
                   s.{prefix}_boys AS group_boys,
                   s.{prefix}_girls AS group_girls,
                   s.{prefix}_share AS group_share,
                   {sql_string(code)} AS group_code,
                   {sql_string(label)} AS group_label,
                   {band_case(f's.{prefix}_share')} AS band_order
            FROM social_composition s
            JOIN raw_profile_1 p USING (pseudocode)
            WHERE s.total_students > 0
            """
        )
    connection.execute(
        "CREATE OR REPLACE TEMP VIEW group_school_long AS " + " UNION ALL ".join(unions)
    )


def stage_gender_rows(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    stages = (
        (0, "Primary", "primary"),
        (1, "Upper primary", "upper_primary"),
        (2, "Secondary", "secondary"),
        (3, "Higher secondary", "higher_secondary"),
    )
    rows: list[dict[str, Any]] = []
    for stage_order, stage_label, suffix in stages:
        for code, label in GROUPS:
            prefix = code.lower()
            boys, girls = connection.execute(
                f"SELECT SUM({prefix}_{suffix}_boys), SUM({prefix}_{suffix}_girls) FROM social_composition"
            ).fetchone()
            boys = int(boys or 0)
            girls = int(girls or 0)
            total = boys + girls
            rows.extend(
                [
                    {
                        "stage_order": stage_order,
                        "stage": stage_label,
                        "group_code": code,
                        "group_label": label,
                        "gender": "boys",
                        "students": boys,
                        "within_group_stage_gender_share_percent": boys * 100.0 / total if total else None,
                    },
                    {
                        "stage_order": stage_order,
                        "stage": stage_label,
                        "group_code": code,
                        "group_label": label,
                        "gender": "girls",
                        "students": girls,
                        "within_group_stage_gender_share_percent": girls * 100.0 / total if total else None,
                    },
                ]
            )
    return rows


def supporting_religion_totals(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    columns = (
        ("A0", "Muslim", "a0_students"),
        ("R6", "Christian", "christian_students"),
        ("R7", "Sikh", "sikh_students"),
        ("R8", "Buddhist", "buddhist_students"),
        ("R9", "Parsi", "parsi_students"),
        ("R10", "Jain", "jain_students"),
        ("RR", "Religion residual", "religion_residual_students"),
    )
    total_students = int(
        connection.execute("SELECT SUM(total_students) FROM social_composition").fetchone()[0]
        or 0
    )
    rows: list[dict[str, Any]] = []
    for code, label, column in columns:
        students = int(
            connection.execute(f"SELECT SUM({column}) FROM social_composition").fetchone()[0]
            or 0
        )
        rows.append(
            {
                "code": code,
                "religion_category": label,
                "students": students,
                "share_of_reconciled_total_percent": students * 100.0 / total_students if total_students else None,
                "interpretation_note": (
                    "Residual category is not labelled Hindu without official documentation."
                    if code == "RR"
                    else "Directly reported religion item."
                ),
            }
        )
    return rows


def build_report(totals: list[dict[str, Any]], primary_columns: int, code_rows: int) -> str:
    a0 = next(row for row in totals if row["group_code"] == "A0")
    return "\n".join(
        [
            "# Source and social-composition analysis",
            "",
            f"Direct source columns catalogued: {primary_columns:,}",
            f"Raw DCF-code distribution rows: {code_rows:,}",
            f"Muslim students in Classes 1 to 12: {int(a0['students']):,}",
            f"Muslim share of reconciled enrolment: {a0['national_share_percent']:.2f}%",
            f"Schools reporting Muslim enrolment: {int(a0['schools_with_group']):,}",
            "",
            "A0 is the substantive population. B0 to E0 are comparison baselines.",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    output = args.output
    tables_dir = output / "tables"
    figures_dir = output / "figures"
    work_dir = output / "work"
    for directory in (tables_dir, figures_dir, work_dir):
        directory.mkdir(parents=True, exist_ok=True)

    print("Downloading the processed DuckDB database", flush=True)
    database_path = download_database(args, work_dir)
    connection = duckdb.connect(str(database_path), read_only=True)
    connection.execute("PRAGMA threads=2")
    connection.execute("PRAGMA memory_limit='4GB'")
    connection.execute("PRAGMA preserve_insertion_order=false")
    connection.execute(f"PRAGMA temp_directory={sql_string(str(work_dir / 'duckdb_temp'))}")
    try:
        print("Constructing the reconciled social-composition table", flush=True)
        create_social_composition(connection)
        create_group_view(connection)

        print("Cataloguing all direct source columns and raw DCF codes", flush=True)
        inventory = primary_source_inventory(connection)
        numeric_summary = primary_numeric_summary(connection)
        dcf_codes = codebook_audit(connection)

        print("Calculating national and state composition outputs", flush=True)
        totals = group_totals(connection)
        stages = stage_rows(connection)
        state_stages = stage_rows(connection, geographic=True)
        stage_gender = stage_gender_rows(connection)
        distribution = concentration_distribution(connection)
        state_distribution = concentration_distribution(connection, by_state=True)
        religions = supporting_religion_totals(connection)
        teacher_national = teacher_representation(connection)
        teacher_state = teacher_representation(connection, by_state=True)

        outputs = {
            "primary_source_column_inventory.csv": inventory,
            "primary_numeric_summary.csv": numeric_summary,
            "dcf_raw_code_audit.csv": dcf_codes,
            "national_group_totals.csv": totals,
            "national_stage_representation.csv": stages,
            "state_stage_representation.csv": state_stages,
            "national_stage_gender_composition.csv": stage_gender,
            "national_concentration_distribution.csv": distribution,
            "state_concentration_distribution.csv": state_distribution,
            "supporting_religion_totals.csv": religions,
            "national_teacher_social_category_representation.csv": teacher_national,
            "state_teacher_social_category_representation.csv": teacher_state,
        }
        for filename, rows in outputs.items():
            write_csv(tables_dir / filename, rows)

        save_stage_chart(stages, figures_dir / "a0_representation_by_stage.png")
        save_a0_distribution_chart(
            distribution, figures_dir / "a0_concentration_distribution.png"
        )

        report = build_report(totals, len(inventory), len(dcf_codes))
        (output / "source_composition_report.md").write_text(report, encoding="utf-8")
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write(report)
        print("Source and composition analysis completed", flush=True)
    finally:
        connection.close()
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
