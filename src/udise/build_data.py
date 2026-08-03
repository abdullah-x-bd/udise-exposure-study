from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import yaml
from huggingface_hub import HfApi, hf_hub_download


TABLE_ORDER = (
    "profile_1",
    "profile_2",
    "facility",
    "enrolment_1",
    "enrolment_2",
    "teacher",
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def normalize(value: str) -> str:
    return value.replace("\ufeff", "").strip().lower()


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def human_bytes(value: int | None) -> str:
    if value is None:
        return "n/a"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def resolve_archives(
    repo_files: list[str], archive_config: dict[str, Any]
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    errors: list[str] = []
    for table_name in TABLE_ORDER:
        pattern = archive_config[table_name]["pattern"]
        matches = [
            file_name
            for file_name in repo_files
            if fnmatch.fnmatch(Path(file_name).name, pattern)
        ]
        if len(matches) == 1:
            resolved[table_name] = matches[0]
        else:
            errors.append(
                f"{table_name}: {pattern!r} matched {len(matches)} files: {matches}"
            )
    if errors:
        raise RuntimeError("\n".join(errors))
    return resolved


def table_type_map(
    table_name: str,
    expected_schema: dict[str, Any],
    type_config: dict[str, Any],
) -> dict[str, str]:
    columns = [normalize(column) for column in expected_schema[table_name]["expected"]]
    strings = {
        normalize(column)
        for column in type_config[table_name].get("string_columns", [])
    }
    doubles = {
        normalize(column)
        for column in type_config[table_name].get("double_columns", [])
    }
    unknown = (strings | doubles) - set(columns)
    if unknown:
        raise ValueError(f"Unknown typed columns for {table_name}: {sorted(unknown)}")
    overlap = strings & doubles
    if overlap:
        raise ValueError(f"Columns have conflicting types for {table_name}: {sorted(overlap)}")
    return {
        column: "VARCHAR" if column in strings else "DOUBLE" if column in doubles else "BIGINT"
        for column in columns
    }


def extract_single_csv(archive_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise RuntimeError(f"Corrupt ZIP member: {bad_member}")
        members = [
            member
            for member in archive.infolist()
            if not member.is_dir() and Path(member.filename).suffix.lower() == ".csv"
        ]
        if len(members) != 1:
            raise RuntimeError(
                f"Expected exactly one CSV in {archive_path.name}; found {[m.filename for m in members]}"
            )
        member = members[0]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, destination.open("wb") as output:
            shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
    return destination


def csv_source(path: Path) -> str:
    return (
        f"read_csv_auto({sql_string(str(path))}, header=true, all_varchar=true, "
        "sample_size=-1, parallel=true, strict_mode=true, null_padding=true)"
    )


def source_columns(connection: duckdb.DuckDBPyConnection, source: str) -> list[str]:
    return [
        item[0]
        for item in connection.execute(f"SELECT * FROM {source} LIMIT 0").description
    ]


def typed_expression(column: str, data_type: str) -> str:
    quoted = quote_identifier(column)
    cleaned = f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '')"
    if data_type == "VARCHAR":
        return f"{cleaned} AS {quoted}"
    return f"TRY_CAST({cleaned} AS {data_type}) AS {quoted}"


def cast_failure_expression(column: str, data_type: str) -> str | None:
    if data_type == "VARCHAR":
        return None
    quoted = quote_identifier(column)
    cleaned = f"NULLIF(TRIM(CAST({quoted} AS VARCHAR)), '')"
    alias = quote_identifier(column)
    return (
        f"SUM(CASE WHEN {cleaned} IS NOT NULL "
        f"AND TRY_CAST({cleaned} AS {data_type}) IS NULL THEN 1 ELSE 0 END) AS {alias}"
    )


def convert_csv_to_parquet(
    csv_path: Path,
    parquet_path: Path,
    type_map: dict[str, str],
) -> dict[str, Any]:
    connection = duckdb.connect()
    connection.execute("PRAGMA threads=4")
    connection.execute("PRAGMA memory_limit='11GB'")
    source = csv_source(csv_path)
    try:
        actual_columns = source_columns(connection, source)
        actual_normalized = [normalize(column) for column in actual_columns]
        expected_columns = list(type_map)
        if actual_normalized != expected_columns:
            raise RuntimeError(
                "Column order or names differ from configuration. "
                f"Expected {expected_columns}; found {actual_normalized}"
            )

        lookup = {normalize(column): column for column in actual_columns}
        failure_terms = [
            cast_failure_expression(lookup[column], data_type)
            for column, data_type in type_map.items()
        ]
        failure_terms = [term for term in failure_terms if term]
        cast_failures: dict[str, int] = {}
        if failure_terms:
            failure_query = f"SELECT {', '.join(failure_terms)} FROM {source}"
            failure_row = connection.execute(failure_query).fetchone()
            failure_columns = [item[0] for item in connection.description]
            cast_failures = {
                normalize(column): int(value or 0)
                for column, value in zip(failure_columns, failure_row, strict=True)
            }
        nonzero_failures = {
            column: count for column, count in cast_failures.items() if count > 0
        }
        if nonzero_failures:
            raise RuntimeError(f"Non-empty values failed type conversion: {nonzero_failures}")

        row_count = int(connection.execute(f"SELECT COUNT(*) FROM {source}").fetchone()[0])
        select_list = ",\n".join(
            typed_expression(lookup[column], data_type)
            for column, data_type in type_map.items()
        )
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        connection.execute(
            f"""
            COPY (
                SELECT {select_list}
                FROM {source}
            )
            TO {sql_string(str(parquet_path))}
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
            """
        )
        parquet_count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM read_parquet({sql_string(str(parquet_path))})"
            ).fetchone()[0]
        )
        if parquet_count != row_count:
            raise RuntimeError(
                f"Row-count mismatch after conversion: CSV {row_count}, Parquet {parquet_count}"
            )
        schema_rows = connection.execute(
            f"DESCRIBE SELECT * FROM read_parquet({sql_string(str(parquet_path))})"
        ).fetchall()
        return {
            "source_rows": row_count,
            "parquet_rows": parquet_count,
            "parquet_bytes": parquet_path.stat().st_size,
            "parquet_sha256": sha256(parquet_path),
            "cast_failures": cast_failures,
            "parquet_schema": [
                {"column": row[0], "type": row[1], "null": row[2]}
                for row in schema_rows
            ],
        }
    finally:
        connection.close()


def build_duckdb_database(
    database_path: Path,
    parquet_paths: dict[str, Path],
) -> dict[str, Any]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database_path.unlink(missing_ok=True)
    connection = duckdb.connect(str(database_path))
    connection.execute("PRAGMA threads=4")
    connection.execute("PRAGMA memory_limit='11GB'")
    try:
        for table_name in TABLE_ORDER:
            path = parquet_paths[table_name]
            connection.execute(
                f"CREATE TABLE raw_{table_name} AS "
                f"SELECT * FROM read_parquet({sql_string(str(path))})"
            )

        connection.execute(
            """
            CREATE VIEW school_master_base AS
            SELECT
                p1.*,
                p2.* EXCLUDE (pseudocode),
                f.* EXCLUDE (pseudocode),
                t.* EXCLUDE (pseudocode)
            FROM raw_profile_1 AS p1
            LEFT JOIN raw_profile_2 AS p2 USING (pseudocode)
            LEFT JOIN raw_facility AS f USING (pseudocode)
            LEFT JOIN raw_teacher AS t USING (pseudocode)
            """
        )

        connection.execute(
            """
            CREATE TABLE audit_source_counts AS
            SELECT 'profile_1' AS table_name, COUNT(*) AS row_count,
                   COUNT(DISTINCT pseudocode) AS school_count FROM raw_profile_1
            UNION ALL
            SELECT 'profile_2', COUNT(*), COUNT(DISTINCT pseudocode) FROM raw_profile_2
            UNION ALL
            SELECT 'facility', COUNT(*), COUNT(DISTINCT pseudocode) FROM raw_facility
            UNION ALL
            SELECT 'enrolment_1', COUNT(*), COUNT(DISTINCT pseudocode) FROM raw_enrolment_1
            UNION ALL
            SELECT 'enrolment_2', COUNT(*), COUNT(DISTINCT pseudocode) FROM raw_enrolment_2
            UNION ALL
            SELECT 'teacher', COUNT(*), COUNT(DISTINCT pseudocode) FROM raw_teacher
            """
        )

        connection.execute(
            """
            CREATE TABLE audit_school_join_coverage AS
            WITH e1 AS (SELECT DISTINCT pseudocode FROM raw_enrolment_1),
                 e2 AS (SELECT DISTINCT pseudocode FROM raw_enrolment_2)
            SELECT
                p1.pseudocode,
                p2.pseudocode IS NOT NULL AS has_profile_2,
                f.pseudocode IS NOT NULL AS has_facility,
                t.pseudocode IS NOT NULL AS has_teacher,
                e1.pseudocode IS NOT NULL AS has_enrolment_1,
                e2.pseudocode IS NOT NULL AS has_enrolment_2
            FROM raw_profile_1 AS p1
            LEFT JOIN raw_profile_2 AS p2 USING (pseudocode)
            LEFT JOIN raw_facility AS f USING (pseudocode)
            LEFT JOIN raw_teacher AS t USING (pseudocode)
            LEFT JOIN e1 USING (pseudocode)
            LEFT JOIN e2 USING (pseudocode)
            """
        )

        connection.execute(
            """
            CREATE TABLE audit_join_summary AS
            SELECT
                COUNT(*) AS profile_1_schools,
                SUM(has_profile_2::INTEGER) AS schools_with_profile_2,
                SUM(has_facility::INTEGER) AS schools_with_facility,
                SUM(has_teacher::INTEGER) AS schools_with_teacher,
                SUM(has_enrolment_1::INTEGER) AS schools_with_enrolment_1,
                SUM(has_enrolment_2::INTEGER) AS schools_with_enrolment_2,
                SUM((NOT has_enrolment_1)::INTEGER) AS schools_missing_enrolment_1,
                SUM((NOT has_enrolment_2)::INTEGER) AS schools_missing_enrolment_2,
                SUM((has_enrolment_1 <> has_enrolment_2)::INTEGER)
                    AS schools_with_enrolment_presence_mismatch
            FROM audit_school_join_coverage
            """
        )

        connection.execute(
            """
            CREATE TABLE audit_enrolment_item_combinations AS
            SELECT 'enrolment_1' AS source, item_group, item_id,
                   COUNT(*) AS row_count, COUNT(DISTINCT pseudocode) AS school_count
            FROM raw_enrolment_1
            GROUP BY item_group, item_id
            UNION ALL
            SELECT 'enrolment_2', item_group, item_id,
                   COUNT(*), COUNT(DISTINCT pseudocode)
            FROM raw_enrolment_2
            GROUP BY item_group, item_id
            """
        )

        connection.execute(
            """
            CREATE TABLE audit_enrolment_missing_schools AS
            SELECT pseudocode, has_enrolment_1, has_enrolment_2
            FROM audit_school_join_coverage
            WHERE NOT has_enrolment_1 OR NOT has_enrolment_2
            """
        )

        connection.execute("CHECKPOINT")
        counts = [
            {
                "table_name": row[0],
                "row_count": int(row[1]),
                "school_count": int(row[2]),
            }
            for row in connection.execute(
                "SELECT * FROM audit_source_counts ORDER BY table_name"
            ).fetchall()
        ]
        summary_row = connection.execute("SELECT * FROM audit_join_summary").fetchone()
        summary_columns = [item[0] for item in connection.description]
        join_summary = {
            column: int(value)
            for column, value in zip(summary_columns, summary_row, strict=True)
        }
        master_rows = int(
            connection.execute("SELECT COUNT(*) FROM school_master_base").fetchone()[0]
        )
        return {
            "source_counts": counts,
            "join_summary": join_summary,
            "school_master_base_rows": master_rows,
            "database_bytes": database_path.stat().st_size,
            "database_sha256": sha256(database_path),
        }
    finally:
        connection.close()


def build_report(manifest: dict[str, Any]) -> str:
    lines = [
        "# UDISE+ 2024-25 Processing Report",
        "",
        f"Generated: {manifest['generated_at']}",
        "",
        f"Dataset repository: `{manifest['dataset_repo']}`",
        "",
        "## Parquet conversion",
        "",
        "| Table | Rows | Parquet size | Type failures |",
        "|---|---:|---:|---:|",
    ]
    for table_name in TABLE_ORDER:
        item = manifest["tables"][table_name]
        failures = sum(item["cast_failures"].values())
        lines.append(
            f"| {table_name} | {item['parquet_rows']:,} | "
            f"{human_bytes(item['parquet_bytes'])} | {failures:,} |"
        )

    database = manifest["database"]
    lines.extend(
        [
            "",
            "## DuckDB database",
            "",
            f"Database size: {human_bytes(database['database_bytes'])}",
            "",
            f"School master base rows: {database['school_master_base_rows']:,}",
            "",
            "### Join coverage",
            "",
            "| Measure | Count |",
            "|---|---:|",
        ]
    )
    for key, value in database["join_summary"].items():
        lines.append(f"| {key} | {value:,} |")

    lines.extend(
        [
            "",
            "## Private outputs",
            "",
            f"Processed files were uploaded to `{manifest['remote_output_path']}`.",
            "",
            "The GitHub artifact contains this aggregate report and the processing manifest only. "
            "School-level Parquet and DuckDB files remain in the private dataset repository.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-config", type=Path, default=Path("config/dataset.yml"))
    parser.add_argument("--schema", type=Path, default=Path("config/expected_schema.yml"))
    parser.add_argument("--types", type=Path, default=Path("config/data_types.yml"))
    parser.add_argument("--output", type=Path, default=Path("outputs/build"))
    parser.add_argument("--skip-upload", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_config = load_yaml(args.dataset_config)
    schemas = load_yaml(args.schema)
    type_config = load_yaml(args.types)

    repo_id = os.getenv(dataset_config["source"]["repo_env"], "").strip()
    token = os.getenv(dataset_config["source"]["token_env"], "").strip()
    if not repo_id:
        raise RuntimeError("HF_DATASET_REPO is not configured")
    if not token:
        raise RuntimeError("HF_TOKEN is not configured")

    year = dataset_config["year"]
    remote_output_path = f"processed/{year}"
    output_dir = args.output
    parquet_dir = output_dir / "parquet"
    database_dir = output_dir / "database"
    manifest_dir = output_dir / "manifests"
    for directory in (parquet_dir, database_dir, manifest_dir):
        directory.mkdir(parents=True, exist_ok=True)

    api = HfApi(token=token)
    repo_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
    resolved = resolve_archives(repo_files, dataset_config["archives"])
    table_results: dict[str, Any] = {}
    parquet_paths: dict[str, Path] = {}

    with tempfile.TemporaryDirectory(prefix="udise_build_") as temp:
        temp_dir = Path(temp)
        for table_name in TABLE_ORDER:
            archive_file = resolved[table_name]
            archive_path = Path(
                hf_hub_download(
                    repo_id=repo_id,
                    filename=archive_file,
                    repo_type="dataset",
                    token=token,
                    local_dir=temp_dir / "downloads",
                )
            )
            csv_path = temp_dir / f"{table_name}.csv"
            extract_single_csv(archive_path, csv_path)
            parquet_path = parquet_dir / f"{table_name}.parquet"
            result = convert_csv_to_parquet(
                csv_path,
                parquet_path,
                table_type_map(table_name, schemas, type_config),
            )
            result.update(
                {
                    "source_archive": archive_file,
                    "source_archive_sha256": sha256(archive_path),
                    "source_csv_bytes": csv_path.stat().st_size,
                }
            )
            table_results[table_name] = result
            parquet_paths[table_name] = parquet_path
            csv_path.unlink(missing_ok=True)
            archive_path.unlink(missing_ok=True)

    database_path = database_dir / "udise_2024_25.duckdb"
    database_result = build_duckdb_database(database_path, parquet_paths)
    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_repo": repo_id,
        "year": year,
        "remote_output_path": remote_output_path,
        "tables": table_results,
        "database": database_result,
    }
    manifest_path = manifest_dir / "build_manifest.json"
    report_path = manifest_dir / "build_report.md"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = build_report(manifest)
    report_path.write_text(report, encoding="utf-8")

    if not args.skip_upload:
        api.upload_folder(
            repo_id=repo_id,
            repo_type="dataset",
            folder_path=str(output_dir),
            path_in_repo=remote_output_path,
            commit_message="Build typed Parquet and DuckDB outputs for UDISE 2024-25",
        )

    if summary_path := os.getenv("GITHUB_STEP_SUMMARY"):
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(report)

    print(report)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Build failed: {error}", file=sys.stderr)
        raise
