# Causal Identification Audit

## Bottom line

The eight-year UDISE+ source is already large and longitudinal enough for serious causal/quasi-experimental research. The main limitation is not sample size. It is treatment assignment.

The dataset should be treated as a national school-level outcome panel to which defensible exogenous assignment mechanisms can be attached. School fixed effects, district fixed effects, lagged covariates, or millions of observations do not by themselves identify causal effects.

The existing Composite School Grant study already contains one defensible quasi-experimental causal claim: crossing a statutory CSG assignment threshold causes a large local change in later UDISE-recorded financial status, under the RD continuity assumptions and subject to the remaining coincident-policy caveat. It does not establish the causal effect of audited cash receipt on school outcomes.

## 1. What the source actually gives us

### Scale and continuity

The harmonized panel contains approximately 1.47-1.55 million schools in each academic year from 2018-19 through 2025-26. In the completed panel build, adjacent-year school-code match rates from the earlier year are:

- 2018-19 to 2019-20: 95.68%
- 2019-20 to 2020-21: 99.09%
- 2020-21 to 2021-22: 98.14%
- 2021-22 to 2022-23: 97.74%
- 2022-23 to 2023-24: 99.16%
- 2023-24 to 2024-25: 98.49%
- 2024-25 to 2025-26: 98.63%

This is unusually strong continuity for an administrative school panel.

### Repeated outcome families

The schema audit confirms repeated availability across the source period for the core analytical families needed for panel research, including:

- school identifier and state/district geography;
- school management, rural/urban status and class span;
- class-by-gender enrolment and social-category enrolment;
- teacher counts, employment type, qualification and training;
- classrooms, building condition and repair needs;
- toilets, water and WASH;
- electricity;
- internet;
- ICT devices and laboratories;
- libraries and learning resources;
- road accessibility;
- grant receipt/expenditure fields;
- inspections and administrative visits;
- SMC/SMDC governance fields;
- textbook/uniform support;
- special training and out-of-school-child related fields.

The exact schema changes substantially after 2021-22, so every proposed outcome must still be semantically harmonized rather than matched by column name alone.

Religion and several enrolment concepts are row-coded rather than directly named in later headers, so the automated header-keyword audit understates their availability. They have already been reconstructed in the existing social-equity work.

### Geographic limitation and opportunity

The early Profile 1 schema does not expose the later LGD block/village fields in the same form. From 2022-23 onward the source contains block, LGD village and LGD village-panchayat names. Earlier years contain state, district and panchayat-related location information but not the same later geography fields.

Because school pseudocodes are highly persistent, later stable location fields can potentially be back-propagated to the same school in earlier UDISE rounds after explicit validation. That can enable village/GP-level external-treatment linkage for longitudinal designs.

Latitude/longitude are not present in the audited UDISE headers.

## 2. Causal claims that are already supportable

### A. CSG statutory assignment -> later reported financial status

Status: **identified quasi-experimental reduced form, already executed**.

At the 250/251 threshold, the correctly timed UDISE probability of reporting receipt at least Rs 75,000 rises by approximately 25-33 percentage points across four independent assignment cohorts. The effect replicates across cohorts, management universes, specifications, and other CSG thresholds.

Defensible estimand:

> The local causal effect of crossing the statutory assignment threshold on later UDISE-recorded CSG financial status, conditional on the RD identifying assumptions.

Not established:

- causal effect of receiving exactly Rs 25,000 additional audited cash;
- causal effect of CSG on learning;
- proof that below-target records are actual funding denials.

The PM POSHAN coincident 250 rule has been materially reduced through Classes I-VIII restrictions but state-specific coincident rules remain a residual exclusion-restriction concern.

## 3. Causal design that is closest to being runnable entirely from UDISE plus law

### B. RTE teacher-entitlement thresholds -> actual teacher staffing

Status: **high-priority design-ready candidate**.

The RTE Act imposes enrolment-linked pupil-teacher norms. UDISE provides class enrolment and detailed teacher counts across all eight years. This creates potential local assignment discontinuities in statutory teacher entitlement.

Primary causal estimand:

> Does crossing an RTE enrolment threshold causally increase the number/type of teachers actually observed at the school?

Possible second stage, only if the first stage is strong and exclusion restrictions survive:

> What is the local effect of formula-induced teacher staffing on subsequent enrolment, PTR, class progression proxies or school conditions?

Required before causal language:

1. reconstruct the exact statutory running variable and entitlement in each relevant school category;
2. verify whether states operationalize staffing from contemporaneous or lagged enrolment;
3. audit density/manipulation at each threshold;
4. test predetermined continuity;
5. build a registry of other rules sharing the same thresholds;
6. use mass-point-aware RD inference.

This is likely the strongest next internally generated causal design because both the assignment variable and first-stage staffing outcome live in UDISE.

## 4. Designs for which UDISE is now outcome-ready but an external treatment file is required

### C. BharatNet staggered rollout -> school internet/digital capability

Status: **data-ready, treatment-timing not yet ready**.

The earlier pilot could not make a causal claim because it used one 2024-25 UDISE cross-section against a March 2022 service-ready snapshot. The source now contains eight school years and repeated internet/electricity/device/ICT measures.

A causal panel becomes feasible if a defensible GP-level BharatNet service-ready/commissioning date history can be assembled. Then use staggered event-study/DiD with school fixed effects, cohort-appropriate estimators, pre-trend diagnostics and never-treated/not-yet-treated comparisons.

Key outcomes:

- internet adoption;
- device and ICT-lab adoption;
- complete digital capability stack;
- trained-computer-teacher availability;
- possibly downstream enrolment outcomes.

Do not use the 2022 snapshot itself as causal treatment timing.

### D. EMRS 2018 expansion eligibility -> tribal secondary/residential schooling access

Status: **strong external-rule candidate**.

The Ministry of Tribal Affairs states that the expansion policy targeted blocks/sub-districts with more than 50% ST population and at least 20,000 tribal persons, using Census 2011 figures, for EMRS coverage. The UDISE panel begins in 2018-19 and runs through 2025-26.

Potential design:

- fuzzy RD around predetermined Census 2011 eligibility thresholds, possibly combined with actual school-opening dates;
- block/sub-district outcomes assembled from school-level UDISE.

Potential outcomes:

- presence/capacity of residential Class VI-XII schooling;
- ST secondary and higher-secondary enrolment;
- girls' enrolment;
- class-span access;
- local school infrastructure/teacher resources.

Main work required: Census 2011 eligibility variables, sub-district crosswalk, official EMRS opening/sanction list, and proof that competing tribal programmes do not create the same discontinuities.

### E. PMGSY / road-connectivity treatment -> school access and enrolment

Status: **potentially strong, external data required**.

UDISE repeatedly measures school road accessibility and enrolment. If schools can be linked to village/GP geography and PMGSY treatment/eligibility records, population-threshold or rollout-timing designs could estimate effects of rural road connectivity on school access and enrolment outcomes. This is identification-rich but requires village-level linkage and must be positioned against the substantial existing PMGSY causal literature.

### F. Jal Jeevan / school-water rollout -> functional school WASH

Status: **possible panel event study, assignment quality must be audited**.

Repeated UDISE water-source functionality, toilets and handwashing outcomes make the data well suited as outcomes. A causal claim requires independently dated village/school treatment and a defensible source of variation; rollout timing alone may be selected.

### G. Exogenous climate/disaster shocks -> school enrolment and physical condition

Status: **causal panel feasible with external shock data**.

District/village-year rainfall, flood, cyclone, heat or other plausibly exogenous physical shocks can be merged to the UDISE panel. School/district fixed effects and event-study specifications can estimate impacts on enrolment, infrastructure repair needs, road access and other school conditions, subject to spatial measurement and migration/attrition checks.

This route does not require a government treatment programme, only a defensible exogenous shock measure.

### H. State-specific school consolidation/closure rules

Status: **potentially strong but policy-registry intensive**.

If a state applies deterministic low-enrolment or distance rules for closure/merger, UDISE can track school disappearance, class-span change, survivor-school enrolment and resource changes. Causality depends on locating exact rules, dates and thresholds and distinguishing genuine closure/merger from code changes.

## 5. Questions that the current data do not make causal by themselves

The following remain descriptive/associational unless instrumented or attached to exogenous assignment:

- effect of Muslim/SC/ST/OBC composition on school funding or facilities;
- effect of school management type on outcomes;
- effect of rurality on outcomes;
- effect of having internet on enrolment;
- effect of teacher count on enrolment;
- effect of inspections or SMC meetings on facilities;
- state speed/strength of CSG implementation as a cause of school outcomes;
- stable-entitlement reliability and chronic below-target reporting;
- receipt-to-expenditure correlations;
- differences between high- and low-fidelity schools.

School fixed effects improve within-school comparisons but do not solve time-varying confounding or reverse causality.

## 6. CSG extension decision

The proposed stable-entitlement, entitlement-to-receipt funnel, chronic mismatch, speed-strength, district variance and data-quality studies are useful if the goal is to deepen the administrative public-finance paper. They are not prerequisites for causal inference.

Recommended minimum CSG extensions:

1. state latency x strength/fidelity typology;
2. one stable-entitlement reliability analysis;
3. one decomposition of persistent versus temporary recorded mismatch.

Stop there unless these produce a qualitatively new finding. The manipulation arm is closed except as a robustness section.

## 7. Recommended causal research sequence

### Priority 1: RTE teacher entitlement RD

Why: almost all required treatment assignment and outcomes are already inside UDISE; it can generate an independent causal paper/design without first building a massive external geospatial data system.

### Priority 2: BharatNet longitudinal event study

Why: the eight-year panel now fixes the single-cross-section weakness of the pilot. The gating item is treatment timing, not UDISE outcomes.

### Priority 3: EMRS eligibility fuzzy RD

Why: unusually sharp predetermined Census eligibility and a policy expansion beginning at the start of the panel; strong substantive fit for distributional/tribal educational access research.

### Priority 4: one external physical-infrastructure/shock design

PMGSY, water rollout, or climate shocks depending data acquisition and novelty.

## 8. Overall verdict

**Yes, there is enough UDISE data to make causal claims. There is not enough information in UDISE alone to make every interesting relationship causal.**

The correct strategy is no longer to mine the panel for associations. It is to use the panel as a national outcome measurement system and attach a small number of high-quality assignment mechanisms.

A causal portfolio can therefore be built around:

1. formula-based funding assignment;
2. statutory staffing assignment;
3. staggered digital infrastructure rollout;
4. predetermined geographic eligibility rules;
5. exogenous physical shocks.

Each design should be pre-specified after its assignment rule is verified, with placebo outcomes/cutoffs, density or pre-trend tests, attrition checks, and explicit separation of reduced-form assignment effects from treatment-on-the-treated claims.
