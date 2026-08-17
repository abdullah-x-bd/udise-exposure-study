# Composite School Grant Robustness Audit

## Scope and conclusion

This audit stress-tests the original causal interpretation of the Composite School Grant threshold design. The checks preserve a strong local policy-threshold result while narrowing claims about the causal effect of an exact additional Rs 25,000 received by a school.

The robust core is:

> Around the 250/251 Composite School Grant formula threshold, schools are substantially more likely to report CSG receipt and expenditure in the higher grant range. The financial threshold response survives outlier-resistant estimation, mass-point-aware RD inference, alternative bandwidths, State-clustered inference, management-universe checks and PM POSHAN-safe subsamples. The available UDISE facility and personnel outcomes do not show a large replicating improvement, but those outcomes do not measure many legitimate CSG uses.

The audit therefore supports an implementation and administrative-measurement interpretation. It does not identify a clean local average treatment effect of exactly Rs 25,000 in cash received.

---

## 1. Financial outliers

### Threat

The UDISE CSG financial fields have extreme upper tails. Some school records contain reported grant receipts or expenditure in the tens or hundreds of millions of rupees, making raw means vulnerable to a small number of implausible or unusual observations.

Examples include:

- 2022-23 assignment cohort, first observed receipt maximum about Rs 75.8 million;
- first observed expenditure maximum about Rs 23.9 million;
- cumulative expenditure maximum above Rs 100 million;
- cumulative receipt maximum above Rs 600 million.

### Checks

The first stage and cumulative finance outcomes were re-estimated using:

- trimming at the 99th, 99.5th and 99.9th percentiles;
- winsorisation at the same cut points;
- inverse-hyperbolic-sine transformations;
- indicators for positive receipt/expenditure;
- indicators for reported receipt/expenditure at or above Rs 75,000.

### Result

The financial threshold response survives strongly. Outlier-resistant first-year receipt and expenditure estimates remain positive, while threshold-band probabilities show a clear shift toward the higher CSG range.

The existence of the financial discontinuity is robust; the earliest raw-mean rupee magnitudes are not treated as preferred headline estimates.

---

## 2. Discrete running variable and RD inference

### Threat

School enrolment is an integer running variable with mass points. Conventional continuous-RD standard errors and bandwidth choices can therefore be overconfident.

### Checks

The core finance results were re-estimated using `rdrobust` with:

- mass-point adjustment;
- local linear point estimation and local quadratic bias correction;
- robust bias-corrected inference;
- CR3 cluster-robust variance by assignment-year State;
- State dummy covariates;
- automatic MSE bandwidths;
- fixed +/-20, +/-30 and +/-40 bandwidths;
- the same conservative donut around the cutoff.

### Result

The main financial threshold response remains positive across the mass-point-aware and alternative-bandwidth specifications. The central direction is therefore not an artefact of treating enrolment as a continuously distributed running variable.

---

## 3. Fuzzy treatment rather than a deterministic Rs 25,000 jump

The formula changes discontinuously at 250/251, but the UDISE receipt field does not jump deterministically by Rs 25,000 for every school. Formula assignment is therefore a fuzzy administrative treatment rather than a sharp switch in observed cash receipt.

The reduced-form RD coefficients identify the effect of crossing the policy threshold on the administrative outcomes. They are not direct estimates of the causal effect of exactly Rs 25,000 of additional cash received.

This distinction is particularly important for the facility-equivalence tests. A tightly estimated near-zero reduced-form outcome does not automatically imply an equally small treatment-on-the-treated effect among schools whose actual resources changed because of the threshold.

---

## 4. PM POSHAN overlap at 250

PM POSHAN has an enrolment-linked kitchen-device assistance schedule with a breakpoint at 250 pupils for its covered grades. This creates a real exclusion-restriction concern for an unrestricted 250-pupil RD.

CSG assignment uses total school enrolment, while PM POSHAN covers Bal Vatika and Classes I-VIII. The design was therefore repeated among schools whose total Classes I-XII enrolment is near 250 but whose Classes I-VIII enrolment is safely below the PM POSHAN breakpoint.

Restrictions at Classes I-VIII <=220 and <=200 preserve a positive CSG-like financial response in both clean cohorts. The PM POSHAN overlap is therefore a genuine confound to disclose, but it does not explain away the main financial threshold result.

---

## 5. Sorting and enrolment manipulation

The enrolment density is not perfectly smooth around 250. Earlier diagnostics show a positive local density irregularity, although it is much smaller than the severe structure around 100.

A dedicated longitudinal integrity analysis subsequently compared exact landing, minimum-crossing and reversion behaviour at 250/251 with placebo thresholds at 200/201 and 300/301. The differences are small and do not support a distinctive CSG-specific manipulation pattern.

The 250/251 design is therefore treated as quasi-experimental rather than as a pristine textbook RD. The density evidence is reported openly and is not used as proof of fraud or strategic enrolment inflation.

---

## 6. Baseline balance, attrition and school identifiers

A longitudinal RD can be biased if schools just above and below the cutoff differ before treatment, disappear at different rates or are linked inconsistently over time.

The validity audit tested:

- predetermined facility variables;
- teacher and staffing variables;
- class span and school characteristics;
- later presence across Profile 1, Profile 2, Facility, Teacher, Enrolment 1 and Enrolment 2 files;
- stability of school type, low/high class, rural/urban status, block and district identifiers;
- leave-one-State-out sensitivity;
- broad specification grids.

No attrition or predetermined-balance family survives FDR correction in the clean cohorts. School type, class span and rural/urban fields are highly stable. Block identity is also highly stable and does not show a meaningful threshold discontinuity.

District-name stability deteriorates in later years, plausibly because of administrative or coding changes, but not discontinuously at 250. Direct State-name stability is not used because State representation changed across vintages.

The observable evidence does not indicate that differential attrition or ordinary identifier instability drives the result.

---

## 7. Specification sensitivity

The robustness grid varies:

- bandwidths from +/-15 to +/-75;
- donuts 0-3;
- triangular versus uniform kernels;
- local linear versus local quadratic forms.

The main financial direction is stable across the grid and survives the later outlier-resistant `rdrobust` audit. The facility-deterioration composite does not reveal a stable positive maintenance response across corresponding specifications.

Preferred reporting therefore emphasizes mass-point-aware, outlier-resistant specifications rather than raw mean grids.

---

## 8. Placebo cutoffs

One early placebo at 150 pupils is invalid as a policy-null comparison because PM POSHAN has enrolment-linked rules around that region. It is excluded from the final placebo interpretation.

Placebo thresholds without known national policy breaks do not generate a comparable stable financial response in the clean audit.

---

## 9. Outcome coverage

The first broad outcome screen covered the numeric Facility/Profile universe and the 2025-26 Safety data but did not initially include all teacher and class-enrolment outcomes. Some categorical variables also cannot be interpreted by treating raw codes as continuous quantities.

The later audit added:

- teacher counts and composition;
- trained-computer teachers;
- contract/regular teacher variables;
- pupil-teacher ratio;
- class-specific enrolment changes;
- codebook-aware furniture transitions.

In the 2021-22 cohort, 69 teacher/staffing/class-enrolment outcomes produce zero within-family FDR hits. In the 2022-23 cohort, three within-family FDR hits appear, including lower PTR, but the staffing pattern does not replicate in the independent cohort.

The supported statement is therefore that no positive mechanism replicates across the broad set of usable UDISE physical, WASH, digital, accessibility, safety, furniture, teacher, staffing and class-enrolment outcomes tested.

Important outcomes remain unavailable or inadequately measured, including direct learning achievement for the same schools, detailed attendance intensity, service quality and uptime, repair events, quantities and quality of consumables, and transaction-level CSG expenditure purposes.

---

## 10. Furniture and other asset channels

Furniture was explicitly recoded because its raw categorical code is not a suitable continuous outcome.

The 2022-23 cohort shows no significant improvement in full furniture coverage or upgrades. One small 2021-22 subgroup/horizon furniture-upgrade coefficient is nominally significant but is absent at other horizons and does not replicate.

Furniture is therefore not supported as a stable observed spending channel.

---

## 11. Precision of the maintenance result

At the reduced-form threshold level, the deterioration composite is estimated precisely enough to rule out a large response in the observed asset-transition measure. No replicating reduction in deterioration appears.

Because financial compliance is fuzzy, this precision does not imply an equally tight equivalence bound for the effect of actual additional CSG receipt among compliers.

The result is therefore interpreted as ruling out a large policy-threshold maintenance response in the observed composite rather than a zero effect of actual CSG resources on all forms of maintenance.

---

## 12. Baseline need heterogeneity

High-need schools have larger cumulative-expenditure point estimates than low-need schools in both clean cohorts, but formal heterogeneity is too noisy to establish a stable differential effect. No corresponding positive outcome response replicates in the high-need group.

This is retained as a secondary targeting and implementation result rather than evidence that need-targeted CSG succeeds or fails.

---

## 13. Broad standardized outcomes

Fixed-baseline standardized indices for core functionality, WASH, digital, accessibility and overall school condition do not reveal a stable positive response across cohorts and horizons.

Some positive and negative coefficients appear in individual cohort-horizon cells, but they do not reproduce independently.

---

## 14. Other threshold-linked school rules

CSG is not the only scheme using enrolment-linked thresholds.

### PM POSHAN

PM POSHAN kitchen-device assistance uses an enrolment schedule that includes a breakpoint around 250, making it the most important co-threshold national policy for the CSG design. PM POSHAN also has other enrolment-linked operational rules around 100 and subsequent blocks.

### Samagra Shiksha ICT

Government and aided schools with enrolment above 700 may be considered for an additional ICT lab. This is a possible future positive-control design, but eligibility is discretionary and the available panel does not yet provide a clean post-treatment UDISE round for the newest approvals.

### Other Samagra grants

Library grants, sports grants, Youth/Eco Club support, uniforms, textbooks and CwSN support do not use the same total-enrolment cliff structure as the main CSG rule.

---

## 15. Where the additional recorded expenditure goes

The public all-India microdata used here contain CSG receipt and expenditure fields but do not expose the richer line-item accounting needed to identify whether marginal recorded expenditure went to cleaning, utilities, repairs, teaching materials, furniture or another purpose.

Plausible explanations consistent with the evidence include:

1. recurring and consumable inputs that do not change UDISE stock variables;
2. cleaning and sanitation supplies;
3. utilities, connectivity charges, water and other recurring services;
4. small repairs and replacements that preserve service without creating new stock;
5. teaching-learning materials and purchases not represented well in UDISE;
6. timing, accounting and reporting lags;
7. substitution across funding sources;
8. measurement and reporting error.

The study provides no evidence that CSG funds are stolen, diverted or illegally used.

Teacher hiring is not supported as a replicating mechanism. The one cohort with lower pupil-teacher ratios does not show a replicating teacher-count response in the independent cohort.

---

## 16. Implications of the robustness audit

The robustness results do not support cutting or abolishing CSG. They support three narrower directions.

### A. Formula design and stability

The main longitudinal project shows that many downward threshold crossings are temporary. This makes the hard annual cliff itself a policy-design object worth testing against smoother alternatives, including a two-year average or an asymmetric downward persistence rule.

### B. Administrative investigation of State heterogeneity

The same national formula produces sharply different CSG-specific receipt patterns across State systems. Existing PRABANDH, PFMS/SNA and State administrative records can be used to investigate where those differences arise without assuming that UDISE alone identifies the underlying mechanism.

### C. External auditability

A standardized public extract linking the existing UDISE school code and financial year to the formula-implied amount, approved amount and selected reconciliation metadata would make independent evaluation easier. This is a transparency recommendation rather than an assertion that government lacks internal records.

Extreme UDISE grant values also justify stronger plausibility checks and cross-validation before publication.

---

## 17. Publication-grade claim boundary

The robustness audit supports the following interpretation:

> **Among government schools near the 250/251 Composite School Grant formula threshold, crossing the threshold produces a robust shift toward higher reported CSG receipt and expenditure. The financial result survives mass-point-aware RD inference, alternative bandwidths, State-clustered inference, management-universe checks and samples constructed to reduce PM POSHAN's coincident 250-pupil rule. Across a broad set of UDISE-observed school conditions, personnel and enrolment outcomes, no large positive mechanism replicates across the clean cohorts. These are effects of formula assignment on administrative records, not direct estimates of the causal return to exactly Rs 25,000 of additional cash received.**

---

## Reproducibility

Main robustness code and workflows are stored under:

- `studies/composite_school_grant/red_team/run_validity_audit.py`
- `studies/composite_school_grant/red_team/run_validity_audit_fixed.py`
- `studies/composite_school_grant/red_team/run_finance_outlier_audit.py`
- `studies/composite_school_grant/red_team/run_rdrobust_audit.py`
- `studies/composite_school_grant/red_team/run_teacher_enrolment_screen.py`
- `studies/composite_school_grant/red_team/run_furniture_recode.py`
- `studies/composite_school_grant/red_team/run_pmposhan_isolation.py`
- `studies/composite_school_grant/red_team/run_management_selection.py`

Associated GitHub Actions workflows are under `.github/workflows/csg-red-team-*.yml` on `research/composite-school-grant-study`.
