# Composite School Grant Study

## Current headline findings

This file supersedes the earlier red-team headline that treated the +2 UDISE financial observation as the main first stage. The definitive analysis is in `FINAL_TIMING_AND_INCENTIVES_FINDINGS.md`.

> **The 250/251 Composite School Grant rule leaves a strong but delayed financial fingerprint in UDISE. Across the four usable middle cohorts, crossing the funding cutoff increases the probability of reporting CSG receipt of at least Rs 75,000 by approximately 25-33 percentage points three UDISE academic-data rounds after the enrolment vintage. The +2 UDISE round shows only a much smaller and statistically weak discontinuity.**

The timing pattern is consistent with the documented administrative clock. Delhi CSG orders for 2019-20, 2022-23 and 2024-25 use UDISE enrolment from two academic years earlier, while UDISE financial fields report receipt/expenditure for the previous financial year. Thus an enrolment vintage can naturally have its strongest fingerprint in the UDISE-labelled file three academic-data rounds later.

## Corrected clustered estimates

Using the 250.5 RD coordinate, mass-point-aware RD and state/UT clustering at bandwidth +/-30:

- 2019-20 enrolment -> 2022-23 UDISE financial field: **+24.70 pp**, p=.0453
- 2020-21 -> 2023-24: **+31.81 pp**, p=.00188
- 2021-22 -> 2024-25: **+33.21 pp**, p=.000176
- 2022-23 -> 2025-26: **+32.52 pp**, p=.000067

The corresponding +2 estimates are approximately 0, +5.65 pp, +6.35 pp and +9.12 pp, and the non-zero estimates are statistically weak under the clustered specification.

Independent local-linear estimates also show correctly timed +3 receipt differences of approximately Rs 9.5k, Rs 13.1k, Rs 14.4k and Rs 13.1k after 99% winsorisation.

## Grant fidelity

For the detailed 2021-22 enrolment cohort, correctly aligned to the 2024-25 UDISE financial field:

- P(receipt exactly Rs 50,000): **-7.11 pp**
- P(receipt exactly Rs 75,000): **+5.29 pp**
- P(receipt >= Rs 75,000): **+33.46 pp**
- 99%-winsorised receipt: **+Rs 14,421**
- P(expenditure >= Rs 75,000): **+32.83 pp**
- 99%-winsorised expenditure: **+Rs 13,275**

The formula therefore clearly moves the recorded financial distribution, but the UDISE field does not mechanically reproduce the exact statutory grant amount.

## Bunching

There is repeatable excess school mass immediately above 250, but the evidence is not strong enough to claim strategic manipulation.

The heaping-adjusted above-versus-below asymmetry at 250/251 is approximately:

- 2018-19: +12.7%
- 2019-20: +14.3%
- 2020-21: +16.4%
- 2021-22: +17.5%
- 2022-23: +9.2%
- 2023-24: +5.7%
- 2024-25: +6.3%
- 2025-26: +6.4%

However, 250/251 is not uniquely extreme relative to placebo cutoffs. In completed placebo-ranking years it ranges from roughly the 70th to 96th percentile. Bunching is therefore a secondary diagnostic, not the headline finding.

## Outcome interpretation

The earlier proposal to headline the absence of changes in toilets, furniture, electricity or other coarse UDISE stocks is abandoned.

Many legitimate CSG uses are recurring or intensive-margin expenditures that UDISE stock indicators cannot reliably detect. Official guidance includes consumables, electricity/internet/water charges, teaching aids, repairs, maintenance, sanitation materials, activities and other small operating expenditures.

Correctly retimed facility results still show no maintenance benefit on the specific UDISE-observed asset set. For the 2022-23 enrolment cohort, the 2025-26 deterioration estimate is +0.054 percentage points with a 95% CI of approximately -0.212 to +0.319 pp. But this is a narrow mechanism result, not evidence that CSG as a whole has no value.

## Claims that are now deprecated

Do not use the following claims:

- "The first stage is only 6-8 percentage points."
- "The same grant expenditure persists over several later years."
- "An additional Rs 25,000 causes no improvement."
- "CSG does not work."
- "Bunching proves manipulation."
- "Nothing improves in the school."

## Defensible bottom line

> **Formula-based school funding leaves a strong but delayed administrative fingerprint. Around India's 250-pupil CSG cutoff, reported school finances respond sharply only after the enrolment, allocation and UDISE reporting clocks are correctly aligned. The recorded response is substantial but not mechanically equal to the statutory amount, while modest bunching around the cutoff is insufficient to establish strategic enrolment manipulation.**

See `FINAL_TIMING_AND_INCENTIVES_FINDINGS.md` for the complete experiment-by-experiment record, timing evidence, grant-fidelity results, bunching/placebo analysis, outcome retiming, and explicit execution status of the remaining code-complete extensions.
