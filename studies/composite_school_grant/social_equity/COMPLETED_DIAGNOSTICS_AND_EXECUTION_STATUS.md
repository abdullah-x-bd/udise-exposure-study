# CSG social-equity extension: completed diagnostics and execution status

## Purpose

This note records which social-composition analyses were completed at each stage of the Composite School Grant project and which results were still pending at that point in the workflow. It is an execution-history document, not a substitute for the final correctly timed social-equity results in `ABSOLUTE_EQUITY_AUDIT.md` and `../FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md`.

## 1. Government-school universe

The original CSG timing analysis restricts management to UDISE codes 1, 2 and 3: Department of Education, Tribal Welfare Department and Local Body schools.

A broader State/UT-government definition used in the repository's earlier social-accountability work is codes 1, 2, 3, 6, 89 and 90. Government-aided and private management categories are separate and are not included in this broad State/UT-government definition.

In the processed 2024-25 school data, the management counts are:

- code 1: 774,126
- code 2: 39,771
- code 3: 194,059
- code 6: 865
- code 89: 25
- code 90: 2,287
- main central-government codes 92, 93, 94, 95, 96 and 101 together: 2,158

Thus the original codes 1/2/3 contain 1,007,956 schools, while the broader State/UT-government codes 1/2/3/6/89/90 contain 1,011,133 schools. The additional verified State/UT-government categories add only 3,177 schools, approximately 0.315 percent relative to the original core sample. Adding the main central-government categories adds a further 2,158 schools.

The original CSG result was therefore already estimated on almost the entire broad State/UT-government universe in 2024-25. Expanding management eligibility is an important robustness check but is quantitatively unlikely, by itself, to overturn the national timing result.

## 2. Social-composition definitions

The validated UDISE 2024-25 extraction uses separate marginal classifications.

Social category:

- General: item_group 1, item_id 1
- SC: item_group 1, item_id 2
- ST: item_group 1, item_id 3
- OBC: item_group 1, item_id 4

Religion/minority classification:

- Muslim: item_group 2, item_id 5
- Christian: item_group 2, item_id 6
- Sikh: item_group 2, item_id 7
- Buddhist: item_group 2, item_id 8
- Parsi: item_group 2, item_id 9
- Jain: item_group 2, item_id 10

Religion and social category are overlapping margins. A Muslim student may also be OBC, SC, ST or General. Total enrolment minus minority-religion shares minus SC/ST/OBC therefore does not produce a valid Hindu-General measure.

## 3. Correctly timed social-equity specification

The committed analysis `social_equity/run_social_equity.py` estimates whether the correctly timed 250/251 CSG threshold response changes with school social composition.

Its principal specification includes:

- enrolment vintages 2019-20, 2020-21, 2021-22 and 2022-23;
- financial outcomes from the aligned UDISE +3 reporting rounds;
- cutoff coordinate 250.5 and +/-30 enrolment window;
- broad State/UT-government sample 1/2/3/6/89/90;
- original 1/2/3 sample as a conservative replication;
- previous-year social composition as the predetermined heterogeneity variable;
- continuous social-composition interactions for inference;
- 5-percentage-point social-composition bins for presentation;
- year, state-by-year and district-by-year fixed-effect versions;
- management, rural/urban and school-category adjustment;
- state-clustered inference and Benjamini-Hochberg correction;
- whole-universe recorded-fidelity gradients as descriptive complements;
- state-specific gradients and school first-difference diagnostics.

It covers Muslim, Christian, Sikh, Buddhist, Parsi and Jain shares, and General, SC, ST and OBC shares. Religion and caste/social-category margins are never combined by subtraction.

## 4. Historical workflow interruption

The workflow `CSG social equity analysis` was triggered as GitHub Actions run 31869977299. At that point, GitHub rejected the job before runner startup with a platform message about failed recent payments or an Actions spending-limit issue.

This meant that no new four-cohort heterogeneous-RD coefficients were available from that specific run. The event was an execution/access limitation rather than an empirical null or failed statistical model.

Later completed analyses supersede this historical status note where results are now available.

## 5. Earlier 2024-25 adjusted grant-intensity diagnostic

A separate earlier analysis estimated 2024-25 cross-sectional associations between social composition and `grant_per_student` on 1,462,231 recognised schools. This is not the correctly lagged CSG RD and includes recognised management types beyond the CSG-eligible government universe, although it includes management-category controls.

The district-fixed-effect model controls for Muslim share; General, SC and ST shares with OBC omitted; log total enrolment; lowest and highest class; minority-managed status; shift-school status; residential-school status; rural/urban category; management-category indicators; and school-category indicators. Standard errors are clustered by district across 782 district clusters.

For a 10-percentage-point increase in the relevant share, the district-fixed-effect associations with reported grant per student are:

| Composition margin | Rupees per student per +10 pp | SE | 95% CI | Approx. p-value |
|---|---:|---:|---:|---:|
| Muslim share | -8.50 | 2.38 | -13.15 to -3.84 | 0.00035 |
| General share | +4.69 | 2.61 | -0.42 to +9.79 | 0.0721 |
| SC share | -9.00 | 2.26 | -13.43 to -4.57 | 0.000069 |
| ST share | -6.41 | 2.46 | -11.23 to -1.60 | 0.00906 |

These are cross-sectional associations in reported grant intensity. They motivated the formula-fidelity extension but do not identify the CSG formula effect, CSG entitlement or discriminatory treatment.

## 6. Earlier raw 2024-25 social gradients

The earlier comprehensive analysis also generated raw all-recognised-school concentration gradients. These are highly non-monotonic and differ greatly by social group, illustrating the importance of geography, management and school composition.

Examples comparing >0-5% group concentration with >75-100% concentration:

### No reported grant

- Muslim: 62.92% to 52.02%
- General: 45.77% to 47.48%
- SC: 56.49% to 26.77%
- ST: 64.07% to 34.10%
- OBC: 37.55% to 50.28%

### Reported grant per student

- Muslim: Rs 308.16 to Rs 342.47
- General: Rs 347.31 to Rs 591.26
- SC: Rs 288.52 to Rs 845.10
- ST: Rs 222.69 to Rs 753.51
- OBC: Rs 440.36 to Rs 413.02

These raw curves cannot be interpreted causally because they mix management systems, geography, school size, school stage and other determinants of funding.

## 7. Government-only need-conditioned diagnostic

An earlier accountability analysis restricts explicitly to State/local-government management codes 1,2,3,6,89,90. It contains both a `major_repair` indicator and `major_repair AND no_grant_received`. Their student-weighted affected-population ratio provides a descriptive measure of the share of students in schools with major-repair need whose school also reports no grant.

Nationally, comparing social-concentration bands:

### Muslim concentration

- >0-5% Muslim: 20.74% no-grant conditional on major repair
- >5-10%: 20.85%
- >10-20%: 19.28%
- >20-30%: 18.14%
- >30-40%: 16.31%
- >40-50%: 14.76%
- >50-75%: 14.17%
- >75-100%: 15.57%

### General concentration

At >75-100% General concentration, the corresponding student-weighted conditional no-grant share is 10.22%. The high-concentration Muslim-General difference is therefore about +5.35 percentage points in this particular need-conditioned measure.

This does not establish a general grant-receipt gap because conditioning on major repair changes the estimand and major repair itself is socially and geographically patterned.

## 8. State heterogeneity in the government-only diagnostic

For schools in the >75% concentration band, the government-only student-weighted conditional no-grant shares among major-repair schools are:

| State | Muslim | General | Muslim-General gap |
|---|---:|---:|---:|
| Assam | 21.38% | 21.38% | approximately 0.00 pp |
| Bihar | 45.60% | 40.82% | +4.78 pp |
| Jharkhand | 9.60% | 5.09% | +4.51 pp, weak General high-band support |
| Uttar Pradesh | 6.34% | 8.29% | -1.95 pp |
| Uttarakhand | 10.05% | 3.76% | +6.30 pp |

The sign is not uniform across States. This was one reason to move from raw national gradients to State-by-year, district-by-year and formula-specific analyses.

## 9. Interpretation of the historical diagnostics

The diagnostics in this file establish that:

1. the original CSG sample already covered almost all of the broad State/UT-government universe in 2024-25;
2. religion and social category can be reconstructed separately without inventing an invalid Hindu-General residual;
3. earlier 2024-25 cross-sectional models showed lower reported grant-per-student associations with higher Muslim, SC and ST shares after district fixed effects and observed school controls;
4. government-only need-conditioned diagnostics produced some high-concentration Muslim-General gaps, but those gaps varied materially across States and could reverse sign;
5. these patterns justified a correctly timed heterogeneous CSG threshold design rather than direct causal interpretation of the cross-section.

They did not, by themselves, establish weaker CSG formula transmission for Muslim, SC, ST or OBC schools, discriminatory intent, or verified underpayment.

## 10. Literature position at this stage

The targeted literature search found close but distinct work on school grants and household substitution, Samagra Shiksha aggregate budgets and implementation, DISE/UDISE social inequality, and other Indian school-policy interventions.

No close predecessor was located that reconstructed the CSG enrolment-to-finance reporting clock and exploited the 250/251 school-level formula cliff while testing heterogeneity by school social composition. This remains a bounded search result rather than a claim that no prior study exists anywhere.

## 11. Relation to the final project

This document is retained as a transparent record of the intermediate diagnostics and the workflow interruption that occurred before later analyses were completed. The final social-equity interpretation is in `ABSOLUTE_EQUITY_AUDIT.md` and `../FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md`.
