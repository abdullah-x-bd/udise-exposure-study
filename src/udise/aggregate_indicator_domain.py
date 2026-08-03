from __future__ import annotations

import argparse
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import duckdb
from huggingface_hub import hf_hub_download

from udise.comprehensive_a0_analysis import (
    GROUPS,
    REMOTE_SCHOOL_INDICATORS,
    baseline_gap_rows,
    band_case,
    concentration_gradient_rows,
    display_multiplier,
    display_unit,
    fixed_effect_slopes,
    group_exposure_rows,
    pairwise_gap_rows,
    save_bar_chart,
    save_domain_gap_heatmaps,
    save_gradient_chart,
    sql_identifier,
    sql_string,
    write_csv,
)
from udise.indicator_registry import ALL_INDICATORS, Indicator, validate_registry

DOMAIN_CHOICES = (
    "access",
    "infrastructure",
    "wash",
    "learning_environment",
    "digital",
    "teachers",
    "governance",
    "welfare",
    "inclusion",
    "vulnerability",
    "age_grade",
    "tertiary",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=DOMAIN_CHOICES, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/domain_analysis"))
    parser.add_argument("--parquet-path", type=Path)
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    return parser.parse_args()


def domain_indicators(domain: str) -> tuple[Indicator, ...]:
    if domain == "tertiary":
        return tuple(item for item in ALL_INDICATORS if item.level == "tertiary")
    return tuple(
        item for item in ALL_INDICATORS
        if item.level == "secondary" and item.domain == domain
    )


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


def create_views(
    connection: duckdb.DuckDBPyConnection,
    parquet_path: Path,
    indicators: tuple[Indicator, ...],
) -> None:
    source = f"read_parquet({sql_string(str(parquet_path))})"
    connection.execute(
        f"CREATE OR REPLACE TEMP VIEW school_indicator_base AS SELECT * FROM {source}"
    )
    selected = ", ".join(sql_identifier(item.code) for item in indicators)
    selected_prefix = f", {selected}" if selected else ""
    unions: list[str] = []
    for code, label in GROUPS:
        prefix = code.lower()
        unions.append(
            f"""
            SELECT state, district, block, pseudocode,
                   total_students, total_boys, total_girls,
                   a0_students, a0_share,
                   {prefix}_students AS group_students,
                   {prefix}_boys AS group_boys,
                   {prefix}_girls AS group_girls,
                   {prefix}_share AS group_share,
                   {sql_string(code)} AS group_code,
                   {sql_string(label)} AS group_label,
                   {band_case(f'{prefix}_share')} AS band_order
                   {selected_prefix}
            FROM school_indicator_base
            """
        )
    connection.execute(
        "CREATE OR REPLACE TEMP VIEW group_school_long AS " + " UNION ALL ".join(unions)
    )


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


def interaction_label(order: int) -> str:
    return {
        0: "0%",
        1: ">0-10%",
        2: ">10-25%",
        3: ">25-50%",
        4: ">50%",
    }[order]


def interaction_rows(
    connection: duckdb.DuckDBPyConnection,
    indicators: tuple[Indicator, ...],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for baseline_code in ("B0", "C0", "D0", "E0"):
        baseline_share = f"{baseline_code.lower()}_share"
        aggregates: list[str] = []
        for item in indicators:
            column = sql_identifier(item.code)
            aggregates.extend(
                [
                    f"AVG(CAST({column} AS DOUBLE)) AS school_{item.code}",
                    f"SUM(CASE WHEN {column} IS NOT NULL THEN a0_students * CAST({column} AS DOUBLE) END) "
                    f"/ NULLIF(SUM(CASE WHEN {column} IS NOT NULL THEN a0_students END), 0) "
                    f"AS a0_weighted_{item.code}",
                ]
            )
        cursor = connection.execute(
            f"""
            WITH banded AS (
                SELECT *,
                       {interaction_band_case('a0_share')} AS a0_band,
                       {interaction_band_case(baseline_share)} AS baseline_band
                FROM school_indicator_base
            )
            SELECT a0_band, baseline_band,
                   COUNT(*)::BIGINT AS schools,
                   SUM(a0_students)::BIGINT AS muslim_students,
                   {", ".join(aggregates)}
            FROM banded
            GROUP BY a0_band, baseline_band
            ORDER BY a0_band, baseline_band
            """
        )
        columns = [item[0] for item in cursor.description]
        records = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        for record in records:
            for item in indicators:
                for estimand in ("school", "a0_weighted"):
                    value = record[f"{estimand}_{item.code}"]
                    output.append(
                        {
                            "baseline_code": baseline_code,
                            "a0_band_order": record["a0_band"],
                            "a0_band": interaction_label(record["a0_band"]),
                            "baseline_band_order": record["baseline_band"],
                            "baseline_band": interaction_label(record["baseline_band"]),
                            "schools": record["schools"],
                            "muslim_students": record["muslim_students"],
                            "estimand": (
                                "equal-school mean"
                                if estimand == "school"
                                else "Muslim-student-weighted mean"
                            ),
                            "indicator_code": item.code,
                            "indicator_label": item.label,
                            "indicator_level": item.level,
                            "domain": item.domain,
                            "raw_value": value,
                            "display_value": (
                                value * display_multiplier(item)
                                if value is not None
                                else None
                            ),
                            "unit": display_unit(item),
                        }
                    )
    return output


def build_report(
    domain: str,
    indicators: tuple[Indicator, ...],
    national_exposures: list[dict[str, Any]],
    state_exposures: list[dict[str, Any]],
    district_exposures: list[dict[str, Any]],
) -> str:
    return "\n".join(
        [
            f"# {domain.replace('_', ' ').title()} A0 analysis",
            "",
            f"Indicators analysed: {len(indicators):,}",
            f"National exposure rows: {len(national_exposures):,}",
            f"State exposure rows: {len(state_exposures):,}",
            f"District exposure rows: {len(district_exposures):,}",
            "",
            "A0 Muslim students are the substantive population. B0 to E0 are comparison baselines.",
            "",
        ]
    )


def main() -> int:
    validate_registry()
    args = parse_args()
    indicators = domain_indicators(args.domain)
    if not indicators:
        raise RuntimeError(f"No indicators configured for domain {args.domain}")

    output = args.output / args.domain
    tables_dir = output / "tables"
    figures_dir = output / "figures"
    work_dir = output / "work"
    for directory in (tables_dir, figures_dir, work_dir):
        directory.mkdir(parents=True, exist_ok=True)

    print(f"Downloading the private indicator base for {args.domain}", flush=True)
    parquet_path = download_parquet(args, work_dir)
    connection = duckdb.connect()
    connection.execute("PRAGMA threads=2")
    connection.execute("PRAGMA memory_limit='4GB'")
    connection.execute("PRAGMA preserve_insertion_order=false")
    connection.execute(f"PRAGMA temp_directory={sql_string(str(work_dir / 'duckdb_temp'))}")
    try:
        print(f"Creating bounded views for {len(indicators)} indicators", flush=True)
        create_views(connection, parquet_path, indicators)

        print("Calculating national exposures and all baseline gaps", flush=True)
        national_exposures = group_exposure_rows(
            connection, ("group_code", "group_label"), indicators
        )
        national_gaps = baseline_gap_rows(national_exposures, keys=())
        pairwise_gaps = pairwise_gap_rows(national_exposures, keys=())

        print("Calculating concentration gradients", flush=True)
        gradients = concentration_gradient_rows(connection, indicators)

        print("Calculating state and district exposure tables", flush=True)
        state_exposures = group_exposure_rows(
            connection,
            ("state", "group_code", "group_label"),
            indicators,
        )
        state_gaps = baseline_gap_rows(state_exposures, keys=("state",))
        district_exposures = group_exposure_rows(
            connection,
            ("state", "district", "group_code", "group_label"),
            indicators,
        )
        district_gaps = baseline_gap_rows(
            district_exposures, keys=("state", "district")
        )

        print("Calculating A0-baseline interaction grids", flush=True)
        interactions = interaction_rows(connection, indicators)

        print("Calculating within-state and within-district A0 associations", flush=True)
        slopes = fixed_effect_slopes(
            connection, tuple(item.code for item in indicators)
        )

        outputs = {
            "national_group_exposures.csv": national_exposures,
            "national_a0_baseline_gaps.csv": national_gaps,
            "national_all_pairwise_gaps.csv": pairwise_gaps,
            "concentration_gradients.csv": gradients,
            "state_group_exposures.csv": state_exposures,
            "state_a0_baseline_gaps.csv": state_gaps,
            "district_group_exposures.csv": district_exposures,
            "district_a0_baseline_gaps.csv": district_gaps,
            "a0_baseline_interaction_grids.csv": interactions,
            "fixed_effect_a0_associations.csv": slopes,
        }
        for filename, rows in outputs.items():
            write_csv(tables_dir / filename, rows)

        print("Generating domain figures", flush=True)
        exposures_by_indicator: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in national_exposures:
            exposures_by_indicator[row["indicator_code"]].append(row)
        for item in indicators:
            save_bar_chart(
                exposures_by_indicator[item.code],
                f"{item.label}: Muslim exposure and comparison baselines",
                display_unit(item),
                figures_dir / "exposures" / f"{item.code}.png",
            )
            save_gradient_chart(
                gradients,
                item,
                figures_dir / "gradients" / f"{item.code}.png",
            )
        save_domain_gap_heatmaps(national_gaps, figures_dir / "gap_heatmaps")

        report = build_report(
            args.domain,
            indicators,
            national_exposures,
            state_exposures,
            district_exposures,
        )
        (output / "domain_report.md").write_text(report, encoding="utf-8")
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write(report)
        print(f"Completed {args.domain} analysis", flush=True)
    finally:
        connection.close()
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
