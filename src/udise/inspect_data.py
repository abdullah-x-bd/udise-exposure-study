from __future__ import annotations

import argparse
import csv
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
from charset_normalizer import from_bytes
from huggingface_hub import HfApi, hf_hub_download

TEXT_EXTENSIONS = {".csv", ".tsv", ".txt"}
TABLE_EXTENSIONS = TEXT_EXTENSIONS | {".parquet", ".xlsx", ".xls"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def normalize(value: str) -> str:
    return value.replace("\ufeff", "").strip().lower()


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def human_bytes(value: int | None) -> str:
    if value is None:
        return "n/a"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_text(path: Path) -> tuple[str, str]:
    sample = path.read_bytes()[:256_000]
    match = from_bytes(sample).best()
    encoding = match.encoding if match and match.encoding else "utf-8"
    try:
        text = sample.decode(encoding, errors="replace")
    except LookupError:
        encoding = "utf-8"
        text = sample.decode("utf-8", errors="replace")

    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    try:
        delimiter = csv.Sniffer().sniff(text, delimiters=",\t;|").delimiter
    except csv.Error:
        pass
    return encoding, delimiter


def duckdb_encoding(encoding: str) -> str | None:
    value = encoding.lower().replace("_", "-")
    if value in {"ascii", "utf-8", "utf8", "utf-8-sig"}:
        return None
    return {
        "cp1252": "windows-1252",
        "windows-1252": "windows-1252",
        "iso-8859-1": "latin-1",
        "latin-1": "latin-1",
        "latin1": "latin-1",
    }.get(value)


def csv_source(
    path: Path,
    delimiter: str,
    encoding: str,
    sample_size: int,
    ignore_errors: bool,
) -> str:
    options = [
        "header=true",
        "all_varchar=true",
        f"sample_size={sample_size}",
        f"ignore_errors={'true' if ignore_errors else 'false'}",
        "null_padding=true",
        f"delim={sql_string(delimiter)}",
    ]
    mapped_encoding = duckdb_encoding(encoding)
    if mapped_encoding:
        options.append(f"encoding={sql_string(mapped_encoding)}")
    return f"read_csv_auto({sql_string(str(path))}, {', '.join(options)})"


def schema_comparison(
    columns: list[str],
    expected_schema: dict[str, Any],
) -> dict[str, Any]:
    actual = {normalize(column) for column in columns}
    expected = {normalize(item) for item in expected_schema.get("expected", [])}
    required = {normalize(item) for item in expected_schema.get("required", [])}
    return {
        "columns": columns,
        "column_count": len(columns),
        "missing_expected_columns": sorted(expected - actual),
        "unexpected_columns": sorted(actual - expected),
        "missing_required_columns": sorted(required - actual),
    }


def inspect_relation(
    connection: duckdb.DuckDBPyConnection,
    source: str,
    expected_schema: dict[str, Any],
) -> dict[str, Any]:
    description = connection.execute(f"SELECT * FROM {source} LIMIT 0").description
    columns = [item[0] for item in description]
    lookup = {normalize(column): column for column in columns}
    result = schema_comparison(columns, expected_schema)

    pseudocode = lookup.get("pseudocode")
    if not pseudocode:
        result["identifier_metrics"] = {
            "row_count": connection.execute(
                f"SELECT COUNT(*) FROM {source}"
            ).fetchone()[0],
            "pseudocode_column_present": False,
        }
        return result

    identifier = sql_identifier(pseudocode)
    metrics = connection.execute(
        f"""
        WITH records AS (
            SELECT * FROM {source}
        ),
        schools AS (
            SELECT {identifier} AS pseudocode, COUNT(*) AS records
            FROM records
            WHERE {identifier} IS NOT NULL
              AND TRIM(CAST({identifier} AS VARCHAR)) <> ''
            GROUP BY {identifier}
        )
        SELECT
            (SELECT COUNT(*) FROM records),
            COUNT(*),
            COALESCE(SUM(records), 0),
            COALESCE(SUM(CASE WHEN records > 1 THEN 1 ELSE 0 END), 0),
            MIN(records),
            MEDIAN(records),
            MAX(records),
            AVG(records)
        FROM schools
        """
    ).fetchone()
    keys = [
        "row_count",
        "unique_pseudocode",
        "rows_with_pseudocode",
        "pseudocodes_with_multiple_rows",
        "minimum_rows_per_school",
        "median_rows_per_school",
        "maximum_rows_per_school",
        "average_rows_per_school",
    ]
    result["identifier_metrics"] = dict(zip(keys, metrics, strict=True))
    result["identifier_metrics"]["missing_pseudocode_rows"] = (
        result["identifier_metrics"]["row_count"]
        - result["identifier_metrics"]["rows_with_pseudocode"]
    )

    item_group = lookup.get("item_group")
    item_id = lookup.get("item_id")
    if item_group and item_id:
        group_q = sql_identifier(item_group)
        item_q = sql_identifier(item_id)
        rows = connection.execute(
            f"""
            SELECT
                CAST({group_q} AS VARCHAR) AS item_group,
                CAST({item_q} AS VARCHAR) AS item_id,
                COUNT(*) AS row_count,
                COUNT(DISTINCT {identifier}) AS school_count
            FROM {source}
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        ).fetchall()
        result["item_combinations"] = [
            {
                "item_group": row[0],
                "item_id": row[1],
                "row_count": row[2],
                "school_count": row[3],
            }
            for row in rows
        ]
    return result


def inspect_delimited(
    path: Path,
    expected_schema: dict[str, Any],
    sample_size: int,
) -> dict[str, Any]:
    encoding, delimiter = detect_text(path)
    result: dict[str, Any] = {
        "format": "delimited_text",
        "detected_encoding": encoding,
        "detected_delimiter": repr(delimiter),
        "strict_parse_ok": True,
    }
    connection = duckdb.connect()
    try:
        strict = csv_source(path, delimiter, encoding, sample_size, False)
        try:
            result.update(inspect_relation(connection, strict, expected_schema))
        except Exception as error:
            result["strict_parse_ok"] = False
            result["strict_parse_error"] = str(error)
            fallback = csv_source(path, delimiter, encoding, sample_size, True)
            result.update(inspect_relation(connection, fallback, expected_schema))
            result["fallback_used"] = "ignore_errors=true"
    finally:
        connection.close()
    return result


def inspect_parquet(path: Path, expected_schema: dict[str, Any]) -> dict[str, Any]:
    connection = duckdb.connect()
    try:
        result: dict[str, Any] = {
            "format": "parquet",
            "strict_parse_ok": True,
        }
        result.update(
            inspect_relation(
                connection,
                f"read_parquet({sql_string(str(path))})",
                expected_schema,
            )
        )
        return result
    finally:
        connection.close()


def inspect_excel(path: Path, expected_schema: dict[str, Any]) -> dict[str, Any]:
    if path.suffix.lower() == ".xls":
        return {
            "format": "xls",
            "strict_parse_ok": False,
            "inspection_error": "Legacy XLS requires conversion before inspection.",
        }

    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheets: list[dict[str, Any]] = []
    for worksheet in workbook.worksheets:
        header = next(worksheet.iter_rows(values_only=True), ())
        columns = [str(value).strip() if value is not None else "" for value in header]
        sheet = schema_comparison([column for column in columns if column], expected_schema)
        sheet.update(
            {
                "sheet": worksheet.title,
                "reported_row_count": worksheet.max_row,
            }
        )
        sheets.append(sheet)
    workbook.close()
    return {"format": "xlsx", "strict_parse_ok": True, "sheets": sheets}


def extract_member(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    destination: Path,
) -> Path:
    target = destination / Path(member.filename).name
    with archive.open(member) as source, target.open("wb") as output:
        shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
    return target


def inspect_archive(
    archive_path: Path,
    table_key: str,
    remote_filename: str,
    expected_schema: dict[str, Any],
    sample_size: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "table": table_key,
        "remote_filename": remote_filename,
        "compressed_file_bytes": archive_path.stat().st_size,
        "sha256": sha256(archive_path),
        "archive_ok": True,
        "members": [],
        "data_members": [],
    }

    try:
        with zipfile.ZipFile(archive_path) as archive:
            bad_member = archive.testzip()
            result["zip_integrity_ok"] = bad_member is None
            if bad_member:
                result["first_bad_member"] = bad_member

            members = [member for member in archive.infolist() if not member.is_dir()]
            result["members"] = [
                {
                    "name": member.filename,
                    "compressed_bytes": member.compress_size,
                    "uncompressed_bytes": member.file_size,
                    "crc": member.CRC,
                }
                for member in members
            ]
            inspectable = [
                member
                for member in members
                if Path(member.filename).suffix.lower() in TABLE_EXTENSIONS
            ]
            result["primary_member"] = (
                max(inspectable, key=lambda member: member.file_size).filename
                if inspectable
                else None
            )

            with tempfile.TemporaryDirectory(prefix=f"udise_{table_key}_") as temp:
                temp_path = Path(temp)
                for member in inspectable:
                    extracted = extract_member(archive, member, temp_path)
                    inspected: dict[str, Any] = {
                        "name": member.filename,
                        "uncompressed_bytes": member.file_size,
                    }
                    try:
                        suffix = extracted.suffix.lower()
                        if suffix in TEXT_EXTENSIONS:
                            inspected.update(
                                inspect_delimited(
                                    extracted,
                                    expected_schema,
                                    sample_size,
                                )
                            )
                        elif suffix == ".parquet":
                            inspected.update(
                                inspect_parquet(extracted, expected_schema)
                            )
                        else:
                            inspected.update(
                                inspect_excel(extracted, expected_schema)
                            )
                    except Exception as error:
                        inspected.update(
                            {
                                "strict_parse_ok": False,
                                "inspection_error": str(error),
                            }
                        )
                    finally:
                        extracted.unlink(missing_ok=True)
                    result["data_members"].append(inspected)

            if not inspectable:
                result["archive_ok"] = False
                result["archive_error"] = "No supported tabular member found."
    except zipfile.BadZipFile as error:
        result["archive_ok"] = False
        result["archive_error"] = str(error)
    return result


def resolve_archives(
    repo_files: list[str],
    archive_config: dict[str, Any],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    errors: list[str] = []
    for table_key, settings in archive_config.items():
        pattern = settings["pattern"]
        matches = [
            filename
            for filename in repo_files
            if fnmatch.fnmatch(Path(filename).name, pattern)
        ]
        if len(matches) == 1:
            resolved[table_key] = matches[0]
        else:
            errors.append(
                f"{table_key}: {pattern!r} matched {len(matches)} files: {matches}"
            )
    if errors:
        raise RuntimeError("\n".join(errors))
    return resolved


def build_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# UDISE+ 2024-25 Source Inspection",
        "",
        f"Generated: {manifest['generated_at']}",
        "",
        f"Private dataset repository: `{manifest['dataset_repo']}`",
        "",
        "## Source archives",
        "",
        "| Table | Archive | Compressed | ZIP valid | Primary data member |",
        "|---|---|---:|:---:|---|",
    ]
    for archive in manifest["archives"]:
        lines.append(
            "| {table} | `{file}` | {size} | {valid} | `{primary}` |".format(
                table=archive["table"],
                file=archive["remote_filename"],
                size=human_bytes(archive.get("compressed_file_bytes")),
                valid="yes" if archive.get("zip_integrity_ok") else "no",
                primary=archive.get("primary_member") or "none",
            )
        )

    for archive in manifest["archives"]:
        lines.extend(["", f"## {archive['table']}", ""])
        if archive.get("archive_error"):
            lines.append(f"Archive error: `{archive['archive_error']}`")
            continue
        lines.append(f"Archive SHA-256: `{archive['sha256']}`")
        lines.append(
            f"Archive members: {len(archive['members'])}; "
            f"inspectable data members: {len(archive['data_members'])}."
        )

        for member in archive["data_members"]:
            lines.extend(["", f"### `{member['name']}`", ""])
            lines.append(
                f"Format: `{member.get('format', 'unknown')}`; "
                f"uncompressed size: {human_bytes(member.get('uncompressed_bytes'))}."
            )
            if member.get("detected_encoding"):
                lines.append(
                    f"Detected encoding: `{member['detected_encoding']}`; "
                    f"delimiter: `{member['detected_delimiter']}`."
                )
            if not member.get("strict_parse_ok", False):
                message = member.get("strict_parse_error") or member.get(
                    "inspection_error"
                )
                lines.append(f"Strict parsing did not succeed: `{message}`")

            if member.get("identifier_metrics"):
                lines.extend(["", "| Metric | Value |", "|---|---:|"])
                for key, value in member["identifier_metrics"].items():
                    lines.append(f"| {key} | {value} |")

            if member.get("columns"):
                lines.extend(
                    [
                        "",
                        f"Columns ({len(member['columns'])}):",
                        "",
                        "```text",
                        "\n".join(member["columns"]),
                        "```",
                    ]
                )

            for key, label in (
                ("missing_required_columns", "Missing required columns"),
                ("missing_expected_columns", "Missing expected columns"),
                ("unexpected_columns", "Unexpected columns"),
            ):
                if member.get(key):
                    lines.append(f"{label}: `{', '.join(member[key])}`")

            if member.get("item_combinations"):
                lines.extend(
                    [
                        "",
                        "| item_group | item_id | rows | schools |",
                        "|---:|---:|---:|---:|",
                    ]
                )
                for item in member["item_combinations"]:
                    lines.append(
                        f"| {item['item_group']} | {item['item_id']} | "
                        f"{item['row_count']} | {item['school_count']} |"
                    )

    lines.extend(
        [
            "",
            "## Privacy",
            "",
            "This report contains structural metadata and aggregate counts only. "
            "It does not contain school-level records or sample rows.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/dataset.yml"))
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("config/expected_schema.yml"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_yaml(args.config)
    schemas = load_yaml(args.schema)

    repo_id = os.getenv(config["source"]["repo_env"], "").strip()
    token = os.getenv(config["source"]["token_env"], "").strip()
    if not repo_id:
        raise RuntimeError("HF_DATASET_REPO is not configured.")
    if not token:
        raise RuntimeError("HF_TOKEN is not configured.")

    output_dir = Path(config["inspection"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = Path("data/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)

    api = HfApi(token=token)
    repo_files = api.list_repo_files(repo_id=repo_id, repo_type="dataset")
    resolved = resolve_archives(repo_files, config["archives"])

    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_repo": repo_id,
        "year": config["year"],
        "resolved_archives": resolved,
        "archives": [],
    }
    critical_errors: list[str] = []

    for table_key, remote_filename in resolved.items():
        local_path = Path(
            hf_hub_download(
                repo_id=repo_id,
                filename=remote_filename,
                repo_type="dataset",
                token=token,
                local_dir=raw_dir,
            )
        )
        inspected = inspect_archive(
            local_path,
            table_key,
            remote_filename,
            schemas.get(table_key, {}),
            int(config["inspection"]["csv_sample_size"]),
        )
        manifest["archives"].append(inspected)
        if not inspected.get("archive_ok"):
            critical_errors.append(
                f"{table_key}: {inspected.get('archive_error', 'inspection failed')}"
            )
        local_path.unlink(missing_ok=True)

    report = build_markdown(manifest)
    (output_dir / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str),
        encoding="utf-8",
    )
    (output_dir / "inspection_report.md").write_text(report, encoding="utf-8")

    if summary := os.getenv("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(report)

    if critical_errors:
        print("\n".join(critical_errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
