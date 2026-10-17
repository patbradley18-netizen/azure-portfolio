# Build #7: The veteran burden cut — the join Q6 couldn't make

**Anchor phrase: the join Q6 couldn't make.**

Live page: https://stazportfoliob1.z14.web.core.windows.net/build-07-veteran-burden/

## The problem

Build #6's warehouse could answer "which states carry the heaviest shelter burden" but not "do veteran-heavy counties carry heavier shelter burden", because no veteran population table was loaded. The page said so instead of pretending. This build loads that one table and asks the question — including the check that tests whether any answer is really just age.

**Answer: no.** The lowest-veteran-share quintile (the large metros) carries the heaviest burden; the other four quintiles sit within one point of each other. Holding age structure roughly constant does not change that. The highest-veteran-share counties are military-base counties with ordinary burden.

## Azure services used and why

| Service | Tier / cost | Why |
|---|---|---|
| Azure SQL Database `aid`, schema `col`, new dataset `acs5_2023_vet` | Free offer; $0 | Same long-format table as build #6; no DDL change |
| Census ACS5 2023 API, table B21001 | $0, one keyed call | Civilian veterans by sex × age band, all counties, same vintage as the shelter inputs |
| Key Vault `kv-azportfolio-b2`, secret `census-api-key` | Existing; $0 | Key reaches the script as an env variable only |

No new resources.

## What changed in the code

- `fetch_acs.py` takes a variable **set** (`shelter`, `veterans`) and fetches each variable's **label from the API's metadata** before the data, saving it beside the raw response. Nothing about what `B21001_017E` means comes from memory.
- `load_acs.py` takes the same set; metric names come from the saved labels. It imports `connect` and `DDL` from build #6's `load_snapshots.py`, which owns the schema.
- `queries.sql` numbers continue from build #6 (Q8–Q12).

## The five questions

| # | Question | Pattern | Answer |
|---|---|---|---|
| Q8 | Veteran share of adults, how distributed? | pivot + CASE bands | 6.4% nationally; 165 counties ≥12% hold 3.6% of adults |
| Q9 | Burden by veteran-share quintile | NTILE(5), three-dataset join, pop-weighted | Q1 (lowest share) 39.1% renter / 52.6% owner; Q2–Q5 34.5–35.4% / 44.3–45.1% |
| Q10 | Top 20 veteran-share counties | TOP with threshold | Base counties, 16.6–21.8% veteran, ordinary burden |
| Q11 | Age structure, veteran vs nonveteran | lookup CTE + window share | 49% of veterans are 65+, vs 20% of nonveterans |
| Q12 | Veteran share within 65+-share terciles | nested NTILE with PARTITION BY | Lowest-veteran tercile most burdened in all three age groups |

Every sentence on the page is computed from `data/results.json`.

## What it cost

$0.00. One Key Vault read, one Census call, one bulk load (74,106 rows), five queries.

## How to run

```
python fetch_acs.py 2023 veterans    # CENSUS_API_KEY by env → data/acs5_2023_veterans_county.json + _labels.json
python load_acs.py 2023 veterans     # SQL token by env → col.measure dataset acs5_2023_vet
python run_analysis.py               # queries.sql → data/results.json
python build_findings.py             # → findings.html
```

## What I learned

1. **Get labels from the source, not from memory.** B21001 has 39 variables and the male/female blocks are offset; one wrong index would have mislabelled every age band. The script asks the API what each code means and stores the answer.
2. **Say no when the data says no.** The hypothesis the roadmap wanted (veteran-heavy = burdened) is not supported; the page leads with that.
3. **The metro effect is the first thing to rule out.** Quintile 1 is 143M people in counties with $1,585 rent and $484k home values. Any county-level cut that doesn't notice that will mistake urbanity for whatever it is studying.
4. **Measure the caveat.** Build #2 asserted that veterans are older; Q11 measures it from the same table (49% vs 20% aged 65+). Q12 then stratifies on it.
5. **Stratifying is not modelling.** Q12 removes coarse age structure and nothing else. Income, tenure and urbanity are still in there, and the page says so.
6. **Numbering continues across builds.** Q8–Q12 follow Q1–Q7, so a reference to "Q9" is never ambiguous in the README, page or AAR.
7. **The sync tool dropped a patch again.** Checked by grep before running; fixed through the shell. Recipe entry stands.

## Cleanup

Nothing new to delete. To remove this build's data only: `DELETE FROM col.measure WHERE dataset_id = 'acs5_2023_vet'; DELETE FROM col.metric WHERE dataset_id = 'acs5_2023_vet'; DELETE FROM col.dataset WHERE dataset_id = 'acs5_2023_vet';`

## Files

| File | Purpose |
|---|---|
| `fetch_acs.py` | Keyed pull of a named variable set + labels from the API's metadata |
| `load_acs.py` | Raw pull → `col.measure`; names from labels; suppression → NULL + flag |
| `queries.sql` | Q8–Q12 |
| `run_analysis.py` | Runs each block, saves `data/results.json` |
| `build_findings.py` | Renders `findings.html`; no typed numbers |
| `data/results.json` | Committed (aggregates only) |
