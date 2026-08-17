# Composite School Grant Robustness Addendum

This addendum records checks completed after the main robustness audit.

## Post-treatment management selection

Earlier outcome code often retained schools that were still coded as government-managed in later UDISE rounds. Because later management status is post-assignment, that restriction could in principle create selection bias.

The maintenance and deterioration outcomes were therefore re-estimated in two samples:

1. all schools that were government-managed in the assignment year, regardless of later management code;
2. only schools still coded as government-managed in the later round.

The estimates are virtually unchanged in both clean cohorts.

For the 2021-22 assignment cohort:

- 2023-24 deterioration: +0.447 pp in the assignment-government sample versus +0.436 pp in the still-government sample;
- 2024-25: +0.134 pp versus +0.110 pp;
- 2025-26: +0.172 pp versus +0.155 pp.

Later management status itself does not change discontinuously at 250. The discontinuity in remaining government-managed is statistically insignificant at every horizon, as is the discontinuity in whether later management is observed.

The same conclusion holds for the 2022-23 cohort. Conditioning on later government-management status therefore does not drive the maintenance result.

## Stability of the 250/251 CSG breakpoint

Historical government implementation records show the 250/251 breakpoint in operation before the clean cohorts used here, with schools at 101-250 pupils assigned a Rs 50,000 CSG norm and schools at 251-1000 assigned Rs 75,000. Lower enrolment slabs have changed in some implementations, but the main 250/251 boundary used by this study is not a recent artifact.

This supports treating 250/251 as the primary threshold rather than pooling all CSG cutoffs mechanically.

## Residual threats after the robustness audit

The completed checks do not eliminate every identification concern:

- formula assignment remains fuzzy because crossing the threshold does not deterministically change the UDISE receipt field by the full nominal step;
- enrolment is potentially manipulable and density around 250 is not perfectly smooth, although the later placebo and longitudinal tests do not establish a distinctive CSG-specific manipulation pattern;
- State-specific programmes using the same or nearby enrolment thresholds have not been exhaustively catalogued;
- exact source documentation for the longitudinal `pseudocode` identifier remains useful for publication-grade panel validation;
- the precise administrative mapping between UDISE academic-year enrolment and previous-financial-year CSG receipt/expenditure fields is supported by the documentary audit but may vary across States;
- reduced-form outcome nulls do not by themselves imply a zero treatment effect among schools whose actual resources changed because of the threshold;
- UDISE cannot observe all plausible benefits, particularly learning achievement, detailed attendance, service quality and uptime, consumable purchases and transaction-level expenditure purposes.

These limitations bound the causal interpretation. The study's strongest result is the effect of formula assignment on school-level administrative finance records rather than a clean estimate of the causal return to an additional rupee of CSG actually received.
