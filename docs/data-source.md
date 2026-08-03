# Data source

The project uses the all-state UDISE+ microdata downloads for 2024-25.

The private source repository is configured through the GitHub Actions variable `HF_DATASET_REPO`. Authentication uses the GitHub Actions secret `HF_TOKEN`.

## Source archives

| Logical table | Source archive pattern | Description |
|---|---|---|
| Profile 1 | `profile_data_1_*2024-25*.zip` | School profile and location |
| Profile 2 | `profile_data_2_*2024-25*.zip` | RTE, grants, inspections and school management |
| Facility | `facility_data_*2024-25*.zip` | Buildings, water, sanitation, laboratories, digital facilities and accessibility |
| Enrolment 1 | `enrolment_data_1_*2024-25*.zip` | Social category, religion, BPL, EWS, disability and repeater enrolment by class and gender |
| Enrolment 2 | `enrolment_data_2_*2024-25*.zip` | Age-wise enrolment by class and gender |
| Teacher | `teacher_data_*2024-25*.zip` | Teacher numbers, social category, employment type, qualification and training |

All source archives join through `pseudocode`, subject to validation of coverage, uniqueness and table grain.

## Data boundary

Raw and school-level processed data remain in private external storage. GitHub contains code, aggregate outputs, validation summaries and documentation only.
