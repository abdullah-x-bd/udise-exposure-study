# Repository Instructions

## Purpose

This repository contains the reproducible code and documentation for the UDISE+ 2024-25 school social exposure study.

## Data handling

- Never commit raw, extracted, sampled, or processed school-level microdata to GitHub.
- Read private source files only from the Hugging Face dataset identified by `HF_DATASET_REPO`.
- Store the Hugging Face token only as the GitHub Actions secret `HF_TOKEN`.
- Generated school-level Parquet and DuckDB files must remain in private external storage.
- GitHub may contain aggregate tables, figures, validation summaries, code, and documentation.

## Development rules

- Work on a feature branch and open a pull request into `main`.
- Keep transformations deterministic and idempotent.
- Preserve the original source archives unchanged.
- Every derived indicator must be defined in documentation and implemented in tested code.
- Treat `pseudocode` as the school joining identifier, subject to source validation.
- Do not interpret undocumented numeric category codes until a UDISE DCF codebook is available.
- Do not label the residual religion category as Hindu unless the source documentation establishes that interpretation.
- Distinguish school-level association from individual-level identity or causal claims.

## Validation

- Record source filenames, sizes, archive members, row counts, columns, identifier coverage, and schema differences.
- Fail clearly when an expected source archive is missing or ambiguous.
- Do not silently skip malformed data.
