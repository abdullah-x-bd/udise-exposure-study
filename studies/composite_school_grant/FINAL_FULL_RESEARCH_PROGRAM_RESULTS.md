# Final Full Research Program Results

## Composite School Grant formula transmission, administrative timing, state implementation, enrolment incentives, social composition, and observable facility outcomes

This document supersedes earlier exploratory and red-team headline summaries where they conflict with the results below. It records the final research design actually executed after correcting the Composite School Grant administrative clock and completing the previously blocked robustness and social-equity experiments.

## 1. Final research question

The strongest study is not an impact paper asking whether an extra Rs 25,000 mechanically improves a binary UDISE facility variable. It is a public-finance implementation and administrative-measurement study.

The central questions are:

1. Does India's enrolment-based Composite School Grant formula leave a measurable school-level financial fingerprint in UDISE?
2. What is the correct enrolment-to-allocation-to-UDISE reporting clock?
3. How faithfully does the recorded amount reproduce the statutory band?
4. How much does formula transmission differ across States and UTs?
5. Does the formula induce strategic enrolment manipulation around the funding thresholds?
6. Does formula transmission weaken as schools serve larger shares of Muslim, SC, ST, OBC, General, or other religious-minority populations?
7. Is a higher formula-induced reported grant associated with subsequent changes in the coarse school-facility outcomes observable in UDISE?

## 2. Institutional clock and main design

The statutory 250/251 threshold changes the Composite School Grant band from Rs 50,000 for enrolment 101-250 to Rs 75,000 for enrolment 251-1000. The econometric cutoff is therefore 250.5.

The documentary audit found that the Delhi CSG allocation orders examined use a two-academic-year-old UDISE enrolment vintage:

- CSG 2019-20 used UDISE 2017-18.
- CSG 2022-23 used UDISE+ 2020-21.
- CSG 2024-25 used UDISE+ 2022-23.

UDISE financial fields record grants received and expenditure during the previous financial year. Consequently, an enrolment assignment vintage t maps to the CSG grant financial year t+2 and then appears in the UDISE financial field at t+3.

This produces four clean, usable assignment cohorts in the available panel:

| Assignment enrolment | Grant financial year | UDISE financial-report field |
|---|---|---|
| 2019-20 | 2021-22 | 2022-23 |
| 2020-21 | 2022-23 | 2023-24 |
| 2021-22 | 2023-24 | 2024-25 |
| 2022-23 | 2024-25 | 2025-26 |

The original 6-8 percentage-point figures were based on a +2 UDISE round alignment. They are superseded. The sharp administrative response occurs at +3.

## 3. Main financial first stage

The primary outcome is the probability that the correctly aligned UDISE field reports Composite School Grant receipt of at least Rs 75,000 near the 250/251 cutoff.

State-clustered `rdrobust` estimates are:

| Assignment cohort | UDISE report field | First-stage jump | SE | p-value |
|---|---|---:|---:|---:|
| 2019-20 | 2022-23 | +24.70 pp | 12.34 pp | .0453 |
| 2020-21 | 2023-24 | +31.81 pp | 10.23 pp | .00188 |
| 2021-22 | 2024-25 | +33.21 pp | 8.85 pp | .000176 |
| 2022-23 | 2025-26 | +32.52 pp | 8.16 pp | .000067 |

A common +/-30 local-linear state-clustered replication produces +25.21, +32.88, +33.46, and +33.24 percentage points respectively.

The correctly aligned 99-percent-winsorized reported-receipt discontinuities are approximately:

- 2019-20: +Rs 9,469
- 2020-21: +Rs 13,136
- 2021-22: +Rs 14,421
- 2022-23: +Rs 13,106

The corresponding expenditure discontinuities are approximately Rs 8,981, Rs 11,593, Rs 13,275, and Rs 12,639.

Interpretation: the statutory formula strongly shifts the distribution of reported school finance, but the average recorded amount change is substantially smaller than the nominal Rs 25,000 difference between the two bands. This is a fuzzy administrative first stage, not deterministic compliance.

## 4. Government-school universe robustness

The original confirmatory sample used UDISE management codes 1, 2 and 3: Department of Education, Tribal Welfare Department, and Local Body schools.

A broader verified State/UT-government sensitivity uses codes 1, 2, 3, 6, 89, and 90. A further all-UDISE-government sensitivity adds the principal central-government management codes 92, 93, 94, 95, 96, and 101.

The direct head-to-head first stages are:

| Cohort | Core 1/2/3 | Broad State/UT govt | All-government sensitivity |
|---|---:|---:|---:|
| 2019-20 | +25.21 pp | +25.24 pp | +25.21 pp |
| 2020-21 | +32.88 pp | +32.87 pp | +32.87 pp |
| 2021-22 | +33.46 pp | +33.72 pp | +33.68 pp |
| 2022-23 | +33.24 pp | +33.42 pp | +33.38 pp |

Thus the headline financial discontinuity is not an artefact of the conservative original management filter. In the processed 2024-25 universe, the original 1/2/3 categories already contained 1,007,956 schools versus 1,011,133 in the broader State/UT-government definition.

## 5. Exact grant fidelity

The formula does not simply create an exact Rs 75,000 point mass.

At +/-30 around 250/251:

| Cohort | Exact Rs 50k | Exact Rs 75k | Receipt >= Rs 75k | Expenditure >= Rs 75k |
|---|---:|---:|---:|---:|
| 2019-20 | -3.25 pp | +2.29 pp | +25.21 pp | +23.79 pp |
| 2020-21 | -6.20 pp | +3.92 pp | +32.88 pp | +30.37 pp |
| 2021-22 | -7.11 pp | +5.29 pp | +33.46 pp | +32.83 pp |
| 2022-23 | -6.67 pp | +6.53 pp | +33.24 pp | +31.96 pp |

The consistent pattern is important. Crossing 250 moves schools away from the lower-band exact amount and toward the upper financial region, but exact statutory recording rises by only roughly 2-7 percentage points.

This should be described as imperfect recorded fiscal fidelity. It should not be interpreted as proof that schools below Rs 75,000 were denied their entitlement. Timing, balances, instalments, accounting conventions, partial releases, or UDISE reporting can all contribute.

## 6. Multi-threshold formula fingerprint

The correctly aligned financial data also move at the other statutory CSG boundaries. These are formula-fingerprint tests rather than four separate causal outcome designs because other programmes overlap some thresholds and the small-school schedule changed historically.

For `P(receipt >= statutory target)`:

| Threshold | Target | 2019-20 | 2020-21 | 2021-22 | 2022-23 |
|---|---:|---:|---:|---:|---:|
| 30/31 | Rs 25k | +24.58 pp | +27.22 pp | +30.52 pp | +30.03 pp |
| 100/101 | Rs 50k | +34.27 pp | +39.46 pp | +40.51 pp | +39.99 pp |
| 250/251 | Rs 75k | +25.21 pp | +32.88 pp | +33.46 pp | +33.24 pp |
| 1000/1001 | Rs 100k | +15.07 pp | +11.36 pp | +19.44 pp | +15.02 pp |

The repetition across formula boundaries makes a coincidental 250-specific discontinuity substantially less plausible. The 250/251 threshold remains the primary design because 100/101 overlaps PM POSHAN rules, 30/31 has historical schedule complications, and 1000/1001 is much sparser.

## 7. PM POSHAN isolation

The CSG 250/251 threshold overlaps a PM POSHAN kitchen-device threshold based on Classes I-VIII enrolment. Restricting schools near total Classes I-XII enrolment 250 so that Classes I-VIII enrolment remains safely below the PM POSHAN boundary preserves the financial first stage.

For Classes I-VIII enrolment <=220, the four local first stages are approximately +17.48, +11.94, +20.81, and +26.22 percentage points. Results are similar at <=200.

This does not prove that no state-specific programme shares the cutoff, but it materially weakens the principal national-programme confound.

## 8. State implementation heterogeneity

The same national formula produces dramatically different reported financial discontinuities across States and UTs. Four-cohort mean state first stages are:

| State/UT | Mean first stage |
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
| Tripura | +19.4 pp |
| Bihar | +18.9 pp |
| Madhya Pradesh | +17.0 pp |
| Andhra Pradesh | +14.8 pp |
| West Bengal | +13.5 pp |
| Kerala | +12.6 pp |
| Karnataka | +8.1 pp |
| Odisha | +7.9 pp |
| Punjab | +7.7 pp |
| Maharashtra | +7.6 pp |
| Uttarakhand | +6.1 pp |
| Telangana | +2.0 pp |
| Himachal Pradesh | -0.3 pp |

These figures should be interpreted as variation in the strength of the UDISE-recorded formula fingerprint, not automatically as variation in actual cash delivery. Differences in release practices, accounting, reporting, grant administration, and measurement can all contribute.

State rankings are meaningfully persistent over time, particularly between the two latest cohorts. This is consistent with persistent administrative systems rather than pure sampling noise.

## 9. State-specific timing

The +3 clock is not merely a national average.

Across 92 state-cohort cells, the lag with the largest positive 250/251 financial discontinuity is:

- lag 0: 9 cells
- lag +1: 5 cells
- lag +2: 7 cells
- lag +3: 65 cells
- lag +4: 6 cells

Thus +3 is the modal best lag in 70.7 percent of state-cohort cells.

Assam, Chhattisgarh, Delhi, Gujarat, Haryana, Jammu & Kashmir, Jharkhand, Madhya Pradesh, Rajasthan, and Uttar Pradesh select +3 in all four cohorts. Bihar, Karnataka, Maharashtra, and West Bengal select +3 in three of four. Telangana selects +3 in none.

The state-level average financial discontinuity is sharply concentrated at +3 and much smaller at the surrounding lags.

## 10. Bunching and strategic enrolment manipulation

Heaping-adjusted above-versus-below asymmetry around 250/251 is modest and declines in later years:

| UDISE year | Asymmetry |
|---|---:|
| 2018-19 | 0.127 |
| 2019-20 | 0.143 |
| 2020-21 | 0.164 |
| 2021-22 | 0.175 |
| 2022-23 | 0.092 |
| 2023-24 | 0.057 |
| 2024-25 | 0.063 |
| 2025-26 | 0.064 |

Dedicated placebo-cutoff comparisons show that the 250 pattern is not exceptional enough to establish strategic manipulation.

The longitudinal crossing/reversion analysis provides a stronger falsification. Across six possible three-year windows, comparing the true 250 threshold with placebo thresholds at 200 and 300, the true-minus-placebo averages are only about:

- +0.32 percentage points for approach/landing from the last 20 below to the first 5 above;
- -0.15 percentage points for subsequent reversion;
- +0.45 percentage points for projected threshold landing.

These are tiny.

State formula strength also does not predict stronger bunching. State first-stage versus bunching correlations across the four cohorts are about .16, .31, .17, and .07; permutation p-values are all above .23.

Final conclusion: there is modest repeated bunching/heaping around the cutoff, but the evidence does not support a claim of systematic strategic enrolment manipulation, gaming, or fraud induced by CSG.

## 11. Social-composition design

The social-equity extension was rebuilt around the correctly timed formula discontinuity itself, not contemporaneous grant-per-student regressions.

The preferred specification uses:

- the four correctly aligned assignment cohorts;
- the broad State/UT-government universe;
- +/-30 around 250.5;
- previous-year school social composition as a predetermined heterogeneity variable;
- the outcome `P(UDISE reported CSG receipt >= Rs 75,000)`;
- management, rural/urban, and school-category controls;
- State-by-year and district-by-year fixed-effect versions;
- state-clustered inference;
- core 1/2/3 and broader/all-government sensitivity samples;
- continuous share interactions for inference;
- 5-percentage-point bins for presentation;
- multiple-testing correction;
- joint compositional models;
- false cutoffs at 200.5 and 300.5;
- state-specific joint models and support diagnostics;
- school first-difference diagnostics.

Social category and religion are separate marginal classifications. General, SC, ST, and OBC are mutually exclusive within the social-category margin. Muslim, Christian, Sikh, Buddhist, Parsi, and Jain are separately recorded religion/minority categories. A student can be both Muslim and OBC, for example. Therefore no `total - minority religions - SC - ST - OBC` variable is constructed. Such a residual would double-subtract overlapping students and cannot identify Hindu-General or upper-caste-Hindu pupils.

The valid alternatives are:

- General share within the social-category classification; and
- residual/non-listed-religion share within the religion classification.

## 12. Predetermined social-composition continuity

Before interpreting heterogeneity, previous-year group shares were tested for their own discontinuity at the current 250/251 cutoff.

Across 44 group-by-cohort state-clustered continuity tests, only one raw p-value is below .05. None survives Benjamini-Hochberg correction; the smallest adjusted q-value is approximately .159. Muslim share shows no discontinuity in any cohort.

This supports using previous-year composition as a predetermined heterogeneity measure around the funding threshold.

## 13. Primary social-composition results

The pooled preferred district-by-year model contains 171,464 local school-year observations.

Estimated change in the 250/251 financial first stage per +10 percentage points of group share:

| Composition share | Change in first stage | 95% CI | p | BH q across 11 univariate group tests |
|---|---:|---:|---:|---:|
| Muslim | -0.18 pp | -1.19 to +0.84 | .733 | .807 |
| SC | +1.37 pp | -1.10 to +3.85 | .276 | .379 |
| ST | -1.20 pp | -3.55 to +1.15 | .318 | .389 |
| OBC | +0.94 pp | -0.33 to +2.21 | .149 | .273 |
| General | -1.16 pp | -2.56 to +0.23 | .101 | .267 |
| Residual/non-listed religion | +0.57 pp | -0.33 to +1.47 | .212 | .333 |
| Christian | -3.21 pp | -6.30 to -0.11 | .042 | .154 |
| Sikh | -2.64 pp | -4.69 to -0.59 | .011 | .126 |
| Buddhist | -7.92 pp | -15.28 to -0.56 | .035 | .154 |
| Jain | -23.25 pp | -52.68 to +6.17 | .121 | .267 |
| Parsi | -6.38 pp | -59.26 to +46.50 | .813 | .813 |

No group survives family-wide FDR correction.

The Muslim estimate is essentially zero and is stable across the core, broad-State, and all-government samples. Cohort-specific Muslim interactions are also null and do not show a replicating negative pattern.

## 14. The requested 0-5 percent through 95-100 percent curves

These are presentation estimates, not the primary inferential specification. Each cell is the estimated 250/251 jump in `P(reported receipt >= Rs 75,000)` for schools in that composition band, in percentage points.

| Share bin | Muslim | SC | ST | OBC | General |
|---|---:|---:|---:|---:|---:|
| 0-5% | 29.3 | 29.2 | 33.8 | 24.0 | 31.6 |
| 5-10% | 33.6 | 27.0 | 22.8 | 25.1 | 34.1 |
| 10-15% | 35.5 | 27.5 | 21.9 | 21.9 | 31.7 |
| 15-20% | 37.2 | 28.8 | 23.3 | 29.4 | 31.4 |
| 20-25% | 37.9 | 29.7 | 19.4 | 26.8 | 30.0 |
| 25-30% | 29.5 | 29.7 | 22.5 | 28.9 | 30.5 |
| 30-35% | 35.0 | 29.2 | 29.2 | 31.4 | 23.7 |
| 35-40% | 44.0 | 34.3 | 21.0 | 30.6 | 30.7 |
| 40-45% | 45.6 | 37.0 | 17.9 | 33.6 | 22.6 |
| 45-50% | 38.4 | 38.0 | 32.0 | 36.3 | 26.7 |
| 50-55% | 26.5 | 39.0 | 27.0 | 35.2 | 31.0 |
| 55-60% | 37.7 | 40.9 | 21.7 | 32.7 | 18.3 |
| 60-65% | 32.7 | 33.2 | 26.5 | 30.9 | 18.6 |
| 65-70% | 33.7 | 33.2 | 21.8 | 33.4 | 13.3 |
| 70-75% | 20.7 | 34.0 | 25.3 | 31.1 | 20.6 |
| 75-80% | 33.4 | 37.1 | 24.9 | 35.5 | 10.8 |
| 80-85% | 27.5 | 33.7 | 26.0 | 32.2 | 23.5 |
| 85-90% | 30.4 | 41.8 | 14.1 | 32.7 | 29.7 |
| 90-95% | 26.3 | 24.6 | 25.2 | 33.8 | 27.6 |
| 95-100% | 25.4 | 29.0 | 28.1 | 32.4 | 23.7 |

The central fact is not the noise in individual bins. It is that every displayed bin for all five major composition margins retains a positive formula first stage. There is no monotonic collapse in formula transmission as Muslim, SC, ST, OBC, or General concentration rises.

For Muslim share specifically, the first stage is 29.3 pp at 0-5 percent and 25.4 pp at 95-100 percent, with substantial non-monotonic variation in between. The continuous preferred interaction is statistically zero.

Extreme bins for smaller religious groups have very sparse support and are not suitable for the same visual interpretation.

## 15. Joint compositional models

Because General, SC, ST, and OBC shares sum to one, estimating each separately can be misleading. The final social-category model enters SC, ST, and OBC jointly, with General as the omitted reference.

In the four-cohort pooled, previous-year-composition, district-by-year, state-clustered model:

| Relative composition change | First-stage interaction | 95% CI | p |
|---|---:|---:|---:|
| SC relative to General | +1.92 pp per +10 pp | -0.70 to +4.55 | .151 |
| ST relative to General | +0.02 pp | -1.44 to +1.47 | .984 |
| OBC relative to General | +1.33 pp | -0.24 to +2.90 | .096 |

The joint social-category Wald test is chi-square(3)=3.00, p=.391.

Thus the cohort-level suggestion of a modestly stronger SC/OBC formula response is not strong enough under the correct pooled state-clustered model. The correct conclusion is no robust social-category heterogeneity.

The religion model enters Muslim, Christian, Sikh, Buddhist, Parsi, and Jain jointly, with the residual/non-listed-religion share as the omitted reference.

The pooled Muslim coefficient is -0.26 pp per +10 percentage points, 95% CI -1.27 to +0.75, p=.615. The religion-family joint Wald test at the real 250/251 cutoff is p=.248.

Christian, Sikh, and Buddhist individual coefficients are nominally negative, but none survives a correction across the pooled joint coefficients. More importantly, the entire religion family is strongly significant at fake cutoffs where no CSG band changes:

- false cutoff 200.5: joint p approximately 1.0e-19;
- false cutoff 300.5: joint p approximately .00032.

Those smaller-religion associations therefore fail cutoff specificity. They should not be interpreted as CSG formula-transmission effects.

## 16. State-wise social composition

State-specific social models were estimated jointly within the compositional families, using previous-year composition, district fixed effects, and district-clustered inference where support was sufficient.

There is no uniform Muslim pattern.

Large states with substantial within-state Muslim-share variation such as Assam, Bihar, Uttar Pradesh, West Bengal, Karnataka, Gujarat, and Jharkhand do not display a consistent negative formula-transmission gradient across cohorts.

Two exploratory state summaries initially appeared notable in opposite directions:

- Chhattisgarh: positive Muslim interaction;
- Tamil Nadu: negative Muslim interaction.

The support audit shows why these should not be treated symmetrically. Around the cutoff in Chhattisgarh, mean previous-year Muslim share is only about 0.7-0.8 percent, its 90th percentile is only roughly 1.7-2.5 percent, and only about 1.4-1.7 percent of schools reach 10 percent Muslim. A coefficient expressed per +10 percentage points is therefore extrapolating far beyond common local support.

Tamil Nadu has more support, but its negative coefficient is statistically significant in only two of four cohort models and remains an exploratory state-specific association after a large state-by-group search.

Final conclusion: state-wise work reveals major administrative heterogeneity in overall CSG formula transmission, but not a coherent national or state-replicating Muslim disadvantage mechanism.

## 17. Descriptive whole-universe funding gradients are not the causal result

Older 2024-25 cross-sectional regressions had shown lower contemporaneous reported grant per student as Muslim, SC, and ST shares rose. Those regressions were useful motivation but did not reconstruct CSG entitlement or the correct administrative clock.

The properly timed formula-discontinuity design does not reproduce a Muslim penalty.

In the broad State-government sample, secondary district-by-year whole-universe fidelity gradients for Muslim share are approximately zero for meeting the nominal band, exact nominal-band recording, shortfall share, and capped receipt-to-entitlement ratio. School first-difference models also show no statistically clear Muslim, SC, ST, OBC, or General gradient.

This is an important substantive correction. The earlier contemporaneous funding associations should not be presented as evidence that the CSG formula itself disadvantages socially concentrated schools. They appear to mix geography, administrative systems, school structure, accounting, and other determinants of reported funding.

## 18. Correctly timed fuzzy-RD facility sensitivity

A secondary fuzzy-RD sensitivity treats `UDISE reported CSG receipt >= Rs 75,000` as an endogenous administrative treatment and uses the 250/251 threshold as the instrument.

This is still not an audited PFMS cash-receipt treatment, so it is a sensitivity rather than a definitive expenditure-effect design.

For the 2021-22 assignment cohort:

- 2024-25 deterioration LATE: +0.0002, 95% CI approximately -0.0437 to +0.0440, p=.995;
- 2025-26 deterioration LATE: +0.0097, CI -0.0227 to +0.0420, p=.558.

For the 2022-23 assignment cohort:

- 2025-26 deterioration LATE: +0.0034, CI -0.0174 to +0.0242, p=.748.

Upgrade estimates are extremely imprecise:

- 2021-22 -> 2024-25: +0.0535, CI -0.353 to +0.460;
- 2021-22 -> 2025-26: +0.0110, CI -0.412 to +0.434;
- 2022-23 -> 2025-26: +0.0665, CI -0.489 to +0.622.

The appropriate conclusion is narrow: the study finds no evidence of a large improvement or deterioration in these coarse UDISE-observed asset-transition measures. It does not establish that CSG has no value. Official CSG uses include consumables, minor repairs, electricity, internet, water, teaching-learning materials, and recurring school activities that can be poorly represented by binary or stock UDISE facility variables.

## 19. Literature position

The targeted literature search found several close but distinct literatures:

1. causal work on school grants and household substitution in India and Zambia;
2. Samagra Shiksha budget and implementation briefs focused on aggregate allocations, releases, and expenditure;
3. DISE/UDISE research on caste segregation and social inequality in Indian schools;
4. broader regression-discontinuity work on education policy in India.

The search did not locate a published or working paper that reconstructs the CSG enrolment-to-allocation-to-UDISE reporting clock, exploits the school-level CSG formula cliff to measure recorded financial transmission, and then tests that first stage across States and school social composition.

The defensible novelty language is: `We did not locate a close predecessor using this design.` It should not be phrased as an unqualified claim that no prior study exists anywhere.

## 20. What the study now establishes

### Strongly supported

1. The CSG enrolment formula leaves a large, replicating school-level financial fingerprint in UDISE when administrative timing is aligned correctly.
2. The fingerprint peaks at +3 UDISE rounds, consistent with a two-year-old allocation enrolment vintage plus the previous-financial-year UDISE reporting convention.
3. The financial fingerprint replicates at multiple statutory CSG thresholds.
4. Crossing 250/251 changes reported receipt and expenditure substantially, but exact statutory amounts are only imperfectly reproduced in the administrative field.
5. The result is essentially unchanged when the school-management universe is expanded from the original core government categories to the broader State/UT-government population.
6. Formula transmission varies enormously and persistently across States/UTs.
7. +3 is the modal state-level administrative lag.
8. Stronger state formula transmission is not associated with stronger enrolment bunching.
9. Longitudinal crossing/reversion tests do not show a distinctive manipulation pattern at 250 relative to placebo thresholds.
10. There is no robust national evidence that the 250/251 CSG formula first stage weakens with Muslim, SC, ST, OBC, General, or residual-religion concentration.
11. Predetermined social composition is continuous at the cutoff after multiple-testing correction.
12. Rare-religion nominal interactions fail placebo-cutoff specificity and should not be interpreted as CSG effects.
13. Properly timed fuzzy estimates do not reveal large effects on the coarse facility-transition outcomes visible in UDISE, while upgrade effects remain imprecise.

### Not supported

1. `The first stage is only 6-8 percentage points.` This was a timing error.
2. `The grant mechanically increases reported finance by exactly Rs 25,000.` It does not.
3. `Schools below Rs 75,000 were denied money.` UDISE reporting cannot establish that.
4. `Schools manipulate enrolment to cross 250.` The evidence is too weak.
5. `Higher Muslim share causes weaker CSG formula transmission.` The preferred estimate is near zero.
6. `SC or ST schools receive a weaker formula response.` The pooled compositional family is jointly null.
7. `Smaller religious groups are discriminated against by CSG.` The nominal signals fail false-cutoff tests and multiplicity control.
8. `An extra Rs 25,000 causes no educational or infrastructure benefit.` The design is fuzzy and the observable outcomes are incomplete.
9. `CSG does not work.` The study cannot support that statement.
10. `Hindu-General share` can be recovered by subtracting religion and caste margins. It cannot.

## 21. Final paper direction

The strongest paper is now an administrative public-finance paper rather than a conventional school-input impact paper.

A defensible central framing is:

> A formally simple enrolment-based school-funding rule is clearly visible in India's school-level administrative accounts, but only after the policy's allocation and reporting clocks are reconstructed. The size and timing of the recorded response vary sharply across States, statutory amounts are only imperfectly reproduced, and the formula does not appear to generate substantial strategic enrolment manipulation. Despite large descriptive social disparities in school funding, the quasi-experimental CSG first stage does not systematically weaken as Muslim or major caste-category concentration rises.

Possible title:

**The Formula Bites, But the Records Lag: Tracing School Funding Rules Through India's Administrative Data**

A more conventional academic title:

**Tracing Formula-Based School Funding Through India's Administrative Data**

## 22. Remaining limitation that could materially upgrade the paper

The single most valuable external-data extension would be audited or transaction-level PFMS/SNA/PRABANDH or state release records that identify actual school-wise CSG release timing and amounts. Such data could distinguish implementation from UDISE accounting/reporting and turn the current administrative fingerprint into a direct fiscal-transmission analysis.

Until that linkage exists, the paper should consistently use terms such as `reported receipt`, `recorded financial transmission`, and `administrative fingerprint`, rather than treating UDISE as audited disbursement data.
