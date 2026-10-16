# Build #6: Cost-of-Living warehouse — snapshot to source

**Anchor phrase: snapshot to source.**

Live page: https://stazportfoliob1.z14.web.core.windows.net/build-06-cost-of-living/

## The problem

Two cost indices I publish on patrickneilbradley.com — TSCI (shelter and family cost, 3,222 counties) and TCBI (weekly basket, five domains) — ship as derived JSON snapshots. My own live-API plan for them names the real prerequisite before anything goes live: *the derivation pipeline must exist as a runnable, verified script.* Nobody had built that check. This build puts the snapshots and a fresh pull of the Census inputs they cite side by side in a relational warehouse, then asks the first question a Business Analyst asks of any published number: **does it still equal the source, and does its own arithmetic hold?**

Answer: yes, exactly — 16,084 of 16,110 county-field pairs match the Census to the dollar, the other 26 are suppressed in both, and the stored nut, burden and price-to-income figures recompute from inputs with zero mismatches across 3,206 computable counties.

## Azure services used and why

| Service | Tier / cost | Why |
|---|---|---|
| Azure SQL Database `aid`, schema `col` | Free offer (shared with builds #1, #2, #4); $0 | Long-format warehouse: `county`, `dataset`, `metric` (data dictionary), `measure` |
| Key Vault `kv-azportfolio-b2`, secret `census-api-key` | Existing; secret operations $0.03 per 10,000 | The Census API requires a key; it lives here and reaches the script only as an env variable at run time |
| Entra token for SQL (`az account get-access-token --resource https://database.windows.net`) | $0 | No SQL password anywhere |

No new resources were created.

## Architecture

```
patrickneilbradley.com snapshots            Census ACS5 2023 API (key from Key Vault → env)
  counties.json, d1..d5_data.json                    fetch_acs.py → acs5_2023_county.json (raw, untouched)
            │                                                   │
      load_snapshots.py                                    load_acs.py
  (data dictionary + OPENJSON bulk insert)         (negative sentinels → NULL + 'SUPPRESSED')
            └──────────────┬────────────────────────────────────┘
                     Azure SQL (free)  schema col
                     county · dataset · metric · measure  (200,072 rows, 7 datasets, 63 metrics)
                                   │
                     queries.sql Q1–Q7  →  run_analysis.py  →  data/results.json
                                   │
                     build_findings.py  →  findings.html  →  GitHub Actions  →  live site
```

## Warehouse design

- **Long format.** One row per (county, dataset, metric). Adding a dataset or a metric is an insert, not a schema change.
- **Provenance on every row.** `dataset_id` carries the tool and vintage (`tsci_2026-05-12`, `tcbi_d1_2026-06-01`, `acs5_2023`); `dataset.loaded_at` says when. A refresh is a new dataset, not an overwrite of history.
- **Data dictionary.** `col.metric` maps the snapshots' terse codes (`rb`, `p2i`, `cc_m`) to names and units taken from the methodology page.
- **Nulls stay null.** Census suppression codes load as NULL with a text flag, so a join can see a gap instead of a fake number.

## The seven questions

| # | Question | Pattern | Answer |
|---|---|---|---|
| Q1 | Does the snapshot carry the Census inputs unchanged? | FULL OUTER JOIN, CASE status | 100% match where Census publishes; 26 suppressed in both; 0 differ |
| Q2 | Where do they differ, and by how much? | inequality JOIN, TOP 25 | Only suppressed cells; 18 of 25 in small Texas counties |
| Q3 | Does the snapshot's own arithmetic hold? | conditional-aggregation pivot, computed checks | 3,206 computable counties, 0 mismatches |
| Q4 | Which states carry proxy, suppressed or missing inputs? | LEFT JOIN, flag pivot, HAVING | Childcare proxy-filled for all of IN, NM, CT; 108/115 MO |
| Q5 | Who lives above the 30% burden line? | CASE bands, window SUM | 83% of population; severe band avg income $35k |
| Q6 | Which states carry the heaviest burden, weighted by raw Census population? | four-way JOIN across datasets | DC 45.6%, CA 43.8%, MA 42.5% renter burden |
| Q7 | What is loaded? | the warehouse describing itself | 7 datasets, 200,072 rows |

Every sentence on the findings page is computed from `data/results.json` by `build_findings.py`; nothing is typed.

## What it cost

$0.00. The free SQL offer's vCore-seconds absorbed the loads; Key Vault was read twice. Budget alert on the subscription stays at $10.

## How to run

```
python load_snapshots.py          # data/snapshots/*.json → col.*  (SQL token by env)
python fetch_acs.py 2023          # CENSUS_API_KEY by env (from Key Vault) → data/acs5_2023_county.json
python load_acs.py 2023           # raw pull → col.measure dataset acs5_2023
python run_analysis.py            # queries.sql → data/results.json
python build_findings.py          # → findings.html
```

Env: `SQL_ACCESS_TOKEN`, `SQL_SERVER_NAME`, `SQL_DATABASE_NAME`; `CENSUS_API_KEY` from `az keyvault secret show --vault-name kv-azportfolio-b2 --name census-api-key --query value -o tsv`. Never on disk.

## What I learned

1. **Ship the data, not the rows.** Row-by-row parameter binding over the wire ran at ~40 rows/s (an 80-minute load). One `OPENJSON` insert per 20,000-row chunk ran at ~400 rows/s. Same tables, same data, ten times faster.
2. **The Census API needs a key.** I wrote "no key needed" in the plan; the first call returned a *Missing Key* page. Checked, corrected, and the key went into Key Vault under a name — the same pattern as the BLS key in build #2.
3. **A NULL mismatch is not a mismatch.** The first version of Q3 reported 16 failures; they were counties with a suppressed input, where NULL arithmetic returns NULL. Gate on "computable" before counting errors.
4. **A flag that is always on carries no information.** TCBI's pump value is proxy-derived for every county by design; a column that reads 100% in every state was dropped and the "missing from TCBI" count took its place.
5. **Don't title a query for data it doesn't use.** Q6 was first headed as a veteran cut. The warehouse has no state-level veteran population yet, so the title now says what the join actually does and names the next load.
6. **Provenance is a column, not a comment.** Vintage, source file and load time on every dataset row; the warehouse answers Q7 about itself.
7. **A clean reconciliation is a finding.** Zero drift is the result a publisher wants and the one a reader should see proven, not asserted.

## Cleanup

Nothing new to delete. To remove this build's data: `DROP TABLE col.measure, col.metric, col.dataset, col.county; DROP SCHEMA col;` on database `aid`. The Key Vault secret `census-api-key` can be deleted with `az keyvault secret delete --vault-name kv-azportfolio-b2 --name census-api-key`.

## Files

| File | Purpose |
|---|---|
| `load_snapshots.py` | DDL, data dictionary, replace-per-dataset bulk load of the six snapshot files |
| `fetch_acs.py` | One keyed request for five ACS5 variables, all counties; saves the raw response |
| `load_acs.py` | Raw pull → `col.measure` as dataset `acs5_2023`, suppression codes → NULL + flag |
| `queries.sql` | Q1–Q7, each headed by its business question |
| `run_analysis.py` | Runs each block, saves `data/results.json` |
| `build_findings.py` | Renders `findings.html` from the results; no typed numbers |
| `data/results.json` | Committed (aggregates only); snapshots and the raw pull are not (available at the source) |
