# Azure learning portfolio

Small, free-tier builds on an Azure for Students subscription. Each one teaches one real skill, uses only public or made-up data, costs $0 (budget alert: $10), and ends with a README here, a live page, and a post on [patrickneilbradley.com](https://patrickneilbradley.com).

**Live site:** https://stazportfoliob1.z14.web.core.windows.net/ (redeployed on every push to `main` by GitHub Actions)

| # | Build | Skills | Status |
|---|---|---|---|
| 1 | [Algorithmic Influence Detector (AID Lite), stages 1–4](build-01-aid-lite/) | Blob Storage, Azure SQL (free), Entra auth, embeddings + clustering, T-SQL, Functions with identity bindings, AI Language, graph + time-series on text, AI Search vector index, control design | Published and closed (stage 4 is a control-tested null result) |
| 2 | [Veteran employment pipeline (BLS → Function → SQL)](build-02-bls-veterans/) | Keyed API on a schedule, Key Vault reference, least-privilege SQL grant, upsert on a real key | Published and closed |
| 3 | [Live site, deployed by GitHub Actions](.github/workflows/deploy-site.yml) | Blob static website, CI/CD, OIDC federated identity (no deployment token), secret-scan gate | Published |
| 4 | SQL analysis: the queries a Business Analyst writes | T-SQL, business writing | Planned |
| 5 | Summarize a public report with Azure AI, with cost controls | AI services, cost management | Planned |

Rules I hold myself to: cost first; no keys, passwords or connection strings anywhere in code, chat or GitHub; non-commercial only; teach-don't-do; one build at a time; publish the null results too.

Patrick Neil Bradley