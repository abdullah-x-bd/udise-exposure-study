# Pre-analysis Design

## Motivation

The Composite School Grant is an annual recurring grant for government schools intended to support replacement of non-functional equipment and recurring school needs such as consumables, sanitation, electricity, internet, water, teaching aids, and minor maintenance. Grant entitlement is based on enrolment bands. This creates candidate discontinuities that may permit quasi-experimental estimation if actual grant receipt/expenditure changes sharply at the thresholds.

## Main estimand

The causal estimand of interest is the effect of a marginal increase in grant resources induced by an enrolment-band threshold on independently measured school conditions in subsequent UDISE+ rounds.

## Candidate assignment cutoffs

The national scheme architecture has used enrolment bands around 30, 100, 250, and 1000 pupils in recent years, with historical/state implementation variation possible. These are treated as candidate cutoffs only. The analysis will empirically verify the first-stage relationship by year and school type before using any cutoff for causal inference.

## Treatment measures

Preferred treatment measures, conditional on availability and cross-year comparability:

1. Composite/annual school grant received indicator.
2. Amount of school grant received.
3. Amount of school grant expenditure/utilisation.
4. Grant utilisation ratio where both amount received and expenditure are observed.

## Running variable and timing

The preferred running variable is the enrolment vintage actually used to determine the subsequent grant. Candidate lag structures will be tested explicitly, including same-year and one-/two-year lagged enrolment. The first-stage discontinuity determines the empirically supported timing.

## Primary independently recorded outcomes

Outcomes must not be mechanically constructed from treatment or from an index defined for this study. Candidate outcomes include:

- functional girls' toilet
- functional boys' toilet
- drinking-water availability/functionality
- handwashing facility
- functional electricity
- internet availability
- library availability
- classrooms requiring minor/major repair
- building condition
- functional computing equipment where consistently measured

Outcome eligibility requires consistent measurement on both sides of a tested threshold and across the relevant pre/post years.

## Mechanism/administrative outcomes

- inspections/official visits
- SMC/SDMC activity, if measured comparably
- subsequent grant expenditure/utilisation

These are secondary and will not replace the primary physical-condition outcomes.

## Designs

### 1. First-stage RD

Estimate local-linear discontinuities in grant receipt/expenditure around each candidate enrolment threshold, separately by academic year and plausible enrolment lag.

### 2. Sharp/fuzzy RD outcome estimates

If treatment probability/amount jumps at a threshold and validity diagnostics are acceptable, estimate the reduced-form outcome discontinuity. Where treatment is imperfect but the first stage is strong, report a fuzzy-RD/Wald estimate as a local treatment effect, with appropriate caution.

### 3. Panel threshold-crossing design

Track the same UDISE school code across years. Compare changes when a school crosses a validated funding threshold with changes among schools close to the threshold that do not cross, using school and year fixed effects and event-time diagnostics. This is a complementary design, not a substitute for RD validity.

## Validity diagnostics

- density/bunching around cutoffs
- predetermined covariate continuity
- school-code continuity and attrition
- school opening/closure/merger sensitivity
- bandwidth sensitivity
- polynomial/functional-form sensitivity, favouring local linear specifications
- placebo cutoffs
- placebo outcomes not plausibly affected by the grant over the relevant horizon
- state and management restrictions
- pre-trend/event-time tests in the panel design

## Causal language rule

If there is no credible first stage, substantial sorting around a cutoff, or severe covariate discontinuity, the corresponding estimate will be described as descriptive/associational and excluded from the headline causal result.