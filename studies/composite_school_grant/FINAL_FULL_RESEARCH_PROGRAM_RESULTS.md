# Final Full Research Program Results

## Composite School Grant formula transmission, administrative timing, State implementation, enrolment incentives, social composition and observable facility outcomes

This document records the final research design and results for the Composite School Grant study. Earlier exploratory summaries remain part of the project history but are superseded where they conflict with the corrected administrative clock or the completed robustness analyses.

## 1. Research question

This study is a public-finance implementation and administrative-measurement analysis of India's enrolment-based Composite School Grant.

The central questions are:

1. Does the CSG formula leave a measurable school-level financial fingerprint in UDISE?
2. What enrolment-to-allocation-to-UDISE reporting clock aligns the policy rule with the financial records?
3. How closely does the recorded CSG amount reproduce the formula-implied annual amount?
4. How much do timing, strength and durability of the recorded response differ across States and UTs?
5. Do enrolment densities and longitudinal crossings show evidence of CSG-specific strategic manipulation?
6. Does the formula response vary systematically with school social composition?
7. What do the available expenditure and facility outcomes add, and what do they not identify?

## 2. Institutional clock and primary design

The 250/251 threshold changes the CSG formula-implied annual amount from Rs 50,000 for enrolment 101-250 to Rs 75,000 for enrolment 251-1000. The econometric cutoff is therefore 250.5.

The documentary audit found that the Delhi CSG allocation orders examined use a two-academic-year-old UDISE enrolment vintage:

- CSG 2019-20 used UDISE 2017-18.
- CSG 2022-23 used UDISE+ 2020-21.
- CSG 2024-25 used UDISE+ 2022-23.

UDISE financial fields report grants received and expenditure during the previous financial year. The common national alignment supported by the documentary and empirical evidence is therefore:

**enrolment vintage T -> grant financial year T+2 -> UDISE financial report at T+3.**

This produces four usable assignment cohorts:

| Assignment enrolment | Grant financial year | UDISE financial-report field |
|---|---|---|
| 2019-20 | 2021-22 | 2022-23 |
| 2020-21 | 2022-23 | 2023-24 |
| 2021-22 | 2023-24 | 2024-25 |
| 2022-23 | 2024-25 | 2025-26 |

Earlier 6-8 percentage-point estimates came from a +2 reporting-round alignment and are superseded by the corrected timing specification.

## 3. Primary financial threshold response

The primary outcome is the probability that the correctly aligned UDISE field reports CSG receipt of at least Rs 75,000 near the 250/251 cutoff.

State-clustered `rdrobust` estimates are:

| Assignment cohort | UDISE report field | Threshold response | SE | p-value |
|---|---|---:|---:|---:|
| 2019-20 | 2022-23 | +24.70 pp | 12.34 pp | .0453 |
| 2020-21 | 2023-24 | +31.81 pp | 10.23 pp | .00188 |
| 2021-22 | 2024-25 | +33.21 pp | 8.85 pp | .000176 |
| 2022-23 | 2025-26 | +32.52 pp | 8.16 pp | .000067 |

A common +/-30 local-linear state-clustered replication produces +25.21, +32.88, +33.46 and +33.24 percentage points respectively.

The correctly aligned 99-percent-winsorised reported-receipt discontinuities are approximately:

- 2019-20: +Rs 9,469
- 2020-21: +Rs 13,136
- 2021-22: +Rs 14,421
- 2022-23: +Rs 13,106

The corresponding expenditure discontinuities are approximately Rs 8,981, Rs 11,593, Rs 13,275 and Rs 12,639.

The formula therefore shifts the distribution of reported school finance sharply, while the average recorded rupee change remains below the nominal Rs 25,000 difference between the two bands. The result is a fuzzy administrative threshold response rather than deterministic one-to-one recording of the formula amount.

## 4. Government-school universe robustness

The original confirmatory sample used UDISE management codes 1, 2 and 3: Department of Education, Tribal Welfare Department and Local Body schools.

A broader verified State/UT-government sensitivity uses codes 1, 2, 3, 6, 89 and 90. A further all-UDISE-government sensitivity adds the principal central-government management codes 92, 93, 94, 95, 96 and 101.

| Cohort | Core 1/2/3 | Broad State/UT govt | All-government sensitivity |
|---|---:|---:|---:|
| 2019-20 | +25.21 pp | +25.24 pp | +25.21 pp |
| 2020-21 | +32.88 pp | +32.87 pp | +32.87 pp |
| 2021-22 | +33.46 pp | +33.72 pp | +33.68 pp |
| 2022-23 | +33.24 pp | +33.42 pp | +33.38 pp |

The main threshold result is therefore not an artefact of the conservative original management filter.

## 5. Recorded grant fidelity

The formula does not create an exact Rs 75,000 point mass in UDISE.

At +/-30 around 250/251:

| Cohort | Exact Rs 50k | Exact Rs 75k | Receipt >= Rs 75k | Expenditure >= Rs 75k |
|---|---:|---:|---:|---:|
| 2019-20 | -3.25 pp | +2.29 pp | +25.21 pp | +23.79 pp |
| 2020-21 | -6.20 pp | +3.92 pp | +32.88 pp | +30.37 pp |
| 2021-22 | -7.11 pp | +5.29 pp | +33.46 pp | +32.83 pp |
| 2022-23 | -6.67 pp | +6.53 pp | +33.24 pp | +31.96 pp |

Crossing 250 moves schools away from the lower-band exact amount and toward the upper financial region, but exact Rs 75,000 recording rises by only roughly 2-7 percentage points.

This is treated as imperfect recorded fiscal fidelity. A difference between the formula-implied amount and the UDISE CSG receipt field is a recorded administrative realization gap. UDISE alone cannot determine which part reflects approval, authorization, utilization, balances, timing, carry-forward or reporting, so the gap is not automatically classified as an unpaid cash obligation.

## 6. Multi-threshold formula fingerprint

The correctly aligned financial data also move at the other CSG boundaries.

For `P(receipt >= formula-implied target)`:

| Threshold | Target | 2019-20 | 2020-21 | 2021-22 | 2022-23 |
|---|---:|---:|---:|---:|---:|
| 30/31 | Rs 25k | +24.58 pp | +27.22 pp | +30.52 pp | +30.03 pp |
| 100/101 | Rs 50k | +34.27 pp | +39.46 pp | +40.51 pp | +39.99 pp |
| 250/251 | Rs 75k | +25.21 pp | +32.88 pp | +33.46 pp | +33.24 pp |
| 1000/1001 | Rs 100k | +15.07 pp | +11.36 pp | +19.44 pp | +15.02 pp |

The repetition across formula boundaries makes a coincidental 250-specific discontinuity substantially less plausible. The 250/251 threshold remains the primary identification threshold because 100/101 overlaps PM POSHAN rules, 30/31 has historical schedule complications and 1000/1001 is much sparser.

## 7. PM POSHAN isolation

The 250/251 CSG threshold overlaps a PM POSHAN kitchen-device threshold based on Classes I-VIII enrolment. Restricting schools near total Classes I-XII enrolment 250 so that Classes I-VIII enrolment remains safely below the PM POSHAN boundary preserves a positive financial response.

For Classes I-VIII enrolment <=220, the four local responses are approximately +17.48, +11.94, +20.81 and +26.22 percentage points. Results are similar at <=200.

This does not eliminate every possible State-specific coincident rule, but it materially weakens the principal national-programme confound.

## 8. State implementation heterogeneity

The same national formula produces dramatically different recorded financial responses across States and UTs. Four-cohort mean State responses at 250/251 include:

| State/UT | Mean threshold response |
|---|---:|
| Chhattisgarh | +67.1 pp |
| Uttar Pradesh | +66.7 pp |
| Delhi | +65.7 pp |
| Haryana | +55.3 pp |
| Gujarat | +46.0 pp |
| Jammu & Kashmir | +44.8 pp |
| Jharkhand | +33.8 pp |
| Rajasthan | +26.9 pp |
| Assam | +26.1 pp |
| Tamil Nadu | +25.7 pp |
| Bihar | +18.9 pp |
| Madhya Pradesh | +17.0 pp |
| Andhra Pradesh | +14.8 pp |
| West Bengal | +13.5 pp |
| Kerala | +12.6 pp |
| Karnataka | +8.1 pp |
| Odisha | +7.9 pp |
| Punjab | +7.7 pp |
| Maharashtra | +7.6 pp |
| Telangana | +2.0 pp |
| Himachal Pradesh | -0.3 pp |

These differences establish large heterogeneity in the State-level administrative realization of the same national formula in the CSG-specific UDISE receipt field. They do not, from UDISE alone, identify the precise administrative stage responsible for each formula-to-record difference.

State patterns are persistent over time and replicate strongly across separate CSG thresholds, which is consistent with systematic State administrative environments rather than one-cutoff noise.

## 9. State-specific timing and record-convergence latency

Across 92 state-cohort cells, the lag with the largest positive 250/251 financial discontinuity is:

- lag 0: 9 cells
- lag +1: 5 cells
- lag +2: 7 cells
- lag +3: 65 cells
- lag +4: 6 cells

Thus +3 is the modal best lag in 70.7 percent of state-cohort cells.

The longitudinal first-recorded-convergence analysis adds a second timing concept. Among continuously eligible schools, national N50 is T+3 at all three clean thresholds. N80 is T+4 at 100/101 and 250/251 and T+5 at 1000/1001. These values measure the first observed cycle by which 50% or 80% have ever recorded at least the corresponding formula amount in UDISE. They are not cash-transfer times.

State N50/N80 values vary substantially. At 250/251, some States reach N80 by T+2 or T+3, while others do not reach N80 within the observed T+6 horizon. The ordering also replicates across independent CSG thresholds.

A separate current-recording analysis shows why first convergence and durable fidelity are different objects. National current recording at or above the formula amount does not reach 80% through T+6 at any clean threshold even though first-recorded-convergence N80 is reached earlier.

## 10. Enrolment density, heaping and manipulation tests

Administrative enrolment data exhibit visible heaping and non-smoothness at several policy-relevant and round-number values.

At 100/101, the heaping-adjusted asymmetry is much larger than at 250/251. The 100 region cannot be interpreted as a clean CSG behavioural response because it is both a salient round number and implicated by other school-program rules, including PM POSHAN.

Around 250/251, the irregularity is smaller but repeated:

| UDISE year | Heaping-adjusted asymmetry |
|---|---:|
| 2018-19 | 0.127 |
| 2019-20 | 0.143 |
| 2020-21 | 0.164 |
| 2021-22 | 0.175 |
| 2022-23 | 0.092 |
| 2023-24 | 0.057 |
| 2024-25 | 0.063 |
| 2025-26 | 0.064 |

Placebo-cutoff comparisons and longitudinal landing/reversion tests do not distinguish 250/251 strongly enough to establish a CSG-specific manipulation mechanism. Across six possible three-year windows, true-minus-placebo averages are only about +0.32 pp for approach/landing, -0.15 pp for subsequent reversion and +0.45 pp for projected threshold landing.

The supported conclusion is therefore that heaping and local irregularity are present, but the evidence does not establish systematic CSG-induced enrolment manipulation, gaming or fraud.

## 11. Enrolment churn and formula stability

The longitudinal panel also shows that annual formula assignment reacts to enrolment movements that are often temporary.

For clean downward crossings:

- 100/101: 89.84% reverse within two years;
- 250/251: 91.13% reverse within two years;
- 1000/1001: 91.40% reverse within two years.

The weighted clean-threshold two-year reversal rate is about **90.2%** across 242,769 downward crossings with the required follow-up.

A full-panel counterfactual using the average of the latest two enrolment snapshots reduces simulated band changes by about 26%, A-B-A ping-pong reversals by about 65% and nominal volatility by about 26%, with illustrative incremental nominal exposure of about 0.53%. The exact rupee figure is treated cautiously because the <=30 historical schedule changed.

This provides the main policy-design motivation for testing a more stable band-assignment rule rather than allowing every annual threshold crossing to change formula support immediately.

## 12. Recorded persistence under unchanged formula amount

When a school's formula-implied amount remains unchanged but its UDISE CSG receipt record falls below that amount, the recorded gap is usually not eliminated over the next two observed cycles.

Among complete clean-threshold cases, two-cycle cumulative recorded convergence is approximately:

- 100/101: 13.33%
- 250/251: 15.81%
- 1000/1001: 11.51%

Weighted across the clean thresholds, only **14.1%** of complete cases converge cumulatively within two additional observed cycles. This is an administrative-record persistence statistic, not a measure of unpaid money.

Among complete clean-threshold cases followed for two cycles, 59.4% finish with a cumulative recorded gap larger than the initial gap.

## 13. Recorded receipt and expenditure

UDISE CSG receipt and expenditure move very closely together. Across the clean thresholds, receipt/expenditure capped-ratio correlations are roughly 0.94-0.95.

In matched State x formula-band x aligned-cycle comparisons, all 152 supported clean-threshold cells comparing a downward receipt-record transition with stable recording show lower expenditure ratios, while all 134 supported clean-threshold recovery cells show higher expenditure ratios. The broader all-band counts are 315/315 and 274/274 respectively.

This is strong internal administrative/accounting co-movement. It is not independent validation that lower recorded receipt caused lower real expenditure because receipt and expenditure can be generated by the same underlying accounting and drawing process.

## 14. Social-composition design and results

The social-equity extension uses the correctly timed formula response rather than contemporaneous grant-per-student regressions.

The preferred specification uses the four aligned cohorts, broad State/UT-government universe, +/-30 around 250.5, previous-year social composition, district-by-year fixed effects, management/rural/school-category controls, state-clustered inference, multiple-testing correction, joint compositional models and false cutoffs.

Religion and social category are separate UDISE classifications. General, SC, ST and OBC are mutually exclusive within the social-category margin, while Muslim, Christian, Sikh, Buddhist, Parsi and Jain are religion/minority categories. A pupil can belong to one category in each margin, so subtracting religion and caste shares together cannot identify a Hindu-General or upper-caste-Hindu population.

Estimated change in the 250/251 response per +10 percentage points of group share in the preferred pooled model is:

| Composition share | Change in threshold response | p |
|---|---:|---:|
| Muslim | -0.18 pp | .733 |
| SC | +1.37 pp | .276 |
| ST | -1.20 pp | .318 |
| OBC | +0.94 pp | .149 |
| General | -1.16 pp | .101 |

No univariate group survives FDR correction. In the joint social-category model, the Wald test is p=.391. The pooled Muslim coefficient in the joint religion model is -0.26 pp per +10 percentage points, p=.615, and the religion-family joint test at the true cutoff is p=.248.

Nominal negative coefficients for some smaller religious groups fail multiplicity control and cutoff specificity because the religion family is also strongly significant at fake cutoffs 200.5 and 300.5.

The formula-specific conclusion is therefore no robust evidence that the 250/251 CSG threshold response systematically weakens as Muslim, SC, ST, OBC, General or residual-religion concentration rises.

Separate absolute-level analyses identify some descriptive State and group differences in recorded target fidelity. Those are documented in `social_equity/ABSOLUTE_EQUITY_AUDIT.md` and are not equivalent to differential application of the 250/251 formula threshold.

## 15. Correctly timed facility sensitivity

A secondary fuzzy-RD sensitivity treats `UDISE reported CSG receipt >= Rs 75,000` as an endogenous administrative treatment and uses the 250/251 threshold as the instrument.

This is not an audited PFMS cash-receipt treatment and is therefore interpreted as a sensitivity rather than a definitive causal estimate of the return to additional CSG resources.

For the 2021-22 assignment cohort:

- 2024-25 deterioration LATE: +0.0002, 95% CI approximately -0.0437 to +0.0440, p=.995;
- 2025-26 deterioration LATE: +0.0097, CI -0.0227 to +0.0420, p=.558.

For the 2022-23 assignment cohort:

- 2025-26 deterioration LATE: +0.0034, CI -0.0174 to +0.0242, p=.748.

Upgrade estimates are extremely imprecise.

The narrow conclusion is that the study does not detect a large improvement or deterioration in these coarse UDISE-observed asset-transition measures. It does not establish that CSG has no value. Many official CSG uses involve consumables, minor repairs, utilities, connectivity, teaching materials and recurring activities that are poorly represented by binary stock indicators.

## 16. Literature position

The targeted literature review identifies related work on school grants and household substitution, Samagra Shiksha budgets and implementation, DISE/UDISE social inequality, and regression-discontinuity applications in Indian education.

The search did not identify a close predecessor that reconstructs the CSG enrolment-to-allocation-to-UDISE reporting clock, exploits the school-level CSG formula cliff to measure recorded financial transmission, and then tests that response across States, thresholds and school social composition.

The novelty claim is therefore deliberately bounded: **no close predecessor using this design was located in the targeted search**.

## 17. What the final analysis establishes

### Strongly supported

1. The CSG enrolment formula leaves a large, replicating school-level financial fingerprint in UDISE when administrative timing is aligned correctly.
2. The dominant national response appears at T+3, consistent with a two-year-old allocation enrolment vintage plus the previous-financial-year UDISE reporting convention.
3. The financial fingerprint replicates at multiple CSG thresholds.
4. Crossing 250/251 changes reported CSG receipt and expenditure substantially, while exact formula amounts are only imperfectly reproduced in the administrative field.
5. The result is essentially unchanged when the school-management universe is broadened.
6. Formula realization in the UDISE CSG receipt record varies enormously and persistently across States and UTs.
7. State response latency and response strength are separate dimensions, and State patterns replicate across thresholds.
8. Around 90% of observed clean-threshold downward enrolment crossings with two-year follow-up reverse within two years.
9. Enrolment heaping is present, especially around 100, but placebo and longitudinal evidence does not support a CSG-specific manipulation interpretation at 250/251.
10. There is no robust national evidence that the 250/251 formula response weakens with Muslim, SC, ST, OBC, General or residual-religion concentration.
11. Predetermined social composition is continuous at the cutoff after multiple-testing correction.
12. Correctly timed facility sensitivities do not reveal large effects on the coarse asset-transition outcomes observed in UDISE.

### Interpretations not identified by the study

1. The formula does not mechanically increase the UDISE receipt field by exactly Rs 25,000 for every school.
2. A school whose UDISE CSG receipt field is below the formula-implied amount cannot automatically be classified as having been denied that amount in cash.
3. The density evidence does not establish systematic enrolment manipulation or fraud.
4. The preferred models do not establish a Muslim, SC or ST penalty in the CSG threshold response.
5. Nominal smaller-religion coefficients do not establish discrimination.
6. The design does not identify the causal effect of exactly Rs 25,000 of additional cash received on school expenditure or facilities.
7. The facility results do not support a general conclusion that CSG has no value.
8. Religion and caste margins cannot be subtracted to recover a Hindu-General population.

## 18. Research contribution

The study's central contribution is the reconstruction of a national formula's administrative transmission through school-level data.

> **A formally simple enrolment-based school-funding rule is clearly visible in India's school-level administrative accounts once the policy's allocation and reporting clocks are reconstructed. The size, timing and durability of the recorded response vary sharply across States; formula-implied amounts are only imperfectly reproduced in the UDISE CSG receipt field; temporary enrolment movements generate substantial band churn; and the 250/251 threshold does not show a distinctive longitudinal manipulation pattern. The quasi-experimental formula response also does not systematically weaken as Muslim or major social-category concentration rises.**

Working title:

**The Formula Bites, But the Records Lag: Tracing School Funding Rules Through India's Administrative Data**

## 19. Remaining external-data limitation

The most valuable external extension would be school-level linkage to audited or transaction-level PFMS/SNA/PRABANDH or State records identifying approval, authorization, draw, balances and expenditure for the CSG component.

Such a linkage would separate the stages behind the formula-to-UDISE realization gap. Until that linkage is available, the study consistently distinguishes `formula-implied amount`, `UDISE-reported CSG receipt`, `recorded administrative realization` and verified cash disbursement.
