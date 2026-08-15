# Enrolment Integrity and State Administrative Response Time

## Why these extensions matter

This module answers two questions that a single T+3 regression cannot answer.

1. Does the distribution and longitudinal movement of reported enrolment around 250/251 contain evidence consistent with threshold targeting or false enrolment reporting?
2. How quickly does the higher-band financial signal emerge after a school crosses 250/251, and do States differ in administrative latency as well as eventual response strength?

These questions are related but distinct from the main CSG first-stage result.

---

# Part I. Enrolment integrity around 250/251

## 1. Year-by-year 0-400 density

For each academic year 2018-19 through 2025-26, the audit counts broad State/UT-government schools at every integer reported enrolment from 0 through 400. It produces a full density figure and a local 220-280 figure with a counterfactual that explicitly models ordinary heaping at multiples of 5, 10, 25, 50 and 100.

The graph shows obvious structure at policy/round-number locations, especially 30, 100 and 250. Therefore a visible spike by itself cannot establish strategic manipulation.

### Heaping-adjusted 250/251 asymmetry

The preferred broad-State-government 250/251 asymmetry is:

| Academic year | Excess 251-255 | Excess 245-249 | Above-minus-below asymmetry | Placebo percentile |
|---|---:|---:|---:|---:|
| 2018-19 | +8.24% | -3.97% | **0.122** | 83rd |
| 2019-20 | +9.00% | -4.53% | **0.135** | 92nd |
| 2020-21 | +10.13% | -6.16% | **0.163** | 100th |
| 2021-22 | +11.08% | -4.56% | **0.156** | 100th |
| 2022-23 | +10.12% | +3.09% | **0.070** | 83rd |
| 2023-24 | +7.49% | +3.00% | **0.045** | 67th |
| 2024-25 | +7.22% | +2.23% | **0.050** | 75th |
| 2025-26 | +7.18% | +1.95% | **0.052** | 67th |

There is therefore a real and repeatable density irregularity around 250/251, strongest in 2019-20 through 2021-22 and weaker thereafter.

The exact counts also demonstrate why the relevant threshold is 250/251 rather than 249/250. Examples:

- 2020-21: 646 schools at 250 and 747 at 251.
- 2021-22: 721 at 250 and 815 at 251.
- 2022-23: 710 at 250 and 820 at 251.

However, ordinary density evidence is not enough to infer false reporting.

## 2. Other thresholds

The heaping-adjusted asymmetry at 100/101 is much larger, roughly 0.25-0.45 across years. This cannot be treated as cleaner evidence of CSG manipulation because 100 is also implicated by other school-program rules, especially PM POSHAN, and is a strong round number.

The 30/31 threshold does not show a stable positive asymmetry.

Thus 250/251 remains the cleanest CSG-specific threshold for integrity testing.

---

# Part II. Exact minimal crossing and reversion

A stronger manipulation test follows schools longitudinally.

For each three-year window, schools beginning within 20 pupils below a threshold are followed into the next year. The audit asks whether they land exactly at the first eligible integer, whether their enrolment increment is exactly the minimum necessary to cross, and whether they then fall back below the threshold one year later.

The true threshold 250/251 is compared with fake thresholds 200/201 and 300/301.

## 3. Exact landing at 251 is rare

Among broad State-government schools beginning within 20 pupils below 250, the distance-standardised probability of landing exactly at 251 is:

| Starting cohort | P(land exactly 251) |
|---|---:|
| 2018-19 | 1.43% |
| 2019-20 | 1.65% |
| 2020-21 | 1.76% |
| 2021-22 | 1.12% |
| 2022-23 | 0.76% |
| 2023-24 | 0.93% |

These rates are extremely similar to the corresponding probability of landing exactly one pupil above the placebo thresholds.

Examples:

- 2018-19: 200/201 placebo 1.45%, true 250/251 1.43%, 300/301 placebo 1.22%.
- 2019-20: 1.75%, **1.65%**, 1.40%.
- 2020-21: 1.98%, **1.76%**, 1.40%.
- 2022-23: 0.71%, **0.76%**, 0.72%.

There is no large national excess of schools moving by exactly the minimum number of pupils necessary to hit 251.

## 4. Reversion looks dramatic but also occurs at placebo thresholds

Schools landing exactly at 251 frequently fall back below 251 the following year. The reversion rate is about:

- 2018-19: 40.6%
- 2019-20: 31.5%
- 2020-21: 61.7%
- 2021-22: 68.1%
- 2022-23: 70.2%
- 2023-24: 60.0%

Taken alone, this could look suspicious. But the placebo thresholds show similarly high reversion.

For example:

- 2020-21 exact landing: 200/201 reversion 63.5%, true 250/251 61.7%, 300/301 55.2%.
- 2021-22: 74.3%, **68.1%**, 75.0%.
- 2022-23: 67.8%, **70.2%**, 60.3%.

High reversion therefore appears to be a general property of school enrolment around arbitrary local thresholds, especially in the pandemic/post-pandemic years, rather than a distinctive 250/251 fingerprint.

## 5. Enrolment-integrity conclusion

The density data are compatible with some threshold-related sorting, particularly in the earlier years. But the longitudinal forensic signatures that would make strategic recruitment or false reporting more persuasive do not distinguish 250/251 from placebo thresholds.

The defensible conclusion is:

> **Reported enrolment displays a modest, repeatable excess immediately above the 250/251 CSG threshold, strongest in the earlier cohorts. However, schools do not disproportionately land exactly at 251 or revert after doing so relative to comparable fake thresholds. The evidence does not establish systematic threshold gaming, fabricated pupils, or fraud.**

A density spike can arise from legitimate recruitment, ordinary heaping, natural enrolment volatility, reporting processes or strategic behaviour. UDISE aggregate data alone cannot adjudicate false-student reporting.

---

# Part III. Dynamic State response curves

## 6. Why fixed T+3 is not enough

T+3 remains the correct common comparison point because documentary and national empirical evidence place the major formula response there. But a common T+3 snapshot does not distinguish:

- a State that responds quickly and has already reached its plateau;
- a State that is slow but catches up later;
- a State that remains weak at all observed lags.

A new dynamic analysis therefore estimates the 250/251 first stage for each State at every available lag from the assignment cohort forward.

For each State/cohort it records:

- response at every lag;
- peak observed response;
- lag of the peak;
- first lag reaching 50%, 80% and 90% of the observed peak;
- raw right-side P(receipt >= Rs 75,000), reported separately rather than conflated with the discontinuity.

## 7. National response time

Across all four correctly aligned cohorts, the national response peaks at **T+3**:

| Assignment cohort | Peak first stage | Peak lag | First lag reaching 80% of peak |
|---|---:|---:|---:|
| 2019-20 | 24.80 pp | +3 | +3 |
| 2020-21 | 32.41 pp | +3 | +3 |
| 2021-22 | 32.53 pp | +3 | +3 |
| 2022-23 | 32.72 pp | +3 | +3 |

The national raw share of schools just above the threshold reporting >= Rs 75,000 never reaches 80% in these cohort-specific dynamic windows. This is another reason not to define successful administration as reaching 100% raw reporting.

## 8. State latency and strength are separate dimensions

Restricting interpretation to lags 0 through +3, the four-cohort mean T+3 first stage is approximately:

- Chhattisgarh 66.9 pp
- Uttar Pradesh 66.5 pp
- Haryana 55.2 pp
- Gujarat 45.8 pp
- Jharkhand 35.0 pp
- Rajasthan 27.7 pp
- Assam 26.6 pp
- Tamil Nadu 26.0 pp
- Bihar 18.6 pp
- Madhya Pradesh 16.7 pp
- Andhra Pradesh 14.6 pp
- West Bengal 14.0 pp
- Odisha 8.0 pp
- Maharashtra 7.9 pp
- Karnataka 7.9 pp
- Punjab 7.4 pp
- Uttarakhand 5.1 pp
- Telangana 3.2 pp.

But this ranking alone hides timing. Telangana is the clearest example: its four-cohort mean response is about **16.2 pp at T+2 but only 3.2 pp at T+3**, indicating a systematically earlier financial-record pattern than the national clock. Odisha and Punjab also often attain much of their observed response before +3.

Conversely, some States have older cohorts whose largest later response occurs after +3. Those later peaks must be interpreted cautiously because subsequent annual CSG allocation cycles can enter the later UDISE fields.

Therefore the fixed T+3 result should remain the common causal/administrative benchmark, while the full curve is used to describe timing heterogeneity.

---

# Part IV. School-level time to first higher-band recognition

## 9. Cleaner T+N design

To get closer to the intuitive question 'after a school crosses the threshold, how long until the higher band appears?', the audit defines:

- **crosser**: school moves from 221-250 to 251-280;
- **control**: school remains in 221-250;
- crosser is censored when it falls back to <=250;
- control is censored when it crosses above 250;
- event is first later UDISE report of CSG receipt >= Rs 75,000.

This is a recorded-recognition measure, not proof that the original grant tranche arrived at that date.

## 10. National cumulative recognition curves

### 2019-20 crossing cohort

| Lag | Crosser ever >=75k | Control ever >=75k | Net separation |
|---|---:|---:|---:|
| +3 | 56.5% | 16.3% | **40.3 pp** |
| +4 | 73.0% | 21.6% | **51.4 pp** |
| +5 | 82.7% | 29.5% | **53.3 pp** |
| +6 | 87.9% | 34.7% | **53.2 pp** |

80% of the eventual observed net separation is reached at **T+4**.

### 2020-21 crossing cohort

| Lag | Crosser | Control | Net |
|---|---:|---:|---:|
| +2 | 30.5% | 17.9% | 12.5 pp |
| +3 | 69.3% | 23.4% | **45.9 pp** |
| +4 | 82.4% | 30.3% | **52.1 pp** |
| +5 | 88.3% | 35.4% | **52.9 pp** |

80% of eventual net separation is reached at **T+3**.

### 2021-22 crossing cohort

| Lag | Crosser | Control | Net |
|---|---:|---:|---:|
| +1 | 23.4% | 18.7% | 4.7 pp |
| +2 | 35.9% | 24.0% | 11.9 pp |
| +3 | 68.5% | 31.1% | **37.4 pp** |
| +4 | 78.0% | 35.9% | **42.1 pp** |

80% of the observed net separation is reached at **T+3**.

### 2022-23 crossing cohort

Only through +3 is currently observable:

| Lag | Crosser | Control | Net |
|---|---:|---:|---:|
| 0 | 21.1% | 18.7% | 2.4 pp |
| +1 | 33.1% | 25.7% | 7.4 pp |
| +2 | 46.0% | 33.1% | 12.9 pp |
| +3 | 66.4% | 37.7% | **28.7 pp** |

The large common background rate among controls demonstrates why raw 'percentage of eligible schools ever reporting >=75k' cannot be read as entitlement fulfilment.

## 11. State time-to-recognition typology

Across all four crossing cohorts with adequate support, the crosser-minus-control event-time curves suggest a useful two-dimensional classification.

### High-strength, approximately T+3 systems

- Uttar Pradesh
- Jharkhand
- Haryana
- Gujarat
- Chhattisgarh

Their net crossing signal is large and generally reaches most of its observed strength around +3.

### Earlier-response systems

- Odisha
- Telangana

Their event-time signal often develops earlier than the national modal clock.

### Slower systems

- Bihar
- Madhya Pradesh
- Maharashtra
- Karnataka

In the event-time curves, the average lag reaching 80% of observed net separation is later, around 3.5 for Bihar and about 4.5 for Madhya Pradesh, Maharashtra and Karnataka.

### Weak recorded crossing signal

- Karnataka
- Tamil Nadu
- Punjab

These have relatively small crosser-control net separation even when followed forward. Weakness and latency should not be conflated: a State can be fast but weak, or slow but eventually stronger.

This State typology should be treated as administrative-record evidence, not an audited ranking of States by actual grant-payment speed.

---

# Part V. What should enter the paper

The two extensions materially improve the study.

## Enrolment integrity

Show the year-by-year 0-400 enrolment densities as an intuitive descriptive figure. Pair them with the heaping-adjusted 250/251 counterfactual and the exact-crossing/placebo analysis. The figure can motivate scrutiny, while the longitudinal tests prevent overclaiming.

The paper should say that modest bunching exists but the evidence does not establish strategic manipulation or fabricated enrolment.

## Administrative latency

Retain T+3 as the common national benchmark. Add an event-time State figure with:

- x-axis: lag after crossing;
- y-axis: crosser-minus-control cumulative probability of ever reporting >= Rs 75,000;
- one curve per State or a selected set of State archetypes.

Then summarise States using two quantities:

1. **latency**: N80, first lag reaching 80% of the observed net response;
2. **strength**: eventual observed net response / plateau.

A State scatter of latency versus strength would distinguish fast-strong, slow-strong, fast-weak and slow-weak administrative systems.

## Important limitation

Later event-time recognition can reflect a later annual grant cycle rather than literal late arrival of the original allocation. For this reason the object should be called **time to recorded higher-band recognition**, not 'payment delay of the original grant'.

The combination of the documentary T+3 clock, dynamic RD curves and persistent-crosser recognition curves is much stronger than replacing the original T+3 analysis with a single T+N statistic.
