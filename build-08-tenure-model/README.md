# Build #8: Tenure and a model — controls one at a time

**Anchor phrase: controls one at a time.**

Live page: https://stazportfoliob1.z14.web.core.windows.net/build-08-tenure-model/

## The problem

Build #7 answered "do veteran-heavy counties carry heavier shelter burden?" with a no, then admitted its only check held age constant and nothing else. A stratified table is not a model. This build loads the one table that addresses ownership (B25003, tenure) and fits four small regressions, adding one control at a time, so the reader can see which control changes what.

**Answer:** for renter burden, the raw veteran-share association (−0.68 points per point) is gone once ownership, income and population are controlled (−0.02, p = 0.74). Ownership does most of that work. For owner burden, a small negative association (−0.63) survives every control: more veterans, slightly cheaper to own. Build #7's "no" stands and is now explained rather than asserted.

## Azure services used and why

| Service | Tier / cost | Why |
|---|---|---|
| Azure SQL Database `aid`, schema `col`, dataset `acs5_2023_tenure` | Free offer; $0 | 9,666 rows; the wide county table (Q14) is built in T-SQL from five datasets |
| Census ACS5 2023 API, table B25003 | $0, one keyed call | Owner / renter occupied housing units |
| Key Vault `kv-azportfolio-b2`, secret `census-api-key` | Existing; $0 | Key by name only |
| Local Python: statsmodels (installed into the existing venv) | $0 | WLS on 3,208 rows. The free SQL tier is for storing and joining, not for fitting models |

No new Azure resources.

## The model

Weighted least squares, weight = county population, HC1 robust standard errors. Outcome: TSCI renter burden, then owner burden (percentage points).

| Spec | Adds | Renter: veteran-share coef (p) | R² | Owner: coef (p) | R² |
|---|---|---|---|---|---|
| M1 | veteran share | −0.676 (<0.001) | 0.081 | −1.404 (<0.001) | 0.188 |
| M2 | + 65+ share | −0.667 (<0.001) | 0.081 | −1.450 (<0.001) | 0.189 |
| M3 | + owner share | −0.116 (0.118) | 0.441 | −0.636 (<0.001) | 0.611 |
| M4 | + log income, log population | −0.023 (0.740) | 0.496 | −0.626 (<0.001) | 0.627 |

Every number on the findings page comes from `data/model.json` and `data/results.json`.

## What it cost

$0.00. One Key Vault read, one Census call, one bulk load, two queries, one pip install.

## How to run

```
python fetch_acs.py 2023 tenure     # CENSUS_API_KEY by env → data/acs5_2023_tenure_county.json + _labels.json
python load_acs.py 2023 tenure      # SQL token by env → dataset acs5_2023_tenure
python run_analysis.py              # queries.sql Q13–Q14 → data/results.json
python model.py                     # → data/model.json
python build_findings.py            # → findings.html
```

## What I learned

1. **Add controls one at a time and show every step.** A single "fully controlled" coefficient hides which variable did the work. Here it was ownership (R² 0.08 → 0.44), not age.
2. **A stratified table was the right first move and the wrong last one.** Build #7's Q12 was honest about what it could not hold constant; this build holds it.
3. **Weight by people.** Unweighted, 3,000 small rural counties would outvote the 143 million people in quintile 1. Population weights make the coefficient describe where people live.
4. **Robust standard errors by default.** County burdens are heteroskedastic (big metros vary less); HC1 costs nothing.
5. **Keep the model out of the database.** SQL builds the wide table (Q14); Python fits the model. Each tool does the thing it is for.
6. **A surviving coefficient needs a plain-English size.** −0.63 means about 6 points of owner burden across a 10-point difference in veteran share — real, but veteran share ranges 1–22%, so most county pairs differ by far less.
7. **Association, not effect.** Cross-sectional, county-level, three controls. The page says so in the note under the tables.
8. **The serverless database pauses between builds.** Twice tonight the loader's retry loop absorbed a resume; keep it in every loader.
9. **Inline Python through PowerShell → WSL breaks on commas.** A three-line `run.sh` is the reliable way to chain steps.

## Cleanup

Nothing new to delete. To remove this build's data only: `DELETE FROM col.measure WHERE dataset_id = 'acs5_2023_tenure'; DELETE FROM col.metric WHERE dataset_id = 'acs5_2023_tenure'; DELETE FROM col.dataset WHERE dataset_id = 'acs5_2023_tenure';`

## Files

| File | Purpose |
|---|---|
| `fetch_acs.py`, `load_acs.py` | Build #7's scripts with the `tenure` set added |
| `queries.sql` | Q13 (ownership by veteran-share quintile), Q14 (county table for the model) |
| `run_analysis.py`, `run.sh` | Runs the queries then the model |
| `model.py` | Four WLS specifications → `data/model.json` |
| `build_findings.py` | Renders `findings.html` from both JSON files |
| `data/results.json`, `data/model.json` | Committed (county aggregates and coefficients only) |
