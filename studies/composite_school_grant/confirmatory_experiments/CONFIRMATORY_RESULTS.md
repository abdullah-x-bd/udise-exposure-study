# Confirmatory Experiments: Results

## Summary

All four prespecified confirmatory experiments were completed on the two clean post-pandemic assignment cohorts.

The confirmatory package does not reveal a stable positive effect on the coarse school-condition outcomes observed in UDISE. The strongest result is that the earlier null is not explained by a maintenance mechanism: the deterioration composite is estimated precisely and shows no replicating reduction in deterioration. Upgrade effects are less precise, but effects as large as five percentage points are rejected.

The baseline-need analysis does not identify a stable subgroup in which observed school conditions improve. High-need schools do have larger cumulative-expenditure point estimates than low-need schools in both cohorts, but the subgroup differences are too imprecise to establish a stable heterogeneous effect and no corresponding positive outcome pattern replicates.

Dynamic standardized indices likewise show no stable positive movement across core functionality, WASH, digital, accessibility or the overall index. Isolated positive and negative coefficients occur in individual cohort-horizon cells, but they do not reproduce across cohorts.

The empirical puzzle from this stage of the project is therefore:

> **The 250-pupil threshold is associated with higher reported CSG expenditure, while individual school assets, maintenance transitions, upgrade transitions, need-stratified outcomes and broad standardized outcome indices do not show a stable corresponding improvement in the observed UDISE measures.**

This module is retained as a mechanism and observability analysis. The later project-wide results reconstruct the administrative clock more completely and are summarized in `../FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md`.

---

# Experiment 1. Maintenance versus improvement

## Question

The first experiment tests whether the CSG is valuable primarily because it prevents existing facilities from deteriorating rather than creating visible new assets.

For each school and asset, the analysis separates:

- deterioration among assets that were functional/good at baseline;
- upgrading among assets that were deficient at baseline.

The asset family contains functional water, meal handwashing, electricity, internet, library, ramps, handrails, fully functional girls' toilets and fully functional boys' toilets where observed in both vintages.

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

Both estimates pass equivalence tests within +/-2 percentage points.

### Upgrade composite

2024-25:

- effect = **-0.64 percentage points**
- 95% CI = **-3.02 to +1.75 pp**
- p = 0.602

2025-26:

- effect = **+0.21 percentage points**
- 95% CI = **-2.22 to +2.64 pp**
- p = 0.868

Equivalence within +/-2 pp is not established for upgrading, while +/-5 pp equivalence is established.

No individual deterioration or upgrade outcome survives Benjamini-Hochberg FDR < 0.10 in this cohort.

## 2021-22 assignment cohort

### Deterioration composite

2023-24:

- effect = **+0.436 percentage points**
- 95% CI = **+0.055 to +0.816 pp**
- p = 0.0249

This is a small increase rather than reduction in short-run deterioration above the threshold and does not persist.

2024-25:

- effect = **+0.110 pp**
- 95% CI = -0.151 to +0.370 pp
- p = 0.410

2025-26:

- effect = **+0.155 pp**
- 95% CI = -0.107 to +0.417 pp
- p = 0.246

All three deterioration estimates are statistically equivalent within +/-2 pp.

### Upgrade composite

2023-24:

- +0.35 pp, 95% CI -1.82 to +2.53 pp, p = 0.750

2024-25:

- +0.04 pp, 95% CI -2.46 to +2.55 pp, p = 0.972

2025-26:

- -0.75 pp, 95% CI -3.41 to +1.90 pp, p = 0.579

Equivalence within +/-2 pp is not established, while +/-5 pp equivalence is.

Three individual transition estimates survive within-cohort FDR correction, but all are adverse rather than beneficial and none forms a replicating mechanism:

- 2023-24 library upgrading: -4.55 pp, q = 0.0057
- 2023-24 boys' fully-functional-toilet deterioration: +1.33 pp, q = 0.049
- 2025-26 internet upgrading: -2.30 pp, q = 0.033

These do not reproduce in the 2022-23 cohort and are treated as cohort-specific signals rather than stable causal mechanisms.

## Experiment 1 conclusion

The maintenance hypothesis does not explain the broader null result. The marginal CSG threshold step does not generate a stable reduction in deterioration of the observed school assets. Large upgrade effects are also ruled out, although modest upgrading effects below roughly 2-3 percentage points remain compatible with the confidence intervals.

---

# Experiment 2. Baseline-need heterogeneity

## Construction

A pre-treatment infrastructure-deficit score was constructed from the baseline asset family. Both cohorts produce the same empirical cut points in the local +/-75-pupil sample:

- 33rd percentile = 1/9 = 0.1111
- 67th percentile = 2/9 = 0.2222

Because the score is discrete, the middle group is relatively small. The most informative contrast is therefore low-need versus high-need schools rather than balanced tertiles.

## Funding response

### 2021-22 assignment cohort, cumulative expenditure through 2025-26

All schools:

- **+Rs 28,839**
- 95% CI Rs 11,802 to Rs 45,876
- p = 0.00091

Low need:

- +Rs 10,007
- 95% CI -Rs 6,402 to Rs 26,416
- p = 0.232

High need:

- **+Rs 38,474**
- 95% CI Rs 9,558 to Rs 67,391
- p = 0.0091

### 2022-23 assignment cohort, cumulative expenditure through 2025-26

All schools:

- **+Rs 34,033**
- 95% CI Rs 9,597 to Rs 58,469
- p = 0.0063

Low need:

- **+Rs 15,289**
- 95% CI Rs 6,766 to Rs 23,812
- p = 0.00044

High need:

- +Rs 47,972
- 95% CI -Rs 2,341 to Rs 98,284
- p = 0.0616

The high-need point estimate is larger than the low-need estimate in both cohorts, but the subgroup estimates are not precise enough to establish a stable differential effect.

## Outcome heterogeneity

No need stratum shows a stable positive outcome response across cohorts and horizons. Isolated digital and WASH coefficients differ in sign and timing across the two cohorts and do not replicate.

The observed outcome null therefore does not appear to conceal a robust benefit concentrated in initially disadvantaged schools.

---

# Experiment 3. Power and equivalence

This experiment asks how large an effect the data can rule out rather than only whether a coefficient is statistically significant.

## Maintenance/deterioration

Across both clean cohorts and all available horizons, the deterioration-composite 95% intervals are narrow. The largest absolute 95% confidence bound is approximately **0.82 percentage points**, from the first 2021-22 horizon.

In the 2022-23 cohort, the bounds are approximately +/-0.3 percentage points.

Every deterioration-composite specification rejects effects outside +/-2 pp. The data therefore provide evidence inconsistent with a maintenance effect of several percentage points on the observed asset-transition composite.

## Upgrading

The upgrade composite is less precise. Across the two cohorts, 95% intervals extend to roughly 2-3.4 percentage points in either direction depending on horizon.

- +/-2 pp equivalence is not established.
- +/-5 pp equivalence is established at every horizon.

A modest upgrade effect therefore remains possible, while a large upgrade effect does not.

## Standardized dynamic indices

Precision varies by domain and cohort. The 2021-22 cohort is particularly informative for digital and accessibility outcomes, while core-functionality and WASH indices are less consistently equivalent within +/-0.05 SD. The corresponding 2022-23 indices are substantially less precise.

The evidence is therefore strongest for maintenance transitions, moderately strong for large upgrade effects and domain-dependent for standardized indices.

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

2023-24:

- core functionality: -0.028 SD, p = 0.077
- WASH: **-0.043 SD**, p = 0.016
- digital: -0.013 SD, p = 0.254
- accessibility: -0.007 SD, p = 0.691
- overall: **-0.033 SD**, p = 0.044

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

The negative point estimates do not reproduce in the 2022-23 cohort and are insufficient for a stable harm interpretation.

---

# Integrated interpretation

The four confirmatory tests rule out several simple explanations for the observed outcome pattern.

- A maintenance mechanism is not supported in the observed asset transitions.
- High-need schools do not show a replicating positive observed-outcome response, although their expenditure point estimates are larger.
- The maintenance null is not simply underpowered; large upgrade effects are also inconsistent with the data.
- Broad fixed-baseline indices do not reveal a hidden positive response concealed by noisy individual outcomes.

The resulting interpretation is:

> **At the 250-pupil CSG threshold, formula assignment is associated with higher reported CSG expenditure, while comprehensive discovery and confirmatory analyses do not identify a stable corresponding improvement in the school assets and administrative outcomes observed by UDISE. In particular, the data rule out a sizeable response operating through reduced deterioration of the observed asset set.**

This remains a local quasi-experimental result around the 250-pupil threshold and inherits the documented density and treatment-fuzziness caveats. It is not evidence that the entire CSG programme is ineffective, that funds are misused, or that unmeasured recurring and consumable benefits do not exist.

## Reproducibility

The prespecification, analysis code and workflow are stored in:

- `studies/composite_school_grant/confirmatory_experiments/README.md`
- `studies/composite_school_grant/confirmatory_experiments/run_confirmatory.py`
- `.github/workflows/csg-confirmatory-four-experiments.yml`

Workflow run: `31861984700`.
