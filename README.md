# Azure learning portfolio

Small, free-tier builds on an Azure for Students subscription. Each one teaches one real skill, uses only public or made-up data, costs $0 (budget alert: $10), and ends with a README here, a live page, and a post on [patrickneilbradley.com](https://patrickneilbradley.com).

**Live site:** https://stazportfoliob1.z14.web.core.windows.net/ (redeployed on every push to `main` by GitHub Actions)

| # | Build | Skills | Status |
|---|---|---|---|
| 1 | [Algorithmic Influence Detector (AID Lite), stages 1–4](build-01-aid-lite/) | Blob Storage, Azure SQL (free), Entra auth, embeddings + clustering, T-SQL, Functions with identity bindings, AI Language, graph + time-series on text, AI Search vector index, control design | Published and closed (stage 4 is a control-tested null result) |
| 2 | [Veteran employment pipeline (BLS → Function → SQL)](build-02-bls-veterans/) | Keyed API on a schedule, Key Vault reference, least-privilege SQL grant, upsert on a real key | Published and closed |
| 3 | [Live site, deployed by GitHub Actions](.github/workflows/deploy-site.yml) | Blob static website, CI/CD, OIDC federated identity (no deployment token), secret-scan gate | Published and closed |
| 4 | [SQL analysis: seven questions, seven queries, seven sentences](build-04-sql-analysis/) | T-SQL (CTEs, self-joins, FULL OUTER JOIN, conditional aggregation), findings computed from results | Published |
| 5 | [AI summary with cost controls: estimate, cap, ledger, verify](build-05-ai-summary/) | Azure AI Language (F0), per-record cost estimation, hard caps, billed-vs-estimated ledger, exact-match verification, tier gates | Published and closed |
| 6 | [Cost-of-living warehouse: snapshot to source](build-06-cost-of-living/) | Long-format warehouse design, data dictionary, provenance, OPENJSON bulk loads, keyed Census API via Key Vault, reconciliation in T-SQL | Published and closed |
| 7 | [Veteran burden cut: the join Q6 couldn't make](build-07-veteran-burden/) | Metadata-driven labels, NTILE quintiles, stratified comparison, publishing a no | Published and closed |
| 8 | [Tenure and a model: controls one at a time](build-08-tenure-model/) | SQL builds the feature table, Python fits WLS with robust SEs; which control does what | Published and closed |
| 9 | [Measure the renter, not the county: the right outcome](build-09-renter-burden/) | Distribution table → rate with the right denominator, GROUP BY ROLLUP, state fixed effects | Published and closed |
| 10 | [Can veterans reach the VA? Spatial SQL and the portfolio as code](build-10-va-access/) | `geography` type, spatial indexes, nearest-neighbour joins with STDistance, Bicep + what-if, inline SVG map, reading the output before trusting the flags | Published and closed |
| 11 | [How much does straight-line lie? Road miles under a cap and a ledger](build-11-road-distance/) | Materialised spatial join, capped and ledgered batch against a free API, detour index, resume-safe runs, a region-policy dead end documented | Published and closed |
| 12 | [Before the bill: the free SQL limit, KQL, and an alert that proved itself](build-12-operations/) | Azure Monitor metric alert + action group, Log Analytics / KQL query pack, workbook, proving an alert by firing it, monitoring added to the Bicep | Published and closed |
| 13 | [The warehouse as a product: a public data API](build-13-data-api/) | Functions HTTP API with SQL bindings + managed identity, Durable Functions fan-out/fan-in, API Management products and policies, OpenAPI as the contract, contract tests in CI | Published and closed |
| 14 | [Every file is guilty until proven innocent: event-driven ingestion with quality gates](build-14-ingestion/) | Event Grid blob events, validator Function with YAML contracts, quarantine with reasons, Storage queues + poison queue, Docker loader on GHCR running on Azure Container Instances, idempotent loads via an ingest ledger, Event Grid dead-lettering | Published and closed |
| 15 | [Two wars, matched years: Vietnam and GWOT veterans at the same distance from service](build-15-two-wars/) | Azure Data Explorer free cluster + KQL, Durable Functions async-job pattern (submit / poll / download / ingest), IPUMS API with the key in Key Vault, survey harmonisation spec, BJS reference table | Published and closed |
| 16 | [Who they were, who is left: cohort profiles and a mortality method that fails honestly](build-16-who-is-left/) | ADX materialized view, pipeline creates tables from the file header, SSA life tables + VetPop reference tables, two-proportion inference (CI, index, Cohen's h), a negative result stated plainly | Published |

Note for anyone copying the OIDC setup: GitHub now presents the subject claim with owner and repository IDs embedded (
epo:<owner>@<id>/<repo>@<id>:ref:refs/heads/main); the federated credential subject must match that string exactly.

Rules I hold myself to: cost first; no keys, passwords or connection strings anywhere in code, chat or GitHub; non-commercial only; teach-don't-do; one build at a time; publish the null results too.

Patrick Neil Bradley