# Composite School Grant Study

This folder contains the full longitudinal research programme on India's Composite School Grant using UDISE+ school-level microdata from 2018-19 through 2025-26.

The study asks how a simple enrolment-based national formula is translated into school-level administrative finance records, how long that signal takes to appear, how closely recorded CSG receipt follows the formula-implied amount, how implementation differs across States, and how unstable annual threshold assignment is when enrolment moves around grant cutoffs.

The final project is a **public-finance implementation and administrative-measurement study**. The earlier framing as a simple impact paper on school facilities is superseded.

## Main research questions

1. Does the CSG formula leave a measurable school-level financial fingerprint in UDISE?
2. What enrolment-to-allocation-to-reporting clock correctly aligns the formula with the UDISE financial fields?
3. How closely does the recorded CSG amount reproduce the formula-implied annual amount?
4. How much do timing, strength and durability of the recorded formula response differ across States and UTs?
5. How often do schools move across CSG bands, and how often are downward crossings temporary?
6. Do enrolment densities around CSG thresholds show evidence consistent with CSG-specific manipulation?
7. Does formula transmission systematically vary with school social composition?
8. What do the available UDISE expenditure and facility measures add, and what can they not identify?

## CSG thresholds

The clean headline analyses use the stable boundaries:

| Enrolment | Formula-implied annual amount |
|---|---:|
| 31 to 100 | ₹25,000 |
| 101 to 250 | ₹50,000 |
| 251 to 1,000 | ₹75,000 |
| Above 1,000 | ₹100,000 |

The main quasi-experimental design uses the **250/251** boundary because it combines a clear ₹25,000 formula change with stronger identification than the other cutoffs. The 100/101 and 1,000/1,001 boundaries are important independent formula replications. The 30/31 boundary is retained for diagnostics but is not used as a clean headline comparison because the small-school schedule changed historically.

## Administrative clock

Documentary evidence shows that CSG allocation can use lagged UDISE enrolment, while UDISE financial fields report grants for the previous financial year. The common national alignment used in the main analysis is therefore:

**enrolment vintage T -> CSG grant financial year T+2 -> UDISE financial reporting at T+3**

The four clean assignment/reporting cohorts are:

| Assignment enrolment | Grant financial year | UDISE financial-report field |
|---|---|---|
| 2019-20 | 2021-22 | 2022-23 |
| 2020-21 | 2022-23 | 2023-24 |
| 2021-22 | 2023-24 | 2024-25 |
| 2022-23 | 2024-25 | 2025-26 |

The observed threshold response is consistent with this documentary timing. Across 92 State-cohort timing cells, +3 is the largest positive 250/251 response in 65 cells. The remaining 27 cells are an important reminder that State timing is heterogeneous. The result does **not** mean that cash literally takes three years to reach a school.

## Headline empirical results

### Formula fingerprint

At 250/251, the correctly aligned probability of recording CSG receipt of at least ₹75,000 rises by approximately:

- **+24.7 pp** for the 2019-20 assignment cohort
- **+31.8 pp** for 2020-21
- **+33.2 pp** for 2021-22
- **+32.5 pp** for 2022-23

The result is essentially unchanged when the government-school management universe is broadened. Similar threshold fingerprints appear at 100/101 and 1,000/1,001.

### Recorded amount fidelity

The formula moves the financial distribution strongly but UDISE does not behave as a deterministic formula ledger. Around 250/251, the average recorded receipt discontinuity is approximately **₹9,500 to ₹14,400**, while the nominal formula jump is ₹25,000. Exact recording of ₹75,000 rises by only about **2 to 7 percentage points** across cohorts.

These are CSG-specific receipt fields, not aggregate school-grant totals. A difference between the formula-implied amount and the recorded CSG receipt is therefore a genuine administrative realization gap in the record. UDISE alone, however, cannot identify how much of a particular gap arises from approval, authorization, utilization, balances, carry-forward, timing or reporting. It should not automatically be labelled an unpaid cash obligation.

### Time to recorded convergence

Among continuously eligible schools, national time-to-first-recorded-convergence measures are:

| Threshold | N50 | N80 |
|---|---:|---:|
| 100/101 | T+3 | T+4 |
| 250/251 | T+3 | T+4 |
| 1,000/1,001 | T+3 | T+5 |

`N50` and `N80` are the first observed cycles by which 50% or 80% of continuously eligible schools have ever recorded at least the formula-implied amount. They are **administrative record-latency measures, not cash-payment times**.

State N50/N80 values vary sharply, and latency and strength are separate dimensions. Some States show an earlier but weaker recorded response, while others are slower but eventually stronger.

### Enrolment churn

At the clean 100, 250 and 1,000 boundaries, approximately **89.8% to 91.4%** of observed downward crossings with two years of follow-up cross back above the same threshold within two years.

Across the full historical panel, 42.5% of schools change CSG band at least once, 20.6% change at least twice, and 11.3% show a short A-B-A reversal. Because the full-panel figures include the historically changing small-school boundary, the clean-threshold reversal rates are the preferred policy evidence.

### Enrolment integrity

Administrative enrolment data are not smooth. Strong heaping and concentration appear at policy-relevant and round-number values, especially around 100. At 250/251 there is a smaller repeated excess immediately above the threshold, particularly in earlier years.

However, the stronger tests do not support a CSG-specific manipulation interpretation. Schools beginning just below 250 do not disproportionately land exactly at 251 relative to placebo thresholds at 200/201 and 300/301, and subsequent reversion is similarly high around the placebo cutoffs. The evidence therefore does **not** establish systematic gaming, fabricated pupils or fraud induced by CSG.

### State heterogeneity

The same national formula produces very different CSG receipt patterns across States. The strength, timing and durability of the recorded response vary substantially, and State patterns reproduce strongly across independent CSG thresholds.

The safe conclusion is that **persistent State-level administrative realization patterns reproduce across the national formula boundaries**. The study does not identify every underlying mechanism, but the variation is too large and too systematic to treat as a one-cutoff artefact.

### Expenditure and facilities

UDISE CSG receipt and expenditure move exceptionally closely together. Within State, formula band and aligned cycle, supported recorded downward-transition cells show lower expenditure movement, while recorded upward-transition cells show higher expenditure movement with near-perfect sign consistency.

This is **internal administrative consistency, not independent validation of cash delivery**. Receipt and expenditure are fields in the same administrative reporting architecture and may be mechanically linked under utilization and drawing arrangements.

Correctly timed facility analyses do not detect a large effect on the coarse UDISE asset-transition measures studied. Many legitimate CSG uses are flow expenditures that are not well represented by binary or slowly moving infrastructure indicators, so these nulls are not a verdict on the value of CSG.

## Social-composition extension

The preferred correctly timed interaction designs find no robust evidence that the 250/251 recorded-finance threshold response systematically weakens as Muslim, SC, ST, OBC or General enrolment shares rise. No main univariate group survives multiple-testing correction, and the pooled religion and social-category joint tests do not support a national CSG-specific disparity claim.

These analyses are secondary to the main implementation study and should not be used to construct unsupported residual categories that mix religion and social-category classifications.

## Policy interpretation

The strongest directly supported policy question is formula stability. Annual threshold assignment can translate temporary enrolment changes into discrete ₹25,000 changes in the formula-implied annual amount even though many downward crossings reverse quickly. This motivates a pilot comparing the status quo with a persistence or downward hold-harmless rule, rather than assuming that a two-year average is already optimal.

The large State differences are an administrative diagnostic. DoSE&L and State systems can use **existing** PRABANDH, PFMS/SNA and State records to investigate why the same national formula produces very different school-level CSG receipt patterns. The study does not claim that government lacks these internal records.

A lower-priority transparency recommendation is to publish enough standardized school-year CSG information to make formula-to-record differences externally auditable using the existing UDISE school code, financial year and CSG component.

## Study navigation

Start with these files:

- [`HEADLINE_FINDINGS.md`](HEADLINE_FINDINGS.md) - concise summary of the final research programme
- [`FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md`](FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md) - definitive full results and interpretation
- [`ENROLMENT_INTEGRITY_AND_RESPONSE_TIME_FINDINGS.md`](ENROLMENT_INTEGRITY_AND_RESPONSE_TIME_FINDINGS.md) - national density, placebo crossing, State timing and recognition-time analyses
- [`FINAL_TIMING_AND_INCENTIVES_FINDINGS.md`](FINAL_TIMING_AND_INCENTIVES_FINDINGS.md) - corrected administrative clock, fidelity and incentive findings
- [`THRESHOLD_SCHEME_REGISTRY.md`](THRESHOLD_SCHEME_REGISTRY.md) - overlapping enrolment-linked policies and cutoff interpretation
- [`docs/STUDY_DESIGN.md`](docs/STUDY_DESIGN.md) - design documentation
- [`red_team/RED_TEAM_REPORT.md`](red_team/RED_TEAM_REPORT.md) - adversarial robustness audit
- [`social_equity/COMPLETED_DIAGNOSTICS_AND_EXECUTION_STATUS.md`](social_equity/COMPLETED_DIAGNOSTICS_AND_EXECUTION_STATUS.md) - social-equity diagnostics and execution status

## Code map

- `scripts/` - core panel construction, assignment diagnostics and RD analyses
- `timing_core/`, `timing_matrix/`, `timing_incentives/` - documentary and empirical timing reconstruction
- `grant_fidelity/` and `multi_threshold/` - exact-amount and cross-threshold formula tests
- `enrolment_integrity/` - density, heaping and placebo crossing analyses
- `state_lag/` and `state_response_time/` - State timing and recorded-recognition analyses
- `crossing_dynamics/` and `entitlement_dynamics/` - longitudinal school paths and formula-band spells
- `policy_deepening/` - churn, cumulative record convergence, expenditure co-movement and counterfactual stability rules
- `government_universe/` - management-universe sensitivity
- `red_team/` - robustness, confound and validity checks
- `social_equity/` - composition heterogeneity and absolute-level diagnostics
- `figures/` - R source for study visuals and rendered figures

## Data and reproducibility

Raw and school-level UDISE+ microdata are stored outside GitHub in the private Hugging Face dataset configured by `HF_DATASET_REPO`. `HF_TOKEN` is supplied through GitHub Actions secrets. GitHub stores reproducible code, workflow definitions, aggregate outputs, frozen policy-comparison inputs, documentation and figures.

The main study universe is State/UT-government schools, with narrower and broader management definitions retained for sensitivity. Missing financial records are not silently recoded as zero in longitudinal analyses.

## Claim boundary

The final study supports a strong statement about **formula transmission, administrative timing, recorded fiscal fidelity, State heterogeneity and threshold churn**.

It does not establish that every formula-to-record difference is unpaid cash, that visible enrolment heaping proves manipulation, or that a null result on coarse facility variables means the grant has no benefit.
