# Definitive CSG Social-Equity and Absolute-Level Audit

## Purpose

This report extends the Composite School Grant study beyond heterogeneous regression coefficients and answers the more intuitive question: **what are the actual recorded funding rates for socially or religiously concentrated government schools, and do apparent gaps survive like-for-like comparisons?**

It supersedes any interpretation that treats a raw national funding-rate difference as evidence that the CSG formula itself discriminates between social or religious groups.

The analysis separates three different equity questions.

1. **Formula equity.** Does the 250/251 formula-induced jump in reported CSG finance become weaker as Muslim, SC, ST, OBC, General, or other religious-group concentration increases?
2. **Level equity.** Irrespective of the 250/251 jump, are socially concentrated schools more or less likely to report CSG receipt, or to report at least the nominal amount corresponding to their enrolment band?
3. **Geographic mediation.** If a raw national level gap exists, does it survive comparisons among schools in the same district and the same nominal CSG band?

These estimands are not interchangeable. A group can have a lower national recorded funding rate because its schools are concentrated in States or districts with weaker administration even if the formula itself is transmitted equally within comparable locations.

## Definitions and guardrails

### Religion and social category are separate classifications

`General`, `SC`, `ST`, and `OBC` are mutually exclusive categories within the UDISE social-category margin. `Muslim`, `Christian`, `Sikh`, `Buddhist`, `Parsi`, and `Jain` are religion/minority categories. These classifications overlap. A Muslim pupil can also be OBC or General.

Therefore:

- `Muslim-majority` means previous-year Muslim share is strictly greater than 50 percent.
- `Non-Muslim-majority` means previous-year Muslim share is strictly less than 50 percent. It does **not** mean Hindu-majority.
- Exact 50/50 schools are excluded from strict majority-versus-majority comparisons.
- `General-majority` is a separate social-category concept and is not the opposite of Muslim-majority.

### Recorded finance is not audited cash receipt

The outcome is what UDISE reports for Composite School Grant receipt. A school reporting less than the nominal formula amount is not automatically proven to have been denied that amount. Instalments, balances, accounting conventions, reporting practices, release timing, and data quality can all affect the field.

For this reason this report uses the phrase **recorded target fidelity** for the probability that UDISE reports receipt at least as large as the nominal CSG amount corresponding to the school’s enrolment band.

### Stable full-universe target analysis

For the full-universe fidelity analysis, schools with enrolment above 30 are assigned the stable nominal bands used in the study period:

- 31-100: Rs 25,000
- 101-250: Rs 50,000
- 251-1000: Rs 75,000
- above 1000: Rs 100,000

Schools at 30 or below are omitted from the full target-fidelity comparison because the small-school schedule changed historically. They can still contribute to descriptive `any positive receipt` analyses where appropriate.

The four correctly aligned assignment cohorts remain:

- 2019-20 enrolment -> 2022-23 UDISE financial field
- 2020-21 -> 2023-24
- 2021-22 -> 2024-25
- 2022-23 -> 2025-26

All social-composition variables used for heterogeneity are previous-year composition measures.

---

# 1. What the main CSG study establishes

The social-equity audit sits inside a stronger administrative-finance result.

Around the 250/251 enrolment threshold, crossing into the Rs 75,000 band increases `P(reported receipt >= Rs 75,000)` by roughly 25-33 percentage points when the enrolment, allocation, and UDISE reporting clocks are correctly aligned at +3 UDISE rounds. The response is much smaller at +2. The formula fingerprint replicates across four cohorts, persists under the broader State/UT-government universe, and appears at the other statutory CSG thresholds as well.

The recorded response is not an exact entitlement ledger: exact Rs 75,000 reporting rises by only a few percentage points even though the broader `>= Rs 75,000` region rises by about 25-33 points. State implementation/reporting heterogeneity is very large and persistent. Longitudinal placebo tests do not support a strong strategic-enrolment-manipulation story.

That remains the central contribution of the study.

---

# 2. Muslim-majority schools: the full numbers

## 2.1 Raw national full-universe numbers

Among schools above 30 pupils with observed financial records, pooled across the four correctly aligned cohorts:

| Measure | Muslim-majority | Non-Muslim-majority | Raw difference |
|---|---:|---:|---:|
| School-years with observed receipt field | 284,135 | 2,824,099 | -- |
| Any positive reported CSG receipt | **82.66%** | **79.12%** | **+3.54 pp** |
| Reported receipt >= own nominal band target | **59.22%** | **61.81%** | **-2.59 pp** |
| 99%-winsorized mean reported receipt | about **Rs 39,606** | about **Rs 38,133** | about **+Rs 1,473** |

The raw data therefore do **not** say that Muslim-majority schools are simply less likely to receive CSG. They are more likely to report some positive CSG receipt, and their raw mean reported rupee amount is slightly higher. They are, however, less likely in the raw national data to report at least the nominal amount corresponding to their enrolment band.

This apparent contradiction is exactly why absolute amounts must be normalized to entitlement bands and geography before interpretation.

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

Again, this is descriptive. Muslim-concentrated schools are not geographically exchangeable with low-Muslim-share schools.

## 2.3 Like-for-like district and grant-band comparison

The preferred absolute-level comparison restricts attention to district x grant-band x cohort cells containing both Muslim-majority and non-Muslim-majority schools, then overlap-weights those cells. This compares schools facing the same nominal formula amount inside the same district and year.

Across 4,432 overlapping district-band-cohort cells, spanning 27 States/UTs and 502 districts:

- standardized Muslim-majority recorded target fidelity: **55.97%**
- standardized non-Muslim-majority target fidelity: **56.09%**
- difference: **-0.12 percentage points**
- state-clustered SE: **0.53 pp**
- p = **.816**

Thus the raw national -2.59 pp target-fidelity gap essentially disappears when schools are compared within the same district and the same nominal grant band.

This is one of the most important findings of the deeper audit: **the raw national Muslim-majority gap is predominantly compositional/geographic rather than evidence of a general Muslim penalty in CSG recorded fidelity.**

## 2.4 The local 250/251 upper band

For schools with 251-280 pupils, all of which face the Rs 75,000 nominal band:

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

The much larger raw local gap therefore also contracts sharply after geographic standardization. A residual roughly 2.5 pp difference remains suggestive but does not reach the conventional 5-percent threshold in the pooled overlap analysis.

## 2.5 Missingness does not explain these results

In the full band-normalized universe, the financial field is observed for about 98.54% of Muslim-majority school-years and 99.11% of non-Muslim-majority school-years. Around 251-280 it is observed for about 99.28% versus 99.63% respectively.

Treating missing reports as zero does not materially alter the raw local differences. More importantly, the preferred within-district/band result is already based on observed finance and geographic overlap.

---

# 3. Does the 250/251 formula itself treat Muslim-majority schools differently?

The earlier continuous-share analysis found no robust pooled Muslim interaction. The preferred pooled district-year estimate was approximately -0.18 pp in the formula first stage per +10 percentage points Muslim share, p=.733. The joint religion-composition model also placed the Muslim coefficient near zero.

To answer the user-facing categorical question directly, the 250/251 first stage was re-estimated separately for Muslim-majority and non-Muslim-majority schools, and then a direct `Muslim-majority x cutoff` interaction was estimated only in districts with actual support for both composition groups on both sides of the cutoff.

The strict overlap interaction results are:

| Assignment cohort | Muslim-majority minus non-Muslim-majority first stage | p |
|---|---:|---:|
| 2019-20 | +2.71 pp | .743 |
| 2020-21 | -5.31 pp | .539 |
| 2021-22 | +3.29 pp | .276 |
| 2022-23 | **-13.77 pp** | **.009** |

Therefore there is **no stable four-cohort Muslim-majority penalty in formula transmission**. Three cohorts are statistically consistent with no differential first stage. The latest 2022-23 assignment cohort is a genuine exception and should not be averaged away.

This latest-cohort anomaly is an important replication target, but it is not yet a persistent national result.

## 3.1 State decomposition of the latest anomaly

A stricter within-state, within-district decomposition for the 2022-23 cohort finds highly heterogeneous signs among the seven States with enough support for this demanding specification:

| State | Muslim-majority minus non-Muslim-majority first stage | p | BH q across 7 supported states |
|---|---:|---:|---:|
| Karnataka | **-27.37 pp** | .0160 | .0373 |
| Bihar | -10.97 pp | .0720 | .1259 |
| Uttar Pradesh | -0.28 pp | .962 | .962 |
| Assam | +7.73 pp | .703 | .820 |
| West Bengal | +5.63 pp | .155 | .217 |
| Jharkhand | **+30.26 pp** | .0150 | .0373 |
| Maharashtra | **+40.95 pp** | .0021 | .0144 |

The opposite signs are crucial. The latest pooled national anomaly is **not** a common Muslim-majority penalty reproduced across States. Karnataka is strongly negative, Uttar Pradesh is essentially zero, while Jharkhand and Maharashtra are strongly positive.

The appropriate conclusion is that the 2022-23 cohort contains a heterogeneous Muslim-majority formula-transmission anomaly that deserves replication and state-specific administrative investigation. It is not legitimate to present it as evidence of a stable nationwide religious penalty.

---

# 4. State-wise Muslim-majority absolute levels

The state-wise religious study was done in two distinct ways:

1. **Formula heterogeneity within states:** does Muslim share change the 250/251 first stage? This was already part of the earlier study and showed no coherent national pattern.
2. **Absolute recorded fidelity within states:** among schools in the same district and nominal grant band, do Muslim-majority schools have a different probability of reporting at least the nominal target? This was added in the deeper audit.

The second analysis produces mixed state signs. Selected well-supported examples pooled across the four cohorts are:

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

Several negative and positive state gaps survive multiple-testing correction, but the direction is not common across States. These are **state-specific recorded-fidelity patterns**, not a single nationwide religious effect.

The state-level result is therefore more nuanced than either “Muslim schools get less” or “religion never matters.” The national average is essentially null after geographic standardization, while some States display meaningful positive or negative local disparities that should be investigated as administrative heterogeneity.

---

# 5. Other religions

The absolute-level extension was run for all religion groups with sufficient majority-school support.

## 5.1 Christian-majority schools

Christian-majority schools produce the clearest secondary religion-level signal.

Across 499 overlapping district-band-cohort cells in 16 States and 102 districts:

- standardized Christian-majority target fidelity: **64.89%**
- standardized non-Christian-majority: **69.05%**
- gap: **-4.16 pp**
- state-clustered SE: about **1.45 pp**
- p = **.0040**
- BH q across the four religion-majority comparisons with usable support: **.0080**

The four cohort-specific same-district/band gaps are approximately:

- 2019-20: -2.59 pp
- 2020-21: -5.48 pp
- 2021-22: -5.46 pp
- 2022-23: -2.99 pp

A simultaneous model controlling SC, ST, OBC and all listed religions together, plus log enrolment, management, rurality, school category, and district x nominal-band fixed effects, also gives a negative Christian-share coefficient in all four cohorts. The effect is individually significant in 2020-21 and 2021-22.

However, this is a **level-fidelity association**, not evidence that the 250/251 formula itself discriminates against Christian schools. The earlier formula-specific religion family was jointly insignificant at the true cutoff, while the same flexible religion model also generated strong signals at false cutoffs. The Christian-majority level result should therefore be treated as a secondary, preferably preregistered replication target.

State signs are also mixed. For example, Meghalaya is about -4.17 pp and Kerala about -6.64 pp in supported same-district/band comparisons, whereas Tripura is about +3.65 pp. That heterogeneity again points toward state/local administration rather than a uniform national formula mechanism.

## 5.2 Sikh-majority schools

The categorical overlap comparison is about +0.66 pp, but support is concentrated in only five States and the continuous Sikh-share models are essentially null. Raw Sikh-majority rates are dominated by Punjab and should not be interpreted as a general causal advantage.

## 5.3 Buddhist-majority schools

The standardized difference is about +0.55 pp with p=.571. No robust national disparity is established.

## 5.4 Jain and Parsi majority comparisons

There is insufficient majority-school overlap for a credible national categorical comparison. Coefficients from sparse continuous models should not be promoted as substantive findings.

---

# 6. Social-category absolute levels

The same band-normalized, within-district analysis was conducted separately for General, SC, ST, and OBC majority schools. These are not religion comparisons.

## 6.1 Raw national rates

Among observed school-years above 30 pupils:

| Group comparison | Majority meets nominal target | Non-majority meets target | Majority any-positive receipt | Non-majority any-positive |
|---|---:|---:|---:|---:|
| General | 56.42% | 62.27% | 85.51% | 78.63% |
| SC | 67.00% | 60.44% | 84.40% | 78.41% |
| ST | 59.15% | 62.04% | 75.98% | 80.10% |
| OBC | 62.18% | 61.12% | 77.26% | 81.05% |

These raw figures are highly confounded by geography and school composition. The General and SC examples demonstrate why a raw national percentage cannot be read as a treatment effect.

## 6.2 Same-district, same-band majority comparisons

Pooled across all four cohorts using harmonic overlap weights and state-clustered inference:

| Group | Majority target fidelity | Non-majority | Adjusted gap | p |
|---|---:|---:|---:|---:|
| General | 55.40% | 55.50% | -0.10 pp | .739 |
| SC | 63.81% | 64.45% | **-0.64 pp** | .0037 |
| ST | 57.67% | 60.80% | **-3.14 pp** | 2.8e-5 |
| OBC | 62.87% | 61.43% | **+1.43 pp** | 6.2e-7 |

After BH correction across the four majority comparisons, ST, SC, and OBC remain statistically distinguishable from zero. Statistical significance is not the same as substantive robustness, however.

### General

The raw national gap disappears almost completely within district and band. There is no robust General-majority fidelity effect.

### SC

The categorical SC-majority comparison is modestly negative, but the continuous composition model points positive rather than negative in several cohorts. This sign sensitivity indicates nonlinearity and compositional selection. It is not defensible to headline an SC disadvantage from the categorical result alone.

### OBC

The OBC-majority comparison is modestly positive and replicates across all four cohorts, about +1.3 to +1.6 pp. Continuous models are also positive in the later cohorts. This appears to be a small positive recorded-fidelity association, not a causal benefit of OBC composition.

### ST

ST is the strongest and most consistent social-category level result.

The ST-majority adjusted gaps by cohort are approximately:

- 2019-20: **-3.10 pp**
- 2020-21: **-3.06 pp**
- 2021-22: **-3.09 pp**
- 2022-23: **-3.31 pp**

Pooled: **-3.14 pp**.

This pattern is unusually stable across cohorts.

---

# 7. ST robustness tests

## 7.1 Missing financial reports

Treating missing financial reports as zero within the same overlapping district-band cells gives:

- ST-majority target fidelity: **56.88%**
- non-ST-majority: **59.83%**
- gap: **-2.96 pp**
- p about **5.3e-5**

In those overlapping cells, the financial field is if anything slightly more often observed for ST-majority schools. Missingness therefore does not generate the ST deficit.

## 7.2 Continuous composition rather than a 50-percent threshold

Existing pooled district-year fidelity models also show that greater ST share is associated with lower recorded target fidelity, a larger shortfall share, and a lower receipt-to-target ratio.

The stricter simultaneous level model controls social category and religion together, plus school size, management, rurality, school category, and district x nominal-band fixed effects. The ST coefficient per +10 percentage points ST share is negative in all four cohorts:

- 2019-20: about **-0.30 pp**, p=.0116
- 2020-21: about **-0.17 pp**, p=.0435
- 2021-22: about **-0.06 pp**, p=.499
- 2022-23: about **-0.18 pp**, p=.0186

Thus the ST-majority result is not solely created by the arbitrary 50-percent majority threshold.

## 7.3 Religion controls

The ST coefficient remains negative when Muslim, Christian, Sikh, Buddhist, Parsi, and Jain shares are entered simultaneously. The ST result is therefore not simply the result of ST-majority schools having a different religious composition.

## 7.4 Formula jump and within-school changes

Crucially, the earlier 250/251 heterogeneity model did **not** find a robust weaker formula jump as ST share increased. School first-difference diagnostics also do not show that within-school increases in ST composition predict deteriorating fidelity.

Therefore the robust conclusion is:

> **ST-majority schools have a persistent lower level of UDISE-recorded CSG target fidelity even within the same district and nominal grant band, but the available design does not identify ST composition itself as the causal mechanism and does not show that the 250/251 formula is applied differently to ST schools.**

This is a serious descriptive implementation disparity worthy of further investigation, not proof of discriminatory underpayment.

---

# 8. Simultaneous multigroup level model

A stricter model estimates SC, ST, OBC, Muslim, Christian, Sikh, Buddhist, Parsi, and Jain composition simultaneously. General and the residual/non-listed religion category are the implicit references. It includes:

- district x nominal-grant-band fixed effects;
- log enrolment within band;
- management controls;
- rural/urban controls;
- school-category controls;
- state-clustered inference.

Per +10 percentage points composition, the approximate coefficients in percentage points are:

| Group | 2019-20 | 2020-21 | 2021-22 | 2022-23 |
|---|---:|---:|---:|---:|
| Muslim | -0.05 | +0.13 | -0.01 | -0.06 |
| Christian | -0.23 | -0.52 | -0.50 | -0.16 |
| SC | -0.10 | +0.10 | +0.19 | +0.03 |
| ST | **-0.30** | **-0.17** | -0.06 | **-0.18** |
| OBC | ~0.00 | +0.09 | +0.19 | +0.12 |

This is a useful synthesis:

- Muslim composition remains effectively null after the strongest multigroup adjustment.
- ST remains directionally negative in every cohort.
- Christian remains directionally negative in every cohort, although precision varies.
- OBC becomes modestly positive in later cohorts.
- SC is not directionally stable.

---

# 9. How the state-wise religious study should be interpreted

Yes, the study now includes a genuinely state-wise religious analysis at two levels.

### A. State-wise formula transmission

Within each state/cohort, religion shares are entered jointly and the 250/251 first stage is tested with district fixed effects and district-clustered inference. There is no coherent Muslim penalty across large States: Uttar Pradesh, Assam, Bihar, Jharkhand, Karnataka, and West Bengal do not produce a stable common negative Muslim gradient across cohorts. Tamil Nadu has some negative continuous slopes but support is concentrated at relatively low Muslim shares and the pattern is not a Muslim-majority comparison.

### B. State-wise absolute target fidelity

The new analysis compares majority and non-majority schools within the same district and nominal grant band. This reveals some real state-specific disparities, but both signs occur.

The substantive lesson is that **state administration dominates the geography of CSG reporting**. State-wide formula first stages differ by tens of percentage points, much more than most national social-composition gradients. Social disparities should therefore be decomposed through state and district implementation rather than inferred from one pooled national raw rate.

---

# 10. What this study now shows

The most defensible interpretation is layered.

## Finding 1: the national CSG formula has a strong but delayed administrative effect

The enrolment formula clearly bites in UDISE financial records after the correct administrative clock is reconstructed. This is the strongest causal/administrative result.

## Finding 2: recorded fiscal fidelity is incomplete

The financial distribution shifts strongly at formula thresholds, but exact statutory amounts do not appear mechanically. UDISE is not a perfect entitlement ledger.

## Finding 3: State implementation/reporting heterogeneity is enormous

The same national rule leaves very different recorded fingerprints across States, and those differences persist. This is the strongest distributional heterogeneity in the study.

## Finding 4: there is no stable nationwide Muslim penalty in either absolute target fidelity or formula transmission

Muslim-majority schools have a raw national target-fidelity deficit of about 2.6 pp, but it collapses to about 0.1 pp in same-district/same-band comparisons. Muslim composition is near zero in the strongest multigroup level models. Three of four strict categorical formula-interaction cohorts are statistically null.

The exception is the latest 2022-23 assignment cohort, where the Muslim-majority 250/251 first stage is about 13.8 pp smaller. State decomposition shows sharply mixed signs rather than a common national penalty. This is an anomaly to replicate, not the general conclusion.

## Finding 5: ST-majority schools exhibit a persistent recorded-fidelity deficit

This is the strongest new social-equity level result. The roughly 3 pp deficit persists across all four cohorts, within district and grant band, under missing-as-zero sensitivity, continuous-share models, and simultaneous religion/social-category controls.

It is not accompanied by a robust weaker 250/251 formula jump and does not establish causal discrimination.

## Finding 6: Christian-majority schools show a secondary recorded-fidelity deficit

The adjusted majority gap is about 4.2 pp and directionally replicates across four cohorts. Continuous multigroup models also point negative. But state signs are mixed, formula-specific religion tests do not establish a Christian penalty, and the result emerged in this deeper extension. It should be treated as secondary and replicated.

## Finding 7: OBC-majority schools show a small positive recorded-fidelity association; SC is nonlinear; General is null

OBC is around +1.4 pp in the categorical adjusted comparison. SC changes sign depending on parameterization and should not be described as a robust disadvantage. General-majority raw differences disappear after geographic adjustment.

## Finding 8: there is weak evidence for strategic enrolment manipulation

Bunching exists but the longitudinal/placebo evidence is too weak to support systematic gaming or fraud.

---

# 11. Claims the data do not justify

Do **not** say:

- "Muslim schools receive less CSG nationally."
- "The formula discriminates against Muslim schools."
- "ST schools are being denied grants because they are ST-majority."
- "Christian schools are discriminated against by the CSG formula."
- "A school below its nominal amount in UDISE was definitely underpaid."
- "The 2022 Muslim-majority anomaly proves a nationwide religious effect."
- "CSG does not work."

The administrative data do not identify these claims.

---

# 12. Claims the data do justify

A defensible high-level statement is:

> **India's enrolment-based Composite School Grant formula produces a large, delayed and highly state-dependent financial fingerprint in UDISE. Raw religious and social differences in recorded funding can be misleading because school populations are geographically sorted. Muslim-majority schools have essentially the same recorded target fidelity as comparable non-Muslim-majority schools within the same district and grant band, although one latest cohort shows a heterogeneous Muslim-majority cutoff anomaly that merits replication. By contrast, ST-majority schools exhibit a persistent roughly three-percentage-point deficit in recorded target fidelity even within comparable district-band cells, and Christian-majority schools show a secondary negative level association. These are administrative-record disparities, not proof of discriminatory cash allocation.**

The paper should therefore distinguish **formula transmission**, **recorded fiscal fidelity**, **state implementation**, and **social distribution** rather than compressing them into a single claim about who "gets the grant."

---

# 13. Strongest next validation

The cleanest way to turn the remaining fidelity disparities into a stronger causal/administrative claim is to match UDISE schools to actual sanction, release, or expenditure-account records at school level for a set of States. That would separate real release differences from UDISE reporting/accounting differences.

Priority follow-up should focus on:

1. ST-majority schools, especially whether the deficit is concentrated by management type, Tribal Welfare administration, remoteness, or particular States;
2. the 2022-23 Muslim-majority cutoff anomaly, with preregistered replication in the next correctly aligned financial cohort;
3. Christian-majority fidelity in States with both positive and negative local gaps;
4. States with exceptionally weak or strong overall formula transmission.

Until such administrative-release data are available, the appropriate outcome label remains **UDISE-recorded CSG fidelity**, not verified underpayment.
