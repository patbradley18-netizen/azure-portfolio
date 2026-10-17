# Build #9: Measure the renter, not the county — the right outcome

**Anchor phrase: the right outcome.**

Live page: https://stazportfoliob1.z14.web.core.windows.net/build-09-renter-burden/

## The problem

Builds #7 and #8 asked whether veteran-heavy counties carry heavier renter burden, using TSCI's county renter nut over *all* households' median income. That is a county index, not a renter's burden (defect D-007 on the build #8 card). Census publishes the real thing: B25070, gross rent as a share of *renter* household income, in eleven bands. This build turns the bands into a rate, re-asks the question with that outcome, and adds state fixed effects (defect D-008).

**Answer:** cost burden (30%+): nothing — coefficient −0.04, p = 0.59, with all controls and state fixed effects. Severe burden (50%+): a small negative association survives (−0.22, p < 0.001): about 2 points fewer severely burdened renter households per 10 points of veteran share. The thread ends here; four builds on one question is enough, and the page says so.

## Azure services used and why

| Service | Tier / cost | Why |
|---|---|---|
| Azure SQL Database `aid`, schema `col`, dataset `acs5_2023_rentburden` | Free offer; $0 | 35,442 rows; band arithmetic and the feature table in T-SQL |
| Census ACS5 2023 API, table B25070 | $0, one keyed call | Eleven bands, all counties, labels from the API |
| Key Vault `kv-azportfolio-b2`, secret `census-api-key` | Existing; $0 | Key by name only |
| statsmodels (local) | $0 | WLS with HC1; state dummies for M5 |

No new Azure resources.

## The denominator

B25070's total includes households for which the ratio is **not computed** (no cash rent, or zero/negative income). The rate is `burdened / (total − not_computed)`. Nationally that is the difference between **50.4%** (right) and 46.9% (wrong); in Louisiana, 7.1 points. Q15 prints both so the mistake is visible.

## The questions

| # | Question | Pattern | Answer |
|---|---|---|---|
| Q15 | From the bands to a rate, by state | band arithmetic, `GROUP BY ROLLUP` | US 50.4% burdened, 25.3% severe; FL 58.7% leads |
| Q16 | The veteran question with the right outcome | NTILE(5) | Quintiles nearly flat: 51.7% vs 48.5–49.9% |
| Q17 | Feature table v2 | six-dataset join; ≥100 computed renter households | 3,058 counties |
| Model | M1–M4 as build #8, M5 + state FE | WLS, renter-household weights, HC1 | 30%+: −0.04 ns; 50%+: −0.22*** |

Every sentence on the page is computed from `data/results.json` and `data/model.json`.

## What it cost

$0.00. One Key Vault read, one Census call, one bulk load, three queries, one model run.

## How to run

```
bash load.sh      # CENSUS_API_KEY and SQL token by env → fetch + load dataset acs5_2023_rentburden
bash run.sh       # queries.sql → data/results.json; model.py → data/model.json
python build_findings.py
```

## What I learned

1. **The denominator is the analysis.** A distribution table's total is not the base for a rate until the "not computed" bucket is removed. Q15 shows the wrong number next to the right one.
2. **Measure the thing, not a proxy for the thing.** TSCI's county nut and B25070's renter-household rate agree on the headline (no veteran effect) and disagree on what else matters (R² 0.49 vs 0.28 under the same controls). The proxy was more "explainable" because it was built from the controls.
3. **State fixed effects absorb more than every county control combined** (R² 0.28 → 0.58). Rent law, supply and wages vary by state; if the question is within-state, say so.
4. **Weight by the unit the outcome describes.** Renter households here, not population.
5. **Drop tiny denominators before modelling.** A rate on 40 households is noise; the cut was 100 and is stated.
6. **Know when a thread is done.** This is the fourth build on one question. The answer has been no four ways; the next build should ask something new.
7. **A backslash inside an f-string expression is a syntax error** — the one bug this build hit. Typographic quotes fixed it.

## Cleanup

Nothing new to delete. To remove this build's data only: `DELETE FROM col.measure WHERE dataset_id = 'acs5_2023_rentburden'; DELETE FROM col.metric WHERE dataset_id = 'acs5_2023_rentburden'; DELETE FROM col.dataset WHERE dataset_id = 'acs5_2023_rentburden';`

## Files

| File | Purpose |
|---|---|
| `fetch_acs.py`, `load_acs.py` | Build #8's scripts with the `rentburden` set added |
| `queries.sql` | Q15 (bands → rate, by state), Q16 (by veteran quintile), Q17 (feature table v2) |
| `load.sh`, `run.sh`, `run_analysis.py` | Fetch + load; queries + model |
| `model.py` | Five specifications × two outcomes, plus the build #8 outcome for comparison |
| `build_findings.py` | Renders `findings.html` from both JSON files |
| `data/results.json`, `data/model.json` | Committed (aggregates and coefficients) |
