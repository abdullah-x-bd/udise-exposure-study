# Composite School Grant Study

## Headline findings

This study is now complete as a first full empirical pass across the available UDISE vintages from 2018-19 through 2025-26.

The strongest result is not that larger Composite School Grants clearly improve basic school facilities. The stronger and more defensible finding is that the enrolment formula does generate larger reported grant receipts and expenditures around the 250-pupil threshold in the usable post-pandemic cohorts, but those extra reported resources do not produce a consistent detectable improvement in basic facility functionality over the following period.

In short:

**Money moves. Basic facility outcomes mostly do not.**

That is potentially a useful implementation-effectiveness result, but it should be framed as suggestive quasi-experimental evidence rather than a perfect textbook regression discontinuity because the enrolment distribution is not completely smooth around the thresholds.

---

## Study design

The study exploits the enrolment bands used for the Composite School Grant. Under the schedule tested here, crossing 250 pupils changes the nominal grant band from ₹50,000 to ₹75,000, a ₹25,000 statutory step.

The empirical sample is restricted to UDISE government-management categories 1, 2 and 3, corresponding to Department of Education, Tribal/Social Welfare, and Local Body government schools. Private and government-aided schools are excluded from the causal sample because the Composite School Grant under Samagra Shiksha is a government-school grant.

The analysis uses lagged enrolment to define assignment and follows the same school forward. Six assignment-to-outcome cohorts were constructed:

- 2018-19 to 2020-21
- 2019-20 to 2021-22
- 2020-21 to 2022-23
- 2021-22 to 2023-24
- 2022-23 to 2024-25
- 2023-24 to 2025-26

The central specification uses the 250-pupil threshold, a ±30-pupil bandwidth, excludes the immediate cutoff observation with a one-pupil donut, includes assignment-state fixed effects, and clusters uncertainty at the state level.

Outcome analysis is based on changes in the same school's measured condition from the assignment-year baseline to the later outcome year. This is deliberately stricter than a cross-sectional comparison because it differences out persistent school-level condition differences.

---

## Finding 1. The grant formula creates a real first stage in the clean post-pandemic cohorts

### 2021-22 assignment to 2023-24 outcome

At the 250-pupil threshold:

- Reported CSG receipt increases by **₹12,461**
- Standard error = ₹4,514
- 95% CI approximately ₹3,615 to ₹21,307
- p = 0.0058

Reported CSG expenditure increases by **₹8,897**

- Standard error = ₹2,862
- 95% CI approximately ₹3,287 to ₹14,506
- p = 0.0019

### 2022-23 assignment to 2024-25 outcome

At the same threshold:

- Reported CSG receipt increases by **₹12,232**
- Standard error = ₹5,978
- 95% CI approximately ₹514 to ₹23,950
- p = 0.0408

Reported CSG expenditure increases by **₹10,175**

- Standard error = ₹5,096
- 95% CI approximately ₹187 to ₹20,163
- p = 0.0459

Across these two clean central cohorts, an inverse-variance descriptive combination gives approximately:

- **₹12,378 additional reported receipt**, 95% CI about ₹5,318 to ₹19,438
- **₹9,203 additional reported expenditure**, 95% CI about ₹4,312 to ₹14,094

This is not a substitute for the cohort-specific estimates, but it summarizes the scale of the observed first stage.

The observed receipt step is roughly half of the ₹25,000 statutory band increase. The spending step is smaller still. This suggests incomplete transmission from nominal entitlement to reported school-level receipt and spending.

---

## Finding 2. The first stage is not equally clean in every year

The earlier cohorts are not informative in the same way.

For 2018-19 to 2020-21 and 2019-20 to 2021-22, the relevant reported receipt and expenditure fields are zero in the local sample, so those cohorts cannot identify a funding effect.

For 2020-21 to 2022-23, the 250-pupil receipt discontinuity is small and statistically indistinguishable from zero.

For 2023-24 to 2025-26, the receipt point estimate is very large and imprecise, while the expenditure estimate is also imprecise. This cohort appears to contain either a reporting, implementation, or coding regime change and should not be pooled mechanically with the cleaner 2021-22 and 2022-23 cohorts.

Therefore the most credible first-stage evidence comes from **2021-22 and 2022-23 assignment cohorts**.

---

## Finding 3. Basic facility functionality does not show a consistent positive response

In the two cohorts with the cleanest 250-pupil funding first stage, the following outcomes show no consistent positive discontinuity in subsequent change:

- functional girls' toilets
- functional boys' toilets
- functional drinking water
- handwashing facilities for meals
- electricity
- internet
- library availability

### 2021-22 to 2023-24 central specification

Estimated change at the threshold:

- Girls' toilet functionality: -0.41 percentage points, p = 0.223
- Boys' toilet functionality: -0.69 percentage points, p = 0.081
- Functional water: -0.01 percentage points, p = 0.979
- Handwashing for meals: -0.39 percentage points, p = 0.419
- Electricity: +0.34 percentage points, p = 0.095
- Internet: -0.82 percentage points, p = 0.288
- Library: -0.74 percentage points, p = 0.207

### 2022-23 to 2024-25 central specification

- Girls' toilet functionality: -0.08 percentage points, p = 0.770
- Boys' toilet functionality: -0.30 percentage points, p = 0.241
- Functional water: +0.02 percentage points, p = 0.797
- Handwashing for meals: +0.13 percentage points, p = 0.700
- Electricity: -0.37 percentage points, p = 0.015
- Internet: +0.94 percentage points, p = 0.353
- Library: +0.28 percentage points, p = 0.421

The isolated negative electricity estimate in 2022-23 is not robust enough to treat as a substantive adverse effect. It weakens at wider bandwidths and does not replicate in the preceding or following cohorts.

The overall pattern is therefore **no stable evidence that the marginal CSG increase at 250 pupils materially improves these basic facility-functionality outcomes over this horizon**.

---

## Finding 4. This is not evidence that the grant is useless

The estimates are local to schools around the enrolment threshold. They identify the effect of moving from one grant band to the next, not the effect of eliminating the Composite School Grant entirely.

A null marginal effect can arise for several reasons:

1. the grant increment may be too small relative to the school's maintenance needs
2. the money may be spent on eligible items not captured by the selected UDISE facility indicators
3. the spending may prevent deterioration rather than generate a visible upgrade
4. schools may face procurement, timing, administrative, or implementation constraints
5. reported receipt and reported expenditure may not perfectly measure usable cash at the school level

The paper should therefore avoid the claim that CSG "does not work." The supported claim is narrower:

> Around the 250-pupil funding threshold, larger reported Composite School Grant receipts and expenditures are not followed by a consistent detectable improvement in the basic facility-functionality indicators measured here.

---

## Finding 5. The 100-pupil cutoff should not be the headline RD

The 100-pupil threshold has a strong funding first stage in several cohorts, but the enrolment distribution shows pronounced bunching around 100.

In the 2022-23 assignment cohort, for example, the local log-density diagnostic implies roughly a 31% discontinuity in school counts around 100, and the five-cell count ratio just above versus just below the cutoff is about 1.31.

That is too large to ignore in a continuity-based RD design.

The 250 cutoff is better, but not perfect. The corresponding log-density diagnostics around 250 are approximately:

- 2018-19: +7.6%
- 2019-20: +7.3%
- 2020-21: +18.8%
- 2021-22: +18.2%
- 2022-23: +9.3%
- 2023-24: +6.1%

The immediate five-enrolment-cell ratios above versus below 250 are much closer to one in the later cohorts, approximately 1.15 in 2021-22, 1.05 in 2022-23, and 1.01 in 2023-24.

This makes the 250 threshold substantially more defensible than 100, but still not an immaculate RD. Possible explanations include strategic enrolment reporting, heaping, administrative assignment rules, or naturally discontinuous school-size distributions.

The final causal language should therefore remain careful.

---

## Finding 6. Baseline continuity is reasonably good for the headline facility outcomes

At the 250 threshold in the two clean funding cohorts, most baseline facility outcomes do not show statistically significant discontinuities before the later grant/outcome period.

This is reassuring for:

- toilet functionality
- functional water
- handwashing
- internet
- library
- electricity, although the 2022-23 baseline electricity test is somewhat close to conventional significance at p ≈ 0.086

Major-repair classroom condition is borderline discontinuous at baseline and classroom-repair fields also have poor cross-state coverage in the focused vintage. Classroom-condition estimates should therefore not be headline outcomes.

The national WASH, electricity, internet, and library outcomes have much broader state coverage and are the safer outcome family.

---

## Best current substantive interpretation

The cleanest interpretation is an implementation chain:

1. Crossing the 250-pupil threshold raises nominal CSG entitlement by ₹25,000.
2. In the cleanest post-pandemic cohorts, reported receipt rises by only about ₹12,000.
3. Reported expenditure rises by roughly ₹9,000 to ₹10,000.
4. The selected basic facility-functionality outcomes do not show a corresponding stable positive change.

That creates two policy questions rather than one:

- Why does only part of the nominal grant-band increase appear in reported school receipt?
- Why does the additional reported spending not translate into detectable changes in the basic facility indicators measured by UDISE?

This is potentially more interesting than a simple positive-effect story because it separates **allocation, transmission, expenditure, and outcome conversion**.

---

## Recommended paper framing

A defensible working title is:

**From Entitlement to Outcomes: What India's Composite School Grant Thresholds Reveal About Funding Transmission and School Facilities**

A sharper alternative is:

**Money Moves, Facilities Do Not: Quasi-Experimental Evidence from India's Composite School Grant Formula**

The second title is punchier but should only be used with the caveat that the RD density test is imperfect.

The central research question should be:

**Does crossing an enrolment-based Composite School Grant threshold increase school-level funding, and does the marginal increase translate into measurable improvements in basic school facilities?**

The answer from the current study is:

**The threshold increases reported funding in the cleanest cohorts, but we do not find a consistent corresponding improvement in basic facility functionality.**

---

## What should and should not be claimed

### Supported

- CSG receipt and expenditure respond to the 250-pupil formula threshold in the strongest post-pandemic cohorts.
- The realized receipt increase is materially smaller than the statutory ₹25,000 step.
- Most measured WASH, electricity, internet, and library outcomes show no robust positive discontinuity in subsequent change.
- The evidence points toward a potential implementation or conversion gap between entitlement, receipt, expenditure, and observable facility outcomes.

### Not supported

- CSG has no value.
- The grant causes school conditions to worsen.
- Every rupee is misused or leaked.
- The full ₹25,000 entitlement fails to reach schools because the UDISE receipt measure may not map perfectly onto administrative disbursement.
- The design is a flawless RD. The density diagnostics prevent that claim.
- The estimates generalize to very small or very large schools far from the threshold.

---

## Status

The computational study has been run successfully across all six longitudinal cohorts. The analysis code, schema diagnostics, first-stage checks, density diagnostics, pre-treatment continuity tests, placebo cutoffs, bandwidth variants, and cohort replications are contained in this study folder on the `research/composite-school-grant-study` branch.

The next stage is paper production rather than basic discovery: final figures, final tables, a formal methods write-up, and a stricter robustness appendix should be generated from these results before submission.