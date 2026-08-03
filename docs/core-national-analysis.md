# Core national comparative analysis

## Central purpose

The principal study is a national school-level analysis of the schooling conditions experienced by Muslim students compared with the conditions associated with increasing concentrations of General, Scheduled Caste, Scheduled Tribe and Other Backward Class students in UDISE+ 2024-25.

The analysis is not restricted to Muslim-majority schools. Its main design is continuous: it measures how school conditions change as the share of each focal group rises, and then compares those gradients across groups.

## Focal groups

All group counts are calculated by school, class and gender from Enrolment 1.

| Code | Group | School-level count | School-level share |
|---|---|---|---|
| A0 | Muslim | Muslim enrolment | Muslim enrolment divided by reconciled total enrolment |
| B0 | General | Total enrolment minus SC minus ST minus OBC, equivalent to the General item after reconciliation | General enrolment divided by reconciled total enrolment |
| C0 | Scheduled Caste | SC enrolment | SC enrolment divided by reconciled total enrolment |
| D0 | Scheduled Tribe | ST enrolment | ST enrolment divided by reconciled total enrolment |
| E0 | Other Backward Class | OBC enrolment | OBC enrolment divided by reconciled total enrolment |

`B0` is General, not non-Muslim and not Hindu. The source records religion and caste as separate aggregate dimensions. A Muslim student can also be represented within one of B0, C0, D0 or E0. The microdata do not identify the individual-level cross-tabulation.

The denominator for A0 is not the sum of the listed minority-religion items because the schema does not include a Hindu item. The denominator will be the reconciled total derived from General, SC, ST and OBC enrolment, subject to class-and-gender consistency checks.

## Main comparisons

The primary comparisons are:

1. A0 versus B0
2. A0 versus C0
3. A0 versus D0
4. A0 versus E0
5. B0 versus C0
6. B0 versus D0
7. B0 versus E0

C0 versus D0, C0 versus E0 and D0 versus E0 will be retained as supplementary caste-composition comparisons, but they are not the principal frame of the study.

## Meaning of “as students increase”

For each group, schools will be ordered by the group’s enrolment share. The analysis will not rely on one majority threshold. It will estimate conditions across the full distribution using:

- zero-enrolment versus positive-enrolment status
- fixed share bands: 0, above 0 to 5, 5 to 10, 10 to 20, 20 to 30, 30 to 40, 40 to 50, 50 to 75 and 75 to 100 percent
- national deciles among schools with positive group enrolment
- within-state deciles
- within-district relative ranks where district sample sizes permit
- continuous shares modelled flexibly with restricted cubic splines

Every major result will therefore show whether disadvantage appears gradually, only after a threshold, or not at all.

## Three distinct estimands

### 1. School-condition gradient

Each school receives equal weight. This answers:

> How do the characteristics of schools change as A0, B0, C0, D0 or E0 concentration rises?

For every outcome, report the school mean or prevalence in each share band and estimate the continuous gradient.

### 2. Total-student exposure

Schools are weighted by total enrolment. This answers:

> What conditions does the average student experience at different school-composition levels?

This prevents very small and very large schools from being treated as equally important to the student population.

### 3. Group-student exposure

Schools are weighted by focal-group enrolment. For group g and school condition k:

`Exposure(g, k) = sum_s enrolment(g,s) * condition(k,s) / sum_s enrolment(g,s)`

This answers:

> What share of Muslim, General, SC, ST or OBC students attend schools with the specified condition?

This is the principal national comparison of actual student exposure.

## Pairwise analytical design

### A0 compared with B0, C0, D0 and E0

A0 is a religion share and B0 to E0 are caste shares. They are not mutually exclusive. Each pair will therefore be analysed using both shares simultaneously.

For each pair A0-X0:

1. Plot the separate A0 and X0 one-dimensional gradients for the same outcome.
2. Build a two-dimensional grid using A0 quintiles and X0 quintiles.
3. Report the average outcome in every observed cell and suppress cells with inadequate school counts.
4. Construct four descriptive categories using within-state medians or quartiles:
   - low A0, low X0
   - high A0, low X0
   - low A0, high X0
   - high A0, high X0
5. Estimate an adjusted model containing A0 share, X0 share and their interaction.
6. Estimate flexible versions using spline terms rather than assuming a straight line.

The high-A0, high-X0 category describes a school environment in which both groups are highly represented. It does not identify individual Muslim-General, Muslim-SC, Muslim-ST or Muslim-OBC students.

### B0 compared with C0, D0 and E0

B0, C0, D0 and E0 are components of the same caste composition and sum to one after reconciliation. A direct regression containing all four shares and an intercept is perfectly collinear.

For each pair B0-X0, the analysis will use:

- a two-dimensional descriptive grid of B0 and X0 shares
- separate concentration gradients
- a pair-composition measure `B0 / (B0 + X0)` among schools where the pair total is positive
- the combined pair share `(B0 + X0)` as a separate control
- the remaining caste composition as contextual controls
- compositional log-ratio specifications as robustness checks

This separates a shift from X0 toward B0 within the pair from a school simply having a larger combined B0-X0 population.

## Outcome domains

The main analysis will cover every outcome that the source can support, grouped into coherent domains. Domain-specific measures remain primary. Composite indices are summaries, not substitutes for individual indicators.

### A. School access and class span

- school offers primary grades
- school offers upper-primary grades
- school reaches Class 10
- school reaches Class 12
- school ends at Class 5
- school ends at Class 8
- school ends at Class 10
- enrolment exposure to schools ending before Class 10
- enrolment exposure to schools ending before Class 12
- pre-primary availability
- Balavatika availability
- Anganwadi inside the school
- all-weather road accessibility
- residential-school status
- shift-school status

The class-by-group data will also be used to compare each group’s representation across primary, upper-primary, secondary and higher-secondary levels. These cross-sectional representation changes will not be labelled dropout or transition rates.

### B. Buildings and classroom capacity

- building status
- pucca-building availability
- boundary wall
- total classrooms
- classrooms per 100 students
- share of classrooms in good condition
- classrooms requiring minor repair
- classrooms requiring major repair
- separate head-teacher room
- furniture availability
- classroom crowding indicators

### C. Water, sanitation and hygiene

- any drinking-water source
- any functional drinking-water source
- functional tap water
- functional hand pump
- functional protected well
- functional boys’ toilets
- functional girls’ toilets
- functional toilet seats per 100 boys or girls
- CWSN-friendly toilets
- handwashing near toilets
- handwashing facility for meals
- rainwater harvesting

Girls’ toilet exposure will be calculated using group-specific girls’ enrolment weights.

### D. Electricity, library and general learning environment

- functional electricity
- solar panels
- library
- book bank
- reading corner
- playground
- alternative play area
- medical check-ups

### E. Digital conditions

- internet
- computer or ICT laboratory
- ICT laboratory under Samagra Shiksha
- desktop, laptop and tablet availability
- devices per 100 students
- digital boards
- smart classrooms
- projectors
- printers
- servers
- DTH
- computer-trained teachers

### F. Science and subject facilities

Among schools whose class span makes the facility relevant:

- physics laboratory
- chemistry laboratory
- biology laboratory
- mathematics laboratory
- computer-science laboratory
- language laboratory
- geography laboratory
- home-science laboratory
- psychology laboratory

A school will not be penalised for lacking a laboratory that is not relevant to its grade span.

### G. Teachers and staffing

- total teachers
- student-teacher ratio
- teachers per 100 students
- single-teacher school
- school with two or fewer teachers
- no female teacher
- female-teacher share
- regular-teacher share
- contract-teacher share
- part-time-teacher share
- below-graduate, graduate and postgraduate teacher shares
- no professionally qualified teacher
- B.Ed or equivalent share
- D.El.Ed share
- computer-trained teacher availability
- CWSN-trained teacher availability
- special-educator availability
- teachers engaged in non-training assignments
- coverage of primary, upper-primary, secondary and higher-secondary grades by relevant teachers

Teacher caste counts will support separate SC, ST, OBC and General teacher-representation analysis. The source does not provide teacher religion, so Muslim teacher representation cannot be measured.

### H. Governance, monitoring and resources

- academic inspections
- CRC coordinator visits
- block-level officer visits
- district or state officer visits
- SMC existence
- SMC or SMDC meeting frequency
- grants received
- grants spent
- grant received per student
- expenditure per student
- grant utilisation ratio
- free textbook provision
- free uniform provision
- special training for out-of-school children
- graded supplementary material

### I. Social vulnerability of the school environment

- BPL share
- EWS share
- repeater share
- CWSN share
- disability-category composition
- age-grade distortion
- over-age enrolment
- under-age enrolment
- girls’ share of enrolment

BPL, EWS, repeater, CWSN and age data are not cross-tabulated with religion or caste. The study can therefore say that Muslim students are more or less exposed to schools with high BPL, EWS, repetition, disability or age-grade-distortion levels. It cannot state the Muslim-specific BPL, EWS, repetition or disability rate.

### J. Institutional context

These are mainly stratifiers and controls rather than measures of advantage by themselves:

- rural or urban location
- state and district
- school management
- minority-managed status
- school category
- school type
- lowest and highest class
- enrolment size
- medium of instruction
- board affiliation

## Composite indices

Separate indices will be constructed for:

1. basic infrastructure deprivation
2. water and sanitation deprivation
3. digital deprivation
4. teacher scarcity and weakness
5. governance and resource deprivation
6. inclusion and accessibility deprivation
7. school-access deprivation
8. overall multidimensional school deprivation

The main version will use transparent equal weighting after orienting every component so that a higher value means worse conditions. Alternative standardised and data-driven weights will be robustness checks. Every index result must remain traceable to its component indicators.

## National descriptive outputs

For every outcome and group:

- number of schools in each share band
- number of group students represented in each band
- unweighted school condition
- total-student-weighted condition
- group-student-weighted exposure
- absolute gap from A0 to the comparison group
- relative ratio where substantively meaningful
- confidence interval

The principal national tables are:

1. national group composition and denominator reconciliation
2. national group exposure to school access limitations
3. national group exposure to basic infrastructure gaps
4. national group exposure to digital deprivation
5. national group exposure to teacher shortages
6. national group exposure to governance and resource gaps
7. social-vulnerability environment by group exposure
8. A0-B0, A0-C0, A0-D0 and A0-E0 pairwise surfaces
9. B0-C0, B0-D0 and B0-E0 pairwise caste-composition results
10. adjusted national association models

## Adjustment strategy

The study will present results in layers rather than hiding the raw national pattern behind one model.

### Model 0: unadjusted national association

Outcome against focal group share only.

### Model 1: state-adjusted

Add state fixed effects. This asks whether the national gradient remains after accounting for broad state differences.

### Model 2: district-adjusted

Add district fixed effects. This compares schools within the same district.

### Model 3: school-structure-adjusted

Add rural or urban location, management, school category, class span and enrolment size.

### Model 4: full pairwise model

Add both pair shares, their interaction or compositional balance, and the school-structure controls.

Binary outcomes will use linear probability models as the primary specification because coefficients are directly interpretable as percentage-point differences. Logistic models will be robustness checks. Continuous outcomes will use linear models or appropriate transformed specifications. Standard errors will be clustered by district.

## Heterogeneity and robustness

The national results will be checked separately by:

- rural and urban schools
- government, aided and private management
- minority-managed and non-minority-managed schools
- primary, upper-primary, secondary and higher-secondary school categories
- school-enrolment size
- state region
- exclusion of schools with very small enrolment
- alternative concentration bands
- national versus within-state ranks
- national versus within-district comparisons
- binary majority coding as a secondary presentation only

## Evidence standard for structural disadvantage

The report may describe a pattern as consistent with structural disadvantage when all or most of the following are present:

1. Muslim students have materially worse group-weighted exposure than the relevant comparison group.
2. School conditions worsen as A0 share rises across multiple domains rather than at one arbitrary cutoff.
3. The A0 gradient is worse than the comparison-group gradient.
4. The association remains within states or districts.
5. It remains after accounting for management, rural or urban location, class span and school size.
6. The result is not driven by one state, one management category or very small schools.
7. The pattern appears across several independently measured school-condition domains.

The analysis will not infer individual discrimination, household social conditions or causal effects from school-level cross-sectional associations alone.
