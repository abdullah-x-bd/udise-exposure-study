# Hugging Face UDISE+ Dataset Organization

Completed 2026-08-14.

## Result

The private Hugging Face dataset `abdkul/udise-2024-25-microdata` was reorganized losslessly for longitudinal analysis.

- 49 original all-India ZIP archives were moved by server-side copy/delete operations.
- No ZIP payload was rewritten.
- No top-level ZIP uploads remain.
- All destination files were verified present and all former top-level source paths verified absent.
- Existing `processed/2024_25/` outputs were deliberately preserved in place.
- `README.md`, `manifests/raw_archive_manifest.json`, and `manifests/raw_file_manifest.csv` were added to the Hugging Face dataset.

## Canonical raw layout

```text
raw/
  2018-19/
    enrolment_1.zip
    enrolment_2.zip
    facility.zip
    profile_1.zip
    profile_2.zip
    teacher.zip
  2019-20/
    ...same six core tables...
  2020-21/
    ...same six core tables...
  2021-22/
    ...same six core tables...
  2022-23/
    ...same six core tables...
  2023-24/
    ...same six core tables...
  2024-25/
    ...same six core tables...
  2025-26/
    enrolment_1.zip
    enrolment_2.zip
    facility.zip
    profile_1.zip
    profile_2.zip
    teacher.zip
    safety.zip
```

This provides eight consecutive academic years, 2018-19 through 2025-26.

## Archive inspection

Every archive was opened remotely and every internal CSV header was read before the move. There were zero archive inspection errors and zero internal-header read errors.

Important structural differences recorded in the manifest include:

- Enrolment archives from 2018-19 through 2021-22 are internally sharded across multiple schema-compatible national/state CSVs. `enrolment_1` also contains a distinct `NationalStreamEnrolment.csv` with a different schema, so it must not be concatenated blindly with the main enrolment table.
- From 2022-23 onward, the main enrolment archives generally contain a single national CSV.
- Enrolment 1/2 contain 28 columns in 2018-22, 29 columns in 2022-25, and 42 columns in 2025-26.
- Facility contains 41 columns in 2018-22, 70 columns in 2022-25, and 82 columns in 2025-26.
- Profile 1 contains 53 columns in 2018-21, 54 in 2021-22, 38 in 2022-25, and 49 in 2025-26.
- Profile 2 contains 63 columns in 2018-22 and 17 columns from 2022-23 through 2025-26.
- Teacher contains 32 columns in 2018-22 and 38 columns from 2022-23 onward.
- 2025-26 adds a separate 22-column safety table.

These differences are now explicitly recorded in `manifests/raw_archive_manifest.json` so the multi-year harmonization layer can be built deterministically in the next stage.

## Hugging Face commit

The organization commit created on the dataset is `48362094431ef43fcdca4440651886f5913d74d8`.
