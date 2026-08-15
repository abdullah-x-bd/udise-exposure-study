# Composite School Grant Study

## Red-team-corrected headline findings

The hostile methodological audit materially changed the interpretation of this study. This file supersedes the earlier pre-audit headline summary. The full audit is in `red_team/RED_TEAM_REPORT.md`.

> **Among government schools near the 250-pupil Composite School Grant formula threshold, crossing the threshold produces a robust shift toward higher reported grant receipt/expenditure and a persistent outlier-resistant increase in cumulative reported expenditure. Across a broad set of UDISE-observed physical, WASH, digital, accessibility, safety, furniture, teacher, staffing and class-enrolment outcomes, no positive mechanism replicates across both clean post-pandemic cohorts. These are reduced-form effects of crossing a formula-based policy threshold, not direct estimates of the causal return to an additional ₹25,000 actually received.**

## What survives the red team

The financial threshold effect survives:

- trimming and winsorisation of extreme UDISE financial values;
- mass-point-aware `rdrobust` estimation for the integer enrolment running variable;
- robust bias-corrected inference;
- CR3 clustering by assignment-year state;
- alternative bandwidths;
- leave-one-state-out checks;
- predetermined-balance and differential-attrition tests;
- samples constructed to stay safely below PM POSHAN's coincident Class I-VIII 250-pupil kitchen-device threshold.

Representative mass-point-aware fixed ±30 estimates are:

### 2021-22 assignment cohort

- 99%-winsorised first-year reported receipt: about **+₹5.4k**;
- probability of reported receipt >= ₹75,000: about **+6.1 percentage points**;
- 99%-winsorised first-year reported expenditure: about **+₹4.4k**;
- probability of reported expenditure >= ₹75,000: about **+5.7 pp**;
- 99%-winsorised cumulative reported expenditure through 2025-26: about **+₹25.8k**.

### 2022-23 assignment cohort

- probability of reported receipt >= ₹75,000: about **+7.9 pp**;
- probability of reported expenditure >= ₹75,000: about **+6.8 pp**;
- 99%-winsorised cumulative reported expenditure through 2025-26: about **+₹16.3k**.

The exact rupee estimates vary with robustification and bandwidth. The distributional shift and positive cumulative-expenditure response are more robust than any single rupee magnitude.

## What does not survive as a strong claim

The earlier raw mean discontinuities in receipt and cumulative expenditure are not preferred estimates. The financial fields contain extreme upper-tail observations, including implausibly large school-level values, so untrimmed means are too sensitive to outliers.

The design is also fuzzy. Crossing 250 changes formula-based entitlement and measurably shifts the distribution of reported receipt/expenditure, but it does not deterministically deliver an additional ₹25,000 to every school. Outcome coefficients should therefore be interpreted as reduced-form effects of crossing the policy threshold, not treatment-on-the-treated effects of actual money received.

The 250 cutoff is not uniquely a CSG threshold. PM POSHAN also uses a 250-pupil breakpoint for kitchen-device assistance. This is now an explicit exclusion-restriction caveat. Importantly, the CSG-like financial discontinuity survives when the sample is restricted to schools whose Classes I-VIII enrolment is safely below the PM POSHAN 250 threshold.

The enrolment density around 250 is not perfectly smooth. The 250 design is substantially cleaner than the 100-pupil cutoff, which has been abandoned, but the correct description remains **suggestive quasi-experimental evidence**, not a pristine textbook RD.

## Outcome evidence after expansion

The original outcome set was too narrow. The study now includes:

- broad numeric Facility and Profile outcome screens;
- 2025-26 School Safety fields;
- maintenance versus upgrade transitions;
- fixed-baseline standardized indices for core functionality, WASH, digital, accessibility and overall condition;
- baseline-need heterogeneity;
- teacher counts and composition;
- trained-computer teachers;
- regular/contract staffing measures;
- pupil-teacher ratios;
- class-specific enrolment changes;
- codebook-aware furniture transitions.

No positive mechanism replicates across both clean cohorts.

The 2022-23 cohort shows lower pupil-teacher ratios at later horizons, but no individual teacher-count response survives correction and the PTR pattern is absent in the independent 2021-22 cohort. It is not a credible staffing mechanism.

Furniture likewise does not show a replicating improvement.

The maintenance hypothesis is especially weak at the reduced-form threshold level. The 2022-23 deterioration composite is essentially zero and precisely estimated. The 2021-22 cohort shows a small short-run increase in deterioration which is specification-stable within that cohort but fades over time and does not replicate in 2022-23. The study therefore supports neither a maintenance benefit nor a causal-harm claim.

Because actual funding compliance is fuzzy, tight reduced-form equivalence bounds should **not** be translated mechanically into equally tight bounds on the effect of actual CSG receipt among compliers.

## Selection and longitudinal validity

Hostile checks find:

- no family of predetermined baseline covariates surviving FDR correction;
- no threshold-specific attrition family surviving FDR correction;
- very high stability of school type, class span, rural/urban status and block identifiers;
- no evidence that later management status changes discontinuously at 250;
- virtually identical deterioration estimates whether all assignment-year government schools are retained or only schools still coded government later.

District labels become less stable in later vintages, plausibly because of administrative/coding changes, but that instability is not discontinuous at the threshold.

The repository's source-level documentation of the pseudonymous school identifier remains incomplete. Observable invariant stability is reassuring, but official validation of the longitudinal identifier is still desirable for a journal version.

## What the study can and cannot say about where the money goes

The uploaded all-India microdata provide the relevant reported grant receipt/expenditure fields but do not retain a sufficiently granular school-level expenditure-purpose ledger. The study can identify a persistent reported expenditure difference and test many subsequent school outcomes, but it cannot say that the marginal rupee was spent on cleaning, minor repair, electricity, teaching materials, consumables, furniture, or another specific purpose.

Plausible unobserved channels include recurring consumables, sanitation supplies, utility/service costs, small repairs and replacements, teaching-learning materials, expenditure timing, substitution against other funding sources, and reporting/accounting noise. The study provides no evidence of theft or misuse.

The most valuable next data source would link UDISE code to detailed PRABANDH/PFMS/SNA or school-ledger fields containing entitlement, sanction, release, opening balance, receipt, purpose-coded expenditure and closing/carry-forward balance.

## Publication-grade interpretation

This is strong enough for a careful policy brief about **implementation, conversion and observability**. It is not yet a clean causal estimate of the return to an additional rupee of CSG.

A journal-grade treatment-effect paper would need, at minimum:

1. verified source semantics for the CSG financial fields and the longitudinal school identifier;
2. a fuzzy-RD/compliance design for actual receipt;
3. explicit treatment of coincident national and state-level enrolment rules;
4. preferably a financial-system linkage that identifies release, receipt, expenditure purpose and carry-forward.

See `red_team/RED_TEAM_REPORT.md` for the complete hostile audit and recommendations.
