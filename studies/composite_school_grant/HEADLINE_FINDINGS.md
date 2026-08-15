# Composite School Grant Study

## Final headline findings

The definitive full analysis is in `FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md`. It supersedes earlier summaries where they conflict.

> **India's enrolment-based Composite School Grant formula leaves a strong but delayed financial fingerprint in school-level UDISE records. Around the 250/251 pupil cutoff, the probability of reporting at least Rs 75,000 rises by roughly 25-33 percentage points once enrolment, grant-allocation, and UDISE financial-reporting clocks are aligned. The formula response replicates across cohorts and statutory thresholds, varies sharply and persistently across States, and is essentially unchanged when the government-school universe is broadened. Recorded amounts do not mechanically reproduce the statutory grant, and neither bunching nor longitudinal crossing patterns establish strategic enrolment manipulation.**

## Correct administrative clock

Documentary and empirical evidence imply:

**enrolment vintage t -> grant financial year t+2 -> UDISE financial-report field t+3.**

Primary state-clustered `rdrobust` estimates at 250/251 are:

- 2019-20 -> 2022-23: **+24.70 pp**
- 2020-21 -> 2023-24: **+31.81 pp**
- 2021-22 -> 2024-25: **+33.21 pp**
- 2022-23 -> 2025-26: **+32.52 pp**

The old 6-8 pp result was a +2 timing misalignment and must not be used.

## Government-universe robustness

The original management 1/2/3 sample and the broader State/UT-government sample 1/2/3/6/89/90 give essentially identical first stages:

- 2019-20: 25.21 vs 25.24 pp
- 2020-21: 32.88 vs 32.87 pp
- 2021-22: 33.46 vs 33.72 pp
- 2022-23: 33.24 vs 33.42 pp

Adding the principal centrally managed government categories as a sensitivity also leaves the estimates almost unchanged.

## Recorded grant fidelity

Across the four cohorts, crossing 250/251:

- lowers exact Rs 50,000 reporting by roughly 3-7 pp;
- raises exact Rs 75,000 reporting by only roughly 2-7 pp;
- raises receipt >= Rs 75,000 by roughly 25-33 pp;
- raises 99%-winsorised reported receipt by roughly Rs 9.5k-Rs 14.4k;
- raises reported expenditure by roughly Rs 9.0k-Rs 13.3k.

The policy clearly moves the financial distribution, but UDISE is not a deterministic record of the exact statutory entitlement.

## State implementation and timing

The four-cohort mean 250/251 financial first stage ranges from about 67 pp in Chhattisgarh and Uttar Pradesh, 66 pp in Delhi, and 55 pp in Haryana to about 2 pp in Telangana and approximately zero in Himachal Pradesh.

Across 92 state-cohort timing cells, +3 is the largest positive lag in **65 cells, or 70.7%**. Ten States/UTs select +3 in all four cohorts.

Stronger state formula transmission does not predict stronger enrolment bunching.

## Enrolment manipulation

Heaping-adjusted bunching around 250 is repeatable but not uniquely extreme relative to placebo cutoffs. Longitudinal approach, landing, and reversion tests at 250 differ from placebo thresholds 200 and 300 by only a few tenths of a percentage point on average.

**Do not claim that CSG causes strategic enrolment manipulation, gaming, or fraud.**

## Social composition

The social-equity study uses correctly timed CSG financial outcomes, previous-year social composition, broad State/UT-government schools, district-by-year and state-by-year specifications, management/rural/school-category adjustment, state-clustered inference, multiple-testing correction, compositional models, and false cutoffs.

The preferred pooled district-by-year interaction per +10 percentage points composition is:

- Muslim: **-0.18 pp**, p=.733
- SC: **+1.37 pp**, p=.276
- ST: **-1.20 pp**, p=.318
- OBC: **+0.94 pp**, p=.149
- General: **-1.16 pp**, p=.101

No univariate group survives FDR correction.

In the joint social-category model, with General as the omitted category:

- SC: +1.92 pp, p=.151
- ST: +0.02 pp, p=.984
- OBC: +1.33 pp, p=.096
- joint Wald p=.391.

The pooled Muslim coefficient in the joint religion model is -0.26 pp per +10 percentage points, p=.615. The religion-family joint test at 250/251 is p=.248.

Nominal Christian/Sikh/Buddhist negative coefficients fail multiplicity control and the religion family is strongly significant at fake cutoffs 200.5 and 300.5, so these are not credible CSG-specific effects.

Across the requested 0-5% through 95-100% bins, the CSG first stage stays positive for every displayed Muslim, SC, ST, OBC, and General bin. There is no monotonic collapse in formula transmission as these group shares rise.

**Final social conclusion: the study finds no robust evidence that the statutory CSG formula is transmitted less strongly to schools serving higher Muslim, SC, ST, OBC, General, or residual-religion shares.**

Religion and social category are separate UDISE margins. Do not construct a Hindu-General or upper-caste-Hindu residual by subtracting religion and caste categories together.

## Observable facility outcomes

Correctly timed fuzzy-RD sensitivity estimates are near zero for deterioration in the coarse UDISE facility set. Upgrade estimates are extremely imprecise.

This supports only a narrow statement: no large effect is detected in these coarse observed asset-transition measures. It does **not** establish that CSG has no benefit or that an extra Rs 25,000 causes no improvement.

## Claims that are deprecated

Do not use:

- "The first stage is only 6-8 percentage points."
- "The same grant expenditure persists for years."
- "An additional Rs 25,000 causes no improvement."
- "CSG does not work."
- "Bunching proves manipulation."
- "Muslim schools receive a weaker CSG formula response."
- "SC/ST schools receive a weaker formula response."
- "The smaller-religion nominal coefficients prove discrimination."
- "Hindu-General share can be recovered by subtracting minority religion and caste shares."

## Final paper direction

The strongest paper is an administrative public-finance and measurement paper:

> **A formally simple enrolment-based school-funding rule is clearly visible in India's school-level administrative accounts, but only after the policy's allocation and reporting clocks are reconstructed. The size and timing of the recorded response vary sharply across States, statutory amounts are only imperfectly reproduced, and the formula does not appear to generate substantial strategic enrolment manipulation. Despite descriptive social disparities in reported school funding, the quasi-experimental CSG first stage does not systematically weaken as Muslim or major social-category concentration rises.**

Suggested title:

**The Formula Bites, But the Records Lag: Tracing School Funding Rules Through India's Administrative Data**
