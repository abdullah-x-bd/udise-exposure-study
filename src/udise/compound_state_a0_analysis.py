from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

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


@dataclass(frozen=True)
class Condition:
    code: str
    label: str
    domain: str
    girls_weighted: bool = False


@dataclass(frozen=True)
class Combination:
    code: str
    label: str
    members: tuple[Condition, ...]
    combination_type: str

    @property
    def girls_weighted(self) -> bool:
        return any(member.girls_weighted for member in self.members)

    @property
    def domains(self) -> str:
        return " + ".join(dict.fromkeys(member.domain for member in self.members))


CONDITIONS = (
    Condition("ends_before_class12", "School ends before Class 12", "Access"),
    Condition("str_above_30", "Student-teacher ratio above 30", "Crowding"),
    Condition("no_library", "No library", "Learning resources"),
    Condition("no_reading_corner", "No reading corner", "Learning resources"),
    Condition("no_internet", "No internet access", "Digital resources"),
    Condition("no_core_digital_device", "No laptop, tablet or desktop", "Digital resources"),
    Condition("no_primary_teacher", "No primary-grade teacher", "Teacher capacity"),
    Condition("no_female_teacher", "No female teacher", "Gendered teacher capacity", True),
    Condition("no_functional_girls_toilet", "No functional girls' toilet", "Gendered WASH", True),
    Condition("no_functional_electricity", "No functional electricity", "Basic infrastructure"),
    Condition("no_functional_water_source", "No functional drinking-water source", "Basic infrastructure"),
    Condition("any_major_repair", "At least one classroom needs major repair", "Building condition"),
)
CONDITION_LOOKUP = {condition.code: condition for condition in CONDITIONS}
PREDEFINED_BUNDLES = (
    ("access_crowding_learning", ("ends_before_class12", "str_above_30", "no_library")),
    ("access_crowding_digital", ("ends_before_class12", "str_above_30", "no_internet")),
    ("access_crowding_device", ("ends_before_class12", "str_above_30", "no_core_digital_device")),
    ("access_learning_digital", ("ends_before_class12", "no_library", "no_internet")),
    ("complete_learning_digital_exclusion", ("no_library", "no_reading_corner", "no_internet", "no_core_digital_device")),
    ("gendered_access_capacity", ("ends_before_class12", "str_above_30", "no_female_teacher")),
    ("gendered_resource_exclusion", ("no_female_teacher", "no_functional_girls_toilet", "no_library", "no_internet")),
    ("basic_infrastructure_failure", ("no_functional_electricity", "no_functional_water_source", "any_major_repair")),
    ("total_institutional_exclusion", ("ends_before_class12", "str_above_30", "no_library", "no_internet", "no_female_teacher")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/compound_state_a0"))
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


def combinations() -> tuple[Combination, ...]:
    output: list[Combination] = []
    seen: set[tuple[str, ...]] = set()
    for size in (2, 3):
        for members in itertools.combinations(CONDITIONS, size):
            member_codes = tuple(sorted(member.code for member in members))
            seen.add(member_codes)
            output.append(Combination(
                code="__and__".join(member_codes),
                label=" AND ".join(member.label for member in members),
                members=members,
                combination_type=f"all {size}-condition intersections",
            ))
    for bundle_code, codes in PREDEFINED_BUNDLES:
        members = tuple(CONDITION_LOOKUP[code] for code in codes)
        member_codes = tuple(sorted(codes))
        if member_codes in seen:
            continue
        seen.add(member_codes)
        output.append(Combination(
            code=bundle_code,
            label=" AND ".join(member.label for member in members),
            members=members,
            combination_type="predefined structural bundle",
        ))
    return tuple(output)


def combo_expression(item: Combination) -> str:
    missing = " OR ".join(f"{member.code} IS NULL" for member in item.members)
    all_true = " AND ".join(f"{member.code}=1" for member in item.members)
    return f"CASE WHEN {missing} THEN NULL WHEN {all_true} THEN 1 ELSE 0 END"


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


def combination_catalog(items: Iterable[Combination]) -> list[dict[str, Any]]:
    return [{
        "combination_code": item.code,
        "combination_label": item.label,
        "combination_size": len(item.members),
        "combination_type": item.combination_type,
        "domains": item.domains,
        "member_codes": " | ".join(member.code for member in item.members),
        "weighting": "group girls" if item.girls_weighted else "group students",
    } for item in items]


def exposure_terms(prefix: str, items: tuple[Combination, ...]) -> str:
    terms: list[str] = []
    for index, item in enumerate(items):
        weight = f"{prefix}_girls" if item.girls_weighted else f"{prefix}_students"
        expression = combo_expression(item)
        terms.extend((
            f"SUM(CASE WHEN ({expression}) IS NOT NULL THEN {weight}*({expression}) ELSE 0 END) AS c{index}__affected",
            f"SUM(CASE WHEN ({expression}) IS NOT NULL THEN {weight} ELSE 0 END) AS c{index}__eligible",
            f"COUNT(*) FILTER (WHERE ({expression})=1) AS c{index}__schools_affected",
            f"COUNT(*) FILTER (WHERE ({expression}) IS NOT NULL) AS c{index}__schools_eligible",
        ))
    return ",".join(terms)


def unpack_wide(
    wide: list[dict[str, Any]],
    items: tuple[Combination, ...],
    group_code: str,
    group_label: str,
    *,
    banded: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in wide:
        for index, item in enumerate(items):
            affected = record.get(f"c{index}__affected")
            eligible = record.get(f"c{index}__eligible")
            exposure = affected / eligible if eligible not in (None, 0) else None
            row = {
                "state": record["state"],
                "group_code": group_code,
                "group_label": group_label,
                "combination_code": item.code,
                "combination_label": item.label,
                "combination_size": len(item.members),
                "combination_type": item.combination_type,
                "domains": item.domains,
                "weighting": "group girls" if item.girls_weighted else "group students",
                "affected_weight": affected,
                "eligible_weight": eligible,
                "exposure_share": exposure,
                "exposure_percent": exposure * 100 if exposure is not None and math.isfinite(exposure) else None,
                "schools_affected": record.get(f"c{index}__schools_affected"),
                "schools_eligible": record.get(f"c{index}__schools_eligible"),
            }
            if banded:
                order = int(record["band_order"])
                row.update({
                    "band_order": order,
                    "band": BANDS[order],
                    "group_students_in_band": record["group_students"],
                    "group_girls_in_band": record["group_girls"],
                })
            rows.append(row)
    return rows


def calculate_exposures(
    connection: duckdb.DuckDBPyConnection,
    items: tuple[Combination, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    state_rows: list[dict[str, Any]] = []
    band_rows: list[dict[str, Any]] = []
    states = ",".join(sql_string(state) for state in TOP_STATES)
    for group_code, group_label in GROUPS:
        prefix = group_code.lower()
        terms = exposure_terms(prefix, items)
        statewide = query(connection, f"""
            SELECT state,{terms}
            FROM school_indicator_base
            WHERE state IN ({states})
            GROUP BY state ORDER BY state
        """)
        state_rows.extend(unpack_wide(statewide, items, group_code, group_label, banded=False))
        banded = query(connection, f"""
            SELECT state,{band_case(f'{prefix}_share')} AS band_order,
                   SUM({prefix}_students) AS group_students,
                   SUM({prefix}_girls) AS group_girls,{terms}
            FROM school_indicator_base
            WHERE state IN ({states}) AND {prefix}_share IS NOT NULL
            GROUP BY state,band_order ORDER BY state,band_order
        """)
        band_rows.extend(unpack_wide(banded, items, group_code, group_label, banded=True))
    return state_rows, band_rows


def contrasts(
    state_rows: list[dict[str, Any]],
    band_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    state_lookup = {(row["state"], row["group_code"], row["combination_code"]): row for row in state_rows}
    band_lookup = {(row["state"], row["group_code"], row["combination_code"], row["band_order"]): row for row in band_rows}
    rows: list[dict[str, Any]] = []
    for state in TOP_STATES:
        for item in combinations():
            a0_state = state_lookup[(state, "A0", item.code)]
            a0_low = band_lookup.get((state, "A0", item.code, 1))
            a0_high = band_lookup.get((state, "A0", item.code, 8))
            for baseline_code, baseline_label in GROUPS[1:]:
                base_state = state_lookup[(state, baseline_code, item.code)]
                base_low = band_lookup.get((state, baseline_code, item.code, 1))
                base_high = band_lookup.get((state, baseline_code, item.code, 8))
                a0_change = None
                base_change = None
                if a0_low and a0_high and a0_low["exposure_percent"] is not None and a0_high["exposure_percent"] is not None:
                    a0_change = a0_high["exposure_percent"] - a0_low["exposure_percent"]
                if base_low and base_high and base_low["exposure_percent"] is not None and base_high["exposure_percent"] is not None:
                    base_change = base_high["exposure_percent"] - base_low["exposure_percent"]
                rows.append({
                    "state": state,
                    "baseline_code": baseline_code,
                    "baseline_label": baseline_label,
                    "combination_code": item.code,
                    "combination_label": item.label,
                    "combination_size": len(item.members),
                    "combination_type": item.combination_type,
                    "domains": item.domains,
                    "weighting": "group girls" if item.girls_weighted else "group students",
                    "a0_statewide_exposure_percent": a0_state["exposure_percent"],
                    "baseline_statewide_exposure_percent": base_state["exposure_percent"],
                    "statewide_a0_minus_baseline_pp": subtract(a0_state["exposure_percent"], base_state["exposure_percent"]),
                    "a0_low_exposure_percent": a0_low["exposure_percent"] if a0_low else None,
                    "a0_high_exposure_percent": a0_high["exposure_percent"] if a0_high else None,
                    "a0_high_minus_low_pp": a0_change,
                    "baseline_low_exposure_percent": base_low["exposure_percent"] if base_low else None,
                    "baseline_high_exposure_percent": base_high["exposure_percent"] if base_high else None,
                    "baseline_high_minus_low_pp": base_change,
                    "high_band_a0_minus_baseline_pp": subtract(
                        a0_high["exposure_percent"] if a0_high else None,
                        base_high["exposure_percent"] if base_high else None,
                    ),
                    "difference_in_differences_pp": subtract(a0_change, base_change),
                    "a0_high_eligible_weight": a0_high["eligible_weight"] if a0_high else None,
                    "baseline_high_eligible_weight": base_high["eligible_weight"] if base_high else None,
                    "a0_high_schools_eligible": a0_high["schools_eligible"] if a0_high else None,
                    "baseline_high_schools_eligible": base_high["schools_eligible"] if base_high else None,
                })
    return rows


def subtract(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def robust_rankings(contrast_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in contrast_rows:
        grouped.setdefault((row["state"], row["combination_code"]), []).append(row)
    output: list[dict[str, Any]] = []
    for (state, combination_code), rows in grouped.items():
        high_gaps = [row["high_band_a0_minus_baseline_pp"] for row in rows]
        dids = [row["difference_in_differences_pp"] for row in rows]
        first = rows[0]
        valid = all(value is not None and math.isfinite(value) for value in high_gaps + dids)
        adequate = all(
            (row["a0_high_eligible_weight"] or 0) >= 10_000
            and (row["baseline_high_eligible_weight"] or 0) >= 10_000
            and (row["a0_high_schools_eligible"] or 0) >= 25
            and (row["baseline_high_schools_eligible"] or 0) >= 25
            for row in rows
        )
        output.append({
            "state": state,
            "combination_code": combination_code,
            "combination_label": first["combination_label"],
            "combination_size": first["combination_size"],
            "combination_type": first["combination_type"],
            "domains": first["domains"],
            "weighting": first["weighting"],
            "a0_high_exposure_percent": first["a0_high_exposure_percent"],
            "a0_high_minus_low_pp": first["a0_high_minus_low_pp"],
            "minimum_high_gap_across_baselines_pp": min(high_gaps) if valid else None,
            "mean_high_gap_across_baselines_pp": sum(high_gaps) / len(high_gaps) if valid else None,
            "minimum_did_across_baselines_pp": min(dids) if valid else None,
            "mean_did_across_baselines_pp": sum(dids) / len(dids) if valid else None,
            "a0_worse_than_all_baselines_at_high_concentration": valid and min(high_gaps) > 0,
            "a0_gradient_steeper_than_all_baselines": valid and min(dids) > 0,
            "adequate_cell_size": adequate,
        })
    output.sort(key=lambda row: (
        bool(row["adequate_cell_size"]),
        bool(row["a0_worse_than_all_baselines_at_high_concentration"]),
        bool(row["a0_gradient_steeper_than_all_baselines"]),
        row["minimum_high_gap_across_baselines_pp"] if row["minimum_high_gap_across_baselines_pp"] is not None else -math.inf,
        row["minimum_did_across_baselines_pp"] if row["minimum_did_across_baselines_pp"] is not None else -math.inf,
    ), reverse=True)
    for rank, row in enumerate(output, start=1):
        row["robust_rank"] = rank
    return output


def report(
    output: Path,
    items: tuple[Combination, ...],
    contrast_rows: list[dict[str, Any]],
    rankings: list[dict[str, Any]],
) -> None:
    adequate = [row for row in contrast_rows if
                (row["a0_high_eligible_weight"] or 0) >= 10_000
                and (row["baseline_high_eligible_weight"] or 0) >= 10_000
                and (row["a0_high_schools_eligible"] or 0) >= 25
                and (row["baseline_high_schools_eligible"] or 0) >= 25]
    top_high = sorted(
        (row for row in adequate if row["high_band_a0_minus_baseline_pp"] is not None),
        key=lambda row: row["high_band_a0_minus_baseline_pp"], reverse=True,
    )[:25]
    top_did = sorted(
        (row for row in adequate if row["difference_in_differences_pp"] is not None),
        key=lambda row: row["difference_in_differences_pp"], reverse=True,
    )[:25]
    robust = [row for row in rankings if row["adequate_cell_size"]
              and row["a0_worse_than_all_baselines_at_high_concentration"]
              and row["a0_gradient_steeper_than_all_baselines"]][:25]
    lines = [
        "# Compound state A0 deprivation analysis", "",
        f"Combinations evaluated: {len(items)}.",
        "All two-condition and three-condition intersections are evaluated, plus non-duplicative predefined four- and five-condition structural bundles.",
        "A combination counts only when every component condition is observed and every component is adverse in the same school.",
        "Combinations containing the no-female-teacher or no-functional-girls-toilet condition are weighted by group girls. All others are weighted by group students.", "",
        "## Largest high-concentration A0-baseline gaps", "",
        "| State | Baseline | Combination | A0 above 75% | Baseline above 75% | Gap pp |", "|---|---|---|---:|---:|---:|",
    ]
    for row in top_high:
        lines.append(f"| {row['state'].title()} | {row['baseline_code']} | {row['combination_label']} | {row['a0_high_exposure_percent']:.2f} | {row['baseline_high_exposure_percent']:.2f} | {row['high_band_a0_minus_baseline_pp']:.2f} |")
    lines += ["", "## Largest concentration difference-in-differences", "",
              "Difference-in-differences equals the A0 change from above 0-5% to above 75%, minus the same concentration change for the baseline group.", "",
              "| State | Baseline | Combination | A0 change pp | Baseline change pp | DiD pp |", "|---|---|---|---:|---:|---:|"]
    for row in top_did:
        lines.append(f"| {row['state'].title()} | {row['baseline_code']} | {row['combination_label']} | {row['a0_high_minus_low_pp']:.2f} | {row['baseline_high_minus_low_pp']:.2f} | {row['difference_in_differences_pp']:.2f} |")
    lines += ["", "## Robust compound failures", "",
              "These combinations satisfy both tests against every baseline: A0 exposure is higher above 75%, and the A0 concentration gradient is steeper.", "",
              "| State | Combination | A0 above 75% | A0 change pp | Smallest high gap pp | Smallest DiD pp |", "|---|---|---:|---:|---:|---:|"]
    for row in robust:
        lines.append(f"| {row['state'].title()} | {row['combination_label']} | {row['a0_high_exposure_percent']:.2f} | {row['a0_high_minus_low_pp']:.2f} | {row['minimum_high_gap_across_baselines_pp']:.2f} | {row['minimum_did_across_baselines_pp']:.2f} |")
    lines += ["", "## Interpretation boundary", "",
              "These are school-level intersections and student-weighted exposure comparisons. They do not identify individual Muslim-caste combinations or prove discriminatory intent. Difference-in-differences here compares concentration gradients across cross-sectional school groups; it is not a time-based causal design."]
    (output / "compound_state_a0_report.md").write_text("\n".join(lines), encoding="utf-8")
    write_csv(output / "tables" / "top_100_high_concentration_gaps.csv", top_high)
    write_csv(output / "tables" / "top_100_difference_in_differences.csv", top_did)
    write_csv(output / "tables" / "top_100_robust_compound_failures.csv", robust)


def main() -> int:
    options = parse_args()
    output = options.output
    work = output / "work"
    work.mkdir(parents=True, exist_ok=True)
    items = combinations()
    try:
        parquet = checkpoint(options, work)
        temp = work / "duckdb_temp"
        temp.mkdir(exist_ok=True)
        connection = duckdb.connect(str(work / "compound.duckdb"))
        connection.execute("SET threads=2")
        connection.execute("SET memory_limit='4GB'")
        connection.execute("SET preserve_insertion_order=false")
        connection.execute(f"SET temp_directory={sql_string(str(temp))}")
        required = sorted({member.code for item in items for member in item.members})
        projection = ["state"]
        for group_code, _ in GROUPS:
            prefix = group_code.lower()
            projection.extend((f"{prefix}_students", f"{prefix}_girls", f"{prefix}_share"))
        projection.extend(required)
        connection.execute(
            "CREATE VIEW school_indicator_base AS SELECT " + ",".join(projection)
            + " FROM read_parquet(" + sql_string(str(parquet)) + ")"
        )
        try:
            state_rows, band_rows = calculate_exposures(connection, items)
        finally:
            connection.close()
        contrast_rows = contrasts(state_rows, band_rows)
        rankings = robust_rankings(contrast_rows)
        tables = output / "tables"
        write_csv(tables / "compound_combination_catalog.csv", combination_catalog(items))
        write_csv(tables / "state_group_compound_exposures.csv", state_rows)
        write_csv(tables / "state_group_compound_concentration_gradients.csv", band_rows)
        write_csv(tables / "state_compound_baseline_contrasts.csv", contrast_rows)
        write_csv(tables / "state_compound_robust_rankings.csv", rankings)
        report(output, items, contrast_rows, rankings)
        (output / "analysis_manifest.json").write_text(json.dumps({
            "states": TOP_STATES,
            "groups": [code for code, _ in GROUPS],
            "conditions": [condition.code for condition in CONDITIONS],
            "combination_count": len(items),
            "contrast_rows": len(contrast_rows),
            "ranking_rows": len(rankings),
            "minimum_eligible_weight_for_rankings": 10_000,
            "minimum_eligible_schools_for_rankings": 25,
        }, indent=2), encoding="utf-8")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
