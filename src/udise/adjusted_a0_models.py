from __future__ import annotations

import argparse
import csv
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
from huggingface_hub import hf_hub_download

from udise.indicator_registry import ALL_INDICATORS, Indicator

REMOTE_SCHOOL_INDICATORS = "processed/2024_25/analysis/school_indicator_base.parquet"
PRINCIPAL_OUTCOMES = (
    "ends_before_class10",
    "ends_before_class12",
    "no_functional_water_source",
    "no_functional_electricity",
    "no_internet",
    "str_above_30",
    "no_female_teacher",
    "grant_per_student",
    "access_deprivation_index",
    "teacher_capacity_deprivation_index",
    "institutional_neglect_index",
    "overall_multidimensional_deprivation_index",
)
INTERACTION_OUTCOMES = (
    "access_deprivation_index",
    "teacher_capacity_deprivation_index",
    "institutional_neglect_index",
    "overall_multidimensional_deprivation_index",
)
BASELINE_PAIR_OUTCOMES = (
    "access_deprivation_index",
    "teacher_capacity_deprivation_index",
    "overall_multidimensional_deprivation_index",
)


@dataclass(frozen=True)
class Regressor:
    name: str
    expression: str
    label: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/adjusted_a0"))
    parser.add_argument("--parquet-path", type=Path)
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    return parser.parse_args()


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


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
        return "percentage points"
    if item.level == "tertiary":
        return "index points"
    if item.code.endswith("_share") or item.code.endswith("_rate"):
        return "percentage points"
    if item.code == "student_teacher_ratio":
        return "students per teacher"
    if "grant_per_student" in item.code:
        return "rupees per student"
    return "outcome units"


def download_parquet(args: argparse.Namespace, work_dir: Path) -> Path:
    if args.parquet_path:
        return args.parquet_path
    if not args.dataset_repo or not args.token:
        raise RuntimeError("HF_DATASET_REPO and HF_TOKEN are required")
    return Path(
        hf_hub_download(
            repo_id=args.dataset_repo,
            filename=REMOTE_SCHOOL_INDICATORS,
            repo_type="dataset",
            token=args.token,
            local_dir=work_dir,
        )
    )


def category_values(connection: duckdb.DuckDBPyConnection, relation: str, column: str) -> list[Any]:
    return [
        row[0]
        for row in connection.execute(
            f"SELECT DISTINCT {sql_identifier(column)} FROM {relation} "
            f"WHERE {sql_identifier(column)} IS NOT NULL ORDER BY 1"
        ).fetchall()
    ]


def standard_controls(connection: duckdb.DuckDBPyConnection, relation: str, *, include_caste_composition: bool = True) -> list[Regressor]:
    controls = [Regressor("a0_share", "CAST(a0_share AS DOUBLE)", "Muslim enrolment share")]
    if include_caste_composition:
        controls.extend([
            Regressor("b0_share", "CAST(b0_share AS DOUBLE)", "General share"),
            Regressor("c0_share", "CAST(c0_share AS DOUBLE)", "SC share"),
            Regressor("d0_share", "CAST(d0_share AS DOUBLE)", "ST share"),
        ])
    controls.extend([
        Regressor("log_enrolment", "LN(1.0 + total_students)", "Log total enrolment"),
        Regressor("lowclass", "CAST(lowclass AS DOUBLE)", "Lowest class"),
        Regressor("highclass", "CAST(highclass AS DOUBLE)", "Highest class"),
        Regressor("minority_managed", "CASE WHEN minority_school = 1 THEN 1.0 ELSE 0.0 END", "Minority-managed school"),
        Regressor("shift_school", "CASE WHEN shift_school = 1 THEN 1.0 ELSE 0.0 END", "Shift school"),
        Regressor("residential_school", "CASE WHEN resi_school IN (1, 2) THEN 1.0 ELSE 0.0 END", "Residential school"),
    ])
    for column, prefix, label in (
        ("rural_urban", "location", "Location raw code"),
        ("managment", "management", "Management raw code"),
        ("school_category", "category", "School category raw code"),
    ):
        values = category_values(connection, relation, column)
        for value in values[1:]:
            token = str(value).replace("-", "m").replace(".", "_")
            controls.append(
                Regressor(
                    f"{prefix}_{token}",
                    f"CASE WHEN {sql_identifier(column)} = {sql_string(str(value))} THEN 1.0 ELSE 0.0 END",
                    f"{label} {value}",
                )
            )
    return controls


def model_ctes(relation: str, outcome: str, regressors: list[Regressor], fixed_effect: str, extra_where: str = "TRUE") -> tuple[str, list[str]]:
    aliases = [f"x{index}" for index in range(len(regressors))]
    select_x = ",\n".join(
        f"({regressor.expression}) AS {alias}"
        for alias, regressor in zip(aliases, regressors, strict=True)
    )
    nonmissing = " AND ".join(f"({regressor.expression}) IS NOT NULL" for regressor in regressors)
    partition = "state" if fixed_effect == "state" else "state, district"
    demean_x = ",\n".join(
        f"{alias} - AVG({alias}) OVER (PARTITION BY {partition}) AS {alias}"
        for alias in aliases
    )
    ctes = f"""
        WITH raw_model AS (
            SELECT state, district,
                   CAST({sql_identifier(outcome)} AS DOUBLE) AS y,
                   {select_x}
            FROM {relation}
            WHERE {sql_identifier(outcome)} IS NOT NULL
              AND {nonmissing}
              AND ({extra_where})
        ),
        demeaned AS (
            SELECT state, district,
                   y - AVG(y) OVER (PARTITION BY {partition}) AS y,
                   {demean_x}
            FROM raw_model
        )
    """
    return ctes, aliases


def fit_model(connection: duckdb.DuckDBPyConnection, relation: str, outcome: str, regressors: list[Regressor], fixed_effect: str, *, extra_where: str = "TRUE", robust_se: bool = True) -> dict[str, Any]:
    ctes, aliases = model_ctes(relation, outcome, regressors, fixed_effect, extra_where)
    cross_terms: list[str] = []
    positions: list[tuple[int, int]] = []
    for i, left in enumerate(aliases):
        for j in range(i, len(aliases)):
            right = aliases[j]
            cross_terms.append(f"SUM({left} * {right}) AS xx_{i}_{j}")
            positions.append((i, j))
    xy_terms = [f"SUM({alias} * y) AS xy_{index}" for index, alias in enumerate(aliases)]
    row = connection.execute(
        f"""
        {ctes}
        SELECT COUNT(*)::BIGINT AS observations,
               COUNT(DISTINCT state || '|' || district)::BIGINT AS clusters,
               {", ".join(cross_terms + xy_terms)}
        FROM demeaned
        """
    ).fetchone()
    observations = int(row[0])
    clusters = int(row[1])
    k = len(aliases)
    xtx = np.zeros((k, k), dtype=float)
    offset = 2
    for value, (i, j) in zip(row[offset:offset + len(positions)], positions, strict=True):
        numeric = float(value or 0)
        xtx[i, j] = numeric
        xtx[j, i] = numeric
    xy_start = offset + len(positions)
    xty = np.array([float(value or 0) for value in row[xy_start:xy_start + k]])
    bread = np.linalg.pinv(xtx, rcond=1e-10)
    beta = bread @ xty
    rank = int(np.linalg.matrix_rank(xtx))

    if robust_se:
        residual = "y - (" + " + ".join(
            f"({beta[index]:.17g}) * {alias}"
            for index, alias in enumerate(aliases)
        ) + ")"
        score_terms = [
            f"SUM({alias} * ({residual})) AS score_{index}"
            for index, alias in enumerate(aliases)
        ]
        cluster_rows = connection.execute(
            f"""
            {ctes}
            SELECT state, district, {", ".join(score_terms)}
            FROM demeaned
            GROUP BY state, district
            """
        ).fetchall()
        scores = np.array(
            [[float(value or 0) for value in cluster_row[2:]] for cluster_row in cluster_rows],
            dtype=float,
        )
        meat = scores.T @ scores
        covariance = bread @ meat @ bread
        if clusters > 1 and observations > k:
            covariance *= (clusters / (clusters - 1)) * ((observations - 1) / (observations - k))
        standard_errors = np.sqrt(np.clip(np.diag(covariance), 0, None))
    else:
        standard_errors = np.full(k, np.nan)
    return {
        "observations": observations,
        "clusters": clusters,
        "rank": rank,
        "coefficients": beta,
        "standard_errors": standard_errors,
    }


def coefficient_rows(result: dict[str, Any], regressors: list[Regressor], *, model_name: str, fixed_effect: str, outcome: str, item: Indicator, focal_names: set[str] | None = None, state: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    multiplier = display_multiplier(item)
    focal_names = focal_names or {"a0_share"}
    for index, regressor in enumerate(regressors):
        coefficient = float(result["coefficients"][index])
        standard_error = float(result["standard_errors"][index])
        t_stat = coefficient / standard_error if math.isfinite(standard_error) and standard_error > 0 else None
        row = {
            "model": model_name,
            "fixed_effect": fixed_effect,
            "outcome_code": outcome,
            "outcome_label": item.label,
            "outcome_domain": item.domain,
            "regressor": regressor.name,
            "regressor_label": regressor.label,
            "principal_coefficient": regressor.name in focal_names,
            "coefficient": coefficient,
            "cluster_robust_standard_error": standard_error if math.isfinite(standard_error) else None,
            "t_statistic": t_stat,
            "observations": result["observations"],
            "district_clusters": result["clusters"],
            "matrix_rank": result["rank"],
            "effect_for_10_percentage_point_increase": coefficient * 0.10 * multiplier if regressor.name.endswith("_share") or regressor.name == "a0_share" else None,
            "display_unit": display_unit(item),
        }
        if state is not None:
            row["state"] = state
        rows.append(row)
    return rows


def main_adjusted_models(connection: duckdb.DuckDBPyConnection, relation: str) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    regressors = standard_controls(connection, relation)
    rows: list[dict[str, Any]] = []
    for outcome in PRINCIPAL_OUTCOMES:
        item = registry[outcome]
        for fixed_effect in ("state", "district"):
            result = fit_model(connection, relation, outcome, regressors, fixed_effect)
            rows.extend(coefficient_rows(result, regressors, model_name="A0 adjusted school-condition model", fixed_effect=f"{fixed_effect} fixed effects", outcome=outcome, item=item))
    return rows


def interaction_models(connection: duckdb.DuckDBPyConnection, relation: str) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    base_controls = standard_controls(connection, relation, include_caste_composition=False)[1:]
    rows: list[dict[str, Any]] = []
    for baseline in ("B0", "C0", "D0", "E0"):
        share = f"{baseline.lower()}_share"
        regressors = [
            Regressor("a0_share", "CAST(a0_share AS DOUBLE)", "Muslim share"),
            Regressor(f"{baseline.lower()}_share", f"CAST({share} AS DOUBLE)", f"{baseline} share"),
            Regressor(f"a0_x_{baseline.lower()}", f"CAST(a0_share AS DOUBLE) * CAST({share} AS DOUBLE)", f"A0 × {baseline} share interaction"),
            *base_controls,
        ]
        for outcome in INTERACTION_OUTCOMES:
            item = registry[outcome]
            result = fit_model(connection, relation, outcome, regressors, "district", robust_se=False)
            model_rows = coefficient_rows(
                result, regressors, model_name=f"A0-{baseline} interaction model",
                fixed_effect="district fixed effects", outcome=outcome, item=item,
                focal_names={"a0_share", f"{baseline.lower()}_share", f"a0_x_{baseline.lower()}"},
            )
            interaction_name = f"a0_x_{baseline.lower()}"
            for row in model_rows:
                row["baseline_code"] = baseline
                if row["regressor"] == interaction_name:
                    row["effect_when_both_shares_rise_10pp"] = row["coefficient"] * 0.01 * display_multiplier(item)
            rows.extend(model_rows)
    return rows


def baseline_pair_models(connection: duckdb.DuckDBPyConnection, relation: str) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    controls = standard_controls(connection, relation, include_caste_composition=False)[1:]
    rows: list[dict[str, Any]] = []
    for baseline in ("C0", "D0", "E0"):
        other_share = f"{baseline.lower()}_share"
        pair_total = f"(b0_share + {other_share})"
        regressors = [
            Regressor(f"b0_balance_vs_{baseline.lower()}", f"b0_share / NULLIF({pair_total}, 0)", f"B0 share within B0-{baseline} pair"),
            Regressor(f"b0_{baseline.lower()}_pair_total", pair_total, f"Combined B0-{baseline} share"),
            *controls,
        ]
        for outcome in BASELINE_PAIR_OUTCOMES:
            item = registry[outcome]
            result = fit_model(connection, relation, outcome, regressors, "district", extra_where=f"{pair_total} > 0", robust_se=False)
            rows.extend(coefficient_rows(
                result, regressors,
                model_name=f"B0-{baseline} baseline calibration model",
                fixed_effect="district fixed effects", outcome=outcome, item=item,
                focal_names={f"b0_balance_vs_{baseline.lower()}", f"b0_{baseline.lower()}_pair_total"},
            ))
    return rows


def state_specific_slopes(connection: duckdb.DuckDBPyConnection, relation: str) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    outcomes = (
        "ends_before_class12", "str_above_30", "no_internet",
        "teacher_capacity_deprivation_index", "institutional_neglect_index",
        "overall_multidimensional_deprivation_index",
    )
    rows: list[dict[str, Any]] = []
    for outcome in outcomes:
        item = registry[outcome]
        records = connection.execute(
            f"""
            WITH demeaned AS (
                SELECT state, district,
                       a0_share - AVG(a0_share) OVER (PARTITION BY state, district) AS x,
                       {sql_identifier(outcome)} - AVG({sql_identifier(outcome)}) OVER (PARTITION BY state, district) AS y
                FROM {relation}
                WHERE a0_share IS NOT NULL AND {sql_identifier(outcome)} IS NOT NULL
            )
            SELECT state, COUNT(*)::BIGINT AS observations,
                   COUNT(DISTINCT district)::BIGINT AS districts,
                   SUM(x * y) / NULLIF(SUM(x * x), 0) AS slope,
                   CORR(x, y) AS correlation
            FROM demeaned
            GROUP BY state
            ORDER BY state
            """
        ).fetchall()
        for state, observations, districts, slope, correlation in records:
            rows.append({
                "state": state, "outcome_code": outcome, "outcome_label": item.label,
                "observations": observations, "districts": districts,
                "within_district_slope": slope,
                "effect_for_10_percentage_point_a0_increase": slope * 0.10 * display_multiplier(item) if slope is not None else None,
                "within_district_correlation": correlation,
                "display_unit": display_unit(item),
            })
    return rows


def build_report(main_rows: list[dict[str, Any]], interaction_rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]], state_rows: list[dict[str, Any]]) -> str:
    principal = [row for row in main_rows if row["principal_coefficient"] and row["regressor"] == "a0_share"]
    return "\n".join([
        "# Adjusted A0 models", "",
        "The models estimate associations between Muslim enrolment share and school conditions after controlling for caste composition, total enrolment, class span, minority-managed status, shift and residential status, and raw location, management and school-category codes.", "",
        "State-fixed-effect and district-fixed-effect versions are reported. Standard errors for the principal models are clustered by district.", "",
        f"Principal A0 coefficients: {len(principal):,}.",
        f"A0-baseline interaction coefficient rows: {len(interaction_rows):,}.",
        f"Baseline calibration coefficient rows: {len(baseline_rows):,}.",
        f"State-specific within-district association rows: {len(state_rows):,}.", "",
        "A statistically precise association is not by itself proof of discriminatory intent. The models reduce measured geographic and institutional confounding but cannot control for unobserved household circumstances, school choice, local supply or historical settlement patterns.", "",
    ])


def main() -> int:
    args = parse_args()
    output = args.output
    work_dir = output / "work"
    tables_dir = output / "tables"
    work_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = download_parquet(args, work_dir)
    connection = duckdb.connect()
    connection.execute("PRAGMA threads=4")
    connection.execute("PRAGMA memory_limit='11GB'")
    connection.execute(f"PRAGMA temp_directory={sql_string(str(work_dir / 'duckdb_temp'))}")
    relation = f"read_parquet({sql_string(str(parquet_path))})"
    try:
        main_rows = main_adjusted_models(connection, relation)
        interaction_rows = interaction_models(connection, relation)
        baseline_rows = baseline_pair_models(connection, relation)
        state_rows = state_specific_slopes(connection, relation)
        write_csv(tables_dir / "adjusted_a0_models.csv", main_rows)
        write_csv(tables_dir / "adjusted_a0_baseline_interactions.csv", interaction_rows)
        write_csv(tables_dir / "adjusted_baseline_calibration_models.csv", baseline_rows)
        write_csv(tables_dir / "state_specific_within_district_a0_associations.csv", state_rows)
        report = build_report(main_rows, interaction_rows, baseline_rows, state_rows)
        (output / "adjusted_a0_models_report.md").write_text(report, encoding="utf-8")
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write(report)
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
