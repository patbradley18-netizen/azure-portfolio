# Build #14: The pipeline that says no — event-driven ingestion with a data contract, quarantine, idempotency, poison handling and a container loader

**Anchor phrase: every file is guilty until the gate clears it.**

Live page: https://stazportfoliob1.z14.web.core.windows.net/build-14-ingestion/ · ledger: `GET https://apim-azportfolio-b13.azure-api.net/data/ingest/ledger`

## The problem

Thirteen builds loaded data from scripts an operator ran by hand. A data product has to take files from the outside and refuse the bad ones without a person watching. This build is that: drop a file in a container; events, not polling; a validator with a **data contract**; **quarantine** with a reason; a loader that is **idempotent** by content hash; **poison** handling for messages that keep failing; **dead-lettering** for events that cannot be delivered; and a **ledger** row for every decision, served by build #13's API. The loader is a **container image** built by GitHub Actions, published to GitHub Container Registry and run on Azure with a managed identity.

**What happened in the ledger:** a 12-row file → quarantined (*12 rows; contract allows 3100–3300*); a file no contract matches → quarantined; the real tenure pull → queued, then **loaded 9,666 rows** into `acs5_2023_tenure` (the number build #8 loaded by hand); the same bytes dropped again → **duplicate**, nothing reloaded; a message naming a blob that does not exist → failed five times → **poison**. Event Grid matched 12 events, delivered 6, failed 34 attempts and **dead-lettered 6** to `deadletter/`.

![findings](findings.png)

## Azure services used and why

| Service | Tier / cost | Why |
|---|---|---|
| Event Grid system topic `egst-stazportfoliob1` + subscription `evs-inbox-to-validator` | 100,000 ops/month free; $0 | blob-created events on `inbox/` only; 5 attempts / 60 min; dead-letter to `deadletter/` with the topic's own identity |
| Azure Functions `func-azportfolio-b14` (Flex, Python 3.12) | free grant; $0 | the validator: Event Grid trigger, identity-based blob and queue access, SQL output binding for the ledger |
| Queue Storage `ingest-load`, `ingest-load-poison` | operations at $0.0004 per 10k | the hand-off; the poison queue is explicit because Storage queues have none |
| Azure Container Instances `aci-azportfolio-b14` (0.5 vCPU, 0.5 GiB, restart Never, system identity) | per second while running: a run is ~5 s → fractions of a cent | the loader; started nightly by a timer in build #13's Function app through ARM |
| GitHub Container Registry `ghcr.io/patbradley18-netizen/azportfolio-loader` | free (public repo) | the image, built by `build-loader-image.yml` on every change to `loader/` |
| Azure SQL `aid`, schema `col` | free offer; $0 | `col.ingest_ledger`; validator user INSERT-only; loader user DML on the warehouse tables |

**Cost:** $0 on every free line; queue operations and ACI seconds are fractions of a cent and stated.

## The plan said Container Apps Jobs — and why it isn't

The create test before the plan created a Container Apps *environment* in `northcentralus` and passed. The job did not: new environments on this subscription come up as **express** in every allowlisted region (`ManagedEnvironmentModeNotSupported: Standard is not currently available in this region` for northcentralus, germanywestcentral and spaincentral), and express has no jobs, no system-assigned identity. Lesson: **test the create of the thing you need, not its parent.** The same image runs on ACI with the same identity pattern; the scheduler is a Function timer.

## How it works

```
inbox/ (BlobCreated) ─► Event Grid ─► validator Function ─┬─► ingest-load ─► loader container ─► col.measure (OPENJSON, replace-per-dataset)
                           │ dead-letter: deadletter/      └─► quarantine/<file> + <file>.reason.txt      │ fails ×5 ─► ingest-load-poison
                                              every decision ─► col.ingest_ledger ─► GET /data/ingest/ledger (build #13)
```

- **Contract** (`contracts/acs5_county.yaml`): file-name pattern → dataset id; header rules; row-count bounds; FIPS patterns; unique county; numeric-or-null cells with Census suppression sentinels allowed; a maximum value.
- **Validator**: fetches the blob, hashes it, checks the contract, queues or quarantines, writes the ledger. A blob that has vanished since the event is a no-op (an earlier version raised, and Event Grid retried a non-event 14 times). `poisonpill.json` is the one file it refuses on purpose, to exercise dead-lettering.
- **Loader**: re-hashes and re-checks (never trusts the message); `duplicate` if the hash was already loaded; loads with build #6's OPENJSON path; deletes the inbox blob; moves a message to the poison queue on its fifth failure.
- **Ledger**: one row per gate decision (`validated` → queued|quarantined; `loaded` → loaded|duplicate|poison).

## What went wrong, in order

1. `max_value: 1.0e9` in YAML is a *string* (YAML 1.1 wants `1.0e+9`) → `float > str` crash → `1000000000`.
2. Windows `Compress-Archive` wrote `contracts\acs5_county.yaml` — on Linux a file with a backslash in its name, so no contract loaded → `make_zip.py` (forward slashes).
3. A zip built on the mounted share carried `0700` file modes → the Function host could not read `host.json` → host state *Error*, Event Grid saw *Busy* → `make_zip.py` sets `0644`.
4. The validator raised on a blob that was already quarantined → Event Grid retried 14 times → gone-blob is a no-op now.
5. Container Apps Jobs unavailable (express-only environments) → ACI.
6. `python:3.12-slim` lacks the SQL driver's Kerberos libraries → `libkrb5-3 libgssapi-krb5-2` in the Dockerfile.
7. A recreated container group has a new identity; the SQL external-provider user kept the old SID → `sql_setup.py` drops and recreates the loader user.
8. The loader's first run after recreation hit role-assignment propagation (minutes) → exit 1, then clean.

## Tests

- `tests/e2e_test.py` — drops bad, unknown and good files; starts the loader; asserts quarantine reasons, the load, and the duplicate. Runs on demand and weekly in `ingest-e2e.yml` (Azure login through the deploy identity), and from the PC.
- `tests/poison_message.py` — queues a message the loader cannot satisfy, to exercise the poison path.
- `validator/contract.py` is pure Python; the contract checks run anywhere.

## How to run

```
bash setup.sh aci-azportfolio-b14        # one-time: ledger table, validator user, loader user (SQL token by env)
python make_zip.py data/b14v.zip ...     # validator zip with sane paths and modes, then config-zip --build-remote true
# Event Grid subscription and ACI: see the Build Log for the exact az rest / az container create commands
# Knobs on the container group: MAX_DEQUEUE=5 (poison after the fifth failure) and VISIBILITY_S=30 (a failed message hides 30 s, then
# returns with dequeue_count + 1; the code's default is 300). Changing an env var recreates the group = a new managed identity =
# re-run sql_setup.py for the loader user and re-grant the two storage roles. Left at 30 on purpose at close.
powershell -File snapshot.ps1            # facts for the page -> data/ops_snapshot.json
python build_findings.py
```

## What I learned

1. **Test the create of the thing you need, not its parent.**
2. **A gate that raises on a non-event makes the retry system attack you.** Idempotent no-ops for already-handled work.
3. **Two shells, three platforms:** zip paths and modes are data too.
4. **Storage queues have no poison handling; you write it.** Dequeue count + a visibility window is the whole mechanism.
5. **Never trust the message.** The loader re-hashes and re-checks the bytes.
6. **Managed identities are per resource instance.** Recreate the resource, recreate its database user.
7. **Dead-letter what you cannot deliver, and look at it.** The six dead letters on this page are the build's own outage, recorded.

## Cleanup

`az eventgrid system-topic delete -n egst-stazportfoliob1 -g rg-azportfolio-b1 -y` (takes its subscription); `az container delete -n aci-azportfolio-b14 -g rg-azportfolio-b1 -y`; `az functionapp delete -n func-azportfolio-b14 -g rg-azportfolio-b1`; queues `ingest-load`, `ingest-load-poison`; containers `inbox`, `quarantine`, `deadletter`; SQL: `DROP USER [func-azportfolio-b14]; DROP USER [aci-azportfolio-b14]; DROP TABLE col.ingest_ledger;`. The GHCR image is a package on the repo.

## Files

| File | Purpose |
|---|---|
| `contracts/acs5_county.yaml` | the data contract (copied into validator/ and loader/) |
| `validator/` | the Event Grid-triggered Function and `contract.py` |
| `loader/` | `loader.py`, `Dockerfile`, `requirements.txt`; the image |
| `sql_setup.py`, `setup.sh`, `check_ledger.py`, `make_zip.py`, `snapshot.ps1` | setup, checks, packaging, the page's facts |
| `tests/e2e_test.py`, `tests/poison_message.py` | the end-to-end and the poison exercise |
| `samples/` | the known-bad files |
| `build_findings.py`, `findings.html`, `findings.png` | the page |
| `data/ops_snapshot.json` | committed: the facts as recorded |
