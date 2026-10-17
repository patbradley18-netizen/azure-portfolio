# Build #10: Can veterans reach the VA? — spatial SQL and infrastructure as code

**Anchor phrase: distance is not access, but it is the first thing to measure.**

Live page: https://stazportfoliob1.z14.web.core.windows.net/build-10-va-access/

## The problem

Builds #7–#9 asked about veterans and housing cost and found nothing. This build asks a question where geography is the answer: how far is the nearest VA medical center, and the nearest VA care site of any kind, from where veterans actually live — and which veteran-dense counties are far from a hospital? Two Azure skills ride on it: the `geography` type with spatial indexes on the free Azure SQL tier, and a Bicep template with a `what-if` run that describes the whole portfolio as code.

**Answer:** weighted by where veterans live, the average veteran is **36 straight-line miles** from a VA medical center and **10 miles** from any VA care site. **95%** are within 30 miles of a care site; **57%** are within 30 miles of a medical center and **81%** within 60. The veteran-densest counties far from a hospital are military base counties (Onslow NC, Okaloosa FL, Liberty GA, Cochise AZ, Pulaski MO): a clinic within a few miles, a hospital 64–258 miles away. 897 thousand veterans in 499 counties are more than 100 miles from a VA medical center.

![findings](findings.png)

## Azure services used and why

| Service | Tier / cost | Why |
|---|---|---|
| Azure SQL Database `aid`, schema `col`, tables `facility` and `county_center` | Free offer; $0 | `geography` points (SRID 4326), spatial indexes, `STDistance` nearest-neighbour joins in T-SQL |
| Bicep + `az deployment group what-if` | $0 (files; what-if creates nothing) | The portfolio's resource group described as code; what-if compared against the live resources |
| HRSA GIS portal (VA VAST station list) | $0, no key | 1,657 VA sites with lat/lon, county FIPS and type flags |
| Census 2020 centers of population; 2023 Gazetteer (CT) | $0, no key | Population-weighted county origin points |

No new Azure resources. The Lighthouse VA Facilities API refused a production key for short-term use; HRSA's republished VAST list replaced it (see "What this cannot say").

## The questions

| # | Question | Pattern | Answer |
|---|---|---|---|
| Q18 | Nearest VA medical center and nearest care site, every county | `CROSS APPLY (SELECT TOP 1 … ORDER BY STDistance)` | 3,144 counties; map on the page |
| Q19 | Veteran-weighted distance by state | weighted means, `GROUP BY ROLLUP` | US 36 / 10 miles; AK, ND, MT furthest |
| Q20 | Veteran-densest counties beyond 60 miles from a medical center | filter on the spatial join, TOP 25 | base counties: Onslow, Okaloosa, Liberty, Cochise… |
| Q21 | Distance bands | CASE bands + window share | 57% / 24% / 14% / 5% of veterans at 0–30 / 30–60 / 60–100 / 100+ miles from a VAMC |

Every sentence on the page is computed from `data/results.json`. The map is inline SVG: one dot per county population center, projected with an Albers equal-area conic in `build_findings.py` — no map library, no tiles, no key.

## Infrastructure as code

`infra/main.bicep` describes everything the portfolio runs on: the storage account with its static website, the SQL server and free database, the Key Vault, the two Function apps with their managed identities, the GitHub deploy identity and the role assignments. `infra/README.md` has the `what-if` output against the live resource group and what it taught. Nothing is deployed from it; that is the point of `what-if`.

## What it cost

$0.00. Two public downloads, one bulk load, four queries, one what-if.

## How to run

```
bash load.sh      # SQL token by env → fetch facilities + centroids, load spatial tables, run queries → data/results.json
python build_findings.py
az deployment group what-if -g rg-azportfolio-b1 -f infra/main.bicep   # see infra/README.md
```

## What I learned

1. **A spatial join is `CROSS APPLY` + `TOP 1` + `ORDER BY STDistance`.** With a spatial index it is a nearest-neighbour lookup, not a 1,657 × 3,144 cross product.
2. **Compute the expensive join once.** Q19–Q21 each recomputed Q18's nearest-neighbour pass; the run took three times longer than it needed to. Next time: materialise the per-county result and read from it.
3. **Read the output before trusting the flags.** The 2018 VAST flags list New Orleans VA Medical Center as a clinic and two Atlanta clinics as medical centers. A spot-check of Louisiana caught it; a three-row override fixed it; the Dataset Card records it.
4. **Geographies move.** Connecticut replaced its counties with planning regions in 2022; the 2020 centers file and ACS 2023 no longer join. Nine rows fell out silently until the count was checked.
5. **Population-weighted centers, not geographic ones.** The Gazetteer's interior point is where the county's shape is; the centers-of-population file is where its people are.
6. **The denial was the better outcome.** The API would have given a current list; the refusal forced a documented public source with a stated vintage and a count-level check against VA's own figures (170 medical centers, 1,193 outpatient sites).
7. **Distance is the first thing to measure, not the last.** Straight-line miles say nothing about eligibility, enrollment, community care, or roads. The page says so.

## What this cannot say

Straight-line distance understates travel. A county population center is not where every veteran lives. The facility list is from 2018-09-29: the medical-center map is current at the count level (171 here vs 170 reported by VA in June 2026); the clinic map is a few years behind. VA eligibility and community-care rules are out of scope. Puerto Rico is not in the warehouse.

## Cleanup

Nothing new to delete. To remove this build's data only: `DROP TABLE col.facility; DROP TABLE col.county_center; DELETE FROM col.dataset WHERE dataset_id IN ('vast_2018_facilities','cenpop_2020_county');`

## Files

| File | Purpose |
|---|---|
| `fetch_facilities.py` | HRSA/VAST facility list → `data/vha_facilities.json` + card; classification and the three-row override |
| `fetch_centroids.py` | 2020 centers of population (+ CT planning regions from the 2023 Gazetteer) → `data/county_centroids.json` + card |
| `load_spatial.py` | `col.facility`, `col.county_center` with `geography` columns and spatial indexes; OPENJSON load; validity checks |
| `queries.sql`, `run_analysis.py`, `load.sh` | Q18–Q21; the chained run |
| `build_findings.py` | Renders `findings.html` (map + tables) from `data/results.json` |
| `infra/main.bicep`, `infra/README.md` | The portfolio as code, and the what-if |
| `data/results.json`, `data/*_card.json` | Committed (aggregates and provenance) |
