# CSG social-equity extension: completed diagnostics and execution status

## Purpose

This note records what has actually been estimated for the social-composition extension of the Composite School Grant study and, equally importantly, what has not yet been estimated. It must not be read as evidence of discriminatory CSG implementation until the correctly timed heterogeneous RD has successfully executed.

## 1. Government-school universe

The original CSG timing analysis restricts management to UDISE codes 1, 2 and 3: Department of Education, Tribal Welfare Department and Local Body schools.

A broader State/UT-government definition used in the repository's earlier social-accountability work is codes 1, 2, 3, 6, 89 and 90. Government-aided and private management categories are separate and are not included in this broad State/UT-government definition.

In the successfully processed 2024-25 school data, the management counts are:

- code 1: 774,126
- code 2: 39,771
- code 3: 194,059
- code 6: 865
- code 89: 25
- code 90: 2,287
- main central-government codes 92, 93, 94, 95, 96 and 101 together: 2,158

Thus the original codes 1/2/3 contain 1,007,956 schools, while the broader State/UT-government codes 1/2/3/6/89/90 contain 1,011,133 schools. The additional verified State/UT-government categories add only 3,177 schools, approximately 0.315 percent relative to the original core sample. Adding the main central-government categories would add a further 2,158 schools.

Implication: the original CSG result is already estimated on almost the entire broad State/UT-government universe in 2024-25. Expanding management eligibility is an important robustness check but is quantitatively unlikely, by itself, to overturn the national timing result.

## 2. Social-composition definitions

The validated UDISE 2024-25 extraction uses separate marginal classifications:

Social category:

- General: item_group 1, item_id 1
- SC: item_group 1, item_id 2
- ST: item_group 1, item_id 3
- OBC: item_group 1, item_id 4

Religion/minority classification:

- Muslim: item_group 2, item_id 5
- Christian: item_group 2, item_id 6
- Sikh: item_group 2, item_id 7
- Buddhist: item_group 2, item_id 8
- Parsi: item_group 2, item_id 9
- Jain: item_group 2, item_id 10

Religion and social category are overlapping margins. A Muslim student may also be OBC, SC or ST. Therefore total minus Muslim/Christian/etc minus SC/ST/OBC is not a valid 'Hindu General' measure. No such residual is used in the new analysis.

## 3. The causal social-equity experiment that has been implemented

The committed analysis `social_equity/run_social_equity.py` is designed to estimate whether the correctly timed 250/251 CSG first stage changes with school social composition.

Its principal specification is:

- enrolment vintages 2019-20, 2020-21, 2021-22 and 2022-23;
- financial outcomes from the correctly aligned UDISE +3 reporting rounds;
- cutoff coordinate 250.5 and +/-30 enrolment window;
- broad State/UT-government sample 1/2/3/6/89/90 as the principal expanded universe;
- original 1/2/3 sample as the conservative replication;
- previous-year social composition as the preferred predetermined heterogeneity variable;
- continuous social-composition interaction as the inferential specification;
- 5-percentage-point social-composition bins as the presentation specification;
- year, state-by-year and district-by-year fixed-effect versions;
- management, rural/urban and school-category adjustment;
- state-clustered inference and Benjamini-Hochberg correction across group families;
- whole-universe reported-fidelity gradients as descriptive complements;
- state-specific gradients and school first-difference diagnostics.

It covers Muslim, Christian, Sikh, Buddhist, Parsi and Jain shares, and General, SC, ST and OBC shares. Religion and caste/social-category margins are never combined by subtraction.

## 4. Execution status of the causal social-equity experiment

The workflow `CSG social equity analysis` was triggered as GitHub Actions run 31869977299.

The job did not start. GitHub rejected it before runner startup with the platform message that recent account payments had failed or the Actions spending limit needed to be increased.

Therefore there are no valid new four-cohort heterogeneous-RD coefficients to report. In particular, this project does not currently establish that the CSG first stage is smaller or larger for Muslim-, SC-, ST-, OBC- or other socially concentrated schools.

This is an execution/access limitation, not an empirical null and not a failed statistical model.

## 5. Completed 2024-25 adjusted grant-intensity diagnostic

A separate earlier analysis had already estimated 2024-25 cross-sectional associations between social composition and `grant_per_student` on 1,462,231 recognised schools. This is not the correctly lagged CSG RD and includes recognised management types beyond the CSG-eligible government universe, although it includes management-category controls.

The district-fixed-effect model controls for:

- Muslim share;
- General, SC and ST shares, with OBC as the omitted social-category component;
- log total enrolment;
- lowest and highest class;
- minority-managed status;
- shift-school status;
- residential-school status;
- rural/urban category;
- management-category indicators;
- school-category indicators.

Standard errors are clustered by district. There are 782 district clusters.

For a 10-percentage-point increase in the relevant share, the district-fixed-effect associations with reported grant per student are:

| Composition margin | Rupees per student per +10 pp | SE | 95% CI | Approx. p-value |
|---|---:|---:|---:|---:|
| Muslim share | -8.50 | 2.38 | -13.15 to -3.84 | 0.00035 |
| General share | +4.69 | 2.61 | -0.42 to +9.79 | 0.0721 |
| SC share | -9.00 | 2.26 | -13.43 to -4.57 | 0.000069 |
| ST share | -6.41 | 2.46 | -11.23 to -1.60 | 0.00906 |

Interpretation: conditional on the observed geography and school-structure controls, higher Muslim, SC and ST composition is associated with lower reported grant intensity per student in this 2024-25 cross-section. This is a reason to run the CSG formula-fidelity experiment, not a substitute for it. It does not identify CSG entitlement, the correct historical enrolment vintage, or discriminatory treatment.

## 6. Completed raw 2024-25 social gradients

The older comprehensive analysis also generated raw all-recognised-school concentration gradients. These are highly non-monotonic and differ greatly by social group, illustrating the importance of geography, management and school composition.

Examples comparing >0-5% group concentration with >75-100% concentration:

### No reported grant

- Muslim: 62.92% to 52.02%
- General: 45.77% to 47.48%
- SC: 56.49% to 26.77%
- ST: 64.07% to 34.10%
- OBC: 37.55% to 50.28%

### Reported grant per student

- Muslim: Rs 308.16 to Rs 342.47
- General: Rs 347.31 to Rs 591.26
- SC: Rs 288.52 to Rs 845.10
- ST: Rs 222.69 to Rs 753.51
- OBC: Rs 440.36 to Rs 413.02

Grant-utilisation rates in the same aggregate tables are generally around the mid-90-percent range and are much flatter than grant receipt/intensity.

These raw curves cannot be interpreted causally. They mix management systems, geography, school size, school stage and other determinants of funding.

## 7. Completed government-only need-conditioned diagnostic

An earlier accountability analysis restricts explicitly to State/local-government management codes 1,2,3,6,89,90. It contains both a `major_repair` indicator and `major_repair AND no_grant_received`. Their student-weighted affected-population ratio provides a descriptive measure of the share of students in schools with major-repair need whose school also reports no grant.

Nationally, comparing social-concentration bands:

### Muslim concentration

- >0-5% Muslim: 20.74% no-grant conditional on major repair
- >5-10%: 20.85%
- >10-20%: 19.28%
- >20-30%: 18.14%
- >30-40%: 16.31%
- >40-50%: 14.76%
- >50-75%: 14.17%
- >75-100%: 15.57%

### General concentration

At >75-100% General concentration, the corresponding student-weighted conditional no-grant share is 10.22%. Thus the high-concentration Muslim-General difference is about +5.35 percentage points in this particular need-conditioned measure.

This does not establish a general grant-receipt gap. Conditioning on major repair changes the estimand, and major repair itself is socially and geographically patterned.

## 8. State heterogeneity in the government-only diagnostic

For schools in the >75% concentration band, the government-only student-weighted conditional no-grant shares among major-repair schools are:

| State | Muslim | General | Muslim-General gap |
|---|---:|---:|---:|
| Assam | 21.38% | 21.38% | approximately 0.00 pp |
| Bihar | 45.60% | 40.82% | +4.78 pp |
| Jharkhand | 9.60% | 5.09% | +4.51 pp, weak General high-band support |
| Uttar Pradesh | 6.34% | 8.29% | -1.95 pp |
| Uttarakhand | 10.05% | 3.76% | +6.30 pp |

The sign is not uniform across states. This is exactly why state-by-year and district-by-year versions are required for the planned CSG formula-fidelity experiment.

The same government-only state analysis does not show a uniform disadvantage ordering across SC, ST, OBC and General concentration either.

## 9. What can currently be concluded about social equity

Supported:

1. The original core CSG sample already covers almost all of the broad State/UT-government universe in 2024-25.
2. UDISE social composition can be reconstructed separately for religion and social category without inventing an invalid Hindu-General residual.
3. In a large 2024-25 adjusted cross-section, higher Muslim, SC and ST shares are associated with lower reported grant per student after district fixed effects and observed school controls.
4. Government-only need-conditioned grant diagnostics show some high-concentration Muslim-General gaps, but those gaps vary materially across states and can reverse sign.
5. These completed diagnostics justify the new heterogeneous CSG RD as a serious research question.

Not supported:

1. That CSG formula transmission is weaker for Muslim schools.
2. That CSG formula transmission is weaker for SC, ST or OBC schools.
3. That any observed grant association is evidence of discriminatory intent.
4. That the 2024-25 cross-sectional grant-per-student coefficient measures CSG entitlement or CSG underpayment.
5. That a Hindu-General or upper-caste-Hindu group can be recovered by subtracting the religion and caste margins.

## 10. Literature position after targeted search

The literature search found close but distinct bodies of work:

- causal work on school grants and household substitution in India and Zambia, notably Das, Dercon, Habyarimana, Krishnan, Muralidharan and Sundararaman (2013), but on a different grant and identification design;
- Samagra Shiksha budget and implementation briefs analysing aggregate allocations, releases, expenditure and component budgets rather than the school-level CSG formula discontinuity;
- DISE/UDISE research documenting caste-based school segregation and group inequalities;
- work on other RTE and school-policy interventions.

The search did not locate a published or working paper that reconstructs the CSG enrolment-to-finance reporting clock and exploits the 250/251 statutory school-level funding cliff in UDISE, nor one that estimates whether that formula first stage varies with school social composition.

The defensible novelty wording is therefore `we did not locate a close predecessor`, not `this is definitively the first study`.

## 11. Research decision

The social-equity extension should remain part of the project, but the paper must not be rewritten around a social-discrimination claim before the correctly timed government-only heterogeneous RD has executed.

The most informative possible outcomes are all publishable directions:

- no composition interaction after state/district controls: formula transmission is broadly socially neutral conditional on administrative geography;
- national gradient that disappears within states: inequality is primarily a federal/state-capacity composition effect;
- within-state gradient but no within-district gradient: sub-state geography explains the pattern;
- robust within-district heterogeneous first stage: a substantially stronger administrative-equity result requiring targeted mechanism investigation.

Until the blocked workflow runs, the strongest completed CSG contribution remains the corrected administrative timing and funding-fidelity result, with the 2024-25 social results treated as motivating diagnostics.