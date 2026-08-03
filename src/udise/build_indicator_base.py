from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import duckdb
from huggingface_hub import HfApi

from udise.comprehensive_a0_analysis import (
    REMOTE_SCHOOL_INDICATORS,
    create_indicator_tables,
    download_database,
    export_school_indicator_parquet,
)
from udise.indicator_registry import ALL_INDICATORS, validate_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs/indicator_base"))
    parser.add_argument("--database-path", type=Path)
    parser.add_argument("--dataset-repo", default=os.getenv("HF_DATASET_REPO", ""))
    parser.add_argument("--token", default=os.getenv("HF_TOKEN", ""))
    parser.add_argument("--upload", action="store_true")
    return parser.parse_args()


def main() -> int:
    validate_registry()
    args = parse_args()
    output = args.output
    work_dir = output / "work"
    output.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading the processed UDISE DuckDB database", flush=True)
    database_path = download_database(args, work_dir)
    print(f"Database ready at {database_path}", flush=True)

    connection = duckdb.connect(str(database_path), read_only=True)
    connection.execute("PRAGMA threads=2")
    connection.execute("PRAGMA memory_limit='5GB'")
    connection.execute("PRAGMA preserve_insertion_order=false")
    connection.execute(f"PRAGMA temp_directory='{str(work_dir / 'duckdb_temp')}'")
    parquet_path = work_dir / "school_indicator_base.parquet"
    try:
        print("Constructing school-level social composition and all indicators", flush=True)
        create_indicator_tables(connection)
        print("Exporting the school-level indicator table to Parquet", flush=True)
        export_school_indicator_parquet(connection, parquet_path)
        row_count = int(
            connection.execute("SELECT COUNT(*) FROM school_indicator_base").fetchone()[0]
        )
        column_count = len(connection.execute("DESCRIBE school_indicator_base").fetchall())
        manifest = {
            "school_rows": row_count,
            "columns": column_count,
            "constructed_indicators": len(ALL_INDICATORS),
            "parquet_bytes": parquet_path.stat().st_size,
            "private_remote_path": REMOTE_SCHOOL_INDICATORS,
        }
        (output / "indicator_base_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        report = "\n".join(
            [
                "# School indicator base built",
                "",
                f"School rows: {row_count:,}",
                f"Columns: {column_count:,}",
                f"Constructed secondary and tertiary indicators: {len(ALL_INDICATORS):,}",
                f"Parquet size: {parquet_path.stat().st_size / (1024 ** 2):.1f} MiB",
                "",
                "The school-level file remains in private Hugging Face storage.",
                "",
            ]
        )
        (output / "indicator_base_report.md").write_text(report, encoding="utf-8")
        if summary := os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as handle:
                handle.write(report)

        if args.upload:
            if not args.dataset_repo or not args.token:
                raise RuntimeError("HF_DATASET_REPO and HF_TOKEN are required for upload")
            print("Uploading the private school-level indicator Parquet file", flush=True)
            HfApi(token=args.token).upload_file(
                path_or_fileobj=str(parquet_path),
                path_in_repo=REMOTE_SCHOOL_INDICATORS,
                repo_id=args.dataset_repo,
                repo_type="dataset",
                commit_message="Build complete UDISE 2024-25 school indicator base",
            )
            print("Private indicator base upload completed", flush=True)
    finally:
        connection.close()
        parquet_path.unlink(missing_ok=True)
        shutil.rmtree(work_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
