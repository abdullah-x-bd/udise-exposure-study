# Composite School Grant Red-Team Addendum

This addendum records checks completed after the main hostile red-team report.

## Post-treatment management selection

The earlier outcome code often retained schools that were still coded as government-managed in later UDISE rounds. Because later management status is post-assignment, this could in principle create selection bias.

We reran the maintenance/deterioration outcome two ways:

1. retain all schools that were government-managed in the assignment year, regardless of later management code;
2. retain only those still coded government-managed later.

The estimates are virtually unchanged in both clean cohorts.

For the 2021-22 assignment cohort:

- 2023-24 deterioration: +0.447 pp in the assignment-government sample versus +0.436 pp in the still-government sample;
- 2024-25: +0.134 pp versus +0.110 pp;
- 2025-26: +0.172 pp versus +0.155 pp.

Later management status itself does not change discontinuously at 250. The discontinuity in remaining government-managed is statistically insignificant at every horizon, as is the discontinuity in whether later management is observed.

For the 2022-23 cohort, the same conclusion holds: the assignment-government and still-government deterioration estimates are nearly identical, and later management status has no significant threshold discontinuity.

**Conclusion:** conditioning on later government-management status is not driving the maintenance result.

## Stability of the 250-pupil CSG breakpoint

Historical government implementation records show the 250-pupil breakpoint in operation before the clean cohorts used here, with schools at 101-250 pupils receiving a ₹50,000 CSG norm and schools at 251-1000 receiving ₹75,000. Lower enrolment slabs have changed in some implementations, but the main 250 breakpoint used by this study is not a recent artifact.

This supports the decision to use the 250 threshold rather than pool all CSG cutoffs mechanically.

## Residual threats that remain after the red team

The following issues are not eliminated by the completed robustness checks:

- the design remains fuzzy because formula eligibility does not deterministically change actual reported receipt by the full statutory step;
- enrolment is potentially manipulable and density around 250 is not perfectly smooth;
- state-specific programmes using the same or nearby enrolment thresholds have not been exhaustively catalogued;
- exact source documentation for the longitudinal `pseudocode` identifier should still be obtained;
- exact timing semantics between UDISE academic-year enrolment and the previous-financial-year CSG receipt/expenditure fields should be documented from the official DCF/administrative workflow;
- reduced-form outcome nulls do not by themselves prove zero treatment effect among schools whose actual funding changed because of the threshold;
- UDISE cannot observe all plausible benefits, particularly learning achievement, detailed attendance, service quality/uptime, consumable purchases and transaction-level expenditure purposes.

These residual threats are why the preferred claim remains a **local reduced-form policy-threshold result**, not a clean estimate of the causal return to an additional rupee of CSG.
