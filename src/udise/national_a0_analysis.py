from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from huggingface_hub import hf_hub_download


GROUPS = (
    ("A0", "Muslim"),
    ("B0", "General baseline"),
    ("C0", "Scheduled Caste baseline"),
    ("D0", "Scheduled Tribe baseline"),
    ("E0", "Other Backward Class baseline"),
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

STAGES = (
    ("Primary", (1, 2, 3, 4, 5)),
    ("Upper primary", (6, 7, 8)),
    ("Secondary", (9, 10)),
    ("Higher secondary", (11, 12)),
)

REMOTE_DATABASE = "processed/2024_25/database/udise_2024_25.duckdb"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/national_a0"))
    parser.add_argument("--database-path", type=Path)
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    return parser.parse_args()


def sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def class_total_expression(classes: Iterable[int], suffixes: tuple[str, ...] = ("b", "g")) -> str:
    terms = [f"COALESCE(c{class_number}_{suffix}, 0)" for class_number in classes for suffix in suffixes]
    return " + ".join(terms)


def all_class_total_expression() -> str:
    return class_total_expression(range(1, 13))


def band_case(share_column: str = "group_share") -> str:
    return f"""
        CASE
            WHEN {share_column} = 0 THEN 0
            WHEN {share_column} <= 0.05 THEN 1
            WHEN {share_column} <= 0.10 THEN 2
            WHEN {share_column} <= 0.20 THEN 3
            WHEN {share_column} <= 0.30 THEN 4
            WHEN {share_column} <= 0.40 THEN 5
            WHEN {share_column} <= 0.50 THEN 6
            WHEN {share_column} <= 0.75 THEN 7
            ELSE 8
        END
    """


def band_label_case(order_column: str = "band_order") -> str:
    clauses = "\n".join(
        f"WHEN {order_column} = {order} THEN '{label}'" for order, label in BANDS
    )
    return f"CASE {clauses} END"


def query_dicts(connection: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, Any]]:
    cursor = connection.execute(query)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


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


def build_analysis_tables(connection: duckdb.DuckDBPyConnection) -> None:
    total_all = all_class_total_expression()
    primary = class_total_expression((1, 2, 3, 4, 5))
    upper_primary = class_total_expression((6, 7, 8))
    secondary = class_total_expression((9, 10))
    higher_secondary = class_total_expression((11, 12))

    connection.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE enrolment_components AS
        SELECT
            pseudocode,
            item_group,
            item_id,
            {total_all} AS all_students,
            {primary} AS primary_students,
            {upper_primary} AS upper_primary_students,
            {secondary} AS secondary_students,
            {higher_secondary} AS higher_secondary_students
        FROM raw_enrolment_1
        """
    )

    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE social_composition AS
        SELECT
            pseudocode,
            SUM(CASE WHEN item_group = 2 AND item_id = 5 THEN all_students ELSE 0 END) AS a0_students,
            SUM(CASE WHEN item_group = 1 AND item_id = 1 THEN all_students ELSE 0 END) AS b0_students,
            SUM(CASE WHEN item_group = 1 AND item_id = 2 THEN all_students ELSE 0 END) AS c0_students,
            SUM(CASE WHEN item_group = 1 AND item_id = 3 THEN all_students ELSE 0 END) AS d0_students,
            SUM(CASE WHEN item_group = 1 AND item_id = 4 THEN all_students ELSE 0 END) AS e0_students,
            SUM(CASE WHEN item_group = 2 AND item_id = 5 THEN primary_students ELSE 0 END) AS a0_primary,
            SUM(CASE WHEN item_group = 1 AND item_id = 1 THEN primary_students ELSE 0 END) AS b0_primary,
            SUM(CASE WHEN item_group = 1 AND item_id = 2 THEN primary_students ELSE 0 END) AS c0_primary,
            SUM(CASE WHEN item_group = 1 AND item_id = 3 THEN primary_students ELSE 0 END) AS d0_primary,
            SUM(CASE WHEN item_group = 1 AND item_id = 4 THEN primary_students ELSE 0 END) AS e0_primary,
            SUM(CASE WHEN item_group = 2 AND item_id = 5 THEN upper_primary_students ELSE 0 END) AS a0_upper_primary,
            SUM(CASE WHEN item_group = 1 AND item_id = 1 THEN upper_primary_students ELSE 0 END) AS b0_upper_primary,
            SUM(CASE WHEN item_group = 1 AND item_id = 2 THEN upper_primary_students ELSE 0 END) AS c0_upper_primary,
            SUM(CASE WHEN item_group = 1 AND item_id = 3 THEN upper_primary_students ELSE 0 END) AS d0_upper_primary,
            SUM(CASE WHEN item_group = 1 AND item_id = 4 THEN upper_primary_students ELSE 0 END) AS e0_upper_primary,
            SUM(CASE WHEN item_group = 2 AND item_id = 5 THEN secondary_students ELSE 0 END) AS a0_secondary,
            SUM(CASE WHEN item_group = 1 AND item_id = 1 THEN secondary_students ELSE 0 END) AS b0_secondary,
            SUM(CASE WHEN item_group = 1 AND item_id = 2 THEN secondary_students ELSE 0 END) AS c0_secondary,
            SUM(CASE WHEN item_group = 1 AND item_id = 3 THEN secondary_students ELSE 0 END) AS d0_secondary,
            SUM(CASE WHEN item_group = 1 AND item_id = 4 THEN secondary_students ELSE 0 END) AS e0_secondary,
            SUM(CASE WHEN item_group = 2 AND item_id = 5 THEN higher_secondary_students ELSE 0 END) AS a0_higher_secondary,
            SUM(CASE WHEN item_group = 1 AND item_id = 1 THEN higher_secondary_students ELSE 0 END) AS b0_higher_secondary,
            SUM(CASE WHEN item_group = 1 AND item_id = 2 THEN higher_secondary_students ELSE 0 END) AS c0_higher_secondary,
            SUM(CASE WHEN item_group = 1 AND item_id = 3 THEN higher_secondary_students ELSE 0 END) AS d0_higher_secondary,
            SUM(CASE WHEN item_group = 1 AND item_id = 4 THEN higher_secondary_students ELSE 0 END) AS e0_higher_secondary
        FROM enrolment_components
        GROUP BY pseudocode
        """
    )

    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE national_analysis_base AS
        SELECT
            m.pseudocode,
            m.state,
            m.district,
            m.block,
            m.rural_urban,
            m.school_category,
            m.managment,
            m.lowclass,
            m.highclass,
            m.minority_school,
            m.total_tch,
            m.female,
            m.total_class_rooms,
            m.grants_receipt,
            m.acad_inspections,
            s.* EXCLUDE (pseudocode),
            (s.b0_students + s.c0_students + s.d0_students + s.e0_students) AS total_students,
            s.a0_students / NULLIF((s.b0_students + s.c0_students + s.d0_students + s.e0_students), 0) AS a0_share,
            s.b0_students / NULLIF((s.b0_students + s.c0_students + s.d0_students + s.e0_students), 0) AS b0_share,
            s.c0_students / NULLIF((s.b0_students + s.c0_students + s.d0_students + s.e0_students), 0) AS c0_share,
            s.d0_students / NULLIF((s.b0_students + s.c0_students + s.d0_students + s.e0_students), 0) AS d0_share,
            s.e0_students / NULLIF((s.b0_students + s.c0_students + s.d0_students + s.e0_students), 0) AS e0_share,
            CASE WHEN m.highclass >= 10 THEN 1 ELSE 0 END AS reaches_class10,
            CASE WHEN m.highclass >= 12 THEN 1 ELSE 0 END AS reaches_class12,
            CASE WHEN m.highclass < 10 THEN 1 ELSE 0 END AS ends_before_class10,
            CASE WHEN m.highclass < 12 THEN 1 ELSE 0 END AS ends_before_class12,
            CASE WHEN m.total_tch = 1 THEN 1 ELSE 0 END AS single_teacher,
            CASE WHEN m.total_tch > 0 AND COALESCE(m.female, 0) = 0 THEN 1 ELSE 0 END AS no_female_teacher,
            CASE WHEN m.total_tch > 0 AND
                (s.b0_students + s.c0_students + s.d0_students + s.e0_students) / m.total_tch > 30
                THEN 1 ELSE 0 END AS str_above_30,
            (s.b0_students + s.c0_students + s.d0_students + s.e0_students) / NULLIF(m.total_tch, 0) AS student_teacher_ratio,
            m.total_class_rooms * 100.0 / NULLIF((s.b0_students + s.c0_students + s.d0_students + s.e0_students), 0) AS classrooms_per_100,
            m.grants_receipt / NULLIF((s.b0_students + s.c0_students + s.d0_students + s.e0_students), 0) AS grant_per_student
        FROM school_master_base AS m
        INNER JOIN social_composition AS s USING (pseudocode)
        WHERE (s.b0_students + s.c0_students + s.d0_students + s.e0_students) > 0
        """
    )

    connection.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE group_school_long AS
        WITH groups AS (
            SELECT *, 'A0' AS group_code, 'Muslim' AS group_label,
                   a0_students AS group_students, a0_share AS group_share
            FROM national_analysis_base
            UNION ALL
            SELECT *, 'B0', 'General baseline', b0_students, b0_share
            FROM national_analysis_base
            UNION ALL
            SELECT *, 'C0', 'Scheduled Caste baseline', c0_students, c0_share
            FROM national_analysis_base
            UNION ALL
            SELECT *, 'D0', 'Scheduled Tribe baseline', d0_students, d0_share
            FROM national_analysis_base
            UNION ALL
            SELECT *, 'E0', 'Other Backward Class baseline', e0_students, e0_share
            FROM national_analysis_base
        )
        SELECT
            *,
            {band_case('group_share')} AS band_order
        FROM groups
        """
    )


def national_group_totals(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return query_dicts(
        connection,
        """
        SELECT
            group_code,
            group_label,
            SUM(group_students)::BIGINT AS students,
            SUM(total_students)::BIGINT AS repeated_total_students,
            SUM(group_students) * 100.0 / NULLIF(SUM(total_students), 0) AS national_share_percent,
            SUM((group_students > 0)::INTEGER)::BIGINT AS schools_with_group,
            COUNT(*)::BIGINT AS schools_in_analysis
        FROM group_school_long
        GROUP BY group_code, group_label
        ORDER BY group_code
        """,
    )


def stage_shares(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    stage_columns = {
        "Primary": "primary",
        "Upper primary": "upper_primary",
        "Secondary": "secondary",
        "Higher secondary": "higher_secondary",
    }
    rows: list[dict[str, Any]] = []
    for stage_order, (stage_label, _) in enumerate(STAGES):
        suffix = stage_columns[stage_label]
        query = f"""
            SELECT
                SUM(a0_{suffix}) AS a0,
                SUM(b0_{suffix}) AS b0,
                SUM(c0_{suffix}) AS c0,
                SUM(d0_{suffix}) AS d0,
                SUM(e0_{suffix}) AS e0
            FROM social_composition
        """
        values = connection.execute(query).fetchone()
        total = sum(int(values[index] or 0) for index in range(1, 5))
        for index, (group_code, group_label) in enumerate(GROUPS):
            students = int(values[index] or 0)
            rows.append(
                {
                    "stage_order": stage_order,
                    "stage": stage_label,
                    "group_code": group_code,
                    "group_label": group_label,
                    "students": students,
                    "share_percent": students * 100.0 / total if total else None,
                }
            )
    return rows


def concentration_distribution(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return query_dicts(
        connection,
        f"""
        SELECT
            group_code,
            group_label,
            band_order,
            {band_label_case('band_order')} AS band,
            COUNT(*)::BIGINT AS schools,
            SUM(group_students)::BIGINT AS group_students,
            SUM(total_students)::BIGINT AS total_students,
            COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY group_code) AS school_share_percent,
            SUM(group_students) * 100.0 /
                NULLIF(SUM(SUM(group_students)) OVER (PARTITION BY group_code), 0)
                AS group_student_share_percent
        FROM group_school_long
        GROUP BY group_code, group_label, band_order
        ORDER BY group_code, band_order
        """,
    )


def condition_gradients(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return query_dicts(
        connection,
        f"""
        SELECT
            group_code,
            group_label,
            band_order,
            {band_label_case('band_order')} AS band,
            COUNT(*)::BIGINT AS schools,
            SUM(group_students)::BIGINT AS group_students,
            AVG(reaches_class10) * 100.0 AS reaches_class10_percent,
            AVG(reaches_class12) * 100.0 AS reaches_class12_percent,
            AVG(single_teacher) * 100.0 AS single_teacher_percent,
            AVG(no_female_teacher) * 100.0 AS no_female_teacher_percent,
            AVG(str_above_30) * 100.0 AS str_above_30_percent,
            AVG(student_teacher_ratio) AS mean_student_teacher_ratio,
            MEDIAN(student_teacher_ratio) AS median_student_teacher_ratio,
            AVG(classrooms_per_100) AS mean_classrooms_per_100,
            SUM(total_class_rooms) * 100.0 / NULLIF(SUM(total_students), 0) AS student_weighted_classrooms_per_100,
            AVG(grant_per_student) AS mean_grant_per_student,
            SUM(grants_receipt) / NULLIF(SUM(total_students), 0) AS student_weighted_grant_per_student,
            AVG(acad_inspections) AS mean_academic_inspections
        FROM group_school_long
        GROUP BY group_code, group_label, band_order
        ORDER BY group_code, band_order
        """,
    )


def group_exposures(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    return query_dicts(
        connection,
        """
        SELECT
            group_code,
            group_label,
            SUM(group_students)::BIGINT AS students,
            SUM(group_students * ends_before_class10) * 100.0 / NULLIF(SUM(group_students), 0)
                AS exposure_ends_before_class10_percent,
            SUM(group_students * ends_before_class12) * 100.0 / NULLIF(SUM(group_students), 0)
                AS exposure_ends_before_class12_percent,
            SUM(group_students * single_teacher) * 100.0 / NULLIF(SUM(group_students), 0)
                AS exposure_single_teacher_percent,
            SUM(group_students * no_female_teacher) * 100.0 / NULLIF(SUM(group_students), 0)
                AS exposure_no_female_teacher_percent,
            SUM(group_students * str_above_30) * 100.0 / NULLIF(SUM(group_students), 0)
                AS exposure_str_above_30_percent,
            SUM(group_students * student_teacher_ratio) / NULLIF(SUM(group_students), 0)
                AS weighted_mean_student_teacher_ratio,
            SUM(group_students * classrooms_per_100) / NULLIF(SUM(group_students), 0)
                AS weighted_mean_classrooms_per_100,
            SUM(group_students * grant_per_student) / NULLIF(SUM(group_students), 0)
                AS weighted_mean_grant_per_student
        FROM group_school_long
        WHERE group_students > 0
        GROUP BY group_code, group_label
        ORDER BY group_code
        """,
    )


def a0_baseline_gaps(exposure_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_code = {row["group_code"]: row for row in exposure_rows}
    a0 = by_code["A0"]
    measures = [
        ("Schools ending before Class 10", "exposure_ends_before_class10_percent"),
        ("Schools ending before Class 12", "exposure_ends_before_class12_percent"),
        ("Single-teacher schools", "exposure_single_teacher_percent"),
        ("Schools with no female teacher", "exposure_no_female_teacher_percent"),
        ("Schools with STR above 30", "exposure_str_above_30_percent"),
    ]
    rows: list[dict[str, Any]] = []
    for baseline_code in ("B0", "C0", "D0", "E0"):
        baseline = by_code[baseline_code]
        for outcome, key in measures:
            rows.append(
                {
                    "baseline_code": baseline_code,
                    "baseline_label": baseline["group_label"],
                    "outcome": outcome,
                    "a0_percent": a0[key],
                    "baseline_percent": baseline[key],
                    "a0_minus_baseline_percentage_points": a0[key] - baseline[key],
                }
            )
    return rows


def setup_axes(ax: plt.Axes, title: str, ylabel: str) -> None:
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def save_stage_chart(rows: list[dict[str, Any]], output_path: Path) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["group_code"]].append(row)
    fig, ax = plt.subplots(figsize=(10, 6))
    for code, label in GROUPS:
        group_rows = sorted(grouped[code], key=lambda row: row["stage_order"])
        ax.plot(
            [row["stage"] for row in group_rows],
            [row["share_percent"] for row in group_rows],
            marker="o",
            linewidth=3.2 if code == "A0" else 1.4,
            alpha=1.0 if code == "A0" else 0.72,
            label=f"{code} {label}",
        )
    setup_axes(
        ax,
        "Muslim representation across school stages, with social-category baselines",
        "Share of enrolment (%)",
    )
    ax.set_xlabel("School stage")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_a0_distribution_chart(rows: list[dict[str, Any]], output_path: Path) -> None:
    a0_rows = sorted(
        [row for row in rows if row["group_code"] == "A0"],
        key=lambda row: row["band_order"],
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(
        [row["band"] for row in a0_rows],
        [row["group_student_share_percent"] for row in a0_rows],
        edgecolor="black",
        linewidth=0.7,
    )
    setup_axes(
        ax,
        "Where Muslim students are located across school concentration bands",
        "Share of all Muslim students (%)",
    )
    ax.set_xlabel("Muslim share of school enrolment")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_gradient_chart(
    rows: list[dict[str, Any]],
    measure: str,
    title: str,
    ylabel: str,
    output_path: Path,
) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["group_code"]].append(row)
    fig, ax = plt.subplots(figsize=(10, 6))
    for code, label in GROUPS:
        group_rows = sorted(grouped[code], key=lambda row: row["band_order"])
        ax.plot(
            [row["band"] for row in group_rows],
            [row[measure] for row in group_rows],
            marker="o",
            linewidth=3.2 if code == "A0" else 1.3,
            alpha=1.0 if code == "A0" else 0.68,
            label=f"{code} {label}",
        )
    setup_axes(ax, title, ylabel)
    ax.set_xlabel("Group share of school enrolment")
    ax.tick_params(axis="x", rotation=35)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_exposure_chart(
    rows: list[dict[str, Any]],
    measure: str,
    title: str,
    ylabel: str,
    output_path: Path,
) -> None:
    ordered = sorted(rows, key=lambda row: row["group_code"])
    fig, ax = plt.subplots(figsize=(9, 5.7))
    bars = ax.bar(
        [row["group_code"] for row in ordered],
        [row[measure] for row in ordered],
        edgecolor="black",
        linewidth=[1.8 if row["group_code"] == "A0" else 0.6 for row in ordered],
    )
    if bars:
        bars[0].set_hatch("//")
    setup_axes(ax, title, ylabel)
    ax.set_xlabel("A0 is the Muslim population; B0-E0 are comparison baselines")
    for bar, row in zip(bars, ordered, strict=True):
        value = row[measure]
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_gap_chart(rows: list[dict[str, Any]], output_path: Path) -> None:
    outcomes = list(dict.fromkeys(row["outcome"] for row in rows))
    baselines = ("B0", "C0", "D0", "E0")
    width = 0.19
    x_positions = list(range(len(outcomes)))
    fig, ax = plt.subplots(figsize=(12, 6))
    for baseline_index, baseline in enumerate(baselines):
        selected = [
            next(row for row in rows if row["baseline_code"] == baseline and row["outcome"] == outcome)
            for outcome in outcomes
        ]
        ax.bar(
            [position + (baseline_index - 1.5) * width for position in x_positions],
            [row["a0_minus_baseline_percentage_points"] for row in selected],
            width=width,
            label=f"A0 minus {baseline}",
        )
    ax.axhline(0, linewidth=1, color="black")
    setup_axes(
        ax,
        "Muslim student exposure gap relative to each baseline",
        "A0 minus baseline (percentage points)",
    )
    ax.set_xticks(x_positions)
    ax.set_xticklabels(outcomes, rotation=25, ha="right")
    ax.legend(frameon=False, ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def build_report(
    totals: list[dict[str, Any]],
    stage_rows: list[dict[str, Any]],
    exposures: list[dict[str, Any]],
) -> str:
    by_code = {row["group_code"]: row for row in exposures}
    total_by_code = {row["group_code"]: row for row in totals}
    a0 = by_code["A0"]
    a0_total = total_by_code["A0"]
    stage_a0 = sorted(
        [row for row in stage_rows if row["group_code"] == "A0"],
        key=lambda row: row["stage_order"],
    )
    lines = [
        "# First national A0-centred results",
        "",
        "## Purpose",
        "",
        "This first output tests whether Muslim students face patterns consistent with structural disadvantage in class access and teacher conditions. B0, C0, D0 and E0 appear only as comparison baselines.",
        "",
        "## Muslim population in the school data",
        "",
        f"Muslim enrolment in Classes 1-12: {int(a0_total['students']):,}.",
        f"Muslim share of reconciled Classes 1-12 enrolment: {a0_total['national_share_percent']:.2f}%.",
        f"Schools with at least one Muslim student: {int(a0_total['schools_with_group']):,}.",
        "",
        "## Muslim representation by stage",
        "",
        "| Stage | Muslim students | Muslim share of stage enrolment |",
        "|---|---:|---:|",
    ]
    for row in stage_a0:
        lines.append(
            f"| {row['stage']} | {int(row['students']):,} | {row['share_percent']:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Initial Muslim student exposure",
            "",
            "| Condition | A0 Muslim exposure |",
            "|---|---:|",
            f"| School ends before Class 10 | {a0['exposure_ends_before_class10_percent']:.2f}% |",
            f"| School ends before Class 12 | {a0['exposure_ends_before_class12_percent']:.2f}% |",
            f"| Single-teacher school | {a0['exposure_single_teacher_percent']:.2f}% |",
            f"| School with no female teacher | {a0['exposure_no_female_teacher_percent']:.2f}% |",
            f"| Student-teacher ratio above 30 | {a0['exposure_str_above_30_percent']:.2f}% |",
            "",
            "## Interpretation boundary",
            "",
            "These are national descriptive results. They establish exposure patterns but do not yet account for state, district, rural-urban location, management, class span or school size. The next analytical stages will add those comparisons before making a final claim about structural disenfranchisement.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = args.output
    tables_dir = output / "tables"
    figures_dir = output / "figures"
    work_dir = output / "work"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    database_path = download_database(args, work_dir)
    connection = duckdb.connect(str(database_path), read_only=True)
    connection.execute("PRAGMA threads=4")
    connection.execute("PRAGMA memory_limit='11GB'")
    connection.execute(f"PRAGMA temp_directory='{str(work_dir / 'duckdb_temp')}'")
    try:
        build_analysis_tables(connection)
        totals = national_group_totals(connection)
        stages = stage_shares(connection)
        distribution = concentration_distribution(connection)
        gradients = condition_gradients(connection)
        exposures = group_exposures(connection)
        gaps = a0_baseline_gaps(exposures)

        write_csv(tables_dir / "national_group_totals.csv", totals)
        write_csv(tables_dir / "national_group_stage_shares.csv", stages)
        write_csv(tables_dir / "national_concentration_distribution.csv", distribution)
        write_csv(tables_dir / "national_school_condition_gradients.csv", gradients)
        write_csv(tables_dir / "national_group_student_exposures.csv", exposures)
        write_csv(tables_dir / "national_a0_baseline_gaps.csv", gaps)

        save_stage_chart(stages, figures_dir / "01_a0_representation_by_stage.png")
        save_a0_distribution_chart(
            distribution,
            figures_dir / "02_a0_concentration_distribution.png",
        )

        gradient_specs = (
            (
                "reaches_class10_percent",
                "School access as Muslim concentration rises",
                "Schools reaching Class 10 (%)",
                "03_class10_access_gradient.png",
            ),
            (
                "reaches_class12_percent",
                "Higher-secondary access as Muslim concentration rises",
                "Schools reaching Class 12 (%)",
                "04_class12_access_gradient.png",
            ),
            (
                "mean_student_teacher_ratio",
                "Student-teacher ratio as Muslim concentration rises",
                "Mean students per teacher",
                "05_student_teacher_ratio_gradient.png",
            ),
            (
                "single_teacher_percent",
                "Single-teacher schools as Muslim concentration rises",
                "Single-teacher schools (%)",
                "06_single_teacher_gradient.png",
            ),
            (
                "no_female_teacher_percent",
                "Absence of female teachers as Muslim concentration rises",
                "Schools with no female teacher (%)",
                "07_no_female_teacher_gradient.png",
            ),
            (
                "student_weighted_classrooms_per_100",
                "Classroom availability as Muslim concentration rises",
                "Classrooms per 100 students",
                "08_classrooms_per_100_gradient.png",
            ),
        )
        for measure, title, ylabel, filename in gradient_specs:
            save_gradient_chart(
                gradients,
                measure,
                title,
                ylabel,
                figures_dir / filename,
            )

        exposure_specs = (
            (
                "exposure_ends_before_class10_percent",
                "Muslim exposure compared with baselines: schools ending before Class 10",
                "Students exposed (%)",
                "09_exposure_before_class10.png",
            ),
            (
                "exposure_ends_before_class12_percent",
                "Muslim exposure compared with baselines: schools ending before Class 12",
                "Students exposed (%)",
                "10_exposure_before_class12.png",
            ),
            (
                "exposure_single_teacher_percent",
                "Muslim exposure compared with baselines: single-teacher schools",
                "Students exposed (%)",
                "11_exposure_single_teacher.png",
            ),
            (
                "exposure_no_female_teacher_percent",
                "Muslim exposure compared with baselines: no female teacher",
                "Students exposed (%)",
                "12_exposure_no_female_teacher.png",
            ),
            (
                "exposure_str_above_30_percent",
                "Muslim exposure compared with baselines: student-teacher ratio above 30",
                "Students exposed (%)",
                "13_exposure_str_above_30.png",
            ),
        )
        for measure, title, ylabel, filename in exposure_specs:
            save_exposure_chart(
                exposures,
                measure,
                title,
                ylabel,
                figures_dir / filename,
            )

        save_gap_chart(gaps, figures_dir / "14_a0_baseline_exposure_gaps.png")

        report = build_report(totals, stages, exposures)
        (output / "national_a0_report.md").write_text(report, encoding="utf-8")
        if summary_path := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary_path).open("a", encoding="utf-8") as handle:
                handle.write(report)
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
