# Threshold-linked school programme registry

Purpose: distinguish the CSG assignment rule from overlapping national enrolment-linked programmes, and identify candidate positive-control thresholds. This is a national-programme registry, not an exhaustive registry of every state-specific scheme.

## 1. Composite School Grant, Samagra Shiksha

Running variable: total school enrolment, Classes I-XII in the Delhi implementation documents examined.

Current/revised bands documented in Delhi 2022-23 and 2024-25:

- <=30: Rs 10,000
- 31-100: Rs 25,000
- 101-250: Rs 50,000
- 251-1000: Rs 75,000
- >1000: Rs 100,000

Main study threshold: **250/251**, represented econometrically at 250.5.

Documented timing evidence:

- Delhi CSG 2019-20 used UDISE 2017-18.
- Delhi CSG 2022-23 used UDISE+ 2020-21.
- Delhi CSG 2024-25 used UDISE+ 2022-23.

Thus all three verified Delhi allocation orders use a two-academic-year-old UDISE enrolment vintage.

2024-25 Delhi order source: https://www.edudel.nic.in/upload/upload_2023_24/3083_95_dt_09122024.pdf
2019-20 Delhi order source: https://www.edudel.nic.in/upload/upload_2019_20/3719_50_dt_05082019b.PDF
2022-23 Delhi order source: https://www.edudel.nic.in/upload/upload_2023_24/3091_3101_dt_02012023.pdf

Role in study: principal formula-funding threshold.

## 2. PM POSHAN kitchen devices

Official PM POSHAN material states that kitchen-device assistance became enrolment-linked from 14 March 2019:

- up to 50: Rs 10,000
- 51-150: Rs 15,000
- 151-250: Rs 20,000
- above 250: Rs 25,000

The official web table appears to contain a typographical label for the last band but the schedule clearly introduces a higher unit cost beyond the 151-250 band.

Source: https://pmposhan.education.gov.in/Meal%20Provision.html

Overlap with CSG: **250/251**.

Role in study: serious coincident-rule confound. CSG robustness therefore includes samples whose Classes I-VIII enrolment is <=220 and <=200 while total Classes I-XII enrolment is around 250. This keeps the school well below the PM POSHAN 250-pupil running-variable threshold while retaining the CSG total-enrolment comparison.

## 3. PM POSHAN cook-cum-helper norms

Official PM POSHAN norms:

- one cook-cum-helper up to 25 students
- two cooks-cum-helpers for 26-100 students
- one additional cook-cum-helper for each additional block of up to 100 students

Source: https://pmposhan.education.gov.in/aboutus.html

Important thresholds: 25/26, 100/101, then subsequent 100-pupil increments.

Role in study: makes the CSG 100/101 cutoff especially unsuitable as a clean CSG causal design. It remains useful as a behavioural/bunching threshold, but any causal outcome interpretation at 100 would be confounded by other enrolment-linked programmes.

## 4. PM POSHAN kitchen-cum-store size norms

Official PM POSHAN material describes a base plinth-area norm for schools up to 100 children and additional area for each further block of up to 100 children, with state flexibility.

Source: https://pmposhan.education.gov.in/aboutus.html

Role in study: another reason not to treat 100/101 and subsequent 100-pupil boundaries as CSG-only discontinuities.

## 5. Additional ICT Lab under Samagra Shiksha

Delhi Samagra Shiksha issued an AWP&B 2025-26 sanction for **Additional ICT Lab (New), enrolment >700**, based on UDISE+ 2023-24 and PAB recommendations. Twenty-four Delhi schools were approved. The specified package includes measurable hardware such as five desktops/AIOs, computer tables, a printer, speakers, Wi-Fi setup and UPS equipment.

Role in study: **future positive-control candidate**, not a deterministic analogue to CSG. PAB selection is discretionary, and the available UDISE panel ends at 2025-26, likely too early to cleanly observe a post-installation 2026-27 stock response. It should not be presented as a completed positive control until a genuinely post-treatment UDISE round is available.

## 6. Library and sports grants

Samagra Shiksha provides library and sports grants differentiated primarily by school stage rather than the same total-enrolment cliffs used by CSG.

Role in study: not direct same-running-variable RD comparators.

## Classification for the empirical work

- 250/251 total school enrolment: CSG main threshold, but PM POSHAN kitchen-device overlap must be neutralised with Classes I-VIII restrictions.
- 100/101: heavily overlapping national rules and severe bunching, therefore not a clean causal CSG threshold.
- 30/31: CSG threshold, but smaller-school data and other programme rules require separate diagnostics.
- 1000/1001: CSG threshold, potentially useful but sample density is much smaller and large-school composition differs materially.
- >700: discretionary ICT-support threshold, useful as a future observability/positive-control design rather than an immediate CSG comparison.

## Residual limitation

This registry covers the national programmes identified in the red-team and documentary audit. It does not prove that no state-specific scheme uses exactly the same enrolment cutoffs. Any journal paper relying on an exclusion restriction should either construct a state-by-state scheme registry for the final analysis sample or present coincident state-specific rules as a residual limitation.
