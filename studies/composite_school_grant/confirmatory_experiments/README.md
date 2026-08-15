# Confirmatory CSG Experiments

This folder contains the four prespecified confirmatory experiments run after the broad discovery screen.

## Scope

Headline identification uses the 250-pupil Composite School Grant threshold, a ±30 pupil bandwidth, a one-pupil donut, assignment-state fixed effects, and state-clustered uncertainty. The two clean post-pandemic assignment cohorts are analysed independently:

- 2021-22 assignment, followed through 2023-24, 2024-25 and 2025-26
- 2022-23 assignment, followed through 2024-25 and 2025-26

Only government-management codes 1, 2 and 3 are included in the causal sample.

## Experiment 1. Maintenance versus upgrade

The first-stage question is whether the marginal grant primarily prevents existing assets from deteriorating rather than generating visible upgrades.

For each baseline-observed binary asset, two transition outcomes are constructed:

- `deteriorated`: asset was good/functional at baseline and is bad/non-functional later
- `upgraded`: asset was bad/non-functional at baseline and is good/functional later

The asset family includes, where observed in both vintages:

- functional drinking water
- handwashing facility for meals
- electricity
- internet
- library
- availability of ramps
- availability of handrails
- fully functional girls' toilets
- fully functional boys' toilets

School-level composite deterioration and upgrade rates are also constructed across all eligible baseline assets. Missing later values are not coded as failure.

## Experiment 2. Baseline-need heterogeneity

A pre-treatment infrastructure-deficit score is defined as one minus the mean of the baseline good/functional asset indicators above, requiring at least five observed components. Need strata are determined from the pooled local ±75-pupil baseline sample for each cohort using the 33rd and 67th percentiles of the deficit score:

- low need
- middle need
- high need

The RD first stage, cumulative expenditure difference, maintenance/upgrade composites and dynamic outcome indices are re-estimated separately within each stratum. The strata depend only on pre-treatment information.

## Experiment 3. Power and equivalence

For every headline transition composite and standardized dynamic index estimate, the analysis reports:

- 95% confidence interval
- 80% power minimum detectable effect, approximated as 2.80 × SE
- the smallest symmetric equivalence margin containing the 95% CI
- two-one-sided-test (TOST) equivalence p-values at prespecified margins

For proportion-type outcomes, margins of 0.02 and 0.05 are tested. For standardized indices, margins of 0.05 and 0.10 standard deviations are tested.

A null coefficient is not described as evidence of equivalence unless the corresponding TOST rejects effects outside the stated margin.

## Experiment 4. Dynamic outcome indices

Indices use only baseline means and standard deviations for standardization. The same baseline scaling is applied to later rounds.

The index families are:

- `core_functionality`: functional water, handwashing, electricity, fully functional girls' toilets, fully functional boys' toilets, and classroom good-condition share where available
- `wash`: functional water, handwashing, fully functional girls' toilets and fully functional boys' toilets
- `digital`: internet, device presence and ICT/computer-lab availability where available
- `accessibility`: ramps, handrails, functional CWSN-friendly boys' toilets and functional CWSN-friendly girls' toilets where available
- `overall`: union of all available index components

Each index requires at least half of its candidate components to be observed. The primary outcome is change from the school's own baseline index to each later round.

## Guardrails

These are confirmatory analyses. No alternative threshold, arbitrary outcome search, or unreported recoding will be selected because it produces a smaller p-value. Individual asset transition estimates are adjusted using Benjamini-Hochberg false-discovery correction within the maintenance and upgrade families. Composite/index outcomes are the primary tests.
