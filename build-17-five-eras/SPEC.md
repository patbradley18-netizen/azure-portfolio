# Build #17 — Who was there to serve: five eras against their own civilian population

*Written before the ASEC extract landed. Builds on #15/#16 (inference method); new source and new cohort rule.*

## 1. Question

By era of service, how did the veteran population compare with the civilian population **of the same age at the same time** on race/ethnicity, sex, citizenship and generation, and education? Not "were veterans diverse" — *who served, against who was there.* The page reports representation and its uncertainty; it does not argue a position.

## 2. Source and cohorts

- March ASEC 1968–2025 (58 samples; `ASECWT`). Era = `VETLAST` (most recent period of service): WWII (04), Korea (06), Vietnam era (08), May 1975–Jul 1990 (10), Gulf War I Aug 1990–Aug 2001 (11), Sept 2001+ (12); peacetime codes 05/07/09 and pre-1941 pooled as "other". From 2006 `VET1–VET4` list up to four periods; a veteran is assigned to the **most recent** era throughout (consistent with pre-2006 coding) and the multi-era share is reported.
- No in-theater flags in the ASEC: these are era cohorts. Build #15's in-theater Vietnam and GWOT cohorts are referenced, not mixed in.
- Civilian reference: `VETSTAT` = 1 (no service) in the same survey year and age band (18–34, 35–49, 50–64, 65+). Cohort cells are reweighted to their own age mix within the comparison, as in build #16.

## 3. Measures (availability from the codebook)

| Measure | Variable | Years |
|---|---|---|
| Race/ethnicity: Hispanic; White non-Hispanic; Black; other | `HISPAN`, `RACE` | all (multi-race codes from 2003 → "other") |
| Sex | `SEX` | all |
| Citizenship: born citizen; naturalized; non-citizen | `CITIZEN` (1–3 / 4 / 5) | 1994+ |
| Generation: foreign-born; US-born with ≥1 foreign-born parent; both parents native | `NATIVITY` (5 / 2–4 / 1) | 1994+ |
| Education: < HS; HS; some college; BA+ | `EDUC` | all (1992 recode → four coarse bands) |

Statistics per cell: weighted share, approximate SE (effective n), difference in points ± 95% CI against the age-matched civilian reference, representation index, Cohen's h. Cells with effective n < 100 suppressed.

## 4. Views

- **By era, pooled over the years in which that era's veterans were 18–64** (the "working-age window": WWII 1968–1990, Korea 1968–2000, Vietnam 1968–2025, 1975–90 era 1975–2025, Gulf War I 1991–2025, post-9/11 2006–2025). This is the headline table.
- **By era and survey year** for the time-series panels (how each cohort's composition drifted with age and mortality).
- Survivor caveat: an era observed late (WWII in 2000) is its survivors; the pooled view weights early years where the cohort is complete.

## 5. Azure

`asec_person` created by the pipeline from the header; materialized view `era_base_mv`; ADX dashboard `azportfolio-eras` on the free cluster (data source: the cluster; tiles from the same KQL), linked from the page.

## 6. What this cannot say

Who enlisted or was drafted was decided before the survey saw them; the ASEC sees survivors living in households. Representation ≠ selection policy: a cohort can be whiter than its civilian peers because of who volunteered, who was drafted, who was deferred, who was excluded, who died, or who answers surveys — the data cannot split these. "Era" is a date range, not a deployment.

## Change log

- 2026-10-17 13:50 — written; ASEC codes confirmed from a two-sample smoke extract (#5); full extract #6 submitted.
- 2026-10-17 14:25 — after the data: `VETLAST` codes 10–12 exist from 2006 only (earlier years code post-Vietnam service as 09 "other"), so the three volunteer-era windows are 2006–2025; Hispanic item null before 1971; VETSTAT men-only before 1988; EDUC 72 = graduate pre-1992; reference changed from non-veterans to the whole population. §1 unchanged.
