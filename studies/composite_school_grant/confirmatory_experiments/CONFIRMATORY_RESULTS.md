# Confirmatory Experiments: Results

## Bottom line

All four prespecified confirmatory experiments were completed on the two clean post-pandemic assignment cohorts.

The confirmatory package does **not** uncover a hidden, stable positive outcome effect of the marginal Composite School Grant increase.

The strongest new result is that the earlier null is **not primarily explained by maintenance rather than improvement**. The deterioration composite is estimated very precisely and shows no replicating reduction in deterioration. The data can generally rule out deterioration effects even well below two percentage points. Upgrade effects are less precisely estimated, but effects as large as five percentage points can be rejected.

The baseline-need analysis does not identify a stable subgroup in which observable school conditions improve. A suggestive pattern appears in the *funding response*: high-need schools have larger cumulative-expenditure point estimates than low-need schools in both cohorts. However, the subgroup-difference evidence is not sufficiently precise to treat this as a confirmed heterogeneous causal effect, and no corresponding positive outcome pattern replicates.

Dynamic standardized indices likewise show no stable positive movement across core functionality, WASH, digital, accessibility, or the overall index. Several isolated positive or negative coefficients occur in one cohort or horizon, but they do not reproduce across cohorts and should not be promoted as substantive findings.

The central empirical puzzle therefore survives the full confirmatory exercise:

> **The 250-pupil threshold generates a persistent increase in reported CSG expenditure, but neither individual school assets, maintenance transitions, upgrade transitions, need-stratified outcomes, nor broad standardized outcome indices show a stable corresponding improvement.**

---

# Experiment 1. Maintenance versus improvement

## Question

Could the CSG be valuable because it prevents existing facilities from deteriorating rather than creating visible new assets?

For each school and asset, the analysis separated:

- deterioration among assets that were functional/good at baseline;
- upgrading among assets that were deficient at baseline.

The asset family contains functional water, meal handwashing, electricity, internet, library, ramps, handrails, fully functional girls' toilets, and fully functional boys' toilets where observed in both vintages.

Composite deterioration and upgrade rates were estimated using the headline 250-pupil RD specification.

## 2022-23 assignment cohort

### Deterioration composite

2024-25:

- effect = **-0.026 percentage points**
- SE = 0.153 pp
- 95% CI = **-0.326 to +0.275 pp**
- p = 0.866
- 80% MDE = 0.429 pp

2025-26:

- effect = **+0.054 percentage points**
- SE = 0.136 pp
- 95% CI = **-0.212 to +0.319 pp**
- p = 0.692
- 80% MDE = 0.379 pp

Both estimates pass equivalence tests within ±2 percentage points with overwhelming margin.

### Upgrade composite

2024-25:

- effect = **-0.64 percentage points**
- 95% CI = **-3.02 to +1.75 pp**
- p = 0.602

2025-26:

- effect = **+0.21 percentage points**
- 95% CI = **-2.22 to +2.64 pp**
- p = 0.868

The study cannot establish equivalence within ±2 pp for upgrading, but it does establish equivalence within ±5 pp.

No individual deterioration or upgrade outcome survives Benjamini-Hochberg FDR < 0.10 in this cohort.

## 2021-22 assignment cohort

### Deterioration composite

2023-24:

- effect = **+0.436 percentage points**
- 95% CI = **+0.055 to +0.816 pp**
- p = 0.0249

This is a small **increase**, rather than reduction, in short-run deterioration above the threshold. It does not persist:

2024-25:

- effect = **+0.110 pp**
- 95% CI = -0.151 to +0.370 pp
- p = 0.410

2025-26:

- effect = **+0.155 pp**
- 95% CI = -0.107 to +0.417 pp
- p = 0.246

All three deterioration estimates are statistically equivalent within ±2 pp.

### Upgrade composite

2023-24:

- +0.35 pp, 95% CI -1.82 to +2.53 pp, p = 0.750

2024-25:

- +0.04 pp, 95% CI -2.46 to +2.55 pp, p = 0.972

2025-26:

- -0.75 pp, 95% CI -3.41 to +1.90 pp, p = 0.579

Again, ±2 pp equivalence cannot be established, but ±5 pp equivalence can.

Three individual transition estimates survive within-cohort FDR correction, but all are adverse rather than beneficial and none forms a replicating mechanism:

- 2023-24 library upgrading: -4.55 pp, q = 0.0057
- 2023-24 boys' fully-functional-toilet deterioration: +1.33 pp, q = 0.049
- 2025-26 internet upgrading: -2.30 pp, q = 0.033

These do not reproduce in the 2022-23 cohort, where there are zero FDR hits. They should be treated as cohort-specific anomalies/signals rather than headline causal effects.

## Conclusion from Experiment 1

The maintenance hypothesis does **not** explain the broader null result.

The strongest statement supported by the data is:

> The marginal CSG step does not generate a stable reduction in deterioration of existing observed school assets. The deterioration composite is measured precisely enough to rule out even fairly small maintenance effects.

Large upgrade effects are also ruled out, although modest upgrades below roughly 2-3 percentage points remain compatible with the confidence intervals.

---

# Experiment 2. Baseline-need heterogeneity

## Construction

A pre-treatment infrastructure-deficit score was constructed from the baseline asset family. Both cohorts produce the same empirical cut points in the local ±75-pupil sample:

- 33rd percentile = 1/9 = 0.1111
- 67th percentile = 2/9 = 0.2222

Because the score is discrete, the middle group is relatively small. Interpretation should therefore focus primarily on low-need versus high-need schools, rather than treating the three strata as balanced tertiles.

## Funding response

### 2021-22 assignment cohort, cumulative expenditure through 2025-26

All schools:

- **+₹28,839**
- 95% CI ₹11,802 to ₹45,876
- p = 0.00091

Low need:

- +₹10,007
- 95% CI -₹6,402 to ₹26,416
- p = 0.232

High need:

- **+₹38,474**
- 95% CI ₹9,558 to ₹67,391
- p = 0.0091

### 2022-23 assignment cohort, cumulative expenditure through 2025-26

All schools:

- **+₹34,033**
- 95% CI ₹9,597 to ₹58,469
- p = 0.0063

Low need:

- **+₹15,289**
- 95% CI ₹6,766 to ₹23,812
- p = 0.00044

High need:

- +₹47,972
- 95% CI -₹2,341 to ₹98,284
- p = 0.0616

The high-need point estimate is larger than the low-need estimate in both cohorts. This is **suggestive**, but the subgroup estimates are not precise enough to establish a stable differential treatment effect. It should be presented as a secondary pattern, not a confirmed mechanism.

## Outcome heterogeneity

No need stratum shows a stable positive outcome response across cohorts and horizons.

Examples of why isolated subgroup findings should not be promoted:

- In the 2022-23 cohort, low-need schools show a +0.049 SD digital-index effect in 2024-25 (p = 0.0010) and +0.034 SD in 2025-26 (p = 0.022).
- In the 2021-22 cohort, the same low-need digital effect is approximately zero at all three horizons.
- In 2021-22, high-need schools show a negative digital coefficient in 2025-26 (-0.038 SD, p = 0.019), which does not reproduce in 2022-23.
- Several early low-need WASH coefficients in 2021-22 are negative, but those patterns do not reproduce in 2022-23.

Therefore there is no credible evidence that the overall null is masking a robust benefit concentrated in initially disadvantaged schools.

## Conclusion from Experiment 2

> Baseline need does not reveal a stable positive outcome effect. There is only suggestive evidence that the cumulative expenditure response itself may be larger among higher-need schools.

---

# Experiment 3. Power and equivalence

This experiment asks a different question from statistical significance:

> How large an effect can the data rule out?

## Maintenance/deterioration

The answer is strong.

Across both clean cohorts and all available horizons, the deterioration-composite 95% intervals are narrow. The largest absolute 95% confidence bound is approximately **0.82 percentage points**, from the first 2021-22 horizon.

In the 2022-23 cohort the bounds are tighter still, approximately ±0.3 percentage points.

Every deterioration-composite specification rejects effects outside ±2 pp.

Thus the data do not merely “fail to find” a large maintenance benefit. They provide evidence inconsistent with a maintenance effect of several percentage points on the observed asset-transition composite.

## Upgrading

The upgrade composite is less precise.

Across the two cohorts, 95% intervals extend to roughly 2-3.4 percentage points in either direction depending on horizon.

- ±2 pp equivalence is **not** established.
- ±5 pp equivalence **is** established at every horizon.

So a modest upgrade effect remains possible; a large upgrade effect does not.

## Standardized dynamic indices

Precision varies by domain and cohort.

The 2021-22 cohort is particularly informative for digital and accessibility outcomes:

- digital index effects are equivalent within ±0.05 SD at all three horizons;
- accessibility is equivalent within ±0.05 SD in 2023-24 and 2024-25, and narrowly misses the ±0.05 test in 2025-26 while easily satisfying ±0.10 SD.

For the 2021-22 overall index:

- 2024-25 is equivalent within ±0.05 SD;
- all horizons are equivalent within ±0.10 SD.

Core-functionality and WASH indices are less consistently equivalent within ±0.05 SD, and the corresponding 2022-23 indices are substantially less precise. The study should therefore not claim that all possible domain effects smaller than 0.1 SD have been ruled out.

## Conclusion from Experiment 3

The null is strongest for **maintenance transitions**, moderately strong for **large upgrade effects**, and domain-dependent for standardized indices.

A defensible statement is:

> The evidence rules out a material several-percentage-point maintenance effect and rules out upgrade effects as large as five percentage points, but it cannot exclude all modest improvements in upgrading or every domain index.

---

# Experiment 4. Dynamic outcome indices

Five fixed-baseline indices were analysed:

- core functionality
- WASH
- digital
- accessibility
- overall

All later values use baseline component means and standard deviations. Each outcome is change in the same school's index from the assignment-year baseline.

## 2022-23 cohort

2024-25:

- core functionality: -0.003 SD, p = 0.975
- WASH: -0.010 SD, p = 0.924
- digital: +0.030 SD, p = 0.129
- accessibility: -0.015 SD, p = 0.381
- overall: -0.001 SD, p = 0.990

2025-26:

- core functionality: +0.073 SD, p = 0.379
- WASH: +0.094 SD, p = 0.392
- digital: +0.014 SD, p = 0.402
- accessibility: +0.012 SD, p = 0.596
- overall: +0.057 SD, p = 0.254

There is no statistically established positive index response.

## 2021-22 cohort

Some early coefficients are negative:

2023-24:

- core functionality: -0.028 SD, p = 0.077
- WASH: **-0.043 SD**, p = 0.016
- digital: -0.013 SD, p = 0.254
- accessibility: -0.007 SD, p = 0.691
- overall: **-0.033 SD**, p = 0.044

The negative WASH and overall coefficients weaken later:

2024-25:

- core: -0.021 SD, p = 0.211
- WASH: -0.033 SD, p = 0.073
- digital: -0.008 SD, p = 0.561
- accessibility: -0.006 SD, p = 0.710
- overall: -0.019 SD, p = 0.234

2025-26:

- core: -0.023 SD, p = 0.185
- WASH: -0.033 SD, p = 0.059
- digital: -0.022 SD, p = 0.143
- accessibility: -0.023 SD, p = 0.183
- overall: -0.032 SD, p = 0.064

These negative point estimates do not reproduce in the 2022-23 cohort. They are therefore insufficient for a claim that the grant worsens conditions.

## Conclusion from Experiment 4

> Dynamic domain indices do not reveal a stable positive effect hidden by noisy individual outcomes. Nor is there sufficiently replicating evidence of harm.

---

# Integrated interpretation after all four experiments

The four confirmatory tests materially strengthen the interpretation of the full study.

We can now reject several obvious explanations for the earlier result:

### “Maybe the grant mainly prevents deterioration.”

Not supported. Maintenance transitions are precisely estimated and show no stable benefit.

### “Maybe it only helps schools that begin in poor condition.”

Not supported by observable outcomes. High-need schools do not show a replicating positive response, although their cumulative-expenditure point estimates are larger.

### “Maybe the nulls are just underpowered.”

Only partly. Upgrade and some domain indices remain compatible with modest effects. But maintenance outcomes are highly powered, and large upgrade effects are ruled out.

### “Maybe dozens of individual noisy outcomes conceal a broad improvement.”

Not supported. Fixed-baseline standardized indices show no stable positive movement.

The empirical finding should therefore be framed as:

> **At the 250-pupil CSG threshold, additional entitlement produces persistent additional reported expenditure. Comprehensive discovery and confirmatory analyses do not identify a stable corresponding improvement in the school assets and administrative outcomes observed by UDISE. In particular, the data rule out a sizeable effect operating through reduced deterioration of existing assets.**

This remains a local quasi-experimental result around the 250-pupil threshold and inherits the previously documented density caveat. It is not evidence that the entire CSG programme is useless, that funds are misused, or that unmeasured recurring/consumable benefits do not exist.

## Implication for the paper

The paper should now emphasize **conversion and observability**, not simply a generic null.

The full chain is:

1. formula-based nominal entitlement increase;
2. incomplete immediate transmission into reported receipt;
3. persistent/cumulative increase in reported expenditure;
4. no stable improvement across a comprehensive observed-output search;
5. no maintenance benefit in transition analysis;
6. no stable high-need subgroup benefit;
7. no hidden positive response in standardized dynamic indices;
8. insufficient expenditure-purpose data to identify which unmeasured inputs absorbed the additional spending.

This is a stronger result than the first descriptive outcome analysis because the main alternative explanations have now been directly tested.

## Reproducibility

The prespecification, analysis code and workflow are stored in:

- `studies/composite_school_grant/confirmatory_experiments/README.md`
- `studies/composite_school_grant/confirmatory_experiments/run_confirmatory.py`
- `.github/workflows/csg-confirmatory-four-experiments.yml`

Workflow run: `31861984700`.
