# Preliminary Muslim-share density findings

## Scope

This note records the first descriptive pass for the proposed Muslim educational disenfranchisement study. It uses all eight UDISE+ academic years from 2018-19 through 2025-26 and reconstructs school-level Muslim enrolment share using the already validated cross-schema religion harmonisation in `studies/muslim_government_school_equity/common.py`.

For every State/UT and year, the pipeline produces one-percentage-point Muslim-share density curves for two universes: all schools, and State/UT/local-government schools using management codes 1, 2, 3, 6, 89 and 90. Individual State graphs use raw school counts. Contact sheets normalise the y-axis within State/UT so distributional shapes can be compared.

The Muslim share denominator is reconciled Classes I-XII enrolment from the social-category margin, General + SC + ST + OBC. Schools with zero total Classes I-XII enrolment are excluded. These plots are descriptive and are not interpreted as evidence of discrimination by themselves.

## 1. National descriptive profile

Summing State/UT rows in the government-school universe gives:

| Academic year | Government schools | Student-weighted Muslim share | Schools with exactly zero Muslim pupils | Schools at least 50% Muslim | Schools at least 90% Muslim |
|---|---:|---:|---:|---:|---:|
| 2018-19 | 1,072,941 | 12.95% | 69.15% | 8.25% | 5.09% |
| 2019-20 | 1,024,973 | 13.95% | 68.14% | 8.61% | 5.36% |
| 2020-21 | 1,024,909 | 14.29% | 67.79% | 8.78% | 5.47% |
| 2021-22 | 1,015,069 | 14.42% | 67.41% | 8.78% | 5.47% |
| 2022-23 | 1,009,274 | 16.10% | 61.58% | 9.51% | 5.60% |
| 2023-24 | 1,010,310 | 16.36% | 61.41% | 9.60% | 5.58% |
| 2024-25 | 1,005,761 | 16.45% | 61.05% | 9.58% | 5.53% |
| 2025-26 | 999,370 | 16.75% | 60.80% | 9.66% | 5.54% |

The conspicuous level shift between 2021-22 and 2022-23 coincides with the major UDISE schema transition. It must therefore receive a dedicated semantic and composition audit before any change across that boundary is interpreted substantively. The descriptive trends should initially be treated as two eras rather than as an uninterrupted eight-year trend.

## 2. Latest-year State support

Selected 2025-26 State/UT/local-government distributions are:

| State/UT | Government schools | Student-weighted Muslim share | Exactly zero Muslim pupils | At least 50% Muslim | At least 90% Muslim | Median Muslim share among schools with any Muslim pupils |
|---|---:|---:|---:|---:|---:|---:|
| West Bengal | 79,490 | 35.97% | 43.59% | 26.13% | 13.07% | 42.86% |
| Assam | 44,423 | 44.21% | 49.74% | 33.05% | 25.46% | 90.91% |
| Uttar Pradesh | 136,541 | 15.85% | 41.26% | 7.93% | 1.81% | 12.09% |
| Bihar | 76,340 | 17.23% | 37.71% | 11.78% | 5.16% | 11.40% |
| Karnataka | 48,323 | 14.14% | 50.82% | 10.89% | 8.32% | 11.11% |
| Maharashtra | 64,460 | 14.43% | 67.39% | 5.51% | 4.21% | 9.09% |
| Jharkhand | 35,613 | 17.20% | 68.77% | 8.79% | 4.01% | 17.70% |
| Haryana | 14,273 | 17.75% | 51.43% | 8.78% | 6.07% | 5.88% |
| Kerala | 4,747 | 41.67% | 20.86% | 26.71% | 6.00% | 28.53% |
| Delhi | 2,636 | 19.95% | 1.37% | 12.37% | 3.76% | 11.08% |
| Jammu & Kashmir | 18,518 | 74.99% | 13.84% | 71.97% | 64.13% | 100.00% |

## 3. Distributional shapes

The raw one-percentage-point curves show substantively different support structures across States.

Assam is strongly bimodal. In the 2025-26 government sample, 50.96% of schools fall in the 0 to below-1% Muslim bin and another 16.16% are exactly 100% Muslim. The 98% and 99% bins are also unusually large. This is a segregation/sorting pattern first, not by itself an administrative-treatment result.

West Bengal also has a large low-Muslim mass and a pronounced high-Muslim tail. The 0 to below-1% bin contains 45.03% of government schools and the exact-100% bin contains 5.19%, but there is considerably more intermediate support than in Assam.

Bihar and Uttar Pradesh have large zero/near-zero masses but then decline much more continuously through the low and middle Muslim-share range. They therefore offer much better support for continuous within-location dose-response comparisons than a State dominated only by near-zero and near-100% schools.

Karnataka combines a large low-Muslim mass with a smaller but distinct exact-100% mass. Maharashtra, Jharkhand and Haryana also contain useful high-concentration schools but substantial geographic sorting must be addressed.

Delhi has almost no exact-zero Muslim government schools and its modal bins are around 4% to 9%, producing a comparatively smooth low-to-middle distribution, although its government-school sample is small.

Jammu & Kashmir is overwhelmingly high-Muslim and therefore has weak within-State counterfactual support for estimating a generic Muslim-concentration penalty. It is descriptively important but is unlikely to be a primary identification State for a within-State design.

## 4. Research implication

The density exercise separates two distinct empirical objects that should not be conflated:

1. **Sorting and segregation:** the extent to which Muslim pupils are concentrated into different schools, including near-homogeneous schools.
2. **Conditional administrative response:** once a government school exists and presents a comparable observable need or identical statutory entitlement, whether the State responds differently as predetermined Muslim enrolment share rises.

UDISE is especially strong for the second object because the panel repeatedly observes school need, staffing, facilities, grants, inspections and subsequent remediation. The first object can be described from UDISE but a causal account of why sorting arises would require additional residential, catchment, school-choice or school-location information.

The proposed paper should therefore avoid making a Muslim-majority indicator the treatment. Muslim share should remain continuous wherever common support exists, with categorical concentration bands used for transparent figures and robustness.

## 5. Immediate descriptive sequence before causal identification

The next descriptive layer should calculate within-State and within-district common support, segregation and administrative-outcome gradients. In particular:

- one State-by-year support table for 0, 1-10, 10-25, 25-50, 50-75, 75-90, 90-below-100 and exact-100 percent Muslim schools;
- district-level dissimilarity, isolation/exposure and entropy measures, plus the share of Muslim pupils attending schools above 50% and 90% Muslim;
- raw and district-residualised curves of teacher shortfall, major-repair need, functional toilets, functional water, electricity, internet, inspections and grant outcomes against predetermined Muslim share;
- separate curves for resource stocks and for administrative responses to documented need;
- a State ranking based on genuine within-district overlap, not merely the number of Muslim-majority schools.

West Bengal, Bihar and Uttar Pradesh are immediate high-value candidates because they combine large samples with substantial intermediate support. Assam is essential for the segregation story and can still support response analysis in districts with internal overlap. Karnataka and Haryana are useful additional contrasts. Jammu & Kashmir should not be used as though it supplies the same counterfactual support as Bihar or Uttar Pradesh.

## 6. Causal target

The primary causal question should be framed as conditional State response, not unconditional school quality:

> Among State/UT/local-government schools facing comparable observable educational need or identical statutory entitlement, does the probability, speed or magnitude of administrative response decline as predetermined Muslim enrolment share rises, and which State systems account for any such pattern?

The corresponding primary hypothesis is:

> Holding predetermined need or entitlement, geography, school size and class span, management subtype, social-category composition and baseline resources constant, higher predetermined Muslim enrolment share is associated with a lower probability, slower timing or smaller magnitude of subsequent State administrative response.

A national average should not be assumed in advance. The State-heterogeneity hypothesis is that any under-response is concentrated in particular State administrative systems, rather than being a common coefficient with the same sign everywhere.
