# Final timing, funding-fidelity and incentive findings

## Status

This note supersedes the earlier interpretation that the 250-pupil Composite School Grant threshold produced only a 6-8 percentage-point first stage in school-level grant receipt. That interpretation paired the enrolment vintage with the wrong UDISE financial-reporting round.

The central empirical discovery is now the administrative clock itself.

## Headline finding

**The 250/251 CSG funding rule leaves a strong but delayed administrative fingerprint. Across the four usable middle cohorts, crossing from the lower to the higher CSG enrolment band raises the probability that a school reports CSG receipt of at least Rs 75,000 by approximately 25-33 percentage points three UDISE academic-data rounds after the enrolment vintage. The corresponding +2-round discontinuity is much smaller and statistically weak under state-clustered inference.**

This three-round data lag is consistent with two independently documented features of the administrative process:

1. Delhi CSG allocation orders for 2019-20, 2022-23 and 2024-25 explicitly use UDISE enrolment from two academic years earlier.
2. UDISE's receipts and expenditure section reports grants for the previous financial year. Therefore an enrolment vintage used for a grant approximately two years later can naturally appear in the UDISE financial field labelled one academic-data round after that grant financial year.

This does not establish that every state follows precisely the same clock. It does establish that interpreting same-labelled-year or +2 UDISE financial fields as the definitive first stage was methodologically wrong.

## Experiment 1: full lead-lag timing surface

The analysis was rerun using 250.5 as the RD coordinate because 250 remains in the lower band and 251 is the first integer in the higher band.

The primary outcome is the probability that the school's CSG receipt field is at least Rs 75,000.

State-clustered, mass-point-aware RD estimates at bandwidth +/-30 are:

| Enrolment vintage | UDISE financial field | Lag | Discontinuity in P(receipt >= Rs 75k) | p-value |
|---|---|---:|---:|---:|
| 2019-20 | 2022-23 | +3 | +24.70 pp | .0453 |
| 2020-21 | 2023-24 | +3 | +31.81 pp | .00188 |
| 2021-22 | 2024-25 | +3 | +33.21 pp | .000176 |
| 2022-23 | 2025-26 | +3 | +32.52 pp | .000067 |

For comparison, the +2 estimates are:

| Enrolment vintage | UDISE financial field | Lag | Discontinuity |
|---|---|---:|---:|
| 2019-20 | 2021-22 | +2 | approximately 0, grant field effectively zero-coded |
| 2020-21 | 2022-23 | +2 | +5.65 pp, p=.546 |
| 2021-22 | 2023-24 | +2 | +6.35 pp, p=.359 |
| 2022-23 | 2024-25 | +2 | +9.12 pp, p=.192 |

Negative leads, same-year observations and +1 lags are close to zero in the usable later cohorts. The +4 effect falls back sharply. The lag profile is therefore peaked rather than monotonically reflecting persistent school size.

Using the independent local-linear estimator, the four +3 cohorts also show positive 99%-winsorised receipt discontinuities of approximately Rs 9.5k, Rs 13.1k, Rs 14.4k and Rs 13.1k, respectively. The corresponding expenditure discontinuities are approximately Rs 9.0k, Rs 11.6k, Rs 13.3k and Rs 12.6k.

## Experiment 2: PM POSHAN-safe timing samples

PM POSHAN has a separate enrolment-linked kitchen-device rule around 250 pupils for its covered grades. To reduce this coincident-rule problem, the 250 CSG timing analysis was repeated among schools whose total Classes I-XII enrolment is around 250 but whose Classes I-VIII enrolment is safely below 250.

At the +3 reporting round, the local-linear P(receipt >= Rs 75k) discontinuity remains positive in all four usable cohorts.

With Classes I-VIII <=220, approximate +3 jumps are:

- 2019-20 cohort: +17.5 pp
- 2020-21 cohort: +11.9 pp
- 2021-22 cohort: +20.8 pp
- 2022-23 cohort: +26.2 pp

Using Classes I-VIII <=200 gives the same qualitative result, approximately +18.1, +12.1, +21.1 and +24.9 pp.

These restricted estimates are less precise and are not the headline magnitudes, but they show that the delayed CSG financial fingerprint is not created solely by PM POSHAN's coincident 250-pupil rule.

## Experiment 3: correctly timed grant-fidelity decomposition

A full point-mass decomposition completed for the 2021-22 enrolment vintage, which maps to grant financial year 2023-24 and the UDISE 2024-25 financial field under the corrected clock.

At bandwidth +/-30:

- P(receipt exactly Rs 50,000): -7.11 pp
- P(receipt exactly Rs 75,000): +5.29 pp
- P(receipt >= Rs 75,000): +33.46 pp
- P(receipt > Rs 50,000): +10.91 pp
- P(any positive receipt): +2.12 pp
- 99%-winsorised receipt: +Rs 14,421
- P(expenditure exactly Rs 50,000): -6.87 pp
- P(expenditure exactly Rs 75,000): +5.23 pp
- P(expenditure >= Rs 75,000): +32.83 pp
- 99%-winsorised expenditure: +Rs 13,275

Simple local rates are also revealing. Among schools with enrolment 241-250, 19.9% report receipt >=Rs 75,000. Among schools with enrolment 251-260, 55.2% do so. Exact Rs 75,000 receipt rises only from 3.3% to 9.2%.

Interpretation: **the formula clearly changes the financial distribution, but the UDISE receipt field does not behave like a mechanically assigned exact grant amount.** The threshold strongly shifts schools into a higher reported-receipt region while exact statutory point-mass reporting moves much less.

This is evidence of incomplete or heterogeneous administrative fidelity in the recorded field, not evidence that 45% of schools above the threshold were necessarily denied their grant. The receipt field may reflect timing, balances, accounting conventions, partial releases, additional amounts or other implementation features that cannot be separated with UDISE alone.

## Experiment 4: heaping-adjusted bunching around 250/251

A formal bunching screen was run using a polynomial count counterfactual with explicit indicators for ordinary heaping at multiples of 5, 10, 25, 50 and 100. The +/-5 values around each tested cutoff were excluded from the counterfactual fit.

The full eight-year program estimates the following heaping-adjusted above-versus-below asymmetry around 250/251:

| UDISE year | Heaping-adjusted asymmetry |
|---|---:|
| 2018-19 | +12.7% |
| 2019-20 | +14.3% |
| 2020-21 | +16.4% |
| 2021-22 | +17.5% |
| 2022-23 | +9.2% |
| 2023-24 | +5.7% |
| 2024-25 | +6.3% |
| 2025-26 | +6.4% |

The later years have roughly 7.5% excess mass in the first five integer enrolment values above 250, while the comparable mass immediately below is only around 1-2% above its fitted counterfactual.

However, placebo-threshold comparisons materially weaken a manipulation claim.

For the completed placebo-ranking years, 250/251 lies at approximately:

- 2018-19: 91st percentile among tested placebo thresholds
- 2020-21: 96th percentile
- 2023-24: 78th percentile
- 2024-25: 78th percentile
- 2025-26: 70th percentile

Thus the 250/251 irregularity is repeatable, especially in earlier years, but it is not uniquely extreme relative to the general lumpiness of school-enrolment administrative data.

**Conclusion: bunching is a secondary result. It is not strong enough to claim strategic manipulation of enrolment.**

## Experiment 5: other true thresholds

The same heaping-adjusted distribution screen was run at other CSG thresholds where possible.

The 100/101 boundary displays substantially stronger irregularity than 250/251 in every completed year. For example, its heaping-adjusted asymmetry is approximately +35.1% in 2018-19, +37.6% in 2020-21, +32.5% in 2023-24, +25.2% in 2024-25 and +26.1% in 2025-26.

This cannot be interpreted as a clean CSG behavioural effect. PM POSHAN cook-cum-helper and kitchen-infrastructure rules also change with enrolment around 100 and subsequent 100-pupil blocks. The 100 threshold is therefore useful evidence that administrative enrolment is highly non-smooth around policy-relevant values, but it is not a CSG-only causal experiment.

The 30/31 cutoff does not show analogous positive excess mass in the completed screens. The 1000/1001 cutoff is too sparse for a stable national inference in many years.

## Experiment 6: outcome detectability audit

The earlier outcome-null paper framing is no longer the preferred study.

There are two separate reasons.

First, the treatment was previously paired to the wrong financial-reporting round.

Second, many legitimate CSG uses are flow expenditures that cannot be expected to move coarse UDISE stock indicators. Examples in official utilisation guidance include consumables, newspapers, play materials, electricity, internet and water charges, teaching aids, repairs, maintenance, activities, small materials, transport and honoraria. A school can spend several thousand rupees productively without moving a whole-school furniture category, a binary electricity indicator or a toilet-availability indicator.

Therefore the exhaustive UDISE outcome search remains useful only as a mechanism screen. It does not support the broad claim that CSG produces no benefit.

## Experiment 7: retiming the previous facility results

The previous confirmatory outcome work can be reinterpreted around the corrected clock.

For the 2021-22 enrolment cohort, the documented-style grant financial year is 2023-24 and that financial year appears in the UDISE 2024-25 financial field. Therefore 2024-25 and 2025-26 are the relevant observed facility rounds, not 2023-24 as the primary post-treatment year.

The previously estimated deterioration effects at those horizons are +0.11 pp in 2024-25 (p=.410) and +0.15 pp in 2025-26 (p=.246). There is no evidence of a maintenance benefit.

For the 2022-23 enrolment cohort, the corresponding UDISE financial field is 2025-26. The 2025-26 deterioration estimate is +0.054 pp with a 95% confidence interval of approximately -0.212 to +0.319 pp. Again, there is no observed maintenance benefit.

Likewise, the 2022-23 cohort's 2025-26 standardized indices are Core +0.073 SD, WASH +0.094 SD, Digital +0.014 SD, Accessibility +0.012 SD and Overall +0.057 SD, none statistically established.

These correctly timed reduced-form nulls make a large benefit operating through preservation of the specific UDISE-observed assets unlikely. They do **not** establish that discretionary school spending has no value because the grant's relevant intensive-margin uses are often not measured by UDISE.

## What is superseded

The following earlier claims should no longer appear in the paper or brief:

1. **"The CSG first stage is only 6-8 percentage points."** Superseded. Those were +2 UDISE reporting-round estimates. The correctly aligned +3 first stage is approximately 25-33 pp across four usable cohorts.
2. **"The same grant expenditure persists for several subsequent years."** Not identified. Later annual UDISE expenditure records can reflect new CSG cycles based on later lagged enrolment vintages. Cumulative expenditure across future UDISE rounds should be treated as descriptive, not as a trace of one original grant allocation.
3. **"An additional Rs 25,000 causes no improvement."** Unsupported. Crossing the threshold is a fuzzy assignment and the UDISE financial field does not mechanically record an exact Rs 25,000 treatment difference.
4. **"CSG does not work."** Unsupported.
5. **"Bunching proves schools manipulate enrolment."** Unsupported. The 250/251 anomaly is real but not uniquely extreme against placebo thresholds.
6. **"Nothing in the school improves."** Unsupported. The broad UDISE screen finds no replicating positive mechanism in its observed variables, but many CSG uses are outside their measurement resolution.

## What survives

The following statements are defensible:

1. **The CSG formula has a strong delayed financial fingerprint in UDISE.** Around 250/251, correctly aligned receipt data show approximately 25-33 pp higher probability of reporting at least Rs 75,000.
2. **The administrative clock matters enormously.** Documentary allocation rules and the UDISE financial reporting period jointly explain why the peak appears three academic-data rounds after the enrolment vintage.
3. **Recorded funding fidelity is substantial but far from mechanical.** In the detailed 2021-22 cohort, crossing the cutoff changes P(receipt >=Rs75k) by about 33.5 pp but P(exactly Rs75k) by only about 5.3 pp.
4. **There is modest excess school mass just above 250.** It repeats across years, but placebo comparisons do not justify a manipulation headline.
5. **A large maintenance effect on the UDISE-observed asset set is not supported at the correctly retimed post-grant horizons.** This remains a narrow mechanism finding, not a verdict on overall grant effectiveness.

## Experiments implemented in the repository

The branch now contains reproducible workflows/code for:

- full eight-year lead-lag timing matrix
- corrected 250.5 RD coordinate
- state/UT-clustered timing inference
- PM POSHAN-safe subsamples
- grant-fidelity decomposition
- heaping-adjusted bunching and placebo cutoffs
- longitudinal threshold-crossing and reversion tests
- state-specific lag fingerprints
- state-year implementation-intensity versus bunching tests
- multi-threshold CSG financial tests
- fuzzy-RD outcome sensitivity
- outcome-detectability audit
- national threshold-scheme registry

## Execution limitation encountered after the core runs

The core timing matrix, full eight-year timing program, grant-fidelity cohort and multiple bunching jobs completed successfully. During the remaining parallel extensions GitHub Actions began refusing new jobs before runner startup because the account reported failed recent payments or an Actions spending-limit issue.

As a result, the following code-complete extensions did not obtain fresh runners after their final patches:

- longitudinal threshold-crossing/reversion experiment
- state-specific lag distribution
- state-year implementation-intensity versus bunching correlation
- financial first-stage replication at every CSG cutoff
- final corrected fuzzy-RD treatment-effect run
- exact grant-point-mass fidelity replication for the other three +3 cohorts

These are not being silently reported as completed results. Their code is committed and ready to execute when Actions runner access resumes.

The proposed >700-enrolment ICT positive control is also deliberately not presented as completed: the rule is discretionary and the current panel does not contain a clean post-treatment UDISE round for the newest approvals.

## Bottom line for the study

The strongest paper available from the current evidence is no longer an impact paper asking whether a small marginal grant changes toilets, furniture or other coarse school stocks.

A more defensible empirical contribution is:

> **Formula-based school funding leaves a strong but delayed administrative fingerprint. Around India's 250-pupil Composite School Grant cutoff, the probability of reporting a higher-band school grant jumps sharply only after the enrolment, allocation and UDISE financial-reporting clocks are aligned. The recorded financial response is substantial but does not mechanically reproduce the statutory amount, while modest enrolment bunching around the cutoff is not exceptional enough to establish strategic manipulation.**

This is an implementation and administrative-measurement result. It is materially stronger than the previous outcome-null story, but it should not be oversold as a definitive causal study of the returns to school funding.
