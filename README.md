# UDISE+ 2024-25 Exposure Study

Reproducible school-level analysis of the 2024-25 UDISE+ microdata, with a focus on social composition, educational access, infrastructure, staffing, governance, and student-weighted exposure.

## Data architecture

The six raw all-state ZIP archives are stored in the private Hugging Face dataset configured through `HF_DATASET_REPO`. The token is stored as the GitHub Actions secret `HF_TOKEN`. Raw or school-level microdata are never committed to GitHub.

GitHub stores:

- Python, DuckDB SQL and workflow code
- aggregate validation reports
- state, district and block summary outputs
- figures, model results and documentation

Private Hugging Face storage holds:

- original ZIP archives
- typed Parquet tables
- the portable DuckDB analytical database
- large school-level derived files

## Workflows

### Inspect UDISE source data

Checks ZIP integrity, internal file formats, columns, row counts, `pseudocode` coverage and enrolment item combinations. The report contains aggregate structural metadata only.

### Build private UDISE processed data

Downloads one archive at a time, validates every configured type conversion, writes Zstandard-compressed Parquet, checks exact row preservation, creates the DuckDB database, validates joins, and uploads the processed files to the private dataset repository.

The build workflow runs automatically when its processing code is merged into `main`. It can also be run manually from the Actions page.

## Source tables

- Profile 1, school profile and location
- Profile 2, RTE, grants, inspections and school management
- Facility, infrastructure and facilities
- Enrolment 1, social category, religion, welfare, disability and repeater enrolment
- Enrolment 2, age-wise enrolment
- Teacher, teacher profile

See `docs/data-source.md`, `docs/processing.md`, `docs/research-plan.md` and `AGENTS.md` for the data boundary, processing rules and analytical plan.
