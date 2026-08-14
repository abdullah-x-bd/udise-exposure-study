# Composite School Grant Study

## Headline findings

This study uses the available all-India UDISE+ school microdata from 2018-19 through 2025-26 to examine what happens around the Composite School Grant (CSG) enrolment thresholds.

The strongest current result is more specific than the first outcome pass suggested:

> **Crossing the 250-pupil threshold produces a persistent increase in reported CSG expenditure, but across a comprehensive set of UDISE-observed facility, administrative, digital, WASH, accessibility, and school-safety outcomes we cannot identify a robust corresponding improvement within the following one to three UDISE rounds.**

The clean post-pandemic cohorts show three separate stages:

1. the ₹25,000 statutory band increase is only partly reflected in reported school-level receipt in the first observable post-assignment round;
2. reported expenditure rises immediately and the expenditure discontinuity persists or accumulates in later rounds;
3. the expanded outcome search does not reveal a stable observable channel that survives baseline checks and multiple-testing correction.

The important qualification is that the uploaded all-India microdata contain **total CSG receipt and total CSG expenditure, but no line-item CSG expenditure ledger**. We can therefore locate the additional expenditure **in time**, but not literally identify whether a rupee was spent on cleaning materials, minor repairs, electricity charges, teaching aids, consumables, or another permitted purpose.

This is not evidence of misuse, waste, or no benefit. It is evidence of a measurable gap between additional reported expenditure and the school outcomes that UDISE allows us to observe.

---

## Study design

The study exploits the enrolment bands used for the Composite School Grant. The headline design focuses on the 250-pupil threshold, where the nominal grant band rises from ₹50,000 to ₹75,000, a ₹25,000 statutory step.

The empirical sample is restricted to UDISE government-management categories 1, 2 and 3. Private and government-aided schools are excluded from the causal sample.

The central specification uses:

- the 250-pupil threshold;
- a ±30-pupil bandwidth;
- a one-pupil donut around the threshold;
- assignment-state fixed effects;
- state-clustered standard errors;
- the same school's outcomes over later UDISE rounds where harmonisation permits it.

The 100-pupil threshold is not used as the headline design because enrolment bunching is much stronger there. The 250 threshold is substantially cleaner, although not perfectly smooth, so the preferred language is **suggestive quasi-experimental evidence**, not a flawless textbook regression discontinuity.

---

## Finding 1. The 250-pupil formula produces a real funding first stage in the two clean cohorts

### 2021-22 assignment cohort

In the first post-assignment funding/outcome round, 2023-24:

- reported CSG receipt rises by **₹12,484**;
- SE = ₹4,513;
- 95% CI approximately ₹3,639 to ₹21,329;
- p = 0.0057.

Reported CSG expenditure rises by **₹8,917**:

- SE = ₹2,860;
- 95% CI approximately ₹3,312 to ₹14,523;
- p = 0.0018.

### 2022-23 assignment cohort

In 2024-25:

- reported CSG receipt rises by **₹12,202**;
- SE = ₹5,979;
- 95% CI approximately ₹483 to ₹23,920;
- p = 0.0413.

Reported CSG expenditure rises by **₹10,146**:

- SE = ₹5,096;
- 95% CI approximately ₹159 to ₹20,133;
- p = 0.0465.

The realized receipt discontinuity is therefore roughly half of the nominal ₹25,000 band step in these two clean cohorts.

The earlier pandemic-era cohorts do not provide an equally useful first stage because the relevant grant fields are zero or weak in the local sample. The newest 2023-24 assignment cohort contains extremely noisy grant amounts and is not pooled mechanically with the cleaner cohorts.

---

## Finding 2. The expenditure effect is dynamic, not purely contemporaneous

The first pass only looked at the immediate post-assignment round. Extending the same schools forward changes the picture.

### 2021-22 assignment cohort

Reported expenditure discontinuity:

- **2023-24: +₹8,917**, p = 0.0018;
- **2024-25: +₹13,058**, p = 0.0030;
- **2025-26: +₹6,806**, p = 0.214.

Across all three later reporting rounds, cumulative reported CSG expenditure is:

> **₹28,839 higher** for schools locally above the original 250-pupil threshold.

- SE = ₹8,692;
- 95% CI approximately **₹11,802 to ₹45,876**;
- p = **0.00091**.

### 2022-23 assignment cohort

Reported expenditure discontinuity:

- **2024-25: +₹10,146**, p = 0.0465;
- **2025-26: +₹23,895**, p = 0.0094.

Cumulative reported expenditure over the two subsequent UDISE rounds is:

> **₹34,033 higher**.

- SE = ₹12,467;
- 95% CI approximately **₹9,597 to ₹58,469**;
- p = **0.0063**.

This means the relevant empirical object is not just a one-year expenditure response. The grant threshold is associated with a persistent/cumulative difference in reported expenditure over subsequent rounds.

---

## Finding 3. The later expenditure gap is not simply explained by schools remaining above 250 pupils

A natural concern is that the later expenditure difference is mechanically caused by the originally higher-enrolment schools remaining in the >250 grant band and repeatedly receiving the larger entitlement.

We tested this directly.

### 2022-23 assignment cohort

At the original threshold:

- 2024-25 enrolment discontinuity = **-1.13 pupils**, p = 0.426;
- discontinuity in probability of still being above 250 in 2024-25 = **+0.68 percentage points**, p = 0.610;
- 2025-26 enrolment discontinuity = **-1.59 pupils**, p = 0.305;
- discontinuity in probability of still being above 250 in 2025-26 = **+0.21 percentage points**, p = 0.765.

### 2021-22 assignment cohort

The same pattern holds:

- 2023-24 enrolment discontinuity = **+0.26 pupils**, p = 0.848;
- probability of remaining above 250 = **+1.00 percentage point**, p = 0.356;
- 2024-25 enrolment discontinuity = **-0.54 pupils**, p = 0.717;
- probability of remaining above 250 = **+0.09 percentage points**, p = 0.937;
- 2025-26 enrolment discontinuity = **-1.36 pupils**, p = 0.439;
- probability of remaining above 250 = **+0.44 percentage points**, p = 0.673.

So the persistent cumulative expenditure difference is **not well explained by a persistent local discontinuity in later enrolment or by schools remaining discontinuously more likely to sit above 250**.

This does not prove that the original grant literally sat unspent and was carried forward. UDISE does not identify balances or carry-forward transactions. Plausible mechanisms include allocation/reporting lags, expenditure timing, administrative persistence, or other features of the grant cycle. The data establish persistence in reported expenditure, not the accounting mechanism behind it.

---

## Finding 4. The original outcome set was too narrow, so we expanded it aggressively

The first analysis focused on a conservative harmonised set of WASH, electricity, internet, library, and toilet outcomes. That was useful for validation but too selective for a claim about where the additional spending manifests.

We therefore ran two much broader searches.

### A. Cross-year common-outcome screen

For each clean cohort we screened every usable numeric field shared between the assignment year and later outcome year in the facility and school-profile data. The design uses the change in the same school's outcome from baseline, checks baseline continuity at the threshold, and applies Benjamini-Hochberg false-discovery-rate correction across the outcome family.

This includes much more than the original seven outcomes, such as:

- classroom counts and repair measures;
- toilet and urinal counts;
- multiple drinking-water sources and functionality fields;
- handwashing;
- boundary-wall and accessibility measures;
- devices and digital facilities;
- school-management and inspection variables;
- several administrative and programme-participation measures.

**Result: no outcome survives the combined baseline-continuity and false-discovery screen in either clean cohort.**

Some fields generate nominal raw p-values, but these either have pre-existing threshold discontinuities or disappear once the large number of outcomes tested is accounted for.

### B. 2025-26 exhaustive level screen, including newly introduced fields

The 2025-26 microdata contain outcomes that did not exist in earlier UDISE vintages, including a dedicated school-safety table. Those variables cannot be analysed as baseline-to-outcome changes, but they can be searched exploratorily at the original 250 threshold.

For the 2022-23 assignment cohort, the 2025-26 screen covered **146 numeric fields**:

- 78 facility fields;
- 21 school-safety fields;
- 33 profile-1 fields;
- 14 profile-2 fields.

The 2021-22 assignment cohort was screened over the same 2025-26 field universe.

**Result: zero fields survive Benjamini-Hochberg FDR < 0.10 in either cohort.**

This is important because it means the lack of a visible outcome is not an artefact of having selected only toilets, water, electricity, internet, and libraries.

The new safety fields likewise do not reveal a hidden robust channel.

---

## Finding 5. We cannot directly identify the line-item destination of CSG expenditure from this microdata extract

The actual all-India UDISE+ microdata schemas were inspected year by year.

For CSG finances, the uploaded extract consistently provides:

- `grants_receipt`;
- `grants_expenditure`.

It does **not** provide a national school-level line-item breakdown of CSG expenditure into categories such as cleaning, electricity charges, minor repair, teaching aids, consumables, or housekeeping.

Therefore the study can answer:

- whether the threshold changes reported receipt;
- whether it changes reported expenditure;
- whether the expenditure difference persists over time;
- whether observable school conditions subsequently change.

It cannot answer from UDISE alone:

> “Of the additional ₹10,000 spent, ₹X went to cleaning and ₹Y went to minor repair.”

Any such claim would require a different financial source, such as school-level expenditure ledgers or a sufficiently granular Samagra/PRABANDH administrative extract.

---

## Finding 6. What the comprehensive evidence now says

The study no longer supports the simplistic summary “money moves, facilities do not” as a one-year statement.

The stronger version is:

> **The marginal CSG entitlement produces a smaller immediate increase in reported receipt, a persistent and sometimes growing increase in reported expenditure over later UDISE rounds, but no robust corresponding movement in the broad set of physical, administrative, digital, accessibility, WASH, or school-safety outcomes observable in UDISE.**

That creates a much more interesting implementation question:

> **What does additional flexible school funding purchase when aggregate expenditure rises but the administrative outcome system cannot identify a corresponding output?**

There are at least four non-exclusive explanations consistent with the data:

1. CSG is spent on recurring or consumable inputs that UDISE does not measure as stocks;
2. expenditure maintains existing conditions or prevents deterioration rather than creating new observable assets;
3. the relevant improvements are too small or too heterogeneous to produce a national local-average discontinuity;
4. national reporting is too coarse to connect grant expenditure to what schools actually purchase.

The present evidence cannot distinguish these mechanisms conclusively.

---

## Finding 7. This is not evidence of waste, misuse, or no benefit

The estimates are local to schools near 250 pupils. They identify the marginal effect of moving between adjacent grant bands, not the effect of eliminating CSG.

The following statements are **not supported**:

- CSG money is stolen or misused;
- schools spend the money on nothing;
- CSG has no value;
- the grant causes school conditions to worsen;
- the cumulative expenditure effect proves that the original grant was carried forward unspent.

The supported claim is narrower:

> **At the 250-pupil threshold, reported CSG expenditure increases persistently, but a comprehensive search of UDISE-observed school outcomes does not reveal a robust corresponding output over the horizons available in the data.**

---

## RD validity

The 100-pupil threshold has pronounced bunching and should not be the headline design.

The 250 threshold is cleaner but not immaculate. Density diagnostics still show some non-smoothness in school counts. The later cohorts have more reassuring immediate-cell ratios than the 100 cutoff, and most headline baseline outcomes are reasonably continuous.

The design should therefore be presented as **quasi-experimental evidence around the threshold with explicit density caveats**.

---

## Best paper framing now

A stronger research question than the original facility-only formulation is:

> **What happens to the marginal school grant? Evidence on funding transmission, expenditure persistence, and observable outputs from India's Composite School Grant formula.**

Possible title:

**From Entitlement to Expenditure: What Happens to India's Marginal School Grant?**

A second option:

**Where Does the Marginal School Grant Go? Evidence from India's Composite School Grant Thresholds**

The second title should be understood as an accountability question, not a claim that UDISE can literally trace line-item expenditure.

The empirical contribution is the full chain:

**statutory entitlement → reported receipt → reported expenditure over multiple years → comprehensive observed outcome search**.

The central policy implication is not “cut the grant.” It is that **aggregate grant receipt/expenditure reporting is insufficient for evaluating whether discretionary school funding converts into outputs**. If policymakers want to learn which uses are productive, national administrative systems need either expenditure-purpose coding linked to the school identifier or structured outcome-linked audits that can distinguish maintenance, consumables, utilities, minor repairs, teaching inputs, and other eligible uses.

---

## Status

The study now includes:

- eight UDISE vintages from 2018-19 through 2025-26;
- six longitudinal cohort replications;
- government-school sample validation;
- first-stage receipt and expenditure estimates;
- density diagnostics;
- baseline continuity tests;
- bandwidth and donut variants;
- multi-year expenditure-persistence analysis;
- later-enrolment/repeated-treatment diagnostics;
- a broad common-variable outcome screen with FDR correction;
- an exhaustive 2025-26 screen including the new school-safety table;
- explicit verification that the available microdata do not contain CSG line-item expenditure categories.

The discovery stage is now substantially more complete. The next production stage should turn these results into final figures, tables, a concise policy brief, and a robustness appendix without overstating the causal design or the meaning of the null outcome search.