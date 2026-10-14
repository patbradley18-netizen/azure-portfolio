# Build #1: Algorithmic Influence Detector (AID Lite), stages 1–2

Detecting coordinated messaging in social-media text with Azure Storage, Azure SQL, and Python. Part of my [Azure learning portfolio](../README.md): small, free-tier builds that each teach one real skill and end as a public showcase.

![Stage 1 dashboard](dashboard.png)

## The problem

Influence campaigns post the same message from many accounts and disguise the copies with small edits. The question for stage 1: **given a pile of tweets and no labels, can we find the messages that were pushed by many accounts, and the accounts that pushed them?**

Data: the FiveThirtyEight / Clemson release of ~3 million tweets from accounts Twitter attributed to the Internet Research Agency. I used file 1 of 13 (84,270 English original tweets). The researchers' hand-assigned account categories (RightTroll, LeftTroll, NewsFeed, HashtagGamer, ...) serve as a check on the results; the model never sees them.

## What I found

- **1,642 distinct messages were posted by two or more accounts**, covering **26% of all tweets in the file**. "Distinct message" means identical body text after stripping links and leading/trailing hashtags.
- **A 44-account ring.** The same identical headline ("6 top choices to replace disgraced McConnell", and dozens more) was posted by 44 different accounts, once each. 563 messages were pushed by 10 or more accounts.
- **The disguise is a junk hashtag prefix.** Posts like `#ade VIDEO : President Trump Reacts...` and `#ameliss VIDEO : President Trump Reacts...` are the same message. Each junk tag (`#amb`, `#ara`, `#alis`) appears hundreds of times, which suggests one tag per account.
- **In this file, nearly all of the coordination is one category:** 1,571 of 1,642 templates come from RightTroll accounts. LeftTroll accounts never had more than 5 accounts on one message. This is a finding about file 1, not the whole release.
- **Embeddings agree with the humans.** Clustering tweets by meaning (sentence embeddings + KMeans, k=20) produced clusters that are 94–99.7% one hand-assigned category at the top end, with no labels used.

## Azure services and why

| Service | Role | Why this one | Cost |
|---|---|---|---|
| Blob Storage (Standard, LRS) | Holds the raw 94 MB dataset | Cheapest durable storage; the file is public and re-downloadable, so one copy (LRS) is enough | $0 (within free allowance) |
| Azure SQL Database (free offer, serverless) | Holds results: `posts` (5,000-row clustered sample) and `templates` (1,642 rows); answers the analyst questions in T-SQL | 100,000 vCore-seconds/month free; auto-pauses when idle and when the free amount runs out | $0 |
| Microsoft Entra ID | Sign-in to SQL | Entra-only authentication means there is no SQL password anywhere | $0 |

The embeddings, clustering and template detection run locally in Python (WSL2 Ubuntu). Keeping ML off Azure kept the build at $0.

## Architecture

```
FiveThirtyEight CSV (public)
        |
        v
Blob Storage  stazportfoliob1/raw          <- raw data, one copy
        |
        v
Python (local, WSL2)
   sentence-transformers  -> 384-dim vectors -> KMeans k=20   (signal A: same meaning)
   strip URLs/hashtags    -> exact-body groups across accounts (signal B: same text)
        |
        v
Azure SQL  aid.dbo.posts, aid.dbo.templates   <- Entra sign-in, no password
        |
        v
T-SQL queries (run_queries.py) -> dashboard_data.json -> dashboard.html
```

## Files

| File | What it does |
|---|---|
| `cluster_sample.py` | Signal A: embed a 5,000-tweet sample and cluster it |
| `tune_and_flag.py` | Silhouette across k (didn't help, see below) and a hashtag rule (wrong, see below) |
| `diag_templates.py` | Signal B: identical bodies posted by 2+ accounts |
| `load_to_sql.py` | Creates the two tables and loads results; Entra token by environment variable |
| `run_queries.py` | The analyst's four questions in T-SQL; writes the dashboard JSON |
| `dashboard.html` | Static page built from the JSON (no external scripts) |
| `setup_wsl.sh`, `install_sql_driver.sh` | Environment setup |

Not in the repo: the dataset, result CSVs, logs, and any settings file (`.gitignore`).

## Secrets handling

No key, password or connection string appears in this repo, in any output, or in the dashboard.

- Server and database are referenced **by name** through `SQL_SERVER_NAME` and `SQL_DATABASE_NAME` environment variables.
- Sign-in is Microsoft Entra: a short-lived token from `az account get-access-token`, passed by environment variable only, or a device-code prompt. Nothing is written to disk.
- The SQL server is **Entra-only**; SQL password authentication is disabled at the server.
- Blob access used a role assignment (Storage Blob Data Contributor) scoped to one storage account, not an account key.

## What it cost

$0. Storage is inside the free allowance; the database is on the free offer with auto-pause. Budget alert on the subscription: $10/month.

## What I learned

1. **Newest isn't best for data tooling.** Python 3.15 came out four days before I started; PyTorch had no build for it. Python 3.12 worked first time.
2. **Windows Smart App Control blocks unsigned pip packages** (SciPy, PyTorch). WSL2 Ubuntu sidesteps it and matches the Linux that Azure Functions runs on.
3. **Azure for Students has a hidden region allowlist** (mine: North Central US plus four European regions). It isn't shown on any create form, and the error doesn't name the regions. Find it under Policy → Assignments → "Allowed resource deployment regions".
4. **An allowed region can still refuse capacity.** North Central US accepted storage but not a new SQL server, so SQL lives in Germany West Central.
5. **The portal's create form can resubmit a stale region** after validation fails. The CLI doesn't.
6. **Each service family must be registered once per subscription** (`az provider register`). The portal hides this; the CLI tells you.
7. **Owner of a subscription still can't read blob data** without a separate data-plane role. Control plane and data plane are different permissions, by design.
8. **A serverless database's first connection after idle can time out.** Retry once.
9. **Pick the metric for the data.** Silhouette score was flat (0.02) for every k; it measures tidy round clusters and short tweets don't make those. I kept k=20 and said so.
10. **My first rule was wrong, and the data corrected it.** I assumed the junk hashtags were rare one-offs. They repeat hundreds of times. The real fingerprint was the duplicated body text, not the tag.
11. **Python goes in a `.py` file, not the PowerShell prompt.** Yes, I did that.

## How to run

```
# WSL2 Ubuntu, from this folder
bash setup_wsl.sh
bash install_sql_driver.sh
python cluster_sample.py        # needs data/IRAhandle_tweets_1.csv from the FiveThirtyEight repo
python diag_templates.py
export SQL_SERVER_NAME=<server>.database.windows.net SQL_DATABASE_NAME=<db>
python load_to_sql.py           # prompts for a device-code sign-in
python run_queries.py
```

## Data credit and limits

Data: FiveThirtyEight, ["Why we're sharing 3 million Russian troll tweets"](https://fivethirtyeight.com/features/why-were-sharing-3-million-russian-troll-tweets) (2018); collected by Darren Linvill and Patrick Warren, Clemson University. The repository carries no license file; this is non-commercial educational use with attribution. The accounts are state-operator accounts publicly identified by Twitter, not private individuals.

Findings describe file 1 of 13 only. The category skew may reflect which accounts happen to be in this file. Short, generic tweets form noisy clusters; that is a known limit of this method.

## Stage 2: the detection runs itself

Stage 2 moves signal B (template detection) onto a schedule with no person and no laptop in the loop, and adds key phrases from Azure AI Language.

```
Timer (Mondays 06:00 UTC)
   |
   v
Azure Function  func-azportfolio-b1  (Python 3.12, Flex Consumption, Germany West Central)
   |  managed identity: Storage Blob Data Reader, Cognitive Services User, SQL db_datareader/db_datawriter
   |-- blob input binding  -> raw/IRAhandle_tweets_1.csv       (identity-based connection, no key)
   |-- detect.py           -> 1,642 templates in ~10 s
   |-- AI Language (F0)    -> key phrases for the top 50 messages
   '-- SQL output binding  -> dbo.template_runs (one run_id per run; history kept)
```

| Service | Role | Cost |
|---|---|---|
| Azure Functions, Flex Consumption | Runs the job weekly, scales to zero between runs | $0 (one ~25 s run a week, inside the free grant) |
| Azure AI Language, F0 | Key phrases for the top 50 templates per run | $0 (5,000 text records/month free; ~50 used) |
| Application Insights | Function logs, sampling on | pennies at most |
| Managed identity | The function signs in to Blob, Language and SQL as itself | $0 |

First automated run: 2026-10-14 21:22 UTC, 1,642 rows, 50 with key phrases (for example "6 top choices; disgraced mcconnell", "deep state assassination; ex-mueller deputy; breaking; trump").

**What stays local on purpose:** signal A (embeddings). PyTorch is about 3 GB and does not belong in a serverless function. The template signal is the headline finding, so the function automates that.

**Secrets in stage 2:** none. The function's "connection string" setting contains server and database names plus `Authentication=Active Directory Managed Identity`. The blob connection is a URL. The Language endpoint is a URL. Access comes from three role grants, each scoped to one resource.

### Stage 2 lessons

12. **A function inside Azure is still outside your SQL firewall.** The first run failed with "Client with IP address … is not allowed." Fix: the server-level "Allow Azure services" rule. Trade-off: any Azure-hosted service can now *reach* the server, but nothing can sign in without a granted Entra identity. Private networking would be tighter and is out of scope for a free build.
13. **Bindings beat drivers.** Using the blob input and SQL output bindings meant no database driver to install in the function, no connection code, and no credentials. The host handles it from the setting names.
14. **The SQL output binding needs a primary key** on the target table, and it upserts. Giving every row a `run_id` turns weekly runs into a history instead of an overwrite.
15. **Remote build is slow but worth it.** Deploying a zip and letting Azure install `pandas` took a few minutes; it avoids shipping Windows- or WSL-built packages to a Linux host.

## Next

Stage 3: amplification networks (which accounts co-post which templates) and narrative bursts over time. Possible stage 4: narrative persistence across later public corpora, measured as similarity only, no attribution of people or organizations.