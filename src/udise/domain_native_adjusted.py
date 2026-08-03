from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Any

import duckdb

from udise.adjusted_a0_models import (
    BASELINE_PAIR_OUTCOMES,
    INTERACTION_OUTCOMES,
    PRINCIPAL_OUTCOMES,
    Regressor,
    coefficient_rows,
    fit_model,
    standard_controls,
    write_csv,
)
from udise.domain_native_a0 import (
    DOMAIN_REMOTE_TEMPLATE,
    configure_connection,
    download_one,
    sql_string,
)
from udise.indicator_registry import ALL_INDICATORS

OUTCOME_DOMAIN = {
    "ends_before_class10": "access",
    "ends_before_class12": "access",
    "no_functional_water_source": "wash",
    "no_functional_electricity": "learning_environment",
    "no_internet": "digital",
    "str_above_30": "teachers",
    "no_female_teacher": "teachers",
    "grant_per_student": "governance",
    "access_deprivation_index": "tertiary",
    "teacher_capacity_deprivation_index": "tertiary",
    "institutional_neglect_index": "tertiary",
    "overall_multidimensional_deprivation_index": "tertiary",
}
STATE_SPECIFIC_OUTCOMES = (
    "ends_before_class12",
    "str_above_30",
    "no_internet",
    "teacher_capacity_deprivation_index",
    "institutional_neglect_index",
    "overall_multidimensional_deprivation_index",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task",
        choices=("principal", "interaction", "calibration", "state_specific"),
        required=True,
    )
    parser.add_argument("--outcome", choices=tuple(OUTCOME_DOMAIN))
    parser.add_argument("--baseline", choices=("B0", "C0", "D0", "E0"))
    parser.add_argument("--output", type=Path, default=Path("outputs/domain_native_models"))
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    return parser.parse_args()


def require_args(args: argparse.Namespace) -> None:
    if not args.dataset_repo or not args.token:
        raise RuntimeError("HF_DATASET_REPO and HF_TOKEN are required")
    if args.task in {"principal", "state_specific"} and not args.outcome:
        raise ValueError("--outcome is required")
    if args.task in {"interaction", "calibration"} and not args.baseline:
        raise ValueError("--baseline is required")
    if args.task == "calibration" and args.baseline == "B0":
        raise ValueError("Calibration targets are C0, D0 and E0")


def model_file(args: argparse.Namespace, domain: str, work_dir: Path) -> Path:
    return download_one(
        args.dataset_repo,
        args.token,
        DOMAIN_REMOTE_TEMPLATE.format(domain=domain),
        work_dir,
    )


def principal_rows(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    outcome: str,
) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    item = registry[outcome]
    regressors = standard_controls(connection, relation)
    rows: list[dict[str, Any]] = []
    for fixed_effect in ("state", "district"):
        print(f"Estimating {outcome} with {fixed_effect} fixed effects", flush=True)
        result = fit_model(
            connection,
            relation,
            outcome,
            regressors,
            fixed_effect,
            robust_se=True,
        )
        rows.extend(
            coefficient_rows(
                result,
                regressors,
                model_name="A0 adjusted school-condition model",
                fixed_effect=f"{fixed_effect} fixed effects",
                outcome=outcome,
                item=item,
            )
        )
    return rows


def interaction_rows(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    baseline: str,
) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    base_controls = standard_controls(
        connection, relation, include_caste_composition=False
    )[1:]
    share = f"{baseline.lower()}_share"
    regressors = [
        Regressor("a0_share", "CAST(a0_share AS DOUBLE)", "Muslim share"),
        Regressor(
            f"{baseline.lower()}_share",
            f"CAST({share} AS DOUBLE)",
            f"{baseline} share",
        ),
        Regressor(
            f"a0_x_{baseline.lower()}",
            f"CAST(a0_share AS DOUBLE) * CAST({share} AS DOUBLE)",
            f"A0 × {baseline} interaction",
        ),
        *base_controls,
    ]
    rows: list[dict[str, Any]] = []
    for outcome in INTERACTION_OUTCOMES:
        item = registry[outcome]
        print(f"Estimating {outcome} A0-{baseline} interaction", flush=True)
        result = fit_model(
            connection,
            relation,
            outcome,
            regressors,
            "district",
            robust_se=False,
        )
        model_rows = coefficient_rows(
            result,
            regressors,
            model_name=f"A0-{baseline} interaction model",
            fixed_effect="district fixed effects",
            outcome=outcome,
            item=item,
            focal_names={
                "a0_share",
                f"{baseline.lower()}_share",
                f"a0_x_{baseline.lower()}",
            },
        )
        for row in model_rows:
            row["baseline_code"] = baseline
        rows.extend(model_rows)
    return rows


def calibration_rows(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    baseline: str,
) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    controls = standard_controls(
        connection, relation, include_caste_composition=False
    )[1:]
    other_share = f"{baseline.lower()}_share"
    pair_total = f"(b0_share + {other_share})"
    regressors = [
        Regressor(
            f"b0_balance_vs_{baseline.lower()}",
            f"b0_share / NULLIF({pair_total}, 0)",
            f"B0 share within B0-{baseline} pair",
        ),
        Regressor(
            f"b0_{baseline.lower()}_pair_total",
            pair_total,
            f"Combined B0-{baseline} share",
        ),
        *controls,
    ]
    rows: list[dict[str, Any]] = []
    for outcome in BASELINE_PAIR_OUTCOMES:
        item = registry[outcome]
        print(f"Estimating B0-{baseline} calibration for {outcome}", flush=True)
        result = fit_model(
            connection,
            relation,
            outcome,
            regressors,
            "district",
            extra_where=f"{pair_total} > 0",
            robust_se=False,
        )
        rows.extend(
            coefficient_rows(
                result,
                regressors,
                model_name=f"B0-{baseline} baseline calibration model",
                fixed_effect="district fixed effects",
                outcome=outcome,
                item=item,
                focal_names={
                    f"b0_balance_vs_{baseline.lower()}",
                    f"b0_{baseline.lower()}_pair_total",
                },
            )
        )
    return rows


def state_specific_rows(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    outcome: str,
) -> list[dict[str, Any]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    item = registry[outcome]
    cursor = connection.execute(
        f"""
        WITH demeaned AS (
            SELECT state, district,
                   a0_share - AVG(a0_share) OVER (PARTITION BY state, district) AS x,
                   "{outcome}" - AVG("{outcome}") OVER (PARTITION BY state, district) AS y
            FROM {relation}
            WHERE a0_share IS NOT NULL AND "{outcome}" IS NOT NULL
        )
        SELECT state, COUNT(*)::BIGINT AS observations,
               COUNT(DISTINCT district)::BIGINT AS districts,
               SUM(x * y) / NULLIF(SUM(x * x), 0) AS slope,
               CORR(x, y) AS correlation
        FROM demeaned
        GROUP BY state
        ORDER BY state
        """
    )
    rows: list[dict[str, Any]] = []
    for state, observations, districts, slope, correlation in cursor.fetchall():
        rows.append(
            {
                "state": state,
                "outcome_code": outcome,
                "outcome_label": item.label,
                "observations": observations,
                "districts": districts,
                "within_district_slope": slope,
                "effect_for_10_percentage_point_a0_increase": (
                    slope * 0.10
                    if slope is not None and item.level == "tertiary"
                    else slope * 10.0
                    if slope is not None and item.kind == "binary_adverse"
                    else slope * 0.10
                    if slope is not None
                    else None
                ),
                "within_district_correlation": correlation,
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    require_args(args)
    output = args.output
    work_dir = output / "work"
    tables_dir = output / "tables"
    work_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    if args.task in {"interaction", "calibration"}:
        domain = "tertiary"
    else:
        domain = OUTCOME_DOMAIN[args.outcome]
    path = model_file(args, domain, work_dir)
    connection = configure_connection(work_dir, memory_limit="4GB")
    relation = f"read_parquet({sql_string(str(path))})"
    try:
        if args.task == "principal":
            rows = principal_rows(connection, relation, args.outcome)
            stem = f"principal_{args.outcome}"
        elif args.task == "interaction":
            rows = interaction_rows(connection, relation, args.baseline)
            stem = f"interaction_{args.baseline.lower()}"
        elif args.task == "calibration":
            rows = calibration_rows(connection, relation, args.baseline)
            stem = f"calibration_{args.baseline.lower()}"
        else:
            rows = state_specific_rows(connection, relation, args.outcome)
            stem = f"state_specific_{args.outcome}"
        write_csv(tables_dir / f"{stem}.csv", rows)
        report = "\n".join(
            [
                "# Domain-native adjusted A0 model task",
                "",
                f"Task: {args.task}",
                f"Domain: {domain}",
                f"Outcome: {args.outcome or 'multiple tertiary outcomes'}",
                f"Baseline: {args.baseline or 'not applicable'}",
                f"Rows: {len(rows):,}",
                "",
            ]
        )
        (output / f"{stem}_report.md").write_text(report, encoding="utf-8")
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write(report)
    finally:
        connection.close()
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
