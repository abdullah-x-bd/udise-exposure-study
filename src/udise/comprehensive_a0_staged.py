from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from pathlib import Path
from typing import Any, Iterable, Iterator

import duckdb
from huggingface_hub import HfApi, hf_hub_download

from udise.comprehensive_a0_analysis import (
    GROUPS,
    REMOTE_DATABASE,
    REMOTE_SCHOOL_INDICATORS,
    band_case,
    baseline_gap_rows,
    build_report,
    codebook_audit,
    concentration_distribution,
    concentration_gradient_rows,
    district_profiles,
    export_school_indicator_parquet,
    fixed_effect_slopes,
    gender_exposure_rows,
    group_exposure_rows,
    group_totals,
    indicator_catalog_rows,
    interaction_grids,
    pairwise_gap_rows,
    primary_numeric_summary,
    save_bar_chart,
    save_domain_gap_heatmaps,
    save_gradient_chart,
    save_state_ranking,
    stage_rows,
    state_profiles,
    structural_evidence_profile,
    teacher_representation,
    upload_school_indicator,
    write_csv,
    write_json,
    create_indicator_tables,
    sql_string,
)
from udise.indicator_registry import ALL_INDICATORS as REGISTRY_INDICATORS
from udise.indicator_registry import validate_registry

MEMORY_LIMIT = "4GB"
THREADS = 2
BATCH_SIZE = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the comprehensive A0 analysis in restartable stages."
    )
    parser.add_argument("phase", choices=("build", "aggregate"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/comprehensive_a0"),
    )
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    parser.add_argument("--database-path", type=Path)
    parser.add_argument("--school-indicator-path", type=Path)
    return parser.parse_args()


def log(message: str) -> None:
    print(f"[comprehensive-a0] {message}", flush=True)


def batches(
    values: tuple[Any, ...],
    size: int = BATCH_SIZE,
) -> Iterator[tuple[Any, ...]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def configure_connection(
    path: Path,
    work_dir: Path,
    *,
    read_only: bool,
) -> duckdb.DuckDBPyConnection:
    work_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = work_dir / "duckdb_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(path), read_only=read_only)
    connection.execute(f"PRAGMA threads={THREADS}")
    connection.execute(f"PRAGMA memory_limit={sql_string(MEMORY_LIMIT)}")
    connection.execute("SET preserve_insertion_order=false")
    connection.execute(f"PRAGMA temp_directory={sql_string(str(temp_dir))}")
    return connection


def require_private_source(args: argparse.Namespace) -> None:
    if not args.dataset_repo:
        raise RuntimeError("HF_DATASET_REPO is not configured")
    if not args.token:
        raise RuntimeError("HF_TOKEN is not configured")


def download_database(args: argparse.Namespace, work_dir: Path) -> Path:
    if args.database_path:
        return args.database_path
    require_private_source(args)
    log("Downloading the private DuckDB source checkpoint")
    return Path(
        hf_hub_download(
            repo_id=args.dataset_repo,
            filename=REMOTE_DATABASE,
            repo_type="dataset",
            token=args.token,
            local_dir=work_dir,
        )
    )


def download_school_indicators(args: argparse.Namespace, work_dir: Path) -> Path:
    if args.school_indicator_path:
        return args.school_indicator_path
    require_private_source(args)
    log("Downloading the private school-indicator Parquet checkpoint")
    return Path(
        hf_hub_download(
            repo_id=args.dataset_repo,
            filename=REMOTE_SCHOOL_INDICATORS,
            repo_type="dataset",
            token=args.token,
            local_dir=work_dir,
        )
    )


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    def coerce(value: str) -> Any:
        if value == "":
            return None
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        try:
            if all(character not in value for character in (".", "e", "E")):
                return int(value)
            return float(value)
        except ValueError:
            return value

    with path.open("r", encoding="utf-8", newline="") as handle:
        return [
            {key: coerce(value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def create_group_long_view(connection: duckdb.DuckDBPyConnection) -> None:
    unions: list[str] = []
    for code, label in GROUPS:
        prefix = code.lower()
        unions.append(
            f"""
            SELECT *,
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
    connection.execute(
        "CREATE OR REPLACE TEMP VIEW group_school_long AS "
        + " UNION ALL ".join(unions)
    )


def write_foundational_tables(
    connection: duckdb.DuckDBPyConnection,
    output: Path,
) -> dict[str, int]:
    tables_dir = output / "tables"
    tasks: tuple[tuple[str, Any], ...] = (
        ("indicator_catalog.csv", indicator_catalog_rows),
        ("primary_numeric_summary.csv", primary_numeric_summary),
        ("dcf_raw_code_audit.csv", codebook_audit),
        ("national_stage_representation.csv", lambda c: stage_rows(c)),
        (
            "state_stage_representation.csv",
            lambda c: stage_rows(c, geographic=True),
        ),
        (
            "national_teacher_social_category_representation.csv",
            lambda c: teacher_representation(c),
        ),
        (
            "state_teacher_social_category_representation.csv",
            lambda c: teacher_representation(c, by_state=True),
        ),
    )
    counts: dict[str, int] = {}
    for filename, function in tasks:
        log(f"Building foundational table {filename}")
        rows = function(connection)
        write_csv(tables_dir / filename, rows)
        counts[filename] = len(rows)
    return counts


def build_phase(args: argparse.Namespace) -> int:
    validate_registry()
    output = args.output
    work_dir = output / "work_build"
    output.mkdir(parents=True, exist_ok=True)
    database_path = download_database(args, work_dir)
    connection = configure_connection(database_path, work_dir, read_only=True)
    try:
        log(
            f"Building the school indicator table with {MEMORY_LIMIT} memory "
            f"and {THREADS} DuckDB threads"
        )
        create_indicator_tables(connection)
        log("School indicator table created")

        counts = write_foundational_tables(connection, output)

        checkpoint = work_dir / "school_indicator_base.parquet"
        log("Exporting the private school-level Parquet checkpoint")
        export_school_indicator_parquet(connection, checkpoint)
        require_private_source(args)
        log("Uploading the private school-level checkpoint to Hugging Face")
        upload_school_indicator(args.dataset_repo, args.token, checkpoint)

        manifest = {
            "phase": "build",
            "memory_limit": MEMORY_LIMIT,
            "threads": THREADS,
            "indicator_count": len(REGISTRY_INDICATORS),
            "foundational_table_rows": counts,
            "private_checkpoint": REMOTE_SCHOOL_INDICATORS,
            "checkpoint_bytes": checkpoint.stat().st_size,
        }
        write_json(output / "build_manifest.json", manifest)
        log("Build phase completed")
    finally:
        connection.close()
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


def batched_group_exposures(
    connection: duckdb.DuckDBPyConnection,
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total_batches = (len(REGISTRY_INDICATORS) + BATCH_SIZE - 1) // BATCH_SIZE
    for index, indicator_batch in enumerate(
        batches(REGISTRY_INDICATORS), start=1
    ):
        log(
            f"Exposure batch {index}/{total_batches} for "
            + ", ".join(fields)
        )
        rows.extend(
            group_exposure_rows(
                connection,
                fields,
                indicators=indicator_batch,
            )
        )
    return rows


def batched_gradients(
    connection: duckdb.DuckDBPyConnection,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total_batches = (len(REGISTRY_INDICATORS) + BATCH_SIZE - 1) // BATCH_SIZE
    for index, indicator_batch in enumerate(
        batches(REGISTRY_INDICATORS), start=1
    ):
        log(f"Concentration-gradient batch {index}/{total_batches}")
        rows.extend(
            concentration_gradient_rows(
                connection,
                indicators=indicator_batch,
            )
        )
    return rows


def write_aggregate_tables(
    connection: duckdb.DuckDBPyConnection,
    output: Path,
) -> dict[str, list[dict[str, Any]]]:
    tables_dir = output / "tables"

    log("Building group totals")
    totals = group_totals(connection)

    log("Building national and state concentration distributions")
    national_distribution = concentration_distribution(connection)
    state_distribution = concentration_distribution(connection, by_state=True)

    log("Building national exposures in bounded indicator batches")
    national_exposures = batched_group_exposures(
        connection,
        ("group_code", "group_label"),
    )
    log("Building national baseline gaps")
    national_gaps = baseline_gap_rows(national_exposures, keys=())
    pairwise_gaps = pairwise_gap_rows(national_exposures, keys=())

    log("Building concentration gradients in bounded batches")
    gradients = batched_gradients(connection)

    log("Building gender-specific exposure estimates")
    gender_exposures = gender_exposure_rows(connection)

    log("Building A0-baseline interaction grids")
    interactions = interaction_grids(connection)

    log("Building state and district fixed-effect associations")
    slopes = fixed_effect_slopes(connection)

    log("Building state exposures in bounded indicator batches")
    state_exposures = batched_group_exposures(
        connection,
        ("state", "group_code", "group_label"),
    )
    state_gaps = baseline_gap_rows(state_exposures, keys=("state",))

    state_stage_path = tables_dir / "state_stage_representation.csv"
    if not state_stage_path.exists():
        raise RuntimeError(
            "The foundational state-stage table was not downloaded from "
            "the build-stage artifact."
        )
    state_stages = read_csv_rows(state_stage_path)

    log("Building state profiles")
    profiles = state_profiles(
        state_exposures,
        state_stages,
        state_distribution,
    )
    log("Building district profiles")
    districts = district_profiles(connection)
    log("Building structural evidence classifications")
    evidence = structural_evidence_profile(national_gaps, slopes)

    outputs = {
        "national_group_totals.csv": totals,
        "national_concentration_distribution.csv": national_distribution,
        "state_concentration_distribution.csv": state_distribution,
        "national_group_exposures_all_indicators.csv": national_exposures,
        "national_a0_baseline_gaps_all_indicators.csv": national_gaps,
        "national_all_pairwise_gaps.csv": pairwise_gaps,
        "national_concentration_gradients_all_indicators.csv": gradients,
        "national_gender_exposures.csv": gender_exposures,
        "a0_baseline_interaction_grids.csv": interactions,
        "fixed_effect_a0_associations.csv": slopes,
        "state_group_exposures_all_indicators.csv": state_exposures,
        "state_a0_baseline_gaps_all_indicators.csv": state_gaps,
        "state_a0_profiles.csv": profiles,
        "district_a0_profiles.csv": districts,
        "structural_evidence_profile.csv": evidence,
    }
    for filename, rows in outputs.items():
        log(f"Writing {filename}")
        write_csv(tables_dir / filename, rows)
    return {
        "totals": totals,
        "national_exposures": national_exposures,
        "national_gaps": national_gaps,
        "gradients": gradients,
        "slopes": slopes,
        "profiles": profiles,
        "districts": districts,
        "state_exposures": state_exposures,
        "interactions": interactions,
        "evidence": evidence,
    }


def create_figures(
    output: Path,
    results: dict[str, list[dict[str, Any]]],
) -> None:
    figures_dir = output / "figures"
    exposure_lookup: dict[str, list[dict[str, Any]]] = {}
    for item in REGISTRY_INDICATORS:
        exposure_lookup[item.code] = []
    for row in results["national_exposures"]:
        exposure_lookup[row["indicator_code"]].append(row)

    log(f"Generating {len(REGISTRY_INDICATORS)} exposure figures")
    for index, item in enumerate(REGISTRY_INDICATORS, start=1):
        if index % 20 == 0:
            log(f"Exposure figures {index}/{len(REGISTRY_INDICATORS)}")
        domain = item.domain.replace("/", "_")
        save_bar_chart(
            exposure_lookup[item.code],
            f"{item.label}: Muslim exposure and comparison baselines",
            _unit_for_item(item),
            figures_dir / "exposures" / domain / f"{item.code}.png",
        )

    log(f"Generating {len(REGISTRY_INDICATORS)} gradient figures")
    for index, item in enumerate(REGISTRY_INDICATORS, start=1):
        if index % 20 == 0:
            log(f"Gradient figures {index}/{len(REGISTRY_INDICATORS)}")
        domain = item.domain.replace("/", "_")
        save_gradient_chart(
            results["gradients"],
            item,
            figures_dir / "gradients" / domain / f"{item.code}.png",
        )

    log("Generating domain gap heatmaps")
    save_domain_gap_heatmaps(
        results["national_gaps"],
        figures_dir / "gap_heatmaps",
    )
    log("Generating state ranking figures")
    save_state_ranking(
        results["profiles"],
        "overall_multidimensional_deprivation_index",
        "Muslim-student exposure to multidimensional school deprivation by state",
        figures_dir / "state_rankings" / "overall_deprivation.png",
    )
    save_state_ranking(
        results["profiles"],
        "institutional_neglect_index",
        "Muslim-student exposure to institutional neglect interaction by state",
        figures_dir / "state_rankings" / "institutional_neglect.png",
    )
    save_state_ranking(
        results["profiles"],
        "a0_primary_to_higher_secondary_representation_change_pp",
        "Change in Muslim representation from primary to higher secondary by state",
        figures_dir / "state_rankings" / "stage_representation_change.png",
    )


def _unit_for_item(item: Any) -> str:
    from udise.comprehensive_a0_analysis import display_unit

    return display_unit(item)


def aggregate_phase(args: argparse.Namespace) -> int:
    validate_registry()
    output = args.output
    work_dir = output / "work_aggregate"
    output.mkdir(parents=True, exist_ok=True)
    parquet_path = download_school_indicators(args, work_dir)
    local_database = work_dir / "aggregate.duckdb"
    connection = configure_connection(local_database, work_dir, read_only=False)
    try:
        log("Registering the private school-indicator Parquet checkpoint")
        connection.execute(
            "CREATE OR REPLACE VIEW school_indicator_base AS "
            f"SELECT * FROM read_parquet({sql_string(str(parquet_path))})"
        )
        create_group_long_view(connection)
        results = write_aggregate_tables(connection, output)

        log("Generating the complete graph library")
        create_figures(output, results)

        catalog_path = output / "tables" / "indicator_catalog.csv"
        catalog_count = len(read_csv_rows(catalog_path))
        report = build_report(
            results["totals"],
            results["national_exposures"],
            results["national_gaps"],
            results["slopes"],
            catalog_count,
        )
        (output / "comprehensive_a0_report.md").write_text(
            report,
            encoding="utf-8",
        )
        manifest = {
            "phase": "aggregate",
            "memory_limit": MEMORY_LIMIT,
            "threads": THREADS,
            "batch_size": BATCH_SIZE,
            "indicator_count": len(REGISTRY_INDICATORS),
            "national_exposure_rows": len(results["national_exposures"]),
            "national_gap_rows": len(results["national_gaps"]),
            "gradient_rows": len(results["gradients"]),
            "state_exposure_rows": len(results["state_exposures"]),
            "district_profiles": len(results["districts"]),
            "interaction_rows": len(results["interactions"]),
            "evidence_rows": len(results["evidence"]),
        }
        write_json(output / "analysis_manifest.json", manifest)
        if summary_path := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary_path).open("a", encoding="utf-8") as handle:
                handle.write(report)
        log("Aggregate phase completed")
    finally:
        connection.close()
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


def main() -> int:
    args = parse_args()
    if args.phase == "build":
        return build_phase(args)
    return aggregate_phase(args)


if __name__ == "__main__":
    raise SystemExit(main())
