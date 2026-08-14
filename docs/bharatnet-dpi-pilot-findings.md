# BharatNet DPI and Rural School Digital Capability: Pilot Findings

## Status

This branch executes a first empirical pass on the proposed BharatNet-school digital capability study. It uses the private UDISE+ 2024-25 microdata already configured for the repository and a public BBNL archive of service-ready Gram Panchayats documented as updated on 2 March 2022. No school-level microdata are committed to GitHub; all results below are aggregates.

The current Hugging Face source contains only one UDISE+ year, 2024-25. Therefore the analysis below does **not** identify a causal effect of BharatNet. It establishes the national digital-capability bottleneck structure, validates Gram Panchayat linkage feasibility, and estimates descriptive historical-exposure associations as a diagnostic for a future panel design.

## 1. National and rural digital baseline

The 2024-25 processed data contain 1,471,473 schools and 232,885,600 students in the reconciled Classes 1-12 social-category enrolment total used here.

Among 1,210,062 rural schools:

- 60.32% report internet availability.
- 90.72% report functional electricity.
- 58.79% have at least one desktop, laptop, or tablet.
- 45.24% have at least one computer-trained teacher.
- 47.23% report an ICT/computer lab.
- Only 26.41% have the complete four-input stack defined here: functional electricity + at least one computing device + internet + at least one computer-trained teacher.
- Student-weighted exposure to that complete stack is 46.58%, indicating that larger rural schools are substantially more likely to have all four inputs.

## 2. Sequential bottleneck decomposition

The 1,210,062 rural schools separate as follows:

| Stack level | Bottleneck | Schools | Students | School share | Student share |
|---|---|---:|---:|---:|---:|
| 0 | No functional electricity | 112,336 | 7,278,806 | 9.28% | 4.67% |
| 1 | Electricity, but no computing device | 421,739 | 37,142,149 | 34.85% | 23.84% |
| 2 | Electricity + device, but no internet | 175,047 | 19,133,656 | 14.47% | 12.28% |
| 3 | Electricity + device + internet, but no computer-trained teacher | 181,410 | 19,662,593 | 14.99% | 12.62% |
| 4 | Complete digital capability stack | 319,530 | 72,569,054 | 26.41% | 46.58% |

The key policy implication is that a broadband connection is the next sequential missing input for 175,047 rural schools serving 19.13 million students, but connectivity alone would not complete the full stack for all of them because some also lack a trained teacher.

## 3. Exactly one input away from full readiness

A separate non-sequential gap count shows that 327,383 rural schools serving 38,320,674 students are exactly one input away from the complete four-input stack.

| Sole missing input | Schools | Students | Share of one-gap schools | Share of one-gap students |
|---|---:|---:|---:|---:|
| Computer-trained teacher | 181,410 | 19,662,593 | 55.41% | 51.31% |
| Internet connectivity | 77,334 | 10,248,955 | 23.62% | 26.75% |
| Computing device | 60,285 | 7,367,085 | 18.41% | 19.22% |
| Functional electricity | 8,354 | 1,042,041 | 2.55% | 2.72% |

Thus, among schools closest to becoming fully digitally capable, human capability is the largest single missing input. Internet is the second-largest.

Across all rural schools, the number of missing inputs is distributed as follows:

- Zero missing: 319,530 schools, 26.41%.
- One missing: 327,383 schools, 27.06%.
- Two missing: 306,700 schools, 25.35%.
- Three missing: 212,840 schools, 17.59%.
- All four missing: 43,609 schools, 3.60%.

## 4. Social-group student exposure

These are group-student-weighted school-environment measures. Religion and caste are separate marginal dimensions in UDISE+; therefore Muslim, General, SC, ST, and OBC are not five mutually exclusive individual categories.

Share of each group's rural students exposed to the complete digital stack:

- Muslim: 40.10%.
- General-category enrolment: 56.29%.
- SC: 41.56%.
- ST: 42.74%.
- OBC: 45.50%.

For Muslim students, the largest single sequential bottleneck is electricity being available but no computing device, representing 29.26% of Muslim-student exposure. A further 12.35% are exposed to schools with electricity and devices but no internet, and 13.20% to schools with electricity, devices, and internet but no computer-trained teacher.

## 5. Spatial heterogeneity

Across 759 rural district units with at least 10 schools:

- Median district internet availability is 63.71%; the 10th percentile is 27.05% and the 90th percentile is 97.40%.
- Median district complete-stack availability is only 22.09%; the 10th percentile is 8.44% and the 90th percentile is 78.08%.

This large dispersion means a national average conceals very different local constraint sets.

## 6. BharatNet 2022 historical-exposure linkage

The archived BBNL data contain 183,013 Panchayat rows and 170,272 service-ready GP rows. UDISE+ 2024-25 contains 251,695 rural state-district-block-GP name units covering 1,185,250 schools and 151,575,594 students.

Conservative exact/unique-name matching linked:

- 141,690 GP units, 56.29% of named UDISE GP units.
- 700,779 schools, 59.12% of schools in named UDISE GP units.
- 94,509,561 students, 62.35% of students in named UDISE GP units.
- 100,383 matched GPs are observed as service-ready in the archived 2022 BBNL list; 41,307 matched GPs are in BBNL's Panchayat universe but are not on that archived service-ready list.

The matching is deliberately conservative; unmatched UDISE GP names are not coded as untreated.

## 7. Early BharatNet status and 2024-25 outcomes

School-weighted raw differences between GPs observed service-ready by the March 2022 archive and matched GPs not on that service-ready list are:

- Internet: +6.39 percentage points.
- Functional electricity: +3.46 pp.
- All-weather road: +1.97 pp.
- Girls' functional toilet: +2.40 pp.
- Library: -0.64 pp.
- Any computing device: -4.27 pp.
- Computer-trained teacher: -1.11 pp.
- ICT lab: -5.26 pp.
- Complete digital stack: -0.15 pp.

The large changes in sign across outcomes indicate strong geographic composition/selection.

A simple within-block comparison among blocks containing both early-service-ready and not-yet-service-ready matched GPs reduces the internet difference substantially:

- Internet: +1.86 pp across 944 mixed blocks.
- Complete stack: +1.34 pp.
- Any computing device: +1.46 pp.
- Computer-trained teacher: +0.36 pp.
- ICT lab: +2.29 pp across 872 mixed blocks.

Non-digital comparison outcomes in the same within-block diagnostic are:

- Functional electricity: +1.26 pp.
- All-weather road: +1.33 pp.
- Girls' toilet: +0.15 pp.
- Library: -0.12 pp.

The raw +6.39 pp internet association should therefore **not** be interpreted as the causal effect of BharatNet. Early BharatNet deployment is spatially selected, and non-digital placebos are not uniformly zero. The within-block +1.86 pp internet association is directionally consistent with a positive pass-through, but one cross-section cannot distinguish treatment from residual selection.

## 8. Go/no-go conclusion

### Strongly supported by current data

1. Rural school digital readiness is a complementary-input problem rather than an internet-only problem.
2. Only about one quarter of rural schools currently have the complete four-input stack, although almost half of rural students attend such schools because readiness is concentrated in larger schools.
3. 327,383 rural schools are exactly one input away from full basic digital readiness; the dominant missing input among them is a computer-trained teacher, not internet.
4. There is a large, policy-relevant subgroup of 77,334 rural schools serving 10.25 million students for which internet connectivity is the **only** missing component of the four-input stack.
5. Rural students from different social-group environments have materially different exposure to complete digital capability.
6. School-to-GP linkage to a historical BBNL service-ready list is feasible at national scale, though current name-based coverage is incomplete.

### Not supported as a causal claim with the current source store

The repository currently has only UDISE+ 2024-25 microdata. A causal claim that BharatNet caused school internet adoption or digital capability is not identified from the present cross-section. The naive historical-exposure association is strongly attenuated by within-block comparison and some non-digital outcomes also differ.

## 9. Recommended paper/brief framing from the completed pilot

A defensible immediate policy brief can be framed as:

**Fibre Is Not Connectivity: Where Rural School Digitalisation Breaks Down**

Core question:

> Where are the binding constraints in translating rural digital public infrastructure into usable school-level digital capability, and which schools can be brought to full basic readiness through a single targeted input?

The 2022 BharatNet linkage should be presented as a historical-exposure diagnostic, not as the headline causal estimate.

A stronger causal research paper becomes possible once pre-2024 UDISE+ microdata and a defensible treatment-timing strategy are available. The repo code developed on this branch provides the baseline outcome definitions, GP linkage, matching diagnostics, social-exposure decomposition, and policy simulation needed for that extension.
