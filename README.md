# UDISE+ Composite School Grant Study

An eight-year school-level study of India's Composite School Grant using UDISE+ microdata from 2018-19 through 2025-26.

This branch focuses on how a nationally prescribed enrolment-based school grant appears in administrative finance records: when the formula signal becomes visible, how closely recorded CSG receipt follows the formula-implied amount, how patterns differ across States, how often schools move across grant bands, and whether enrolment data show evidence consistent with threshold gaming.

The project is best understood as a public-finance implementation and administrative-measurement study, not as a simple impact evaluation of whether an extra ₹25,000 changes a binary school-facility outcome.

## Headline findings

- Around the primary 250/251 pupil boundary, the correctly aligned UDISE CSG receipt field shows a repeatable threshold-induced change of roughly **25 to 33 percentage points** across four usable cohorts in the probability of recording at least ₹75,000.
- The same formula fingerprint appears at the other clean CSG boundaries, especially **100/101, 250/251 and 1,000/1,001**.
- The administrative clock matters. Documentary evidence and the data support the mapping **enrolment vintage T -> grant financial year T+2 -> UDISE financial reporting at T+3** as the common national benchmark, while State timing remains heterogeneous.
- Recorded amounts do not mechanically reproduce the formula. At 250/251, the average recorded receipt discontinuity is roughly **₹9,500 to ₹14,400**, below the nominal ₹25,000 formula jump, while exact ₹75,000 recording rises much less.
- Among continuously eligible schools, national **N50 is T+3** at all three clean thresholds. **N80 is T+4 at 100/101 and 250/251, and T+5 at 1,000/1,001**. These are times to first recorded convergence in UDISE, not cash-transfer times.
- State administrative realization differs sharply. The strength, timing and durability of the CSG record vary substantially across States, and State patterns replicate strongly across independent thresholds.
- Around **90% of observed downward clean-threshold crossings with two years of follow-up cross back above the same threshold within two years**, showing that annual formula assignment can react strongly to temporary enrolment movement.
- Administrative enrolment data exhibit substantial heaping and non-smoothness at policy-relevant and round-number values, especially around 100. At 250/251 there is a smaller repeated irregularity, but placebo and longitudinal tests do **not** support a CSG-specific manipulation or fraud interpretation.
- UDISE CSG receipt and expenditure move very closely together. This is strong internal administrative consistency, not independent proof that a formula-to-record difference is an unpaid liability.
- The study finds no robust evidence that the 250/251 formula response systematically weakens as Muslim, SC, ST, OBC or General enrolment shares rise.
- Correctly timed facility analyses do not detect a large effect on the coarse UDISE asset-transition measures studied. This is a narrow measurement result, not evidence that CSG has no value.

## What the study does not claim

A difference between the formula-implied CSG amount and the later UDISE CSG receipt field is a **recorded administrative realization gap**. UDISE alone does not identify which part reflects approval, authorization, utilization, balances, carry-forward, timing or reporting. The study therefore does not classify every gap as an unpaid cash obligation.

Likewise, visible enrolment heaping is not treated as proof of strategic manipulation. The 250/251 density irregularity is modest relative to the broader structure of administrative enrolment data, and the stronger longitudinal placebo tests do not distinguish it as a CSG-specific gaming pattern.

## Start here

- [`HEADLINE_FINDINGS.md`](studies/composite_school_grant/HEADLINE_FINDINGS.md) - concise final findings
- [`FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md`](studies/composite_school_grant/FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md) - definitive full research summary
- [`ENROLMENT_INTEGRITY_AND_RESPONSE_TIME_FINDINGS.md`](studies/composite_school_grant/ENROLMENT_INTEGRITY_AND_RESPONSE_TIME_FINDINGS.md) - density, placebo, crossing and N50/N80 work
- [`FINAL_TIMING_AND_INCENTIVES_FINDINGS.md`](studies/composite_school_grant/FINAL_TIMING_AND_INCENTIVES_FINDINGS.md) - administrative clock, grant fidelity and incentive diagnostics
- [`THRESHOLD_SCHEME_REGISTRY.md`](studies/composite_school_grant/THRESHOLD_SCHEME_REGISTRY.md) - overlapping enrolment-linked rules and identification cautions
- [`studies/composite_school_grant/README.md`](studies/composite_school_grant/README.md) - technical study map and reproducibility guide

## Data architecture

Raw and school-level UDISE+ microdata are not committed to GitHub. The private Hugging Face dataset configured through `HF_DATASET_REPO` stores the original archives and large processed files. `HF_TOKEN` is provided to GitHub Actions through repository secrets.

GitHub contains the reproducible analysis code, workflow definitions, aggregate validation material, frozen policy-comparison inputs, figures and research documentation.

The CSG study uses eight UDISE+ academic rounds from **2018-19 through 2025-26**. The main broad State/UT-government sensitivity uses management codes 1, 2, 3, 6, 89 and 90, with narrower and broader universes retained as robustness checks.

## Repository structure

- `studies/composite_school_grant/` - main research programme
- `studies/composite_school_grant/scripts/` - core panel, RD and financial-channel analyses
- `studies/composite_school_grant/timing_*` - administrative timing reconstruction
- `studies/composite_school_grant/enrolment_integrity/` - density, heaping and placebo crossing tests
- `studies/composite_school_grant/state_response_time/` - State dynamic response and recognition-time analyses
- `studies/composite_school_grant/entitlement_dynamics/` - longitudinal formula-band and record dynamics
- `studies/composite_school_grant/policy_deepening/` - churn, cumulative record convergence, expenditure co-movement and policy simulations
- `studies/composite_school_grant/social_equity/` - social-composition heterogeneity analyses
- `studies/composite_school_grant/red_team/` - robustness and adversarial validity checks
- `studies/composite_school_grant/figures/` - reproducible R figure code and rendered outputs
- `.github/workflows/` - GitHub Actions workflows for the study modules

## Policy direction

The strongest directly supported policy question is whether annual CSG band assignment should react immediately to temporary enrolment crossings. The evidence motivates testing a more stable assignment rule, such as a persistence or hold-harmless design, against the current annual threshold system.

The large State differences are also an administrative diagnostic. DoSE&L and State systems can use the existing PRABANDH, PFMS/SNA and State records to investigate why the same national formula produces very different school-level CSG receipt patterns. A final, lower-priority transparency step would be to publish enough standardized school-year CSG information to make those differences externally auditable.
