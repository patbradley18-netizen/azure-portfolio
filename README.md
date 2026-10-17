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
| 9 | [Measure the renter, not the county: the right outcome](build-09-renter-burden/) | Distribution table → rate with the right denominator, GROUP BY ROLLUP, state fixed effects | Published |

Note for anyone copying the OIDC setup: GitHub now presents the subject claim with owner and repository IDs embedded (
epo:<owner>@<id>/<repo>@<id>:ref:refs/heads/main); the federated credential subject must match that string exactly.

Rules I hold myself to: cost first; no keys, passwords or connection strings anywhere in code, chat or GitHub; non-commercial only; teach-don't-do; one build at a time; publish the null results too.

Patrick Neil Bradley