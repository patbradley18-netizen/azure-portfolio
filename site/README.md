# Build #3: Live site, deployed by GitHub Actions

Live: https://stazportfoliob1.z14.web.core.windows.net/

## The problem

Two builds, two dashboards, and both were screenshots in a README. A portfolio needs a URL, and a URL needs to update itself when the code does.

## What it does

```
push to main
   |
GitHub Actions  .github/workflows/deploy-site.yml
   |-- gate: git grep for secret-shaped strings; fail the deploy if any
   |-- assemble: site/index.html + each build's dashboard.html -> dist/
   |-- azure/login via OIDC  ->  Entra issues a short-lived token to
   |      user-assigned managed identity  id-github-azportfolio
   |      (federated credential trusts only this repo's main branch)
   |-- az storage blob upload-batch -> $web container, stazportfoliob1
   '-- verify: curl each page and grep for its title
```

## Azure services and why

| Service | Role | Why | Cost |
|---|---|---|---|
| Blob Storage static website (`$web`) | Serves the pages over HTTPS | Already had the account; Static Web Apps is unavailable in this subscription's allowed regions | $0 (a few KB of egress) |
| User-assigned managed identity + federated credential | GitHub's identity in Azure | No app registration needed (students can't create them in this tenant); no deployment token anywhere | $0 |
| Storage Blob Data Contributor (scoped to the one account) | What the identity may do | Least privilege: it can write blobs here and nothing else | $0 |

Delete at close: `az identity delete -n id-github-azportfolio -g rg-azportfolio-b1`; disable static website on the storage account.

## Secrets handling

None. The workflow contains three identifiers (tenant, subscription, client ID), which are names, not secrets. GitHub holds no secret for this deploy. The gate step refuses to deploy if a secret-shaped string ever lands in the repo.

## What I learned

1. **Trust, not tokens.** OIDC lets GitHub prove who it is; Azure decides what that identity may do. Nothing to rotate, nothing to leak.
2. **A managed identity can carry a federated credential.** When the tenant blocks app registrations, this is the door; it needs only resource-group rights.
3. **Match the subject claim exactly.** GitHub presents `repo:<owner>@<id>/<repo>@<id>:ref:refs/heads/main`; the first run failed with AADSTS700213 until the credential's subject matched that string. The log line "subject claim" is the source of truth.
4. **Policy decides architecture.** Static Web Apps exists in five regions, none allowed here. Read the policy before the plan; the fallback was better anyway.
5. **Verify in the pipeline.** The last step curls the live pages; a green run means the site is up, not just that files were uploaded.

Hand-made with the same page style as the dashboards; no build tools, no external scripts.