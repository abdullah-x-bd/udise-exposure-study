from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

import duckdb

from udise.adjusted_a0_models import (
    BASELINE_PAIR_OUTCOMES,
    INTERACTION_OUTCOMES,
    PRINCIPAL_OUTCOMES,
    Regressor,
    coefficient_rows,
    download_parquet,
    fit_model,
    standard_controls,
    state_specific_slopes,
    write_csv,
)
from udise.indicator_registry import ALL_INDICATORS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task",
        choices=("principal", "interaction", "calibration", "state_specific"),
        required=True,
    )
    parser.add_argument("--outcome", choices=PRINCIPAL_OUTCOMES)
    parser.add_argument("--baseline", choices=("B0", "C0", "D0", "E0"))
    parser.add_argument("--output", type=Path, default=Path("outputs/adjusted_task"))
    parser.add_argument("--parquet-path", type=Path)
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    return parser.parse_args()


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def principal_task(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    outcome: str,
) -> list[dict[str, object]]:
    registry = {item.code: item for item in ALL_INDICATORS}
    item = registry[outcome]
    regressors = standard_controls(connection, relation)
    rows: list[dict[str, object]] = []
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


def interaction_task(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    baseline: str,
) -> list[dict[str, object]]:
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
            f"A0 × {baseline} share interaction",
        ),
        *base_controls,
    ]
    rows: list[dict[str, object]] = []
    for outcome in INTERACTION_OUTCOMES:
        print(f"Estimating {outcome} A0-{baseline} interaction", flush=True)
        item = registry[outcome]
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


def calibration_task(
    connection: duckdb.DuckDBPyConnection,
    relation: str,
    baseline: str,
) -> list[dict[str, object]]:
    if baseline == "B0":
        raise ValueError("Calibration baseline must be C0, D0 or E0")
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
    rows: list[dict[str, object]] = []
    for outcome in BASELINE_PAIR_OUTCOMES:
        print(f"Estimating B0-{baseline} calibration for {outcome}", flush=True)
        item = registry[outcome]
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


def main() -> int:
    args = parse_args()
    if args.task == "principal" and not args.outcome:
        raise ValueError("--outcome is required for a principal task")
    if args.task in {"interaction", "calibration"} and not args.baseline:
        raise ValueError("--baseline is required for this task")
    if args.task == "calibration" and args.baseline == "B0":
        raise ValueError("B0 is the reference side, not a calibration target")

    output = args.output
    work_dir = output / "work"
    tables_dir = output / "tables"
    work_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = download_parquet(args, work_dir)
    connection = duckdb.connect()
    connection.execute("PRAGMA threads=2")
    connection.execute("PRAGMA memory_limit='4GB'")
    connection.execute("PRAGMA preserve_insertion_order=false")
    connection.execute(f"PRAGMA temp_directory={sql_string(str(work_dir / 'duckdb_temp'))}")
    relation = f"read_parquet({sql_string(str(parquet_path))})"
    try:
        if args.task == "principal":
            rows = principal_task(connection, relation, args.outcome)
            stem = f"principal_{args.outcome}"
        elif args.task == "interaction":
            rows = interaction_task(connection, relation, args.baseline)
            stem = f"interaction_{args.baseline.lower()}"
        elif args.task == "calibration":
            rows = calibration_task(connection, relation, args.baseline)
            stem = f"calibration_{args.baseline.lower()}"
        else:
            print("Estimating state-specific within-district A0 associations", flush=True)
            rows = state_specific_slopes(connection, relation)
            stem = "state_specific"

        write_csv(tables_dir / f"{stem}.csv", rows)
        report = "\n".join(
            [
                "# Adjusted A0 model task",
                "",
                f"Task: {args.task}",
                f"Outcome: {args.outcome or 'multiple'}",
                f"Baseline: {args.baseline or 'not applicable'}",
                f"Output rows: {len(rows):,}",
                "",
            ]
        )
        (output / f"{stem}_report.md").write_text(report, encoding="utf-8")
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write(report)
        print(f"Completed adjusted model task {stem}", flush=True)
    finally:
        connection.close()
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
