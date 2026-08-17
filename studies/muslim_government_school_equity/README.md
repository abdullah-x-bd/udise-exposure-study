# Muslim concentration and government-school administrative response

## Scope

This study is restricted in its headline analyses to State/UT and local-government schools. The primary government universe is UDISE management codes 1, 2, 3, 6, 89 and 90. A conservative robustness universe uses codes 1, 2 and 3. Central-government managements are excluded from the headline estimand because the research question concerns State/UT administrative realization.

The exposure of interest is continuous Muslim enrolment share. No majority threshold defines treatment. Primary models use a 0-1 share and secondary outputs use five-percentage-point bins from 0 to 100 for transparent visualization.

Religion and social category remain separate marginal dimensions. General, SC, ST and OBC shares are controls and comparison gradients, not religious opposites. The residual of total enrolment after subtracting Muslim, Christian, Sikh, Buddhist, Parsi and Jain enrolment is retained as `religion_residual` until source semantics are formally validated. It is not labelled upper-caste Hindu. Because religion-by-social-category cross-tabs are unavailable, Hindu-General or upper-caste-Hindu enrolment cannot be point-identified. Fréchet bounds for the intersection of the residual religion group and General category may be reported as sensitivity analysis.

## National experiments

### 1. RTE staffing realization

Primary sample: State/UT/local-government schools with a clean Classes I-V span.

Policy cutoffs: 60/61, 90/91 and 120/121 pupils in Classes I-V. Each threshold implies one additional teacher under the RTE Schedule. The analysis estimates local-linear discontinuities in observed teacher strength and whether the discontinuity changes continuously with predetermined Muslim share.

Primary exposure: previous-year Muslim share. Frozen earliest-observed Muslim share is a robustness exposure.

Primary outcomes:

- total teachers
- teachers reported as serving primary grades where available
- probability of meeting the local statutory staffing band
- regular teachers
- contract teachers
- female teachers

Primary specification uses triangular kernel weighting, separate running-variable slopes on each side of the cutoff, district-by-year and cutoff-by-year fixed effects, predetermined SC/ST/OBC composition controls with General omitted, and State-clustered inference. Alternative bandwidths and district-clustered inference are robustness checks.

Required diagnostics:

- density and mass-point tables around every real cutoff
- predetermined covariate balance
- fake cutoffs
- alternative bandwidths
- donut specifications excluding the exact threshold-adjacent values
- timing checks using contemporaneous and next-year teacher outcomes
- multiplicity correction across the confirmatory family

The design is described as quasi-experimental unless manipulation diagnostics support stronger language.

### 2. Failure-to-repair

The event population consists of government schools that move from an observed compliant/functional state in year t-1 to the same documented failure in year t.

Confirmatory failure families:

- girls' functional toilet loss, among schools enrolling girls
- boys' functional toilet loss, among schools enrolling boys
- loss of functional drinking water
- loss of functional electricity where coding is harmonizable
- onset of one or more classrooms requiring major repair

For every incident failure the pipeline measures restoration within one, two and three subsequent academic years where follow-up is observable. Muslim share is measured before failure onset. Models compare like failures within district-by-onset-year cells and control for baseline school size, SC/ST/OBC composition, rural/urban status, management and relevant baseline facility stock. Inference is State-clustered with district-clustered sensitivity and FDR correction across the failure family.

This experiment estimates differential administrative remediation conditional on the same observed failure. It does not by itself randomize Muslim concentration.

### 3. Need-to-inspection response

A predetermined school-need measure is constructed only from school-condition variables, never from subsequent inspections. The confirmatory version uses the available share of the following deficiencies:

- no functional girls' toilet when girls are enrolled
- no functional boys' toilet when boys are enrolled
- no functional drinking-water source
- electricity unavailable or non-functional
- at least one classroom requiring major repair

The outcome is administrative attention in the following UDISE year. Outcomes include academic inspections, CRC visits, block-level visits, district/State-level visits, total visits, and a senior-administration visit indicator.

The primary panel specification absorbs school fixed effects and district-by-year fixed effects. The key term is current documented need interacted with frozen baseline Muslim share. Parallel need interactions with baseline SC, ST and OBC shares are included so the Muslim interaction is not merely a generic disadvantaged-composition gradient. Time-varying enrolment is controlled separately. State-clustered inference is primary and district-clustered inference is a sensitivity check.

## Baseline national profile

Before interpreting any experiment, the workflow produces an all-government-school national baseline by year and by five-percentage-point Muslim-share bins. It reports school counts, student counts and the raw distribution of staffing, infrastructure, need and inspection variables. These descriptive gradients are not treated as causal estimates.

## Guardrails

- School-level microdata and derived school-year panels are temporary working files and are never uploaded as GitHub artifacts.
- Only aggregate tables, diagnostics and figures are uploaded.
- Missing source variables fail explicitly rather than being silently treated as zero.
- Every analysis retains the exact number of schools, States, districts and clusters used.
- Religion/caste intersections are never invented from marginal tables.
- Headline claims require replication across years, robustness to the conservative management universe, and survival of the prespecified falsification tests.
