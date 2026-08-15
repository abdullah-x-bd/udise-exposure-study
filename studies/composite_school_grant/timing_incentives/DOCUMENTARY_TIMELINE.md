# Documentary timing evidence for Composite School Grant

This note records documentary evidence about which UDISE enrolment vintage is used for Composite School Grant allocation. It is intentionally separate from the empirical lag tests.

## Delhi 2019-20

Official Samagra Shiksha Delhi circular `F. DE(61)/SS/2019-20` states that the 2019-20 Composite School Grant for 2,735 government schools was approved **as per U-DISE data for 2017-18**.

The same circular states the applicable bands:

- enrolment <=100: Rs 25,000
- >100 and <=250: Rs 50,000
- >250 and <=1000: Rs 75,000
- >1000: Rs 100,000

It also states that funds were to be transferred directly to the Samagra Shiksha account of recipient schools.

Source: https://www.edudel.nic.in/upload/upload_2019_20/3719_50_dt_05082019b.PDF

Implication: a same-labelled-year comparison of 2019-20 enrolment with 2019-20 grant receipt is not the documented assignment rule in Delhi. The documented enrolment vintage is two academic years earlier.

## Delhi 2022-23

Official Samagra Shiksha Delhi circular `F. DE.29(10)/SS/Composite School Grant/03/253/2022-23` states that the 2022-23 Composite School Grant for 2,578 government schools was approved **as per U-DISE data for 2020-21**. The circular explicitly says enrolment is taken from Classes I-XII.

The circular reports the following bands:

- enrolment <=30: Rs 10,000
- >30 and <=100: Rs 25,000
- >100 and <=250: Rs 50,000
- >250 and <=1000: Rs 75,000
- >1000: Rs 100,000

Source: https://www.edudel.nic.in/upload/upload_2023_24/3091_3101_dt_02012023.pdf

Implication: the two-academic-year vintage gap is not confined to the scheme's first year. It is explicitly present in Delhi's 2022-23 allocation documentation as well.

## Later Delhi lists

A later Delhi grant-list document surfaced on the Directorate's circular archive with grant-list rows explicitly carrying `Session 2021-22` enrolment. This supports the need to distinguish the grant/release year from the enrolment vintage rather than assuming the two clocks coincide.

Source: https://www.edudel.nic.in/upload/upload_2023_24/2359_64_dt_14022024.pdf

Because the file's parsed headings mix grant/session labels, it is being used only as corroborating timing evidence, not as the definitive mapping for a particular funding year.

## Consequence for the empirical design

The primary empirical object must be a full lead-lag surface:

`enrolment in assignment vintage t -> reported CSG receipt/expenditure in t+k`

for all feasible negative and positive `k` in the eight-year panel.

Negative lags are falsification leads. Positive lags identify the empirical arrival profile. Documentary evidence is used to pre-specify plausible administrative lags and to avoid choosing a lag merely because it gives the largest coefficient.

The 250/251 threshold is represented as a continuous RD coordinate of **250.5**, because 250 remains in the Rs 50,000 band and 251 is the first integer in the Rs 75,000 band.

## Outcome observability

The Delhi utilisation guidelines also make clear why coarse UDISE stock outcomes are a weak primary endpoint for small marginal CSG spending. Permitted uses include recurring consumables, play material, newspapers, electricity/internet/water charges, teaching aids, maintenance/repair, sanitation supplies, activities, transport and honoraria. Such expenditures can be useful while leaving binary or coarse school-asset indicators unchanged.

Therefore, outcome analyses are retained as secondary mechanism tests. The primary new questions are timing, formula implementation and behavioural responses around funding cliffs.
