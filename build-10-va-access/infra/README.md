# The portfolio as code: `main.bicep` and what `what-if` said

**Anchor phrase: describe it, compare it, don't deploy it.**

`main.bicep` describes the resource group `rg-azportfolio-b1` as it exists after ten builds: storage account with the static site, SQL server and the free serverless database, Key Vault, AI Language (F0), AI Search (free), the GitHub deploy identity, two Flex Consumption plans and Function apps with system identities, and the four role assignments those identities hold. Names only — the SQL admin's object id and login are passed on the command line from the live server and never written down; app settings (Key Vault references, connection strings) are not in the template at all.

## How to run

```
az bicep build -f infra/main.bicep --stdout > /dev/null            # compiles; catches type errors
az deployment group what-if -g rg-azportfolio-b1 -f infra/main.bicep \
   -p sqlAdminObjectId=<from: az sql server show … --query administrators.sid> \
      sqlAdminLogin=<from: az sql server show … --query administrators.login>
```

Cost: $0. `what-if` evaluates the template against the live state and prints the difference; it creates nothing.

## What it printed (2026-10-16)

```
Resource changes: 4 to create, 3 to modify, 8 no change, 4 to ignore.
```

| Result | Resources | What it means |
|---|---|---|
| `=` no change (8) | storage, SQL server, SQL db `aid`, Key Vault, Language, deploy identity, both FC1 plans | The hand-written description matches the live resource property for property — including `useFreeLimit`, `freeLimitExhaustionBehavior: AutoPause`, `minCapacity 0.5`, RBAC on the vault, TLS 1.2 everywhere. |
| `~` modify (3) | AI Search; both Function apps | Noise, not drift: Search reports two server-defaulted properties (`encryptionWithCmk`, `networkRuleSet`) the template does not name; the Function apps show two default `siteConfig` values and the deployment-container URL expressed as an unresolved `reference()` — what-if cannot evaluate runtime references, so it prints the expression against the literal. None of these would change the running resource. |
| `+` create (4) | the four role assignments | **The real lesson.** The assignments already exist, but role assignments are keyed by their GUID name, and the live ones were created by the CLI with random names. The template names them deterministically (`guid(scope, principal, role)`), so ARM sees four new resources. Deploying this template would fail with `RoleAssignmentExists`. To adopt existing assignments into code you must either import their actual names or delete and recreate them under the template's names. |
| `*` ignore (4) | Application Insights ×2, the smart-detection action group, SQL `master` | Resources in the group that the template does not describe. Incremental mode leaves them alone; complete mode would delete them. The two App Insights components were created by the Function wizard and are worth adding. |

## What I learned

1. **`what-if` is the review step IaC gives you for free.** Read it the way you read a diff: `=` is proof the description is right, `~` needs a reason, `+`/`-` needs a decision.
2. **Role assignments are the first thing hand-built environments get wrong in code.** Random names on the live side, deterministic names in the template: same intent, different identity.
3. **Some settings are not ARM at all.** The static website on the storage account is a data-plane setting (`az storage blob service-properties update --static-website`); the SQL schemas, the Key Vault secret values, the federated credential's subject, and the Function app settings live outside this file on purpose.
4. **Student-subscription regions are a parameter, not an accident.** Two location parameters carry the allowlist constraint (`northcentralus`, `germanywestcentral`) that shaped every build.
5. **Flex Consumption needs `functionAppConfig`, not `siteConfig.linuxFxVersion`.** Runtime, deployment container and scale settings are a different shape from the older Consumption plan.

## Not done, on purpose

- No deployment. The portfolio runs; the template is a description with a verified diff.
- The operator's own role assignments (Storage Blob Data Contributor, Key Vault Secrets Officer, Search and Language roles) are not templated: they belong to a person, not the system.
- App Insights components are not described (two `*` lines above). Adding them is the first improvement if this template is ever used to rebuild.
