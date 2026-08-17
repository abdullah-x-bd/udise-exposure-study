# Confirmatory CSG Outcome Experiments

This folder contains the earlier prespecified outcome experiments that followed the initial discovery screen.

These analyses are retained for reproducibility, but they are **not the headline study design anymore**. The final research programme reconstructed the CSG administrative clock and showed that the main school-finance response appears later than the original outcome work assumed. The definitive interpretation is therefore in:

- [`../FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md`](../FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md)
- [`../FINAL_TIMING_AND_INCENTIVES_FINDINGS.md`](../FINAL_TIMING_AND_INCENTIVES_FINDINGS.md)
- [`../HEADLINE_FINDINGS.md`](../HEADLINE_FINDINGS.md)

## Why this module is now secondary

The original confirmatory programme asked whether crossing the 250/251 CSG boundary produced detectable changes in school maintenance, upgrades and standardized facility indices.

Subsequent documentary and empirical work established the common alignment:

**enrolment vintage T -> grant financial year T+2 -> UDISE financial reporting at T+3**

The earlier outcome framing was therefore too close to the enrolment assignment year in several places. The final project treats these experiments as a mechanism screen rather than as the main causal contribution.

A second limitation is measurement. Many legitimate CSG uses are flow expenditures such as minor repairs, consumables, electricity, internet, teaching materials, activities and maintenance. These need not move coarse binary UDISE facility indicators over a short horizon.

The correct conclusion from this module is narrow: **the retimed analyses do not detect a large effect on the coarse UDISE asset-transition measures studied**. They do not establish that CSG has no benefit or that an additional ₹25,000 has no effect on school operations.

## Original experiment structure

### 1. Maintenance versus upgrade

For baseline-observed school assets, the analysis constructs:

- `deteriorated`: an asset is observed in good or functional condition at baseline and bad or non-functional later
- `upgraded`: an asset is bad or non-functional at baseline and good or functional later

The asset family includes drinking water, handwashing, electricity, internet, library, ramps, handrails, boys' and girls' toilet functionality, and related school-condition measures where consistently observed.

School-level composite deterioration and upgrade rates are built only from observed components. Missing later values are not coded as failure.

### 2. Baseline-need heterogeneity

A pre-treatment infrastructure-deficit score is constructed from baseline school conditions. Schools are split into low-, middle- and high-need groups using pre-treatment information only.

The purpose is to test whether any observed grant-related response is concentrated among schools with greater baseline infrastructure need.

### 3. Power and equivalence

For headline transition composites and standardized indices, the analysis reports conventional uncertainty together with minimum detectable effects and equivalence diagnostics.

A statistically non-significant coefficient is not automatically described as evidence of equivalence.

### 4. Dynamic outcome indices

Standardized indices cover broad domains such as:

- core functionality
- WASH
- digital infrastructure
- accessibility
- overall observed school conditions

Baseline means and standard deviations are used for scaling. The same scaling is applied to later rounds.

## Retimed interpretation

Once the corrected administrative clock is used, the relevant post-grant facility rounds are later than in the original version of this module. The retimed reduced-form deterioration estimates remain small and statistically unestablished, and standardized facility indices do not show a robust large effect.

This is useful evidence about **what UDISE can and cannot detect**. It is not the central policy result of the project.

The stronger contribution of the full study is that the CSG formula leaves a large, delayed and reproducible fingerprint in the CSG-specific school finance records, while recorded amount fidelity, timing and State realization vary substantially.

## Relationship to the main 250/251 design

The 250/251 boundary remains the primary identification threshold because it provides a clear ₹25,000 formula change and cleaner interpretation than the other CSG cutoffs.

However, the main outcome is now the correctly aligned **CSG-specific recorded finance response**, not the facility indices in this folder. The 100/101 and 1,000/1,001 thresholds provide additional formula-fingerprint replication, while 30/31 is historically qualified.

## Guardrails

- Do not use this folder to claim that "CSG does not work."
- Do not describe the nominal ₹25,000 formula difference as an exact observed treatment amount for every school.
- Do not interpret a null facility coefficient as evidence that school operating expenditure has no value.
- Do not use the older timing assumptions when summarizing the final study.
- Use the final results documents above whenever this README conflicts with an earlier output or interpretation.

## Reproducibility

`run_confirmatory.py` preserves the original experiment code and associated diagnostics. `CONFIRMATORY_RESULTS.md` records the results from this module. They should be read as part of the study's development history and mechanism testing, not as a replacement for the corrected final research programme.
