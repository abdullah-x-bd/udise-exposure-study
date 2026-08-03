from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import duckdb
import matplotlib

matplotlib.use("Agg")
from huggingface_hub import HfApi, hf_hub_download

from udise.comprehensive_a0_analysis import (
    BANDS,
    GROUPS,
    GROUP_ITEM,
    STAGES,
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
from udise.indicator_registry import (
    ALL_INDICATORS,
    CODEBOOK_REQUIRED_COLUMNS,
    SECONDARY_INDICATORS,
    TERTIARY_INDICATORS,
    Indicator,
    validate_registry,
)

SOURCE_PATHS = {
    "profile_1": "processed/2024_25/parquet/profile_1.parquet",
    "profile_2": "processed/2024_25/parquet/profile_2.parquet",
    "facility": "processed/2024_25/parquet/facility.parquet",
    "enrolment_1": "processed/2024_25/parquet/enrolment_1.parquet",
    "enrolment_2": "processed/2024_25/parquet/enrolment_2.parquet",
    "teacher": "processed/2024_25/parquet/teacher.parquet",
}
FOUNDATION_REMOTE = "processed/2024_25/analysis/foundation/social_foundation.parquet"
DOMAIN_REMOTE_TEMPLATE = "processed/2024_25/analysis/domains/{domain}.parquet"
SECONDARY_DOMAINS = (
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
)
DOMAIN_SOURCES = {
    "access": ("profile_2",),
    "infrastructure": ("facility",),
    "wash": ("facility",),
    "learning_environment": ("facility",),
    "digital": ("facility", "teacher"),
    "teachers": ("teacher", "facility"),
    "governance": ("profile_2",),
    "welfare": ("profile_2",),
    "inclusion": ("facility", "teacher"),
    "vulnerability": (),
    "age_grade": (),
}
FOUNDATION_ESSENTIAL = (
    "pseudocode",
    "state",
    "district",
    "block",
    "rural_urban",
    "school_category",
    "school_type",
    "managment",
    "lowclass",
    "highclass",
    "minority_school",
    "shift_school",
    "resi_school",
    "total_students",
    "total_boys",
    "total_girls",
    "a0_students",
    "a0_boys",
    "a0_girls",
    "a0_share",
    "b0_students",
    "b0_boys",
    "b0_girls",
    "b0_share",
    "c0_students",
    "c0_boys",
    "c0_girls",
    "c0_share",
    "d0_students",
    "d0_boys",
    "d0_girls",
    "d0_share",
    "e0_students",
    "e0_boys",
    "e0_girls",
    "e0_share",
)
PRIMARY_SUMMARY_COLUMNS = {
    "profile_1": (
        "lowclass",
        "highclass",
        "avg_instr_days",
        "same_sch_b",
        "same_sch_g",
        "other_sch_b",
        "other_sch_g",
        "anganwadi_ecce_b",
        "anganwadi_ecce_g",
    ),
    "profile_2": (
        "acad_inspections",
        "crc_coordinator",
        "block_level_officers",
        "district_officers",
        "smc_smdc_meetings",
        "grants_receipt",
        "grants_expenditure",
    ),
    "facility": (
        "no_building_blocks",
        "pucca_building_blocks",
        "total_class_rooms",
        "other_rooms",
        "classrooms_in_good_condition",
        "classrooms_needs_minor_repair",
        "classrooms_needs_major_repair",
        "total_boys_toilet",
        "total_boys_func_toilet",
        "total_girls_toilet",
        "total_girls_func_toilet",
        "total_boys_cwsn_toilet",
        "func_boys_cwsn_friendly",
        "total_girls_cwsn_toilet",
        "func_girls_cwsn_friendly",
        "urinal_boys",
        "urinal_girls",
        "laptop",
        "tablet",
        "desktop",
        "digiboard",
        "teachdev_tot",
        "server_tot",
        "smart_class_tv_tot",
        "projector",
        "printer",
    ),
    "teacher": (
        "total_tch",
        "male",
        "female",
        "transgender",
        "gen_tch",
        "sc_tch",
        "st_tch",
        "obc_tch",
        "regular",
        "contract",
        "part_time",
        "below_graduate",
        "graduate",
        "post_graduate_and_above",
        "trained_comp",
        "trained_cwsn",
        "teacher_involve_non_training_assignment",
    ),
}


def log(message: str) -> None:
    print(f"[domain-native-a0] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("foundation", "source", "domain", "tertiary", "aggregate"),
    )
    parser.add_argument("--domain", choices=SECONDARY_DOMAINS + ("tertiary",))
    parser.add_argument("--output", type=Path, default=Path("outputs/domain_native_a0"))
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    parser.add_argument("--foundation-path", type=Path)
    parser.add_argument("--domain-path", type=Path)
    parser.add_argument("--upload", action="store_true")
    return parser.parse_args()


def require_private_source(args: argparse.Namespace) -> None:
    if not args.dataset_repo:
        raise RuntimeError("HF_DATASET_REPO is not configured")
    if not args.token:
        raise RuntimeError("HF_TOKEN is not configured")


def configure_connection(work_dir: Path, memory_limit: str = "4GB") -> duckdb.DuckDBPyConnection:
    temp_dir = work_dir / "duckdb_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute("SET threads=2")
    connection.execute(f"SET memory_limit={sql_string(memory_limit)}")
    connection.execute("SET preserve_insertion_order=false")
    connection.execute(f"SET temp_directory={sql_string(str(temp_dir))}")
    connection.execute("SET max_temp_directory_size='10GB'")
    return connection


def download_one(repo_id: str, token: str, remote_path: str, local_dir: Path) -> Path:
    return Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=remote_path,
            repo_type="dataset",
            token=token,
            local_dir=local_dir,
        )
    )


def source_files(args: argparse.Namespace, names: Iterable[str], work_dir: Path) -> dict[str, Path]:
    require_private_source(args)
    files: dict[str, Path] = {}
    for name in names:
        log(f"Downloading {name} Parquet")
        files[name] = download_one(
            args.dataset_repo,
            args.token,
            SOURCE_PATHS[name],
            work_dir,
        )
    return files


def foundation_file(args: argparse.Namespace, work_dir: Path) -> Path:
    if args.foundation_path:
        return args.foundation_path
    require_private_source(args)
    log("Downloading social foundation")
    return download_one(args.dataset_repo, args.token, FOUNDATION_REMOTE, work_dir)


def domain_file(args: argparse.Namespace, domain: str, work_dir: Path) -> Path:
    if args.domain_path:
        return args.domain_path
    require_private_source(args)
    log(f"Downloading {domain} domain file")
    return download_one(
        args.dataset_repo,
        args.token,
        DOMAIN_REMOTE_TEMPLATE.format(domain=domain),
        work_dir,
    )


def upload_file(args: argparse.Namespace, local_path: Path, remote_path: str, message: str) -> None:
    require_private_source(args)
    HfApi(token=args.token).upload_file(
        path_or_fileobj=str(local_path),
        path_in_repo=remote_path,
        repo_id=args.dataset_repo,
        repo_type="dataset",
        commit_message=message,
    )


def all_class_expression(suffixes: tuple[str, ...] = ("b", "g")) -> str:
    return " + ".join(
        f"COALESCE(c{class_number}_{suffix}, 0)"
        for class_number in range(1, 13)
        for suffix in suffixes
    )


def stage_expression(classes: tuple[int, ...], suffixes: tuple[str, ...] = ("b", "g")) -> str:
    return " + ".join(
        f"COALESCE(c{class_number}_{suffix}, 0)"
        for class_number in classes
        for suffix in suffixes
    )


def social_aggregation_select() -> str:
    all_students = all_class_expression()
    boys = all_class_expression(("b",))
    girls = all_class_expression(("g",))
    terms: list[str] = []
    for code, (item_group, item_id) in GROUP_ITEM.items():
        prefix = code.lower()
        terms.extend(
            [
                f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN {all_students} ELSE 0 END) AS {prefix}_students",
                f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN {boys} ELSE 0 END) AS {prefix}_boys",
                f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN {girls} ELSE 0 END) AS {prefix}_girls",
            ]
        )
        for stage, _, classes in STAGES:
            terms.extend(
                [
                    f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN {stage_expression(classes)} ELSE 0 END) AS {prefix}_{stage}",
                    f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN {stage_expression(classes, ('b',))} ELSE 0 END) AS {prefix}_{stage}_boys",
                    f"SUM(CASE WHEN item_group={item_group} AND item_id={item_id} THEN {stage_expression(classes, ('g',))} ELSE 0 END) AS {prefix}_{stage}_girls",
                ]
            )
    for name, item_id in (
        ("christian_students", 6),
        ("sikh_students", 7),
        ("buddhist_students", 8),
        ("parsi_students", 9),
        ("jain_students", 10),
    ):
        terms.append(
            f"SUM(CASE WHEN item_group=2 AND item_id={item_id} THEN {all_students} ELSE 0 END) AS {name}"
        )
    terms.extend(
        [
            f"SUM(CASE WHEN item_group=3 AND item_id=13 THEN {all_students} ELSE 0 END) AS bpl_students",
            f"SUM(CASE WHEN item_group=10 AND item_id=32 THEN {all_students} ELSE 0 END) AS ews_students",
            f"SUM(CASE WHEN item_group=5 AND item_id=0 THEN {all_students} ELSE 0 END) AS repeater_students",
            f"SUM(CASE WHEN item_group=4 THEN {all_students} ELSE 0 END) AS cwsn_students",
        ]
    )
    return ",\n".join(terms)


def age_grade_select() -> tuple[str, str, str, str]:
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
        on_terms.append(
            f"CASE WHEN item_id BETWEEN {nominal_age - 1} AND {nominal_age + 1} THEN {count} ELSE 0 END"
        )
    return (
        " + ".join(total_terms),
        " + ".join(over_terms),
        " + ".join(under_terms),
        " + ".join(on_terms),
    )


def build_foundation(args: argparse.Namespace) -> int:
    validate_registry()
    output = args.output / "foundation"
    work_dir = output / "work"
    output.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    files = source_files(args, ("profile_1", "enrolment_1", "enrolment_2"), work_dir)
    social_path = work_dir / "social_composition.parquet"
    age_path = work_dir / "age_grade.parquet"
    foundation_path = work_dir / "social_foundation.parquet"
    connection = configure_connection(work_dir)
    try:
        log("Aggregating social composition directly from Enrolment 1")
        connection.execute(
            f"""
            COPY (
                WITH social_raw AS (
                    SELECT pseudocode, {social_aggregation_select()}
                    FROM read_parquet({sql_string(str(files['enrolment_1']))})
                    GROUP BY pseudocode
                )
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
                      - (a0_students + christian_students + sikh_students
                         + buddhist_students + parsi_students + jain_students)
                      AS religion_residual_students
                FROM social_raw
            ) TO {sql_string(str(social_path))}
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
            """
        )
        log("Aggregating school age-grade conditions directly from Enrolment 2")
        total_age, over_age, under_age, on_age = age_grade_select()
        connection.execute(
            f"""
            COPY (
                SELECT pseudocode,
                       SUM({total_age}) AS age_class_students,
                       SUM({over_age}) AS over_age_students,
                       SUM({under_age}) AS under_age_students,
                       SUM({on_age}) AS on_age_students
                FROM read_parquet({sql_string(str(files['enrolment_2']))})
                WHERE item_group = 8
                GROUP BY pseudocode
            ) TO {sql_string(str(age_path))}
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
            """
        )
        log("Joining compact social and age outputs to Profile 1")
        connection.execute(
            f"""
            COPY (
                SELECT p.*,
                       s.* EXCLUDE (pseudocode),
                       a.* EXCLUDE (pseudocode)
                FROM read_parquet({sql_string(str(files['profile_1']))}) AS p
                INNER JOIN read_parquet({sql_string(str(social_path))}) AS s
                    USING (pseudocode)
                LEFT JOIN read_parquet({sql_string(str(age_path))}) AS a
                    USING (pseudocode)
                WHERE s.total_students > 0
            ) TO {sql_string(str(foundation_path))}
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
            """
        )
        rows = int(
            connection.execute(
                f"SELECT COUNT(*) FROM read_parquet({sql_string(str(foundation_path))})"
            ).fetchone()[0]
        )
        columns = len(
            connection.execute(
                f"DESCRIBE SELECT * FROM read_parquet({sql_string(str(foundation_path))})"
            ).fetchall()
        )
        manifest = {
            "rows": rows,
            "columns": columns,
            "bytes": foundation_path.stat().st_size,
            "remote_path": FOUNDATION_REMOTE,
        }
        (output / "foundation_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        report = "\n".join(
            [
                "# Social foundation built",
                "",
                f"School rows: {rows:,}",
                f"Columns: {columns:,}",
                f"Size: {foundation_path.stat().st_size / (1024 ** 2):.1f} MiB",
                "",
            ]
        )
        (output / "foundation_report.md").write_text(report, encoding="utf-8")
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write(report)
        if args.upload:
            log("Uploading private social foundation")
            upload_file(
                args,
                foundation_path,
                FOUNDATION_REMOTE,
                "Build compact UDISE 2024-25 social foundation",
            )
    finally:
        connection.close()
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


def schema_columns(connection: duckdb.DuckDBPyConnection, path: Path) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            f"DESCRIBE SELECT * FROM read_parquet({sql_string(str(path))})"
        ).fetchall()
    ]


def expression_tokens(expression: str) -> set[str]:
    quoted = re.findall(r'"([^"]+)"', expression)
    plain = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", re.sub(r'"[^"]+"', " ", expression))
    return set(quoted) | set(plain)


def indicators_for_domain(domain: str) -> tuple[Indicator, ...]:
    return tuple(item for item in SECONDARY_INDICATORS if item.domain == domain)


def build_domain(args: argparse.Namespace) -> int:
    if not args.domain or args.domain not in SECONDARY_DOMAINS:
        raise ValueError("A secondary --domain is required")
    validate_registry()
    domain = args.domain
    indicators = indicators_for_domain(domain)
    if not indicators:
        raise RuntimeError(f"No indicators configured for {domain}")
    output = args.output / "domains" / domain
    work_dir = output / "work"
    output.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    foundation = foundation_file(args, work_dir)
    sources = source_files(args, DOMAIN_SOURCES[domain], work_dir)
    domain_path = work_dir / f"{domain}.parquet"
    connection = configure_connection(work_dir)
    try:
        foundation_columns = set(schema_columns(connection, foundation))
        source_columns = {name: set(schema_columns(connection, path)) for name, path in sources.items()}
        referenced = set().union(*(expression_tokens(item.expression) for item in indicators))
        foundation_needed = set(FOUNDATION_ESSENTIAL) | (referenced & foundation_columns)
        source_needed: dict[str, set[str]] = {name: set() for name in sources}
        unresolved: set[str] = set()
        for token in referenced - foundation_columns:
            matches = [name for name, columns in source_columns.items() if token in columns]
            if len(matches) == 1:
                source_needed[matches[0]].add(token)
            elif len(matches) > 1:
                raise RuntimeError(f"Ambiguous source column {token}: {matches}")
            elif token.lower() not in {
                "case", "when", "then", "else", "end", "and", "or", "not",
                "null", "is", "in", "between", "as", "double", "cast", "coalesce",
                "nullif", "true", "false",
            }:
                unresolved.add(token)
        indicator_codes = {item.code for item in indicators}
        unresolved -= indicator_codes
        if unresolved:
            raise RuntimeError(f"Unresolved expression identifiers for {domain}: {sorted(unresolved)}")

        joined_select = [
            f"f.{sql_identifier(column)} AS {sql_identifier(column)}"
            for column in FOUNDATION_ESSENTIAL
        ]
        for column in sorted(foundation_needed - set(FOUNDATION_ESSENTIAL)):
            joined_select.append(f"f.{sql_identifier(column)} AS {sql_identifier(column)}")
        joins: list[str] = []
        for index, (name, path) in enumerate(sources.items(), start=1):
            alias = f"s{index}"
            joins.append(
                f"LEFT JOIN read_parquet({sql_string(str(path))}) AS {alias} USING (pseudocode)"
            )
            for column in sorted(source_needed[name]):
                joined_select.append(f"{alias}.{sql_identifier(column)} AS {sql_identifier(column)}")
        indicator_select = ",\n".join(
            f"({item.expression}) AS {sql_identifier(item.code)}" for item in indicators
        )
        essential_select = ", ".join(sql_identifier(column) for column in FOUNDATION_ESSENTIAL)
        log(f"Building {domain} file with {len(indicators)} indicators")
        connection.execute(
            f"""
            COPY (
                WITH joined AS (
                    SELECT {", ".join(joined_select)}
                    FROM read_parquet({sql_string(str(foundation))}) AS f
                    {' '.join(joins)}
                )
                SELECT {essential_select},
                       {indicator_select}
                FROM joined
            ) TO {sql_string(str(domain_path))}
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
            """
        )
        rows = int(
            connection.execute(
                f"SELECT COUNT(*) FROM read_parquet({sql_string(str(domain_path))})"
            ).fetchone()[0]
        )
        manifest = {
            "domain": domain,
            "rows": rows,
            "indicators": len(indicators),
            "bytes": domain_path.stat().st_size,
            "remote_path": DOMAIN_REMOTE_TEMPLATE.format(domain=domain),
        }
        (output / "domain_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        if args.upload:
            log(f"Uploading private {domain} domain file")
            upload_file(
                args,
                domain_path,
                DOMAIN_REMOTE_TEMPLATE.format(domain=domain),
                f"Build UDISE 2024-25 {domain} indicator domain",
            )
        args.domain_path = domain_path
        aggregate_domain(args, local_output=output / "analysis")
    finally:
        connection.close()
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


def tertiary_initial_groups() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    initial_codes = (
        "access_deprivation_index",
        "infrastructure_deprivation_index",
        "wash_deprivation_index",
        "digital_deprivation_index",
        "teacher_capacity_deprivation_index",
        "governance_response_deficit_index",
        "welfare_support_deficit_index",
        "inclusion_failure_index",
        "gendered_school_disadvantage_index",
    )
    middle_codes = (
        "educational_resource_deficit_index",
        "institutional_need_index",
        "overall_multidimensional_deprivation_index",
    )
    remaining_codes = ("institutional_neglect_index", "vulnerability_context_index")
    final_codes = ("compound_vulnerability_deprivation_index",)
    return initial_codes, middle_codes, remaining_codes, final_codes


def build_tertiary(args: argparse.Namespace) -> int:
    output = args.output / "domains" / "tertiary"
    work_dir = output / "work"
    output.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    foundation = foundation_file(args, work_dir)
    domain_paths = {
        domain: download_one(
            args.dataset_repo,
            args.token,
            DOMAIN_REMOTE_TEMPLATE.format(domain=domain),
            work_dir,
        )
        for domain in SECONDARY_DOMAINS
    }
    connection = configure_connection(work_dir)
    tertiary_path = work_dir / "tertiary.parquet"
    try:
        domain_columns = {
            domain: set(schema_columns(connection, path))
            for domain, path in domain_paths.items()
        }
        all_secondary_codes = {item.code for item in SECONDARY_INDICATORS}
        required_secondary = set().union(
            *(expression_tokens(item.expression) & all_secondary_codes for item in TERTIARY_INDICATORS)
        )
        joined_select = [
            f"f.{sql_identifier(column)} AS {sql_identifier(column)}"
            for column in FOUNDATION_ESSENTIAL
        ]
        joins: list[str] = []
        for index, (domain, path) in enumerate(domain_paths.items(), start=1):
            alias = f"d{index}"
            needed = sorted(required_secondary & domain_columns[domain])
            if not needed:
                continue
            joins.append(
                f"LEFT JOIN read_parquet({sql_string(str(path))}) AS {alias} USING (pseudocode)"
            )
            for column in needed:
                joined_select.append(f"{alias}.{sql_identifier(column)} AS {sql_identifier(column)}")
        initial_codes, middle_codes, _, _ = tertiary_initial_groups()
        registry = {item.code: item for item in TERTIARY_INDICATORS}
        initial_select = ", ".join(
            f"({registry[code].expression}) AS {sql_identifier(code)}" for code in initial_codes
        )
        middle_select = ", ".join(
            f"({registry[code].expression}) AS {sql_identifier(code)}" for code in middle_codes
        )
        neglect = registry["institutional_neglect_index"]
        vulnerability = registry["vulnerability_context_index"]
        compound = registry["compound_vulnerability_deprivation_index"]
        essential_select = ", ".join(sql_identifier(column) for column in FOUNDATION_ESSENTIAL)
        log("Building compact tertiary indicator domain")
        connection.execute(
            f"""
            COPY (
                WITH joined AS (
                    SELECT {", ".join(joined_select)}
                    FROM read_parquet({sql_string(str(foundation))}) AS f
                    {' '.join(joins)}
                ),
                initial AS (
                    SELECT *, {initial_select}
                    FROM joined
                ),
                middle AS (
                    SELECT *, {middle_select}
                    FROM initial
                ),
                ranked AS (
                    SELECT *,
                        CASE WHEN bpl_share IS NOT NULL THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY bpl_share) END AS bpl_percentile,
                        CASE WHEN ews_share IS NOT NULL THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY ews_share) END AS ews_percentile,
                        CASE WHEN repeater_share IS NOT NULL THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY repeater_share) END AS repeater_percentile,
                        CASE WHEN cwsn_share IS NOT NULL THEN PERCENT_RANK() OVER (PARTITION BY state ORDER BY cwsn_share) END AS cwsn_percentile
                    FROM middle
                ),
                remaining AS (
                    SELECT *,
                           ({neglect.expression}) AS institutional_neglect_index,
                           ({vulnerability.expression}) AS vulnerability_context_index
                    FROM ranked
                )
                SELECT {essential_select},
                       {", ".join(sql_identifier(item.code) for item in TERTIARY_INDICATORS[:-1])},
                       ({compound.expression}) AS compound_vulnerability_deprivation_index
                FROM remaining
            ) TO {sql_string(str(tertiary_path))}
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
            """
        )
        rows = int(
            connection.execute(
                f"SELECT COUNT(*) FROM read_parquet({sql_string(str(tertiary_path))})"
            ).fetchone()[0]
        )
        manifest = {
            "domain": "tertiary",
            "rows": rows,
            "indicators": len(TERTIARY_INDICATORS),
            "bytes": tertiary_path.stat().st_size,
            "remote_path": DOMAIN_REMOTE_TEMPLATE.format(domain="tertiary"),
        }
        (output / "domain_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        if args.upload:
            log("Uploading private tertiary domain file")
            upload_file(
                args,
                tertiary_path,
                DOMAIN_REMOTE_TEMPLATE.format(domain="tertiary"),
                "Build UDISE 2024-25 tertiary structural indicators",
            )
        args.domain = "tertiary"
        args.domain_path = tertiary_path
        aggregate_domain(args, local_output=output / "analysis")
    finally:
        connection.close()
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


def domain_indicators(domain: str) -> tuple[Indicator, ...]:
    if domain == "tertiary":
        return TERTIARY_INDICATORS
    return indicators_for_domain(domain)


def create_group_long_view(
    connection: duckdb.DuckDBPyConnection,
    domain_path: Path,
    indicators: tuple[Indicator, ...],
) -> None:
    source = f"read_parquet({sql_string(str(domain_path))})"
    connection.execute(
        f"CREATE OR REPLACE TEMP VIEW school_indicator_base AS SELECT * FROM {source}"
    )
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
    return {0: "0%", 1: ">0-10%", 2: ">10-25%", 3: ">25-50%", 4: ">50%"}[order]


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
                    f"SUM(CASE WHEN {column} IS NOT NULL THEN a0_students * CAST({column} AS DOUBLE) END) / NULLIF(SUM(CASE WHEN {column} IS NOT NULL THEN a0_students END), 0) AS a0_weighted_{item.code}",
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
                            "estimand": "equal-school mean" if estimand == "school" else "Muslim-student-weighted mean",
                            "indicator_code": item.code,
                            "indicator_label": item.label,
                            "indicator_level": item.level,
                            "domain": item.domain,
                            "raw_value": value,
                            "display_value": value * display_multiplier(item) if value is not None else None,
                            "unit": display_unit(item),
                        }
                    )
    return output


def aggregate_domain(args: argparse.Namespace, local_output: Path | None = None) -> int:
    if not args.domain:
        raise ValueError("--domain is required")
    domain = args.domain
    indicators = domain_indicators(domain)
    output = local_output or args.output / "analysis" / domain
    tables_dir = output / "tables"
    figures_dir = output / "figures"
    work_dir = output / "work"
    for directory in (tables_dir, figures_dir, work_dir):
        directory.mkdir(parents=True, exist_ok=True)
    path = domain_file(args, domain, work_dir)
    connection = configure_connection(work_dir, memory_limit="3GB")
    try:
        create_group_long_view(connection, path, indicators)
        log(f"Calculating {domain} national exposures and baseline gaps")
        national_exposures = group_exposure_rows(
            connection, ("group_code", "group_label"), indicators
        )
        national_gaps = baseline_gap_rows(national_exposures, keys=())
        pairwise = pairwise_gap_rows(national_exposures, keys=())
        gradients = concentration_gradient_rows(connection, indicators)
        log(f"Calculating {domain} state and district outputs")
        state_exposures = group_exposure_rows(
            connection, ("state", "group_code", "group_label"), indicators
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
        interactions = interaction_rows(connection, indicators)
        slopes = fixed_effect_slopes(connection, tuple(item.code for item in indicators))
        outputs = {
            "national_group_exposures.csv": national_exposures,
            "national_a0_baseline_gaps.csv": national_gaps,
            "national_all_pairwise_gaps.csv": pairwise,
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
        report = "\n".join(
            [
                f"# {domain.replace('_', ' ').title()} A0 analysis",
                "",
                f"Indicators: {len(indicators):,}",
                f"National exposure rows: {len(national_exposures):,}",
                f"State exposure rows: {len(state_exposures):,}",
                f"District exposure rows: {len(district_exposures):,}",
                "",
            ]
        )
        (output / "domain_report.md").write_text(report, encoding="utf-8")
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write(report)
    finally:
        connection.close()
        if not args.domain_path:
            shutil.rmtree(work_dir, ignore_errors=True)
    return 0


def query_dicts(connection: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, Any]]:
    cursor = connection.execute(query)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def source_inventory(
    connection: duckdb.DuckDBPyConnection,
    paths: dict[str, Path],
) -> list[dict[str, Any]]:
    codebook = {column for column, _ in CODEBOOK_REQUIRED_COLUMNS}
    rows: list[dict[str, Any]] = []
    for source, path in paths.items():
        schema = connection.execute(
            f"DESCRIBE SELECT * FROM read_parquet({sql_string(str(path))})"
        ).fetchall()
        for ordinal, record in enumerate(schema, start=1):
            column = record[0]
            rows.append(
                {
                    "source_table": source,
                    "ordinal": ordinal,
                    "column": column,
                    "data_type": record[1],
                    "nullable": record[2],
                    "primary_indicator": True,
                    "codebook_required": f"{source}.{column}" in codebook,
                    "analysis_role": "school identifier" if column == "pseudocode" else "directly recorded parameter",
                }
            )
    return rows


def primary_summary(
    connection: duckdb.DuckDBPyConnection,
    paths: dict[str, Path],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, columns in PRIMARY_SUMMARY_COLUMNS.items():
        path = paths[source]
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
                FROM read_parquet({sql_string(str(path))})
                """
            ).fetchone()
            rows.append(
                {
                    "source_table": source,
                    "column": column,
                    "rows": record[0],
                    "nonmissing": record[1],
                    "missing": record[0] - record[1],
                    "minimum": record[2],
                    "p10": record[3],
                    "median": record[4],
                    "mean": record[5],
                    "p90": record[6],
                    "maximum": record[7],
                }
            )
    return rows


def raw_code_audit(
    connection: duckdb.DuckDBPyConnection,
    paths: dict[str, Path],
    foundation: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for qualified, description in CODEBOOK_REQUIRED_COLUMNS:
        source, column = qualified.split(".", 1)
        path = paths[source]
        records = query_dicts(
            connection,
            f"""
            SELECT CAST(t.{sql_identifier(column)} AS VARCHAR) AS raw_code,
                   COUNT(*)::BIGINT AS schools,
                   SUM(f.a0_students)::BIGINT AS a0_students,
                   SUM(f.b0_students)::BIGINT AS b0_students,
                   SUM(f.c0_students)::BIGINT AS c0_students,
                   SUM(f.d0_students)::BIGINT AS d0_students,
                   SUM(f.e0_students)::BIGINT AS e0_students,
                   SUM(f.total_students)::BIGINT AS total_students,
                   SUM(f.a0_students) * 100.0 / NULLIF(SUM(f.total_students), 0) AS muslim_share_percent
            FROM read_parquet({sql_string(str(path))}) AS t
            LEFT JOIN read_parquet({sql_string(str(foundation))}) AS f USING (pseudocode)
            GROUP BY t.{sql_identifier(column)}
            ORDER BY TRY_CAST(t.{sql_identifier(column)} AS DOUBLE), raw_code
            """,
        )
        for record in records:
            rows.append(
                {
                    "source_table": source,
                    "column": column,
                    "description": description,
                    **record,
                    "interpretation_status": "raw code only; UDISE DCF required",
                }
            )
    return rows


def group_totals_from_foundation(
    connection: duckdb.DuckDBPyConnection,
    foundation: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total = int(
        connection.execute(
            f"SELECT SUM(total_students) FROM read_parquet({sql_string(str(foundation))})"
        ).fetchone()[0]
        or 0
    )
    schools = int(
        connection.execute(
            f"SELECT COUNT(*) FROM read_parquet({sql_string(str(foundation))})"
        ).fetchone()[0]
    )
    for code, label in GROUPS:
        prefix = code.lower()
        record = connection.execute(
            f"""
            SELECT SUM({prefix}_students)::BIGINT,
                   SUM({prefix}_boys)::BIGINT,
                   SUM({prefix}_girls)::BIGINT,
                   SUM(({prefix}_students > 0)::INTEGER)::BIGINT
            FROM read_parquet({sql_string(str(foundation))})
            """
        ).fetchone()
        rows.append(
            {
                "group_code": code,
                "group_label": label,
                "students": int(record[0] or 0),
                "boys": int(record[1] or 0),
                "girls": int(record[2] or 0),
                "national_share_percent": int(record[0] or 0) * 100.0 / total if total else None,
                "schools_with_group": int(record[3] or 0),
                "schools": schools,
            }
        )
    return rows


def stage_rows_from_foundation(
    connection: duckdb.DuckDBPyConnection,
    foundation: Path,
    by_state: bool = False,
) -> list[dict[str, Any]]:
    geography = "state," if by_state else ""
    group_by = "GROUP BY state" if by_state else ""
    rows: list[dict[str, Any]] = []
    for stage_order, (stage, label, _) in enumerate(STAGES):
        sums = ", ".join(
            f"SUM({code.lower()}_{stage}) AS {code.lower()}" for code, _ in GROUPS
        )
        records = query_dicts(
            connection,
            f"SELECT {geography} {sums} FROM read_parquet({sql_string(str(foundation))}) {group_by}",
        )
        for record in records:
            total = sum(int(record[code.lower()] or 0) for code, _ in GROUPS[1:])
            for code, group_label in GROUPS:
                students = int(record[code.lower()] or 0)
                row = {
                    "stage_order": stage_order,
                    "stage": label,
                    "group_code": code,
                    "group_label": group_label,
                    "students": students,
                    "share_percent": students * 100.0 / total if total else None,
                }
                if by_state:
                    row["state"] = record["state"]
                rows.append(row)
    return rows


def class_representation(
    connection: duckdb.DuckDBPyConnection,
    enrolment: Path,
    profile: Path,
    by_state: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for class_number in range(1, 13):
        geography_select = "p.state," if by_state else ""
        geography_group = "p.state," if by_state else ""
        records = query_dicts(
            connection,
            f"""
            SELECT {geography_select} e.item_group, e.item_id,
                   SUM(e.c{class_number}_b)::BIGINT AS boys,
                   SUM(e.c{class_number}_g)::BIGINT AS girls
            FROM read_parquet({sql_string(str(enrolment))}) AS e
            {f'JOIN read_parquet({sql_string(str(profile))}) AS p USING (pseudocode)' if by_state else ''}
            WHERE (e.item_group=2 AND e.item_id=5)
               OR (e.item_group=1 AND e.item_id IN (1,2,3,4))
            GROUP BY {geography_group} e.item_group, e.item_id
            """,
        )
        lookup = {value: code for code, value in GROUP_ITEM.items()}
        totals: dict[str, int] = defaultdict(int)
        for record in records:
            code = lookup[(record["item_group"], record["item_id"])]
            key = record.get("state", "__national__")
            totals[key] += (
                int(record["boys"] or 0) + int(record["girls"] or 0)
                if code != "A0"
                else 0
            )
        for record in records:
            code = lookup[(record["item_group"], record["item_id"])]
            key = record.get("state", "__national__")
            students = int(record["boys"] or 0) + int(record["girls"] or 0)
            row = {
                "class_order": class_number,
                "class": f"Class {class_number}",
                "group_code": code,
                "group_label": dict(GROUPS)[code],
                "boys": int(record["boys"] or 0),
                "girls": int(record["girls"] or 0),
                "students": students,
                "share_percent": students * 100.0 / totals[key] if totals[key] else None,
            }
            if by_state:
                row["state"] = record["state"]
            rows.append(row)
    return rows


def concentration_distribution_from_foundation(
    connection: duckdb.DuckDBPyConnection,
    foundation: Path,
    by_state: bool = False,
) -> list[dict[str, Any]]:
    unions: list[str] = []
    for code, label in GROUPS:
        prefix = code.lower()
        unions.append(
            f"""
            SELECT state, {sql_string(code)} AS group_code,
                   {sql_string(label)} AS group_label,
                   {prefix}_students AS group_students,
                   {band_case(f'{prefix}_share')} AS band_order
            FROM read_parquet({sql_string(str(foundation))})
            """
        )
    geography = "state," if by_state else ""
    partition = "state, group_code" if by_state else "group_code"
    group_by = (
        "state, group_code, group_label, band_order"
        if by_state
        else "group_code, group_label, band_order"
    )
    return query_dicts(
        connection,
        f"""
        WITH long AS ({' UNION ALL '.join(unions)})
        SELECT {geography} group_code, group_label, band_order,
               CASE
                   WHEN band_order=0 THEN '0%'
                   WHEN band_order=1 THEN '>0-5%'
                   WHEN band_order=2 THEN '>5-10%'
                   WHEN band_order=3 THEN '>10-20%'
                   WHEN band_order=4 THEN '>20-30%'
                   WHEN band_order=5 THEN '>30-40%'
                   WHEN band_order=6 THEN '>40-50%'
                   WHEN band_order=7 THEN '>50-75%'
                   ELSE '>75-100%'
               END AS band,
               COUNT(*)::BIGINT AS schools,
               SUM(group_students)::BIGINT AS group_students,
               COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY {partition}) AS school_share_percent,
               SUM(group_students) * 100.0 / NULLIF(SUM(SUM(group_students)) OVER (PARTITION BY {partition}), 0) AS group_student_share_percent
        FROM long
        GROUP BY {group_by}
        ORDER BY {geography} group_code, band_order
        """,
    )


def teacher_representation_from_files(
    connection: duckdb.DuckDBPyConnection,
    teacher: Path,
    foundation: Path,
    by_state: bool = False,
) -> list[dict[str, Any]]:
    geography = "f.state," if by_state else ""
    group_by = "GROUP BY f.state" if by_state else ""
    records = query_dicts(
        connection,
        f"""
        SELECT {geography}
               SUM(t.gen_tch)::DOUBLE AS b0_teachers,
               SUM(t.sc_tch)::DOUBLE AS c0_teachers,
               SUM(t.st_tch)::DOUBLE AS d0_teachers,
               SUM(t.obc_tch)::DOUBLE AS e0_teachers,
               SUM(t.total_tch)::DOUBLE AS total_teachers,
               SUM(f.b0_students)::DOUBLE AS b0_students,
               SUM(f.c0_students)::DOUBLE AS c0_students,
               SUM(f.d0_students)::DOUBLE AS d0_students,
               SUM(f.e0_students)::DOUBLE AS e0_students,
               SUM(f.total_students)::DOUBLE AS total_students
        FROM read_parquet({sql_string(str(teacher))}) AS t
        JOIN read_parquet({sql_string(str(foundation))}) AS f USING (pseudocode)
        {group_by}
        """,
    )
    rows: list[dict[str, Any]] = []
    for record in records:
        for code, label in GROUPS[1:]:
            prefix = code.lower()
            teacher_share = (
                record[f"{prefix}_teachers"] / record["total_teachers"]
                if record["total_teachers"]
                else None
            )
            student_share = (
                record[f"{prefix}_students"] / record["total_students"]
                if record["total_students"]
                else None
            )
            row = {
                "group_code": code,
                "group_label": label,
                "teacher_share_percent": teacher_share * 100 if teacher_share is not None else None,
                "student_share_percent": student_share * 100 if student_share is not None else None,
                "teacher_minus_student_percentage_points": (
                    (teacher_share - student_share) * 100
                    if teacher_share is not None and student_share is not None
                    else None
                ),
            }
            if by_state:
                row["state"] = record["state"]
            rows.append(row)
    return rows


def build_source_analysis(args: argparse.Namespace) -> int:
    output = args.output / "source"
    work_dir = output / "work"
    tables_dir = output / "tables"
    output.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    foundation = foundation_file(args, work_dir)
    paths = source_files(args, SOURCE_PATHS.keys(), work_dir)
    connection = configure_connection(work_dir, memory_limit="3GB")
    try:
        log("Cataloguing all direct source columns")
        inventory = source_inventory(connection, paths)
        log("Summarising direct numeric parameters")
        numeric = primary_summary(connection, paths)
        log("Auditing all DCF-dependent raw code distributions")
        codes = raw_code_audit(connection, paths, foundation)
        totals = group_totals_from_foundation(connection, foundation)
        stages = stage_rows_from_foundation(connection, foundation)
        state_stages = stage_rows_from_foundation(connection, foundation, by_state=True)
        national_classes = class_representation(
            connection, paths["enrolment_1"], paths["profile_1"]
        )
        state_classes = class_representation(
            connection,
            paths["enrolment_1"],
            paths["profile_1"],
            by_state=True,
        )
        distribution = concentration_distribution_from_foundation(connection, foundation)
        state_distribution = concentration_distribution_from_foundation(
            connection, foundation, by_state=True
        )
        teacher_national = teacher_representation_from_files(
            connection, paths["teacher"], foundation
        )
        teacher_state = teacher_representation_from_files(
            connection, paths["teacher"], foundation, by_state=True
        )
        outputs = {
            "primary_source_column_inventory.csv": inventory,
            "primary_numeric_summary.csv": numeric,
            "dcf_raw_code_audit.csv": codes,
            "national_group_totals.csv": totals,
            "national_stage_representation.csv": stages,
            "state_stage_representation.csv": state_stages,
            "national_class_representation.csv": national_classes,
            "state_class_representation.csv": state_classes,
            "national_concentration_distribution.csv": distribution,
            "state_concentration_distribution.csv": state_distribution,
            "national_teacher_social_category_representation.csv": teacher_national,
            "state_teacher_social_category_representation.csv": teacher_state,
        }
        for filename, rows in outputs.items():
            write_csv(tables_dir / filename, rows)
        report = "\n".join(
            [
                "# Direct source and social composition analysis",
                "",
                f"Direct source columns catalogued: {len(inventory):,}",
                f"Raw DCF-code distribution rows: {len(codes):,}",
                f"National class-representation rows: {len(national_classes):,}",
                f"State class-representation rows: {len(state_classes):,}",
                "",
            ]
        )
        (output / "source_report.md").write_text(report, encoding="utf-8")
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write(report)
    finally:
        connection.close()
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "foundation":
        return build_foundation(args)
    if args.command == "source":
        return build_source_analysis(args)
    if args.command == "domain":
        return build_domain(args)
    if args.command == "tertiary":
        return build_tertiary(args)
    if args.command == "aggregate":
        return aggregate_domain(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
