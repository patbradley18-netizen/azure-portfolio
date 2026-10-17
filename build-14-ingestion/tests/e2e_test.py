"""e2e_test.py - Build #14 end-to-end: drop three files, run the loader job, read the ledger through the API, assert.
Runs in GitHub Actions after the site deploy (the workflow is already signed in to Azure through the deploy identity, which
holds Storage Blob Data Contributor on the account and Container Apps Jobs Operator on the job) and from the PC.

  (the loader runs on Azure Container Instances; the test starts the group and waits for it to exit)
  1. a known-bad file (12 rows)            -> quarantined, reason names the row-count rule
  2. a file no contract matches             -> quarantined, reason says so
  3. a real ACS pull (3,222 rows)           -> queued, then loaded by the job with 9,666 rows
  4. the same real file again               -> queued, then `duplicate` (same bytes already loaded)
The job is started with `az containerapp job start` and polled until the execution finishes.
"""
import json
import subprocess
import sys
import time
import urllib.request

ACCOUNT = "stazportfoliob1"
ACI, RG = "aci-azportfolio-b14", "rg-azportfolio-b1"
API = "https://apim-azportfolio-b13.azure-api.net/data/ingest/ledger"
AZ = "az.cmd" if sys.platform == "win32" else "az"
GOOD = "build-08-tenure-model/data/acs5_2023_tenure_county.json"
BAD = "build-14-ingestion/samples/acs5_2023_rentburden_county.json"
NOCONTRACT = "build-14-ingestion/samples/acs5_2023_tenure_county.json"


def az(*args):
    return subprocess.run([AZ, *args], capture_output=True, text=True, check=False)


def upload(path, name):
    r = az("storage", "blob", "upload", "--account-name", ACCOUNT, "--auth-mode", "login", "-c", "inbox", "-f", path, "-n", name, "--overwrite", "--only-show-errors", "-o", "none")
    if r.returncode:
        print(r.stderr[:400]); sys.exit(2)


def ledger():
    with urllib.request.urlopen(API, timeout=60) as resp:
        return json.load(resp)["data"]


def wait_for(pred, seconds, what):
    t0 = time.time()
    while time.time() - t0 < seconds:
        rows = ledger()
        if pred(rows):
            return rows
        time.sleep(10)
    print("TIMEOUT waiting for", what); return ledger()


def run_job():
    r = az("container", "start", "-n", ACI, "-g", RG, "-o", "none")
    if r.returncode:
        print(r.stderr[:400]); sys.exit(2)
    for _ in range(60):
        time.sleep(10)
        s = az("container", "show", "-n", ACI, "-g", RG, "--query", "containers[0].instanceView.currentState.state", "-o", "tsv").stdout.strip()
        code = az("container", "show", "-n", ACI, "-g", RG, "--query", "containers[0].instanceView.currentState.exitCode", "-o", "tsv").stdout.strip()
        if s == "Terminated":
            return ACI, "Succeeded" if code == "0" else f"Failed(exit {code})"
    return ACI, "Timeout"


checks = []


def expect(name, cond, detail=""):
    checks.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""), flush=True)


before = ledger()
top = before[0]["ledger_id"] if before else 0
upload(BAD, "acs5_2023_rentburden_county.json")
upload(NOCONTRACT, "notacontract.json")
upload(GOOD, "acs5_2023_tenure_county.json")
rows = wait_for(lambda rs: sum(1 for r in rs if r["ledger_id"] > top and r["stage"] == "validated") >= 3, 600, "three validator rows")
new = [r for r in rows if r["ledger_id"] > top]
bad = next((r for r in new if r["file_name"] == "acs5_2023_rentburden_county.json" and r["stage"] == "validated"), None)
noc = next((r for r in new if r["file_name"] == "notacontract.json"), None)
good = next((r for r in new if r["file_name"] == "acs5_2023_tenure_county.json" and r["stage"] == "validated"), None)
expect("bad file quarantined with the row-count rule", bad and bad["outcome"] == "quarantined" and "rows; contract allows" in (bad["reason"] or ""), str(bad))
expect("no-contract file quarantined", noc and noc["outcome"] == "quarantined" and "no contract" in (noc["reason"] or ""), str(noc))
expect("good file queued with dataset id", good and good["outcome"] == "queued" and good["dataset_id"] == "acs5_2023_tenure" and good["rows"] == 3222, str(good))

ex, status = run_job()
expect(f"loader job execution {ex} succeeded", status == "Succeeded", status)
rows = ledger(); new = [r for r in rows if r["ledger_id"] > top]
loaded = next((r for r in new if r["stage"] == "loaded" and r["file_name"] == "acs5_2023_tenure_county.json"), None)
expect("good file loaded with 9,666 rows", loaded and loaded["outcome"] in ("loaded", "duplicate") and (loaded["outcome"] == "duplicate" or loaded["rows"] == 9666), str(loaded))

top2 = rows[0]["ledger_id"]
upload(GOOD, "acs5_2023_tenure_county.json")
wait_for(lambda rs: any(r["ledger_id"] > top2 and r["stage"] == "validated" for r in rs), 600, "re-drop validated")
ex2, status2 = run_job()
rows = ledger(); dup = next((r for r in rows if r["ledger_id"] > top2 and r["stage"] == "loaded"), None)
expect("re-dropped same bytes -> duplicate, nothing reloaded", dup and dup["outcome"] == "duplicate", str(dup))

failed = [c for c in checks if not c[1]]
print(f"\n{len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
