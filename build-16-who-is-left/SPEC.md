# Build #16 — Who they were, who's left: spec addendum to build #15

*Extends `../build-15-two-wars/SPEC.md` (cohorts, clock, weights, rules 1–9 apply unchanged). Written before extract #4 landed.*

## 1. Questions

A. At the same distance from service, how do the two in-theater cohorts differ from non-veterans their age on **education, race/ethnicity and sex** — and from each other?
B. Do the cohorts **die faster than the life table says** they should, on the same clock?

Anchor phrases: *two shares, one interval* (A); *the weights are the headcount* (B).

## 2. Profiles (A)

- Variables added: `EDUC` (basic CPS, all years), `RACE`, `HISPAN`. Harmonised to: education = {less than high school, high school, some college, bachelor's or more}; race/ethnicity = {White non-Hispanic, Black, Hispanic, other}; sex.
- Comparison cells: cohort × years-out bin (separation clock) vs non-veterans in the same survey years **and the same age band** (the civilian reference is age-matched: 18–34, 35–49, 50–64 reweighted to the cohort's age mix).
- Statistics per cell: weighted share, approximate SE (effective n), **difference in points with 95% CI** (`diff ± 1.96·√(SE₁²+SE₂²)`), **representation index** (cohort share ÷ reference share), **Cohen's h** (`2·asin√p₁ − 2·asin√p₂`; |h| < 0.2 small, 0.5 medium, 0.8 large).
- Cells with effective n < 100 suppressed. 1985/1987 (era clock) shown, not compared.

## 3. Survival (B)

- **Closed cohorts.** Vietnam in-theater (`VVIETNAM` = 2) is closed by definition. GWOT in-theater is closed from 2010 only for those **separated by 2009** (`VLASTSERVE` ≤ 2009); later separators are excluded from the survival leg so no one enters after the window opens.
- **Observed:** the cohort's weighted count (all ages, `VTSUPPWT`) by survey year. Deaths between surveys t₁ and t₂ ≈ N(t₁) − N(t₂). CPS excludes the institutionalised and active-duty populations: moves into prison, nursing homes or back onto active duty count as "deaths" here and are named as such.
- **Expected:** for every person in the t₁ sample, the probability of dying before t₂ from the SSA period tables by **sex, single age and calendar year** (`q(x)` compounded across the gap years); expected deaths = Σ wᵢ·(1 − Πₖ(1 − q)). Historical tables to 2020, projected (Alt 2) 2021–2025.
- **Ratio** = observed ÷ expected (an SMR-style standardised mortality ratio). Reported in **5-year windows** with a sampling interval from the two endpoint counts' SEs; never year by year. The 1997 Vietnam universe change is a break shown on the chart. VetPop2023's Vietnam-era projection (2023–2025) drawn alongside as the VA model's line.
- **What it cannot say:** the CPS is a sample, not a registry; a ratio of 1.3 with an interval of 0.9–1.7 is "no evidence", and the page will say so.

## 4. Azure skill

ADX **materialized view** `vet_base_mv` over `cps_person` (the new, wider table) so the cohort base is precomputed and every result query reads it; the pipeline now **creates the table from the file header** (`.create-merge table`) and takes a `table` name in the job, so a new file family needs no hand setup.

## 5. Data flow

Extract #4 (28 samples, 17 variables) → Blob → `vets.cps_person` (pipeline, tag `extract:4`) → `vet_base_mv` → R8–R12 → `data/results.json`; `reference/ssa/*.csv` → `vets.ssa_qx` (year, sex, age, qx); `reference/vetpop_vne.csv` → `vets.vetpop`.

## Change log

- 2026-10-17 03:15 — written; SSA tables fetched through the browser pane (scripted downloads are refused); extract #4 submitted after the pipeline learned to create tables from the header.
