# CSG Social-Equity and Absolute-Level Audit

## Purpose

This report extends the Composite School Grant study beyond heterogeneous threshold coefficients to examine recorded funding levels for socially and religiously concentrated government schools and whether apparent gaps survive like-for-like comparisons.

The analysis separates three distinct questions:

1. **Formula equity.** Does the 250/251 formula-induced jump in reported CSG finance become weaker as Muslim, SC, ST, OBC, General or other religious-group concentration increases?
2. **Level equity.** Irrespective of the 250/251 jump, are socially concentrated schools more or less likely to report CSG receipt or to report at least the nominal amount corresponding to their enrolment band?
3. **Geographic mediation.** If a raw national level gap exists, does it survive comparisons among schools in the same district and the same nominal CSG band?

These estimands are not interchangeable. A group can have a lower national recorded funding rate because its schools are concentrated in States or districts with weaker administrative realization even when the formula itself is transmitted similarly within comparable locations.

## Definitions and guardrails

### Religion and social category are separate classifications

`General`, `SC`, `ST` and `OBC` are mutually exclusive categories within the UDISE social-category margin. `Muslim`, `Christian`, `Sikh`, `Buddhist`, `Parsi` and `Jain` are religion/minority categories. The two classifications overlap, so a Muslim pupil can also be OBC or General.

Accordingly:

- `Muslim-majority` means previous-year Muslim share is strictly greater than 50 percent.
- `Non-Muslim-majority` means previous-year Muslim share is strictly less than 50 percent. It does not mean Hindu-majority.
- Exact 50/50 schools are excluded from strict majority comparisons.
- `General-majority` is a separate social-category concept and is not the opposite of Muslim-majority.

A Hindu-General or upper-caste-Hindu population cannot be constructed by subtracting religion and caste shares together because doing so double-counts overlapping classifications.

### Recorded finance is not audited cash receipt

The outcome is the UDISE Composite School Grant receipt field. A school reporting less than the nominal formula amount is not automatically proven to have been denied that amount. Instalments, balances, accounting conventions, reporting practices, release timing and data quality can all affect the field.

This report therefore uses **recorded target fidelity** for the probability that UDISE reports CSG receipt at least as large as the nominal amount corresponding to the school's enrolment band.

### Stable full-universe target analysis

For the full-universe fidelity analysis, schools with enrolment above 30 are assigned the stable nominal bands used in the study period:

- 31-100: Rs 25,000
- 101-250: Rs 50,000
- 251-1000: Rs 75,000
- above 1000: Rs 100,000

Schools at 30 or below are omitted from the full target-fidelity comparison because the small-school schedule changed historically.

The four aligned assignment cohorts are:

- 2019-20 enrolment -> 2022-23 UDISE financial field
- 2020-21 -> 2023-24
- 2021-22 -> 2024-25
- 2022-23 -> 2025-26

All social-composition variables used for heterogeneity are previous-year composition measures.

---

# 1. Relation to the main CSG study

Around the 250/251 enrolment threshold, crossing into the Rs 75,000 band increases `P(reported receipt >= Rs 75,000)` by roughly 25-33 percentage points when the enrolment, allocation and UDISE reporting clocks are aligned at +3 rounds. The response is much smaller at +2. The formula fingerprint replicates across four cohorts, survives the broader State/UT-government universe and appears at the other stable CSG thresholds.

The recorded response is not an exact formula ledger: exact Rs 75,000 recording rises by only a few percentage points even though the broader `>= Rs 75,000` region rises by about 25-33 points. State administrative heterogeneity is large and persistent. Longitudinal placebo tests do not support a strong CSG-specific enrolment-manipulation interpretation.

This social-equity audit asks how those administrative patterns intersect with school composition without treating raw national differences as causal evidence.

---

# 2. Muslim-majority schools

## 2.1 Raw national full-universe numbers

Among schools above 30 pupils with observed financial records, pooled across the four aligned cohorts:

| Measure | Muslim-majority | Non-Muslim-majority | Raw difference |
|---|---:|---:|---:|
| School-years with observed receipt field | 284,135 | 2,824,099 | -- |
| Any positive reported CSG receipt | **82.66%** | **79.12%** | **+3.54 pp** |
| Reported receipt >= own nominal band target | **59.22%** | **61.81%** | **-2.59 pp** |
| 99%-winsorised mean reported receipt | about **Rs 39,606** | about **Rs 38,133** | about **+Rs 1,473** |

The raw data therefore do not show a simple pattern of lower CSG receipt for Muslim-majority schools. They are more likely to report some positive receipt and have a slightly higher raw mean rupee amount, while being somewhat less likely to report at least the nominal amount for their enrolment band.

This is why raw amounts and raw rates need to be normalized to the grant bands and geography before interpretation.

## 2.2 Muslim concentration bands

Raw band-normalized target fidelity declines somewhat at very high Muslim concentration:

| Previous-year Muslim share | Any positive receipt | Meets nominal recorded target |
|---|---:|---:|
| 0-10% | 78.88% | 61.92% |
| 10-25% | 80.06% | 60.73% |
| 25-50% | 81.90% | 61.62% |
| 50-75% | 82.66% | 60.25% |
| 75-90% | 83.06% | 58.49% |
| 90-100% | 82.57% | 58.97% |

These are descriptive national rates and do not make Muslim-concentrated schools geographically exchangeable with low-Muslim-share schools.

## 2.3 Same-district, same-band comparison

The preferred absolute-level comparison restricts attention to district x grant-band x cohort cells containing both Muslim-majority and non-Muslim-majority schools, then overlap-weights those cells. This compares schools facing the same nominal formula amount inside the same district and year.

Across 4,432 overlapping district-band-cohort cells, spanning 27 States/UTs and 502 districts:

- standardized Muslim-majority recorded target fidelity: **55.97%**
- standardized non-Muslim-majority target fidelity: **56.09%**
- difference: **-0.12 percentage points**
- state-clustered SE: **0.53 pp**
- p = **.816**

The raw national -2.59 pp gap therefore almost completely disappears within district and nominal grant band. The national Muslim-majority difference is predominantly compositional/geographic rather than evidence of a general Muslim penalty in recorded CSG fidelity.

## 2.4 The local 250/251 upper band

For schools with 251-280 pupils, all facing the Rs 75,000 nominal band:

### Raw national rates

- Muslim-majority `P(reported receipt >= Rs 75,000)`: **49.30%**
- non-Muslim-majority: **57.54%**
- raw gap: **-8.24 pp**

### Same-district overlap-standardized rates

- Muslim-majority: **48.55%**
- non-Muslim-majority: **51.02%**
- gap: **-2.47 pp**
- state-clustered SE: about **1.48 pp**
- p = **.095**

The larger raw local difference contracts sharply after geographic standardization. A residual difference of roughly 2.5 pp remains suggestive but is not statistically established at the conventional 5-percent threshold.

## 2.5 Missingness

In the full band-normalized universe, the financial field is observed for about 98.54% of Muslim-majority school-years and 99.11% of non-Muslim-majority school-years. Around 251-280 it is observed for about 99.28% versus 99.63% respectively.

Treating missing reports as zero does not materially alter the raw local differences. The preferred within-district/band comparison is already based on observed finance and geographic overlap.

---

# 3. Formula-specific Muslim-majority heterogeneity

The earlier continuous-share analysis found no robust pooled Muslim interaction. The preferred pooled district-year estimate is approximately -0.18 pp in the 250/251 threshold response per +10 percentage points Muslim share, p=.733. The joint religion-composition model also places the Muslim coefficient near zero.

A stricter categorical version re-estimates the 250/251 response separately for Muslim-majority and non-Muslim-majority schools and then estimates a direct `Muslim-majority x cutoff` interaction only in districts with support for both composition groups on both sides of the cutoff.

| Assignment cohort | Muslim-majority minus non-Muslim-majority threshold response | p |
|---|---:|---:|
| 2019-20 | +2.71 pp | .743 |
| 2020-21 | -5.31 pp | .539 |
| 2021-22 | +3.29 pp | .276 |
| 2022-23 | **-13.77 pp** | **.009** |

There is no stable four-cohort Muslim-majority penalty in formula transmission. Three cohorts are statistically consistent with no differential response. The latest 2022-23 assignment cohort is a genuine exception and is treated as a replication target rather than as a persistent national result.

## 3.1 State decomposition of the latest anomaly

For the 2022-23 cohort, a stricter within-state, within-district decomposition yields mixed signs among the seven States with sufficient support:

| State | Muslim-majority minus non-Muslim-majority response | p | BH q |
|---|---:|---:|---:|
| Karnataka | **-27.37 pp** | .0160 | .0373 |
| Bihar | -10.97 pp | .0720 | .1259 |
| Uttar Pradesh | -0.28 pp | .962 | .962 |
| Assam | +7.73 pp | .703 | .820 |
| West Bengal | +5.63 pp | .155 | .217 |
| Jharkhand | **+30.26 pp** | .0150 | .0373 |
| Maharashtra | **+40.95 pp** | .0021 | .0144 |

The opposite signs matter. The latest pooled anomaly is not a common Muslim-majority penalty reproduced across States.

---

# 4. State-wise Muslim-majority absolute levels

The state-wise religious analysis has two distinct components:

1. **Formula heterogeneity within States:** whether Muslim share changes the 250/251 threshold response.
2. **Absolute recorded fidelity within States:** whether Muslim-majority schools differ from non-Muslim-majority schools within the same district and nominal grant band.

The second analysis produces mixed State signs. Selected well-supported examples pooled across the four cohorts are:

| State | Muslim-majority target fidelity | Non-Muslim-majority | Adjusted gap |
|---|---:|---:|---:|
| Odisha | 77.01% | 81.31% | **-4.29 pp** |
| Telangana | 74.97% | 78.50% | **-3.54 pp** |
| Jammu & Kashmir | 78.06% | 80.79% | **-2.73 pp** |
| Andhra Pradesh | 18.01% | 20.68% | **-2.67 pp** |
| Karnataka | 15.28% | 17.75% | **-2.48 pp** |
| Uttar Pradesh | 85.59% | 85.75% | -0.16 pp |
| West Bengal | 42.87% | 41.71% | +1.16 pp |
| Assam | 73.93% | 72.45% | +1.49 pp |
| Jharkhand | 82.44% | 79.05% | **+3.39 pp** |

Several negative and positive State gaps survive multiple-testing correction, but the direction is not common across States. These are State-specific recorded-fidelity patterns rather than a single nationwide religious effect.

---

# 5. Other religions

## 5.1 Christian-majority schools

Christian-majority schools produce the clearest secondary religion-level signal.

Across 499 overlapping district-band-cohort cells in 16 States and 102 districts:

- standardized Christian-majority target fidelity: **64.89%**
- standardized non-Christian-majority: **69.05%**
- gap: **-4.16 pp**
- state-clustered SE: about **1.45 pp**
- p = **.0040**
- BH q across four religion-majority comparisons with usable support: **.0080**

Cohort-specific same-district/band gaps are approximately -2.59, -5.48, -5.46 and -2.99 pp.

A simultaneous model controlling SC, ST, OBC and all listed religions together, plus log enrolment, management, rurality, school category and district x nominal-band fixed effects, also gives a negative Christian-share coefficient in all four cohorts.

This is a level-fidelity association, not evidence that the 250/251 formula itself discriminates against Christian schools. Formula-specific religion tests are not significant at the true cutoff and the same flexible religion family produces strong signals at false cutoffs. State signs are also mixed, including negative supported gaps in Meghalaya and Kerala and a positive gap in Tripura.

## 5.2 Sikh-majority schools

The categorical overlap comparison is about +0.66 pp, but support is concentrated in only five States and the continuous Sikh-share models are essentially null. The evidence does not establish a general Sikh advantage.

## 5.3 Buddhist-majority schools

The standardized difference is about +0.55 pp with p=.571. No robust national disparity is established.

## 5.4 Jain and Parsi majority comparisons

There is insufficient majority-school overlap for a credible national categorical comparison.

---

# 6. Social-category absolute levels

The same band-normalized, within-district analysis was conducted separately for General, SC, ST and OBC majority schools.

## 6.1 Raw national rates

| Group comparison | Majority meets nominal target | Non-majority meets target | Majority any-positive receipt | Non-majority any-positive |
|---|---:|---:|---:|---:|
| General | 56.42% | 62.27% | 85.51% | 78.63% |
| SC | 67.00% | 60.44% | 84.40% | 78.41% |
| ST | 59.15% | 62.04% | 75.98% | 80.10% |
| OBC | 62.18% | 61.12% | 77.26% | 81.05% |

These raw figures are highly confounded by geography and school composition.

## 6.2 Same-district, same-band comparisons

Pooled across all four cohorts using harmonic overlap weights and state-clustered inference:

| Group | Majority target fidelity | Non-majority | Adjusted gap | p |
|---|---:|---:|---:|---:|
| General | 55.40% | 55.50% | -0.10 pp | .739 |
| SC | 63.81% | 64.45% | **-0.64 pp** | .0037 |
| ST | 57.67% | 60.80% | **-3.14 pp** | 2.8e-5 |
| OBC | 62.87% | 61.43% | **+1.43 pp** | 6.2e-7 |

After BH correction across the four majority comparisons, ST, SC and OBC remain statistically distinguishable from zero, but the substantive interpretation differs by group.

### General

The raw national difference disappears almost completely within district and band. There is no robust General-majority fidelity effect.

### SC

The categorical SC-majority comparison is modestly negative, while continuous composition models point positive in several cohorts. The sign sensitivity indicates nonlinearity and compositional selection rather than a stable SC disadvantage.

### OBC

The OBC-majority comparison is modestly positive and replicates across all four cohorts, about +1.3 to +1.6 pp. Continuous models are also positive in the later cohorts. This is a small positive recorded-fidelity association, not a causal benefit of OBC composition.

### ST

ST is the strongest and most consistent social-category level result.

The ST-majority adjusted gaps by cohort are approximately:

- 2019-20: **-3.10 pp**
- 2020-21: **-3.06 pp**
- 2021-22: **-3.09 pp**
- 2022-23: **-3.31 pp**

Pooled: **-3.14 pp**.

---

# 7. ST robustness tests

## 7.1 Missing financial reports

Treating missing financial reports as zero within the same overlapping district-band cells gives:

- ST-majority target fidelity: **56.88%**
- non-ST-majority: **59.83%**
- gap: **-2.96 pp**
- p about **5.3e-5**

In those overlapping cells, the financial field is slightly more often observed for ST-majority schools, so missingness does not generate the observed deficit.

## 7.2 Continuous composition

The simultaneous level model controls social category and religion together, plus school size, management, rurality, school category and district x nominal-band fixed effects. The ST coefficient per +10 percentage points ST share is negative in all four cohorts:

- 2019-20: about **-0.30 pp**, p=.0116
- 2020-21: about **-0.17 pp**, p=.0435
- 2021-22: about **-0.06 pp**, p=.499
- 2022-23: about **-0.18 pp**, p=.0186

The ST-majority result is therefore not solely created by the 50-percent majority threshold.

## 7.3 Religion controls and formula-specific tests

The ST coefficient remains negative when Muslim, Christian, Sikh, Buddhist, Parsi and Jain shares are entered simultaneously.

Crucially, the 250/251 formula-heterogeneity model does not find a robust weaker threshold response as ST share increases, and school first-difference diagnostics do not show that within-school increases in ST composition predict deteriorating fidelity.

The resulting interpretation is:

> **ST-majority schools have a persistent lower level of UDISE-recorded CSG target fidelity even within the same district and nominal grant band, but the available design does not identify ST composition itself as the causal mechanism and does not show that the 250/251 formula is applied differently to ST schools.**

This is a serious descriptive implementation disparity, not proof of discriminatory underpayment.

---

# 8. Simultaneous multigroup level model

A stricter model estimates SC, ST, OBC, Muslim, Christian, Sikh, Buddhist, Parsi and Jain composition simultaneously, with General and the residual/non-listed religion category as implicit references. It includes district x nominal-grant-band fixed effects, log enrolment, management, rurality, school category and state-clustered inference.

Per +10 percentage points composition, the approximate coefficients in percentage points are:

| Group | 2019-20 | 2020-21 | 2021-22 | 2022-23 |
|---|---:|---:|---:|---:|
| Muslim | -0.05 | +0.13 | -0.01 | -0.06 |
| Christian | -0.23 | -0.52 | -0.50 | -0.16 |
| SC | -0.10 | +0.10 | +0.19 | +0.03 |
| ST | **-0.30** | **-0.17** | -0.06 | **-0.18** |
| OBC | ~0.00 | +0.09 | +0.19 | +0.12 |

The multigroup results reinforce four distinctions: Muslim composition is effectively null after strong adjustment; ST remains directionally negative; Christian remains directionally negative but with variable precision; and SC is not directionally stable.

---

# 9. State-wise interpretation

State-level analysis is central because overall CSG administrative realization differs by tens of percentage points across States, much more than most national social-composition gradients.

Within-state formula-transmission models do not reveal a coherent Muslim penalty across large States. State-wise absolute-fidelity comparisons do reveal some local positive and negative religious disparities, but both signs occur.

The evidence therefore points toward geographic and administrative decomposition rather than a single pooled national story about which social group "gets the grant."

---

# 10. Main findings from the equity audit

1. **The national CSG formula has a strong but delayed administrative effect.** The correctly aligned threshold response remains the central formula-specific result.
2. **Recorded fiscal fidelity is incomplete.** The financial distribution shifts strongly at CSG thresholds, while exact formula amounts do not appear mechanically in UDISE.
3. **State implementation heterogeneity is the largest distributional heterogeneity in the study.** The same national rule leaves very different recorded fingerprints across States.
4. **There is no stable nationwide Muslim penalty in either absolute target fidelity or formula transmission.** The raw national Muslim-majority target-fidelity gap disappears almost entirely within district and grant band. The latest-cohort formula anomaly has mixed State signs.
5. **ST-majority schools exhibit a persistent recorded-fidelity deficit.** The roughly 3 pp difference persists across four cohorts and multiple robustness checks, but it is not accompanied by a robust weaker 250/251 threshold response and does not establish causal discrimination.
6. **Christian-majority schools show a secondary negative level association.** It is directionally persistent but mixed across States and not established as a formula-specific effect.
7. **OBC-majority schools show a small positive recorded-fidelity association; SC is parameterization-sensitive; General is null after geographic adjustment.**
8. **The enrolment-integrity evidence does not establish systematic CSG-specific manipulation.**

---

# 11. Claim boundaries

The administrative data do not identify the following interpretations:

- a general national Muslim penalty in CSG receipt;
- discrimination by the 250/251 formula against Muslim schools;
- causal denial of grants to ST-majority schools because of their ST composition;
- a CSG-formula discrimination mechanism against Christian-majority schools;
- verified underpayment whenever the UDISE receipt field is below the nominal formula amount;
- a nationwide religious mechanism from the 2022-23 Muslim-majority anomaly;
- a conclusion that CSG does not work.

The data do support the following high-level statement:

> **India's enrolment-based Composite School Grant formula produces a large, delayed and highly State-dependent financial fingerprint in UDISE. Raw religious and social differences in recorded funding can be misleading because school populations are geographically sorted. Muslim-majority schools have essentially the same recorded target fidelity as comparable non-Muslim-majority schools within the same district and grant band, although one latest cohort shows a heterogeneous Muslim-majority cutoff anomaly that merits replication. By contrast, ST-majority schools exhibit a persistent roughly three-percentage-point deficit in recorded target fidelity within comparable district-band cells, and Christian-majority schools show a secondary negative level association. These are administrative-record disparities, not proof of discriminatory cash allocation.**

The study therefore distinguishes **formula transmission**, **recorded fiscal fidelity**, **State implementation** and **social distribution** rather than compressing them into a single measure of grant receipt.

---

# 12. Validation priorities

The strongest external validation would link UDISE schools to school-level sanction, authorization, release, draw or expenditure-account records for a set of States. That would distinguish actual administrative fund-flow differences from UDISE accounting and reporting differences.

The most informative replication targets are:

1. ST-majority schools, including whether the recorded-fidelity deficit is concentrated by management type, Tribal Welfare administration, remoteness or particular States;
2. the 2022-23 Muslim-majority cutoff anomaly in the next correctly aligned financial cohort;
3. Christian-majority fidelity in States with both positive and negative local gaps;
4. States with exceptionally weak or strong overall formula realization.

Until such administrative linkage is available, the outcome remains **UDISE-recorded CSG fidelity**, not verified underpayment.
