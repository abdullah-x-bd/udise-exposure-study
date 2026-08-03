# Complete A0 indicator system

## Research focus

A0 Muslim students are the substantive population of the study. B0 General, C0 Scheduled Caste, D0 Scheduled Tribe and E0 Other Backward Class are comparison baselines used to establish the scale, location and distinctiveness of Muslim educational disadvantage.

## Three indicator levels

### Primary indicators

Every directly recorded UDISE+ parameter is catalogued with its source table, column name and data type. Direct categorical fields whose meanings depend on the UDISE DCF remain labelled by raw code until the official codebook is supplied.

### Secondary indicators

Secondary indicators combine direct parameters into interpretable school conditions. They include social-group shares, class access, student-weighted exposure, classroom capacity, WASH adequacy, electricity, learning resources, digital access, staffing, teacher qualifications, governance, grants, welfare provision, CWSN support mismatch and age-grade distortion.

Every supported secondary condition is calculated for A0 and all four baselines. Outputs include national exposure, A0-minus-baseline disadvantage gaps, all pairwise baseline gaps, concentration gradients, Muslim-girls exposure, state comparisons and district profiles.

### Tertiary indicators

Tertiary indicators combine validated secondary conditions into equal-weight domain measures. They include access deprivation, infrastructure deprivation, WASH deprivation, digital deprivation, teacher-capacity deprivation, governance-response deficit, welfare-support deficit, inclusion failure, gendered disadvantage, educational-resource deficit, institutional need, institutional neglect, multidimensional deprivation, vulnerability context and compound vulnerability-deprivation.

The indices are summaries. The individual indicators remain the main evidence and every index is decomposable.

## Structural-disadvantage tests

The analysis tests whether Muslim disadvantage is visible in several layers.

1. Muslim student-weighted exposure
2. A0 gaps relative to B0, C0, D0 and E0
3. Worsening conditions as A0 concentration rises
4. A0 and baseline interaction grids
5. Within-state associations
6. Within-district associations
7. State and district persistence
8. Multiple independent school-condition domains
9. High documented need combined with weak institutional response

These layers can support a finding that the evidence is consistent with structural educational disadvantage. They do not directly prove discriminatory intent.

## Interpretation constraints

Religion and caste are separate marginal dimensions. A high-A0, high-E0 school has high Muslim and high OBC concentration. The data do not identify individual Muslim-OBC students.

Age, BPL, EWS, repeater and CWSN measures describe the school environment. They are not cross-tabulated with Muslim identity.

Teacher religion is unavailable. Muslim teacher representation cannot be measured.

UDISE+ does not directly provide Muslim attendance, learning outcomes, examination performance, household income, school-choice motives or individual experiences of discrimination.

## Output structure

The complete workflow produces an indicator catalog, source summaries, DCF raw-code audits, national and state exposure tables, baseline gaps, concentration gradients, gender comparisons, teacher-representation tables, interaction grids, fixed-effect associations, state profiles, district profiles, a structural-evidence profile and a graph for every supported secondary and tertiary indicator.

A school-level indicator Parquet file is stored only in the private Hugging Face dataset. GitHub artifacts contain aggregate tables, figures and reports.
