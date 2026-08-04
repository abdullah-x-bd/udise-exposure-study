from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import textwrap
from pathlib import Path
from typing import Any

import duckdb
import matplotlib.pyplot as plt
from huggingface_hub import hf_hub_download

from udise.refined_state_accountability_a0_analysis import base as accountability

REMOTE_CHECKPOINT = "processed/2024_25/analysis/school_indicator_base.parquet"
BUNDLES = accountability.BUNDLES
BANDS = accountability.BANDS
GROUPS = (("A0", "Muslim"), ("B0", "General baseline"))
SCOPES = {
    "state_local_government": accountability.SCOPES["state_local_government"],
    "all_recognised": accountability.SCOPES["all_recognised"],
}
GEOGRAPHIES = (
    ("NATIONAL", "National", "TRUE"),
    ("BIHAR", "Bihar", "state='BIHAR'"),
    ("UTTAR PRADESH", "Uttar Pradesh", "state='UTTAR PRADESH'"),
    ("JHARKHAND", "Jharkhand", "state='JHARKHAND'"),
    ("UTTARAKHAND", "Uttarakhand", "state='UTTARAKHAND'"),
    ("ASSAM", "Assam", "state='ASSAM'"),
)


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/a0_b0_accountability_gradients")
    )
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


def checkpoint(options: argparse.Namespace, work: Path) -> Path:
    if options.school_indicator_path:
        return options.school_indicator_path
    if not options.dataset_repo or not options.token:
        raise RuntimeError("HF_DATASET_REPO and HF_TOKEN are required")
    return Path(
        hf_hub_download(
            repo_id=options.dataset_repo,
            filename=REMOTE_CHECKPOINT,
            repo_type="dataset",
            token=options.token,
            local_dir=work,
        )
    )


def band_case(share: str) -> str:
    return (
        f"CASE WHEN {share}=0 THEN 0 WHEN {share}<=0.05 THEN 1 "
        f"WHEN {share}<=0.10 THEN 2 WHEN {share}<=0.20 THEN 3 "
        f"WHEN {share}<=0.30 THEN 4 WHEN {share}<=0.40 THEN 5 "
        f"WHEN {share}<=0.50 THEN 6 WHEN {share}<=0.75 THEN 7 ELSE 8 END"
    )


def flag(components: tuple[str, ...]) -> str:
    observed = " AND ".join(f"{component} IS NOT NULL" for component in components)
    adverse = " AND ".join(f"{component}=1" for component in components)
    return f"CASE WHEN {observed} THEN CASE WHEN {adverse} THEN 1 ELSE 0 END ELSE NULL END"


def calculate_gradients(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scope, scope_filter in SCOPES.items():
        for geography_code, geography_label, geography_filter in GEOGRAPHIES:
            for group_code, group_label in GROUPS:
                prefix = group_code.lower()
                terms: list[str] = []
                for code, _, components, weight_kind, _ in BUNDLES:
                    condition = flag(components)
                    weight = f"{prefix}_{weight_kind}"
                    terms.extend(
                        [
                            f"AVG({condition}) AS {code}__school",
                            f"SUM(CASE WHEN ({condition})=1 THEN {weight} ELSE 0 END)"
                            f"/NULLIF(SUM(CASE WHEN ({condition}) IS NOT NULL THEN {weight} ELSE 0 END),0) "
                            f"AS {code}__weighted",
                            f"SUM(CASE WHEN ({condition}) IS NOT NULL THEN {weight} ELSE 0 END) "
                            f"AS {code}__eligible_weight",
                            f"SUM(CASE WHEN ({condition})=1 THEN {weight} ELSE 0 END) "
                            f"AS {code}__affected_weight",
                            f"SUM(CASE WHEN ({condition}) IS NOT NULL THEN 1 ELSE 0 END) "
                            f"AS {code}__eligible_schools",
                        ]
                    )
                records = query(
                    connection,
                    f"""
                    SELECT {band_case(f'{prefix}_share')} AS band_order,
                           COUNT(*) AS schools,
                           SUM({prefix}_students) AS group_students,
                           {','.join(terms)}
                    FROM school_indicator_base
                    WHERE {scope_filter} AND {geography_filter}
                      AND {prefix}_share IS NOT NULL
                    GROUP BY band_order
                    ORDER BY band_order
                    """,
                )
                for record in records:
                    order = int(record["band_order"])
                    for code, label, components, weight_kind, mechanism in BUNDLES:
                        for estimand, suffix in (
                            ("equal-school prevalence", "school"),
                            ("group-student-weighted exposure", "weighted"),
                        ):
                            value = record.get(f"{code}__{suffix}")
                            rows.append(
                                {
                                    "management_scope": scope,
                                    "geography_code": geography_code,
                                    "geography_label": geography_label,
                                    "group_code": group_code,
                                    "group_label": group_label,
                                    "band_order": order,
                                    "band": BANDS[order],
                                    "schools": record["schools"],
                                    "group_students": record["group_students"],
                                    "estimand": estimand,
                                    "bundle_code": code,
                                    "bundle_label": label,
                                    "mechanism": mechanism,
                                    "components": "|".join(components),
                                    "weight_type": weight_kind,
                                    "exposure_percent": (
                                        value * 100
                                        if value is not None and math.isfinite(value)
                                        else None
                                    ),
                                    "eligible_weight": record.get(
                                        f"{code}__eligible_weight"
                                    ),
                                    "affected_weight": record.get(
                                        f"{code}__affected_weight"
                                    ),
                                    "eligible_schools": record.get(
                                        f"{code}__eligible_schools"
                                    ),
                                }
                            )
    return rows


def calculate_contrasts(gradients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {
        (
            row["management_scope"],
            row["geography_code"],
            row["estimand"],
            row["bundle_code"],
            row["group_code"],
            row["band_order"],
        ): row
        for row in gradients
    }
    rows: list[dict[str, Any]] = []
    for scope in SCOPES:
        for geography_code, geography_label, _ in GEOGRAPHIES:
            for estimand in (
                "equal-school prevalence",
                "group-student-weighted exposure",
            ):
                for code, label, components, weight_kind, mechanism in BUNDLES:
                    for order in range(9):
                        a0 = lookup.get(
                            (scope, geography_code, estimand, code, "A0", order)
                        )
                        b0 = lookup.get(
                            (scope, geography_code, estimand, code, "B0", order)
                        )
                        a0_value = a0.get("exposure_percent") if a0 else None
                        b0_value = b0.get("exposure_percent") if b0 else None
                        rows.append(
                            {
                                "management_scope": scope,
                                "geography_code": geography_code,
                                "geography_label": geography_label,
                                "estimand": estimand,
                                "bundle_code": code,
                                "bundle_label": label,
                                "mechanism": mechanism,
                                "components": "|".join(components),
                                "weight_type": weight_kind,
                                "band_order": order,
                                "band": BANDS[order],
                                "a0_percent": a0_value,
                                "b0_percent": b0_value,
                                "a0_minus_b0_pp": (
                                    a0_value - b0_value
                                    if a0_value is not None and b0_value is not None
                                    else None
                                ),
                                "a0_eligible_weight": a0.get("eligible_weight")
                                if a0
                                else None,
                                "b0_eligible_weight": b0.get("eligible_weight")
                                if b0
                                else None,
                                "a0_eligible_schools": a0.get("eligible_schools")
                                if a0
                                else None,
                                "b0_eligible_schools": b0.get("eligible_schools")
                                if b0
                                else None,
                            }
                        )
    return rows


def calculate_summaries(contrasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {
        (
            row["management_scope"],
            row["geography_code"],
            row["estimand"],
            row["bundle_code"],
            row["band_order"],
        ): row
        for row in contrasts
    }
    rows: list[dict[str, Any]] = []
    for scope in SCOPES:
        for geography_code, geography_label, _ in GEOGRAPHIES:
            for estimand in (
                "equal-school prevalence",
                "group-student-weighted exposure",
            ):
                for code, label, components, weight_kind, mechanism in BUNDLES:
                    low_order = 0 if estimand == "equal-school prevalence" else 1
                    low = lookup.get(
                        (scope, geography_code, estimand, code, low_order), {}
                    )
                    high = lookup.get(
                        (scope, geography_code, estimand, code, 8), {}
                    )
                    a0_low = low.get("a0_percent")
                    b0_low = low.get("b0_percent")
                    a0_high = high.get("a0_percent")
                    b0_high = high.get("b0_percent")
                    a0_change = (
                        a0_high - a0_low
                        if a0_high is not None and a0_low is not None
                        else None
                    )
                    b0_change = (
                        b0_high - b0_low
                        if b0_high is not None and b0_low is not None
                        else None
                    )
                    rows.append(
                        {
                            "management_scope": scope,
                            "geography_code": geography_code,
                            "geography_label": geography_label,
                            "estimand": estimand,
                            "bundle_code": code,
                            "bundle_label": label,
                            "mechanism": mechanism,
                            "components": "|".join(components),
                            "weight_type": weight_kind,
                            "low_band": BANDS[low_order],
                            "a0_low_percent": a0_low,
                            "b0_low_percent": b0_low,
                            "a0_high_percent": a0_high,
                            "b0_high_percent": b0_high,
                            "high_concentration_gap_pp": (
                                a0_high - b0_high
                                if a0_high is not None and b0_high is not None
                                else None
                            ),
                            "a0_change_pp": a0_change,
                            "b0_change_pp": b0_change,
                            "gradient_difference_pp": (
                                a0_change - b0_change
                                if a0_change is not None and b0_change is not None
                                else None
                            ),
                            "a0_high_eligible_weight": high.get(
                                "a0_eligible_weight"
                            ),
                            "b0_high_eligible_weight": high.get(
                                "b0_eligible_weight"
                            ),
                            "a0_high_eligible_schools": high.get(
                                "a0_eligible_schools"
                            ),
                            "b0_high_eligible_schools": high.get(
                                "b0_eligible_schools"
                            ),
                        }
                    )
    return rows


def safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value.lower()).strip("_")


def line_chart(
    rows: list[dict[str, Any]],
    path: Path,
    title: str,
    ylabel: str,
    start_order: int,
) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    for group_code, group_label in GROUPS:
        group_rows = sorted(
            [
                row
                for row in rows
                if row["group_code"] == group_code
                and row["band_order"] >= start_order
                and row["exposure_percent"] is not None
            ],
            key=lambda row: row["band_order"],
        )
        if group_rows:
            ax.plot(
                [row["band_order"] for row in group_rows],
                [row["exposure_percent"] for row in group_rows],
                marker="o",
                linewidth=2,
                label=f"{group_code} {group_label}",
            )
    orders = list(range(start_order, 9))
    ax.set_xticks(orders)
    ax.set_xticklabels([BANDS[order] for order in orders], rotation=35, ha="right")
    ax.set_xlabel("Own-group enrolment share in school")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def gap_chart(rows: list[dict[str, Any]], path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    for estimand, label, start_order in (
        ("equal-school prevalence", "Equal-school gap", 0),
        ("group-student-weighted exposure", "Student-weighted gap", 1),
    ):
        series = sorted(
            [
                row
                for row in rows
                if row["estimand"] == estimand
                and row["band_order"] >= start_order
                and row["a0_minus_b0_pp"] is not None
            ],
            key=lambda row: row["band_order"],
        )
        if series:
            ax.plot(
                [row["band_order"] for row in series],
                [row["a0_minus_b0_pp"] for row in series],
                marker="o",
                linewidth=2,
                label=label,
            )
    ax.axhline(0, linewidth=1)
    ax.set_xticks(range(9))
    ax.set_xticklabels([BANDS[order] for order in range(9)], rotation=35, ha="right")
    ax.set_xlabel("Matched own-group enrolment-share band")
    ax.set_ylabel("A0 minus B0 exposure, percentage points")
    ax.set_title(title)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def ranked_chart(
    rows: list[dict[str, Any]],
    value_key: str,
    path: Path,
    title: str,
    xlabel: str,
) -> None:
    valid = [
        row
        for row in rows
        if row.get(value_key) is not None
        and (row.get("a0_high_eligible_weight") or 0) >= 10_000
        and (row.get("b0_high_eligible_weight") or 0) >= 10_000
        and (row.get("a0_high_eligible_schools") or 0) >= 25
        and (row.get("b0_high_eligible_schools") or 0) >= 25
    ]
    selected = sorted(valid, key=lambda row: row[value_key], reverse=True)[:15]
    if not selected:
        return
    labels = ["\n".join(textwrap.wrap(row["bundle_label"], 46)) for row in selected]
    values = [row[value_key] for row in selected]
    fig, ax = plt.subplots(figsize=(12, 9))
    ax.barh(labels[::-1], values[::-1])
    ax.axvline(0, linewidth=1)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def create_figures(
    gradients: list[dict[str, Any]],
    contrasts: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    figures: Path,
) -> int:
    count = 0
    main_scope = "state_local_government"
    for geography_code, geography_label, _ in GEOGRAPHIES:
        geography_dir = figures / safe_name(geography_code)
        geography_gradients = [
            row
            for row in gradients
            if row["management_scope"] == main_scope
            and row["geography_code"] == geography_code
        ]
        geography_contrasts = [
            row
            for row in contrasts
            if row["management_scope"] == main_scope
            and row["geography_code"] == geography_code
        ]
        geography_summaries = [
            row
            for row in summaries
            if row["management_scope"] == main_scope
            and row["geography_code"] == geography_code
            and row["estimand"] == "group-student-weighted exposure"
        ]
        for code, label, _, _, mechanism in BUNDLES:
            bundle_gradients = [
                row for row in geography_gradients if row["bundle_code"] == code
            ]
            equal_rows = [
                row
                for row in bundle_gradients
                if row["estimand"] == "equal-school prevalence"
            ]
            weighted_rows = [
                row
                for row in bundle_gradients
                if row["estimand"] == "group-student-weighted exposure"
            ]
            line_chart(
                equal_rows,
                geography_dir / "equal_school" / f"{code}.png",
                f"{geography_label}: {label}, A0 versus B0",
                "Share of schools with simultaneous failure (%)",
                0,
            )
            count += 1
            line_chart(
                weighted_rows,
                geography_dir / "student_weighted" / f"{code}.png",
                f"{geography_label}: student exposure to {label}, A0 versus B0",
                "Group-student-weighted exposure (%)",
                1,
            )
            count += 1
            gap_chart(
                [row for row in geography_contrasts if row["bundle_code"] == code],
                geography_dir / "a0_b0_gap" / f"{code}.png",
                f"{geography_label}: A0 minus B0 gap for {label}",
            )
            count += 1
        ranked_chart(
            geography_summaries,
            "high_concentration_gap_pp",
            geography_dir / "summary" / "largest_high_concentration_gaps.png",
            f"{geography_label}: largest A0-B0 gaps above 75% concentration",
            "A0 minus B0 exposure, percentage points",
        )
        count += 1
        ranked_chart(
            geography_summaries,
            "gradient_difference_pp",
            geography_dir / "summary" / "largest_gradient_divergence.png",
            f"{geography_label}: largest A0-B0 concentration-gradient divergence",
            "A0 change minus B0 change, percentage points",
        )
        count += 1
    return count


def report(summaries: list[dict[str, Any]], figure_count: int) -> str:
    main = [
        row
        for row in summaries
        if row["management_scope"] == "state_local_government"
        and row["estimand"] == "group-student-weighted exposure"
        and row["high_concentration_gap_pp"] is not None
        and row["gradient_difference_pp"] is not None
        and (row["a0_high_eligible_weight"] or 0) >= 10_000
        and (row["b0_high_eligible_weight"] or 0) >= 10_000
        and (row["a0_high_eligible_schools"] or 0) >= 25
        and (row["b0_high_eligible_schools"] or 0) >= 25
    ]
    lines = [
        "# A0 versus B0 public-school accountability gradients",
        "",
        "The main figures compare A0 Muslim and B0 General-baseline concentration bands inside state and local-government-managed schools. Equal-school graphs run from 0% to above 75%. Student-weighted graphs begin at above 0-5%, because a zero-share school has no same-group students to weight.",
        "",
        f"Accountability combinations: {len(BUNDLES)}.",
        f"Figures created: {figure_count}.",
        "",
    ]
    for geography_code, geography_label, _ in GEOGRAPHIES:
        rows = [row for row in main if row["geography_code"] == geography_code]
        ranked = sorted(
            rows,
            key=lambda row: (
                row["high_concentration_gap_pp"],
                row["gradient_difference_pp"],
            ),
            reverse=True,
        )[:10]
        lines.extend(
            [
                f"## {geography_label}",
                "",
                "| Compound accountability failure | A0 above 75% | B0 above 75% | Gap pp | A0 change pp | B0 change pp | Gradient difference pp |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in ranked:
            lines.append(
                f"| {row['bundle_label']} | {row['a0_high_percent']:.2f} | "
                f"{row['b0_high_percent']:.2f} | {row['high_concentration_gap_pp']:.2f} | "
                f"{row['a0_change_pp']:.2f} | {row['b0_change_pp']:.2f} | "
                f"{row['gradient_difference_pp']:.2f} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation boundary",
            "",
            "The A0 and B0 lines use each group's own concentration share. These are matched concentration-band comparisons, not mutually exclusive individual populations and not a longitudinal causal difference-in-differences design. The public-school restriction strengthens state-accountability interpretation, but budget histories and local supply remain unobserved.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    options = args()
    output = options.output
    work = output / "work"
    work.mkdir(parents=True, exist_ok=True)
    try:
        parquet = checkpoint(options, work)
        temp = work / "duckdb_temp"
        temp.mkdir(exist_ok=True)
        connection = duckdb.connect(str(work / "analysis.duckdb"))
        connection.execute("SET threads=2")
        connection.execute("SET memory_limit='4GB'")
        connection.execute("SET preserve_insertion_order=false")
        connection.execute(f"SET temp_directory={sql_string(str(temp))}")
        connection.execute(
            "CREATE VIEW school_indicator_base AS SELECT * FROM read_parquet("
            + sql_string(str(parquet))
            + ")"
        )
        try:
            gradients = calculate_gradients(connection)
        finally:
            connection.close()
        contrasts = calculate_contrasts(gradients)
        summaries = calculate_summaries(contrasts)
        tables = output / "tables"
        write_csv(tables / "a0_b0_concentration_gradients.csv", gradients)
        write_csv(tables / "a0_b0_matched_band_contrasts.csv", contrasts)
        write_csv(tables / "a0_b0_gradient_summaries.csv", summaries)
        figure_count = create_figures(
            gradients, contrasts, summaries, output / "figures"
        )
        (output / "a0_b0_accountability_report.md").write_text(
            report(summaries, figure_count), encoding="utf-8"
        )
        (output / "analysis_manifest.json").write_text(
            json.dumps(
                {
                    "geographies": [item[0] for item in GEOGRAPHIES],
                    "management_scopes": list(SCOPES),
                    "groups": [item[0] for item in GROUPS],
                    "bands": BANDS,
                    "bundle_count": len(BUNDLES),
                    "gradient_rows": len(gradients),
                    "contrast_rows": len(contrasts),
                    "summary_rows": len(summaries),
                    "figure_count": figure_count,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
