# Build #4: SQL analysis, the queries a Business Analyst writes

Live page: https://stazportfoliob1.z14.web.core.windows.net/build-04-sql-analysis/

## The problem

Builds #1 and #2 left eight tables in a free Azure SQL database. Tables are not findings. A Business Analyst's job is to ask the questions a manager would ask, answer each one with a query, and turn the result into one sentence with a number and a caveat in it. Anchor phrase: **question, query, sentence.**

## What it does

```
queries.sql  (7 blocks, each headed by its business question)
   |  run_analysis.py: Entra token by env -> runs each block -> data/results.json
   v
build_findings.py: computes the finding sentence from the result rows (no hand-typed numbers) -> findings.html
   |
   '-> deployed by the build #3 workflow on push; live under /build-04-sql-analysis/
```

No new Azure resource. Cost: $0.

## The seven questions

| # | Question | Tables | SQL pattern |
|---|---|---|---|
| Q1 | Veteran vs nonveteran unemployment gap by year | bls | CTE, self-join on year |
| Q2 | Gulf War-era II spike after 2008: size and time to close | bls | CTEs, TOP 1 peak, correlated subqueries, DATEDIFF |
| Q3 | Same-month year-over-year change, every series | bls | LEFT JOIN on DATEADD(year, -1) |
| Q4 | Two recessions: peak month and months to recover, per group | bls | episode table (UNION ALL), three CTEs, LEFT JOIN for not-yet-recovered |
| Q5 | Producers vs amplifiers by account category | dbo.templates + dbo.edges | FULL OUTER JOIN across two signals, COALESCE |
| Q6 | One-day blast share and lifetime by category | dbo.templates + dbo.bursts | JOIN on body, conditional aggregation |
| Q7 | Does each weekly run reproduce the same template set? | dbo.template_runs | GROUP BY run_id (fills in as runs accumulate) |

## What it found (the sentences, as of 2026-10-16)

- Veterans have had the lower unemployment rate in **27 of 27 years** since 2000; widest gap 2020 (1.5 points), narrowest 2018 (0.3). Not age-adjusted.
- Gulf War-era II unemployment peaked at **15.2% in January 2011**, 5.3 points above all veterans; the excess closed to within 1 point in **13 months** and has averaged 0.7 points over the last year.
- September 2026, same-month year-over-year: Gulf War-era II **+1.7 points** (4.1% vs 2.4%); nonveterans −0.3; participation −0.7 for both groups. One NSA month of a small series; read the trend, not the point.
- COVID-19: veterans rose 8.1 points to 11.7% and recovered in **16 months**; nonveterans rose 10.7 to 14.4% and took **20**. Great Recession: veterans **44 months** from peak to the December 2007 level; nonveterans **75**.
- RightTroll accounts wrote **96% of templates** and sent **94% of retweets** from 76 accounts. Producing and amplifying were one operation.
- One-day blasts are a RightTroll signature: **77.5%** of its templates lived one day; every other category's share is **0%**.
- One function run recorded; the first scheduled run (Monday 2026-10-19 06:00 UTC) should reproduce it exactly.

## Secrets handling

Entra access token by environment variable, as in builds #1–#2. Nothing on disk, nothing in the repo. `data/results.json` is committed (it is the findings' source of truth and contains only aggregates); CSV exports and logs are ignored.

## How to run

```bash
# SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME by env (WSL venv from build #1)
python run_analysis.py       # -> data/results.json
python build_findings.py     # -> findings.html
```

## What I learned

1. **Write the question before the query.** Each block's first line is the business question; the SQL exists to answer it and nothing else.
2. **Compute the sentence from the result.** `build_findings.py` derives every number in every sentence from `results.json`. Re-run the queries and the prose updates; nothing is typed by hand, so nothing goes stale.
3. **Same month, one year apart** is the only honest comparison for not-seasonally-adjusted data. Month-to-month "rose/fell" is noise.
4. **Define recovery before you measure it.** "Back to the pre-recession month's level" is one definition; the Great Recession numbers (44 vs 75 months) depend entirely on it, so the page says which.
5. **FULL OUTER JOIN when two signals name the same categories** and either side may be missing; COALESCE the key.
6. **Put the caveat next to the number.** Age mix, NSA, file 1 of 13, hand labels: each sentence carries its own.
7. **A data-quality query belongs in the analysis.** Q7 is the one that catches a broken pipeline before anyone trusts Q1–Q6.

## Data credit

BLS Current Population Survey via api.bls.gov (public domain). FiveThirtyEight / Clemson IRA tweets, file 1 of 13 (attributed, non-commercial).