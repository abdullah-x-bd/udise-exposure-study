# Composite School Grant Study

## Headline findings

The definitive full analysis is recorded in `FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md`. Earlier exploratory summaries are retained only as part of the research history where they differ from the final specification.

> **India's enrolment-based Composite School Grant formula leaves a strong but delayed financial fingerprint in school-level UDISE records. Around the 250/251 pupil cutoff, the probability of reporting at least Rs 75,000 rises by roughly 25-33 percentage points once enrolment, grant-allocation and UDISE financial-reporting clocks are aligned. The formula response replicates across cohorts and CSG thresholds, varies sharply and persistently across States, and is essentially unchanged when the government-school universe is broadened. Recorded amounts do not mechanically reproduce the formula-implied amount, while the density and longitudinal evidence does not establish systematic CSG-specific enrolment manipulation.**

## Administrative clock

Documentary and empirical evidence support the common benchmark:

**enrolment vintage t -> grant financial year t+2 -> UDISE financial-report field t+3.**

Primary state-clustered `rdrobust` estimates at 250/251 are:

- 2019-20 -> 2022-23: **+24.70 pp**
- 2020-21 -> 2023-24: **+31.81 pp**
- 2021-22 -> 2024-25: **+33.21 pp**
- 2022-23 -> 2025-26: **+32.52 pp**

Earlier 6-8 pp estimates came from a +2 reporting-round alignment and are superseded by the corrected timing specification.

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

The policy clearly shifts the financial distribution, but the UDISE CSG receipt field is not a deterministic ledger of the exact formula-implied annual amount. A formula-to-record difference is treated here as a recorded administrative realization gap, not automatically as an unpaid cash obligation.

## State implementation and timing

The four-cohort mean 250/251 financial first stage ranges from about 67 pp in Chhattisgarh and Uttar Pradesh, 66 pp in Delhi and 55 pp in Haryana to about 2 pp in Telangana and approximately zero in Himachal Pradesh.

Across 92 state-cohort timing cells, +3 is the largest positive lag in **65 cells, or 70.7%**. Ten States/UTs select +3 in all four cohorts.

The broader longitudinal analysis also separates administrative response strength from response latency. National first-recorded-convergence N50 is T+3 at the three clean thresholds; N80 is T+4 at 100/101 and 250/251 and T+5 at 1,000/1,001. These are administrative-record latency measures, not cash-transfer times.

State patterns are persistent across separate CSG thresholds, indicating substantial State-level heterogeneity in how the same national formula appears in school-level administrative finance records.

## Enrolment density and manipulation tests

Administrative enrolment data are visibly non-smooth at several policy-relevant and round-number values. The 100/101 region shows particularly strong heaping and local excess mass, but 100 is both a salient round number and a threshold used by other school programmes.

Around 250/251, a smaller repeated density irregularity is present, especially in earlier years. Longitudinal landing, minimal-crossing and reversion tests, however, do not distinguish the true CSG threshold from placebo thresholds strongly enough to support a CSG-specific manipulation, gaming or fraud interpretation.

## Social composition

The social-equity study uses correctly timed CSG financial outcomes, previous-year social composition, broad State/UT-government schools, district-by-year and state-by-year specifications, management/rural/school-category adjustment, state-clustered inference, multiple-testing correction, compositional models and false cutoffs.

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

Across the 0-5% through 95-100% bins, the CSG first stage remains positive for every displayed Muslim, SC, ST, OBC and General bin. There is no monotonic collapse in formula transmission as these group shares rise.

The final formula-specific result is therefore **no robust evidence that the CSG threshold response is systematically weaker in schools serving higher Muslim, SC, ST, OBC, General or residual-religion shares**.

Religion and social category remain separate UDISE margins. A Hindu-General or upper-caste-Hindu residual cannot be recovered by subtracting religion and caste categories together.

## Observable facility outcomes

Correctly timed fuzzy-RD sensitivity estimates are near zero for deterioration in the coarse UDISE facility set. Upgrade estimates are extremely imprecise.

The supported interpretation is narrow: no large effect is detected in these coarse observed asset-transition measures. This does not establish that CSG has no benefit or that an additional Rs 25,000 of actual school resources has no effect.

## Interpretations ruled out by the final analysis

Several early formulations are inconsistent with the corrected design or exceed what the data identify:

- The CSG first stage is not 6-8 percentage points under the corrected administrative clock; it is roughly 25-33 pp at 250/251 across the four usable cohorts.
- Later annual UDISE expenditure records cannot be treated as persistence of one original grant allocation because later CSG cycles enter later reporting rounds.
- The design does not identify the causal effect of exactly Rs 25,000 of additional cash received.
- The results do not support a conclusion that CSG "does not work."
- Enrolment bunching alone does not establish manipulation.
- The preferred models do not support a systematic Muslim, SC or ST penalty in the 250/251 formula response.
- Nominal coefficients for smaller religious groups do not establish discrimination because they fail multiplicity and placebo-cutoff tests.
- Religion and social-category margins cannot be subtracted to construct a Hindu-General population.

## Research contribution

This project is an administrative public-finance and measurement study. Its central contribution is the reconstruction of the CSG administrative clock and the measurement of how a nationally uniform formula is transmitted into school-level administrative finance records across time, thresholds and State systems.

> **A formally simple enrolment-based school-funding rule is clearly visible in India's school-level administrative accounts, but only after the policy's allocation and reporting clocks are reconstructed. The size and timing of the recorded response vary sharply across States, formula-implied amounts are only imperfectly reproduced in the UDISE CSG receipt field, and the formula does not appear to generate substantial CSG-specific strategic enrolment manipulation. Despite descriptive social disparities in reported school funding, the quasi-experimental CSG threshold response does not systematically weaken as Muslim or major social-category concentration rises.**

Working title:

**The Formula Bites, But the Records Lag: Tracing School Funding Rules Through India's Administrative Data**
