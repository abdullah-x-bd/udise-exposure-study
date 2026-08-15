# Composite School Grant Study: Hostile Red-Team Report

## Verdict

The red team does not kill the study, but it kills the strongest version of the original causal claim.

The defensible result is a **local reduced-form / policy-threshold result**, not a clean estimate of the causal effect of an extra ₹25,000 actually received by a school.

The robust core is:

> Around the 250-pupil Composite School Grant formula threshold, schools are substantially more likely to report receipt and expenditure in the higher grant range, and outlier-resistant cumulative expenditure is persistently higher. Across broad UDISE-observed physical, WASH, digital, accessibility, safety, furniture, teacher, staffing and class-enrolment outcomes, no positive mechanism replicates across both clean post-pandemic cohorts. The reduced-form maintenance effect is especially small and does not show a replicating benefit.

The study should **not** claim:

- that every school above 250 actually receives ₹25,000 more;
- that the estimated outcome coefficients are the LATE of actual CSG receipt;
- that the raw mean rupee discontinuities are reliable magnitudes;
- that literally every possible UDISE outcome has been tested;
- that no other policy changes at 250;
- that CSG money is wasted, stolen, or produces no unmeasured benefit.

The study is credible for a policy brief if framed around **implementation, conversion and observability**. A journal-grade causal claim about the return to actual CSG rupees would require a stronger treatment/compliance design and better financial linkage.

---

## 1. Attack: financial outliers could manufacture the first stage

### Problem

The UDISE CSG financial fields have extreme upper tails. In the clean cohorts, some school records contain reported grant receipts/expenditures in the tens or hundreds of millions of rupees. Means are therefore vulnerable to a very small number of implausible or unusual observations.

Examples from the audit include:

- 2022-23 assignment cohort, first observed receipt maximum about ₹75.8 million;
- first observed expenditure maximum about ₹23.9 million;
- cumulative expenditure maximum above ₹100 million;
- cumulative receipt maximum above ₹600 million.

The earlier raw mean statements such as approximately +₹12,000 immediate receipt and +₹29,000 to +₹34,000 cumulative expenditure should therefore **not be headline magnitudes**.

### Test

We reran the first stage and cumulative finance outcomes using:

- trimming at the 99th, 99.5th and 99.9th percentiles;
- winsorisation at the same cut points;
- inverse-hyperbolic-sine transformations;
- indicators for positive receipt/expenditure;
- indicators for reported receipt/expenditure at or above ₹75,000.

### Result

The financial first stage survives strongly.

In the 2022-23 cohort, outlier-resistant first-year receipt estimates are roughly +₹3,000 to +₹6,000 depending on trimming/winsorisation. First-year expenditure is roughly +₹3,000 to +₹6,000. Outlier-resistant cumulative expenditure is roughly +₹14,000 to +₹21,000.

In the 2021-22 cohort, robust first-year receipt is roughly +₹4,000 to +₹7,000, first-year expenditure about +₹4,000 to +₹6,000, and cumulative expenditure roughly +₹23,000 to +₹27,000.

More importantly, crossing 250 causes a clear distributional shift toward the higher grant range. The hand-built estimator finds approximately a 7 to 9 percentage-point increase in the probability of reporting at least ₹75,000 of receipt, depending on cohort.

### Verdict

**The existence of the financial discontinuity survives. The old raw-mean rupee magnitudes do not.**

The preferred finance headline should use outlier-resistant estimates and threshold-band probabilities.

---

## 2. Attack: enrolment is discrete, so conventional RD inference may be overconfident

### Problem

School enrolment is an integer running variable with mass points. Treating it like a continuously distributed running variable can produce misleading standard errors and bandwidth choices.

### Test

We reran the core finance results with the maintained `rdrobust` implementation using:

- mass-point adjustment;
- local linear point estimation and local quadratic bias correction;
- robust bias-corrected inference;
- CR3 cluster-robust variance by assignment-year state;
- state dummy covariates;
- automatic MSE bandwidths;
- fixed ±20, ±30 and ±40 bandwidths;
- the same conservative donut around the cutoff.

### Result

The first stage remains large and precisely estimated in both clean cohorts.

Representative fixed ±30 results:

**2021-22 assignment cohort**

- 99%-winsorised first-year receipt discontinuity about +₹5.4k;
- probability of receipt >=₹75k about +6.1 pp;
- 99%-winsorised first-year expenditure about +₹4.4k;
- probability of expenditure >=₹75k about +5.7 pp;
- 99%-winsorised cumulative expenditure through 2025-26 about +₹25.8k.

**2022-23 assignment cohort**

- probability of receipt >=₹75k about +7.9 pp;
- probability of expenditure >=₹75k about +6.8 pp;
- 99%-winsorised cumulative expenditure about +₹16.3k.

The direction and inference survive automatic MSE and fixed alternative bandwidths.

### Verdict

**The core financial threshold effect is not an artefact of naive continuous-RD inference.**

---

## 3. Attack: the treatment is fuzzy, not a deterministic ₹25,000 jump

### Problem

The statutory formula changes at 250, but actual reported receipt does not jump deterministically by ₹25,000 for every school. The probability of reporting in the >=₹75,000 band rises by only several percentage points.

This means the assignment rule is an **encouragement / entitlement discontinuity**, not a sharp treatment switch in actual money received.

### Consequence

The outcome RD coefficients are reduced-form effects of crossing the policy threshold. They are not directly the causal effect of receiving an additional ₹25,000.

This matters particularly for the equivalence tests. A tightly estimated near-zero reduced-form deterioration effect does not automatically imply an equally tiny treatment-on-the-treated effect among schools whose actual funding changed because of the rule.

### Verdict

The paper should use language such as:

> “reduced-form effect of crossing the CSG formula threshold”

or

> “effect of marginally higher formula-based CSG entitlement.”

It should **not** say that the experiment directly estimates the effect of an additional ₹25,000 received.

A future journal version should build a fuzzy RD using a verified CSG receipt/compliance variable and report the corresponding local Wald estimate, while being explicit about exclusion restrictions.

---

## 4. Attack: another national scheme also changes at 250 pupils

### Problem

PM POSHAN has an enrolment-linked kitchen-device assistance schedule with a breakpoint at 250 pupils. This invalidates the original assumption that the 250 cutoff is uniquely a CSG policy discontinuity.

Therefore an unrestricted 250-pupil RD could in principle combine CSG with PM POSHAN-related effects.

### Isolation test

CSG assignment is based on total school enrolment, whereas PM POSHAN serves Bal Vatika and Classes I-VIII. We therefore reran the design among schools whose total Classes I-XII enrolment is near 250 but whose Classes I-VIII enrolment is safely below the PM POSHAN 250 breakpoint.

We used two restrictions:

- Classes I-VIII enrolment <=220;
- Classes I-VIII enrolment <=200.

### Result

The CSG-like financial first stage survives in both cohorts.

**2022-23 cohort, Classes I-VIII <=220**

- receipt >=₹75k: approximately +6.7 pp, p≈0.019;
- expenditure >=₹75k: approximately +5.4 pp, p≈0.052;
- 99%-winsorised cumulative expenditure: approximately +₹20.7k, p≈0.00033;
- first-horizon deterioration: essentially zero.

With Classes I-VIII <=200, cumulative expenditure remains approximately +₹20.3k, p≈0.0011.

**2021-22 cohort, Classes I-VIII <=220**

- receipt >=₹75k: approximately +5.0 pp, p≈0.008;
- expenditure >=₹75k: approximately +4.6 pp, p≈0.007;
- 99%-winsorised cumulative expenditure: approximately +₹31.3k, p<0.0001.

With Classes I-VIII <=200, cumulative expenditure remains approximately +₹33.2k.

The maintenance/deterioration result does not turn positive in these isolated samples. The earlier cohort has a small adverse deterioration coefficient, while the later cohort is near zero, so there is no replicating evidence of harm or benefit.

### Verdict

**PM POSHAN is a real exclusion-restriction threat and must be disclosed, but it does not explain away the financial threshold result.**

The PM-POSHAN-safe subsample should become a major robustness table in the brief/paper.

---

## 5. Attack: sorting/manipulation around 250

### Problem

The density is not perfectly smooth around 250. Existing diagnostics show a positive density jump of roughly 5-13% depending on bandwidth, although the immediate five-pupil right/left ratio is much smaller than the severe bunching around the 100-pupil cutoff.

The 100 threshold is clearly unsuitable as the main design and has already been abandoned.

### Verdict

The 250 cutoff is **usable but not pristine**.

The correct language is “suggestive quasi-experimental evidence” rather than “textbook RD.” The paper should show the enrolment histogram/density figure prominently rather than bury it.

The PM-POSHAN-safe result and extensive predetermined balance tests help, but they do not logically prove absence of sorting on unobservables.

---

## 6. Attack: baseline imbalance, differential attrition and unstable school identifiers

### Problem

A longitudinal RD can be biased if schools just above and below the cutoff differ before treatment, disappear at different rates, or if the pseudonymous school identifier is unstable across years.

The repository's own data-governance notes correctly warn that the exact source semantics of `pseudocode` require validation.

### Test

A hostile validity audit tested:

- predetermined facility variables;
- predetermined teacher/staffing variables;
- class span and school characteristics;
- threshold-specific presence in later Profile 1, Profile 2, Facility, Teacher, Enrolment 1 and Enrolment 2 files;
- stability of school type, low/high class, rural/urban status, block and district identifiers;
- leave-one-state-out sensitivity;
- broad specification grids.

### Result

In both clean cohorts:

- no attrition family survives FDR correction;
- no predetermined-balance family survives FDR correction;
- school type, low/high class and rural/urban fields are extremely stable;
- block identity is highly stable and has no meaningful threshold discontinuity;
- district-name stability deteriorates in later years, plausibly because of administrative/coding changes, but does not change discontinuously at 250;
- leaving out individual states does not reverse the positive cumulative-expenditure result.

The direct state-name stability diagnostic is invalid because state representation changed across vintages and should not be used.

### Verdict

**There is no evidence that differential observable attrition or ordinary school-code instability drives the result.**

However, source-level documentation of the pseudonymous longitudinal identifier should still be obtained before making a publication-grade panel-identity claim.

---

## 7. Attack: the result may be specification-mined

### Test

The hostile audit varies:

- bandwidths from ±15 to ±75;
- donuts 0-3;
- triangular versus uniform kernels;
- local linear versus local quadratic forms.

The outlier-contaminated raw cumulative-expenditure estimate is positive in every specification; the later outlier-robust `rdrobust` audit also preserves the positive result across MSE and fixed alternative bandwidths.

The deterioration composite does not reveal a stable positive maintenance effect across the corresponding grid.

### Verdict

**The central direction is not tied to one ±30 specification.**

The preferred tables should nevertheless emphasize outlier-resistant and mass-point-aware specifications, not the raw grid.

---

## 8. Attack: invalid placebo cutoffs

One initial placebo test used 150 pupils. This is not a valid policy-null cutoff because PM POSHAN itself has enrolment-linked rules around 150. It should be deleted from the paper.

Other placebo cutoffs without known national policy breaks do not generate a comparable stable cumulative-expenditure discontinuity in the clean audit.

---

## 9. Attack: “we tested everything in UDISE” was false

### Correction

The first broad screen covered the numeric Facility/Profile universe and the 2025-26 Safety data, but it did not initially include all teacher and class-enrolment outcomes. In addition, some categorical/ordinal variables cannot be meaningfully tested by treating their raw numeric code as a continuous quantity.

The correct claim is not “every UDISE variable.”

### Additional tests

We subsequently added:

- teacher counts and composition;
- trained-computer teachers;
- contract/regular teacher variables;
- pupil-teacher ratio;
- class-specific enrolment changes;
- codebook-aware furniture transitions.

**2021-22 cohort:** 69 teacher/staffing/class-enrolment outcomes, zero within-family FDR hits.

**2022-23 cohort:** three within-family FDR hits appear: lower PTR at both horizons and a small Class 3 enrolment change. No individual teacher-count variable survives correction, and the staffing/PTR pattern does not replicate in the 2021-22 cohort. It therefore cannot be treated as a stable hiring/staffing mechanism.

Furniture likewise shows no replicating improvement. One small 2021-22 subgroup/horizon furniture-upgrade coefficient is nominally significant but disappears over time and points differently in the second cohort.

### What remains unobserved

Even after the expansion, UDISE does not give us everything that a causal benefit could affect. Important missing or inadequate outcomes include:

- direct learning achievement for the same schools/pupils;
- detailed student attendance/absence intensity;
- service uptime/quality for internet, electricity and water;
- repair events and preventive-maintenance activity;
- quantities and quality of consumables purchased;
- detailed transaction-level or line-item CSG spending in the public all-India extract.

### Verdict

The defensible statement is:

> “No positive mechanism replicates across the broad set of usable UDISE physical, WASH, digital, accessibility, safety, furniture, teacher, staffing and class-enrolment outcomes tested.”

Do not write “nothing in UDISE changes” without qualification.

---

## 10. Attack: furniture or another mundane asset could absorb the money

Furniture was explicitly recoded because its raw categorical code is not a suitable continuous outcome.

In the 2022-23 cohort, full furniture coverage changes by about -1.1 pp in 2024-25 and -0.7 pp in 2025-26, neither significant. Upgrade estimates among initially deficient schools are also not significant.

In the 2021-22 cohort, one 2024-25 furniture-upgrade estimate is about +3.4 pp with p≈0.048, but the sample is small, the effect is absent at the other horizons and it does not replicate in 2022-23.

**Furniture is not a stable spending channel.**

---

## 11. Attack: the maintenance null is really an underpowered null

At the reduced-form threshold level, this attack largely fails.

The deterioration composite is extremely precise. In the clean cohorts its confidence intervals are generally much narrower than ±2 percentage points, and the later 2022-23 cohort is much tighter still. No replicating reduction in deterioration appears.

However, because actual grant compliance is fuzzy, this does **not** imply an equally tight equivalence bound for the effect of actual additional CSG receipt among compliers.

So the correct conclusion is:

> “The policy-threshold reduced form rules out a large maintenance response in the observed asset-transition composite.”

not

> “Actual CSG receipt cannot have any meaningful maintenance effect.”

---

## 12. Attack: perhaps initially needy schools benefit

High-need schools have larger cumulative-expenditure point estimates than low-need schools in both clean cohorts, but formal heterogeneity is too noisy to establish a stable differential effect.

No corresponding positive outcome response replicates in the high-need group.

This is a useful secondary result for targeting audits/evaluation, not a basis for claiming that need-targeted CSG works or fails.

---

## 13. Attack: the grant may affect broad outcomes even if individual fields do not

Fixed-baseline standardized indices for core functionality, WASH, digital, accessibility and overall school condition do not reveal a stable positive response across cohorts and horizons.

Some negative or positive coefficients occur in one cohort/horizon, but they do not reproduce in the independent cohort and should not be promoted.

---

## 14. Other threshold-linked school funding rules

CSG is not unique in using hard enrolment rules.

### PM POSHAN kitchen-device assistance

The national PM POSHAN scheme links kitchen-device assistance to school enrolment with slabs including 151-250 and a higher amount above 250. This is the most important co-threshold policy for the CSG design and is addressed by the Classes I-VIII-safe subsample test above.

PM POSHAN also has other enrolment-linked operational rules, including cook-cum-helper staffing and kitchen-cum-store size norms, although their principal breakpoints differ from 250.

### Samagra Shiksha ICT

Government/aided schools with more than 700 enrolment may be considered for an additional ICT lab. The associated ICT support is much larger than CSG, including a non-recurring ICT-lab grant and recurring support.

This is potentially useful as a **positive-control threshold policy**, although it is not a clean comparator for CSG because eligibility is discretionary (“can be considered”), the target is a specific asset, and the public UDISE outcomes do not clearly record the number of separate ICT labs.

### Other common Samagra grants

The main grants verified do not use the same kind of total-enrolment cliff:

- library grant varies mainly by school stage;
- sports grant varies by school stage;
- Youth/Eco Club support varies by school stage;
- uniforms and textbooks are per-child entitlements;
- CwSN support is per-child.

Therefore a simple “run the same 250 RD for every grant” strategy is not available from the current public microdata.

---

## 15. Where is the extra expenditure actually going?

The current all-India microdata cannot identify the accounting destination of the marginal CSG expenditure.

The public extract used here provides the CSG receipt and expenditure fields but omits the richer line-item/accounting information required to say that the money went to cleaning, utilities, repairs, teaching materials, furniture, or another purpose.

Plausible explanations consistent with the evidence include:

1. recurring and consumable inputs that do not change UDISE stock variables;
2. cleaning/sanitation supplies and other Swachhta-related operating costs;
3. utilities, connectivity charges, water or other recurring services;
4. small repairs/replacements that preserve service without creating a visible new stock;
5. teaching-learning materials or other purchases not represented well in the public microdata;
6. timing/accounting/reporting lags;
7. substitution, where CSG pays for something previously financed from another source;
8. measurement and reporting error in UDISE finance fields.

The study provides **no evidence** that the money is stolen, diverted, or illegally used.

Teacher hiring is not supported as a replicating mechanism. The one cohort with lower pupil-teacher ratios does not show a replicating teacher-count response in the independent cohort.

The decisive next source would be school-level financial data containing purpose codes, opening balance, sanction, release, receipt, expenditure and closing/carry-forward balance. A UDISE-code linkage to PRABANDH, PFMS/SNA data or school expenditure ledgers would convert the current “where did it go?” puzzle into an accounting analysis.

---

## 16. Recommendations that survive the red team

The red team does **not** support cutting or abolishing CSG.

It supports recommendations about measurement, implementation and formula evaluation.

### A. Publish the full funding chain at school level

For each UDISE code, expose or internally link:

- formula entitlement;
- sanction;
- release;
- opening balance;
- school receipt;
- expenditure;
- closing/carry-forward balance;
- expenditure-purpose code.

The current administrative data make it possible to see that reported expenditure moves, but not what the marginal expenditure purchased.

### B. Add basic expenditure-purpose reporting

At minimum, CSG expenditure should be separable into categories such as:

- maintenance/minor repair;
- WASH/cleaning;
- utilities/services;
- teaching-learning materials;
- furniture/equipment replacement;
- digital/ICT operating costs;
- accessibility;
- other.

This does not require invoice-level public disclosure. A small standardised accounting taxonomy would materially improve evaluation and auditability.

### C. Link UDISE outcomes to financial systems

A secure administrative linkage between UDISE and PRABANDH/PFMS/SNA records would allow researchers and government to distinguish entitlement, actual release, actual receipt, utilization and carry-forward.

### D. Build financial plausibility checks into UDISE

The extreme grant values found in the microdata show a clear data-quality problem. Automated range checks and cross-validation against sanctioned amounts should flag impossible or highly implausible school-level entries before publication/use.

### E. Evaluate whether a hard cliff is the best formula

The study does not prove the current formula is inefficient, but it gives a reason to test alternatives such as a base grant plus a smoother per-pupil or need-weighted component. Hard thresholds create arbitrary differences between otherwise similar schools and complicate evaluation where multiple schemes use enrolment cutoffs.

Any formula redesign should be piloted, not inferred mechanically from this RD.

### F. Coordinate threshold rules across schemes

The PM POSHAN overlap demonstrates that different schemes can generate coincident enrolment breakpoints. The Ministry should maintain a machine-readable registry of scheme eligibility thresholds, definitions of enrolment and financial norms. This would improve both implementation and evaluation.

### G. Target follow-up audits at high-need schools

High-need schools show suggestively larger expenditure responses without a replicating observed-output gain. That is a reason for targeted implementation studies and expenditure tracing, not for assuming misuse.

---

## 17. Final publication-grade claim

The strongest wording supported after the hostile audit is:

> **Among government schools near the 250-pupil Composite School Grant formula threshold, crossing the threshold produces a robust shift toward higher reported CSG receipt/expenditure and a persistent outlier-resistant increase in cumulative reported expenditure. The financial result survives mass-point-aware RD inference, alternative bandwidths, state-clustered inference, leave-one-state-out checks and samples constructed to avoid PM POSHAN's coincident 250-pupil rule. Across a broad set of UDISE-observed school conditions and personnel/enrolment outcomes, no positive mechanism replicates across both clean cohorts. These are reduced-form effects of formula eligibility, not direct estimates of the causal return to an additional ₹25,000 actually received.**

That is a narrower claim than the original version, but it is substantially harder to dismiss.

---

## Reproducibility

Main red-team code/workflows added under:

- `studies/composite_school_grant/red_team/run_validity_audit.py`
- `studies/composite_school_grant/red_team/run_validity_audit_fixed.py`
- `studies/composite_school_grant/red_team/run_finance_outlier_audit.py`
- `studies/composite_school_grant/red_team/run_rdrobust_audit.py`
- `studies/composite_school_grant/red_team/run_teacher_enrolment_screen.py`
- `studies/composite_school_grant/red_team/run_furniture_recode.py`
- `studies/composite_school_grant/red_team/run_pmposhan_isolation.py`
- `studies/composite_school_grant/red_team/run_management_selection.py`

Associated GitHub Actions workflows are stored under `.github/workflows/csg-red-team-*.yml` on `research/composite-school-grant-study`.
