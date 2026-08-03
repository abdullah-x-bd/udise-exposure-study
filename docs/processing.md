# Processing architecture

## Purpose

The processing stage turns the six private all-state UDISE+ ZIP archives into deterministic typed Parquet files and one portable DuckDB database.

## Storage boundary

Large and school-level outputs are uploaded to the private Hugging Face dataset under:

```text
processed/2024_25/
├── parquet/
│   ├── profile_1.parquet
│   ├── profile_2.parquet
│   ├── facility.parquet
│   ├── enrolment_1.parquet
│   ├── enrolment_2.parquet
│   └── teacher.parquet
├── database/
│   └── udise_2024_25.duckdb
└── manifests/
    ├── build_manifest.json
    └── build_report.md
```

GitHub Actions keeps only the aggregate processing report as an expiring workflow artifact. It does not upload Parquet or DuckDB files to GitHub.

## Conversion rules

- The workflow downloads and processes one source ZIP at a time.
- ZIP integrity is checked before extraction.
- Exactly one CSV is required inside each archive.
- CSV fields are read as strings first.
- Profile location names are stored as `VARCHAR`.
- Grant receipt and expenditure are stored as `DOUBLE`.
- Remaining source fields are stored as `BIGINT`.
- Non-empty values that cannot be converted to their configured type cause the workflow to fail.
- The CSV and Parquet row counts must match exactly.
- Parquet uses Zstandard compression and 100,000-row groups.

## DuckDB contents

The database contains:

- `raw_profile_1`
- `raw_profile_2`
- `raw_facility`
- `raw_enrolment_1`
- `raw_enrolment_2`
- `raw_teacher`
- `school_master_base`, a view joining the four one-row-per-school tables
- `audit_source_counts`
- `audit_school_join_coverage`
- `audit_join_summary`
- `audit_enrolment_item_combinations`
- `audit_enrolment_missing_schools`

The enrolment tables remain separate at this stage because they contain multiple rows per school. Later stages will reshape and aggregate them into research-ready social-composition and age-grade tables.
