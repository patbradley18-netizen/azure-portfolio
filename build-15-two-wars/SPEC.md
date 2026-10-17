# Build #15 — Two wars, matched years: harmonisation spec

*Written before any data was extracted. Changes after data lands are logged at the bottom, dated.*

## 1. Question

At the same distance from service, do Vietnam-era and GWOT-era veterans differ on employment, labor-force participation, service-connected disability, and incarceration — and how much of any gap can the data attribute to the war rather than to who served?

Anchor phrase: **same clock, different army.**

## 2. Cohorts (revised 02:55 after reading the codebook's availability table — see change log)

| Cohort | Primary definition (in-theater, all years) | Secondary (era, 2005+ only) | Baseline |
|---|---|---|---|
| Vietnam | `VVIETNAM` = 2 (served in Vietnam/Laos/Cambodia, waters or air) — asked in all 28 samples | `VWHEN` = 4 | non-veterans (`VETSTAT` = 1; 1991+) |
| GWOT | `VIRAQ` = 1 or `VAFGHAN` = 1 — asked 2010+ | `VWHEN` = 1 | non-veterans, same year and age band |

Why in-theater is primary: it is the only cohort flag with one meaning in every year. "Answered VVIETNAM" is not an era flag (it also covers 1955–64 and Korea-era veterans, and its universe widened in 1997); `VWHEN` (period of service) starts in 2005 and is "most recent period" with ~4% contradictions against separation year. In-theater is also the comparison the question wanted — the campaign-medal stand-in.

Availability (from the extract codebook, not memory): `VETSTAT` 1991+; `VLASTSERVE` 1991+; `VDISRATE` 1995+; `VCOMBAT` 2001+; `VWHEN` 2005+; `VIRAQ`/`VAFGHAN` 2010+; `VVIETNAM`, `VDISABLE`, `VTSUPPWT` all years. 1985 is males only (5,427 of 5,428 Vietnam-era answers male). 1985/1987 have no `VETSTAT`, so their baseline is "everyone not in the cohort" and is flagged `baseline = all_other`.

## 3. The clock

- **Primary:** `years_out = survey_year − VLASTSERVE` (year last separated). Available 1991 onward. 2021+ bottom-codes separation at 1965 — rows with VLASTSERVE = 1965 in 2021+ are flagged `bottom_coded`.
- **Fallback (1985, 1987 and any row with VLASTSERVE missing):** `years_out_era = survey_year − era_end`, era_end = 1975 for Vietnam, **2021** for GWOT (operator decision 2026-10-17; separation first, 2021 if not). Rows carry `clock` = `separation` | `era`.
- **Comparable window on the separation clock:** Vietnam in-theater observable at ≥16 years out (1991–2025); GWOT in-theater at 0–22 years out (2010–2025, separation 2003+). **Overlap: 16–22 years out.** On the era clock the 1985/1987 Vietnam points land at 10–12 years out, where GWOT (anchor 2021) has no data yet — shown, not compared. Outside the overlap, series are shown but not compared.
- Years-out are binned: 0–4, 5–9, 10–15, 16–22, 23–30, 31+.

## 4. Outcomes

| Outcome | Definition | Universe | Source |
|---|---|---|---|
| Unemployment rate | `EMPSTAT` unemployed / `LABFORCE` in labor force | age 18–64 | CPS |
| Participation rate | `LABFORCE` in / population | age 18–64 | CPS |
| Service-connected disability | `VDISABLE` = yes; share rated ≥ 50% (`VDISRATE`) | veterans | CPS |
| Incarceration | veteran share of state prisoners by era; rate per 100k veterans where published | adults | BJS published tables (hand-entered, `source_url` per row) |

Weights: `VTSUPPWT` for every CPS estimate. Standard errors: design-naive binomial on the weighted share with effective n = (Σw)²/Σw² (stated as approximate; no replicate weights in these files).

## 5. Harmonisation rules

1. One row per person-survey; keep `YEAR`, `MONTH`, `SERIAL`, `PERNUM`, weight, age, sex, veteran flags, outcomes.
2. Universe changes are data: 1985 is males only → Vietnam series restricted to males for the whole comparison *and* a male-only GWOT series is produced alongside the all-sex one.
3. Supplement respondents are 18+ to 2003, 17+ from 2005; universe set to 18–64 everywhere.
4. Codes 96–99 (refused / don't know / no response / NIU) are null, never zero.
5. A cell with effective n < 100 is suppressed on the page (shown as "—").
6. Nothing is interpolated; missing survey years are gaps.
7. **Supplement non-respondents** (`VTSUPPWT` = 0) are dropped before anything else; they are 2023's explanation for most "NIU" veterans (1,074 of 1,576).
8. **Code conventions differ by variable** (from the 2023 codebook): `VIRAQ`/`VAFGHAN` 1 = Yes, 2 = No; `VVIETNAM` 1 = No, 2 = Yes; `VCOMBAT` 1 = No, 2 = Yes; `VETSTAT` 2 = veteran; `LABFORCE` 2 = in labor force; `VWHEN` is single-valued (1 = Sept 2001+, 2 = Aug 1990–Aug 2001, 3 = May 1975–Jul 1990, 4 = Vietnam era, 5–9 earlier). Every recode is a named KQL function, never an inline literal.
9. `VLASTSERVE` universe: veterans who served Aug 1964 or later (eras 5–9 are NIU by design); the remaining NIU after rule 7 (~5% of each cohort) go to the era clock (rule in §3).

## 6. What this cannot say (written now, kept on the page)

- Cohort snapshots, not linked people: no one is followed from prison to a job.
- Draft vs volunteer: selection into service differs; Angrist (1990) is the only causal estimate on the Vietnam side and there is no GWOT twin. Gaps are associations.
- Era ≠ combat: in-theater flags exist for both cohorts but combat exposure (`VCOMBAT`) is asked only in recent years.
- BJS tables are not microdata: no weights, no SEs, and the 1991/1997/2004/2016 snapshots land at different years-out for each cohort.
- Suicide and mental-health outcomes are out of scope: the VA reports by age, not era.

## 7. Data flow

IPUMS extract (API, key in Key Vault `ipums-api-key`) → Blob `inbox-b15/` → ADX free cluster `azportfolio`, db `vets`: table `cps_vet` (raw rows), KQL functions for cohort/clock/outcome → `results.json` → findings page. BJS table `bjs_prison` ingested from a CSV in the repo with `source_url`.

---

## Change log

- 2026-10-17 02:20 — spec written; extract #1 (one sample, 14 variables) submitted as the mechanics test.
- 2026-10-17 02:30 — extract #1 read (101,315 rows; 5,737 veterans): rules 7–9 added from what the file showed; nothing in §1–§4 changed.
- 2026-10-17 02:55 — extract #2 (28 samples, 3,580,995 rows) ingested to ADX; the codebook's availability table showed `VWHEN` starts 2005 and `VETSTAT` 1991, and the data showed "answered VVIETNAM" is wider than the Vietnam era. §2 rewritten: in-theater cohorts primary (all years), era cohorts secondary (2005+). §1, §3 clock, §4 outcomes unchanged.
