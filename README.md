# UDISE+ 2024-25 Exposure Study

Reproducible school-level analysis of the 2024-25 UDISE+ microdata, with a focus on social composition, educational access, infrastructure, staffing, governance, and student-weighted exposure.

## Data architecture

The six raw all-state ZIP archives are stored in the private Hugging Face dataset configured through `HF_DATASET_REPO`. The token is stored as the GitHub Actions secret `HF_TOKEN`. Raw or school-level microdata are never committed to GitHub.

GitHub stores:

- Python, DuckDB SQL and workflow code
- aggregate validation reports
- state, district and block summary outputs
- figures, model results and documentation

## Current stage

The first workflow, **Inspect UDISE source data**, downloads each private archive, validates ZIP integrity, identifies the internal tables, detects their format and columns, measures row and school coverage, compares the actual schema with the published schema, and records `item_group` and `item_id` coverage for the enrolment tables.

The workflow produces only structural metadata and aggregate counts. It does not publish school-level rows.

## Run

Open **Actions**, select **Inspect UDISE source data**, and choose **Run workflow**. The same workflow also runs automatically on pull requests from branches inside this repository.

## Source tables

- Profile 1, school profile and location
- Profile 2, RTE, grants, inspections and school management
- Facility, infrastructure and facilities
- Enrolment 1, social category, religion, welfare, disability and repeater enrolment
- Enrolment 2, age-wise enrolment
- Teacher, teacher profile

See `docs/data-source.md`, `docs/research-plan.md` and `AGENTS.md` for the data boundary and analytical rules.
