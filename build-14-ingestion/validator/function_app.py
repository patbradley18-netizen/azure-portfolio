"""Build #14 validator: Event Grid tells us a blob landed in `inbox`; we fetch it, hash it, check it against its contract,
and either enqueue a load message, quarantine it with a reason, or record a duplicate. Every outcome is one ledger row.

Identity-based storage access (no keys): the app's managed identity holds Storage Blob Data Contributor and Storage Queue
Data Message Sender on the account. The ledger row is written by a SQL output binding with the same identity.
Event Grid delivery failures dead-letter to the `deadletter` container (configured on the subscription, not here).
"""
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path

import azure.functions as func
import yaml
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueClient, TextBase64EncodePolicy

from contract import check

app = func.FunctionApp()
ACCOUNT_URL = os.environ.get("STORAGE_ACCOUNT_URL", "https://stazportfoliob1.blob.core.windows.net")
QUEUE_URL = os.environ.get("QUEUE_ACCOUNT_URL", "https://stazportfoliob1.queue.core.windows.net")
CONTRACT_DIRS = [Path(__file__).resolve().parent / "contracts", Path.cwd() / "contracts", Path("/home/site/wwwroot/contracts")]
CONTRACTS = {}
for d in CONTRACT_DIRS:
    for p in d.glob("*.yaml") if d.is_dir() else []:
        CONTRACTS.setdefault(p.stem, yaml.safe_load(p.read_text(encoding="utf-8")))
logging.info("contracts loaded: %s from %s", list(CONTRACTS), [str(d) for d in CONTRACT_DIRS if d.is_dir()])
cred = DefaultAzureCredential()


def pick_contract(name):
    import re
    for cid, c in CONTRACTS.items():
        if re.match(c["file_pattern"], name):
            return cid, c
    return None, None


@app.function_name("validate_inbox_blob")
@app.event_grid_trigger(arg_name="event")
@app.sql_output(arg_name="ledger", command_text="col.ingest_ledger", connection_string_setting="SqlConnectionString")
def validate_inbox_blob(event: func.EventGridEvent, ledger: func.Out[str]) -> None:
    # Duplicate detection by content hash is the loader's job (it owns the ledger lookup); the validator records what it
    # saw and gates on the contract. Two gates, two owners.
    data = event.get_json()
    url = data.get("url", "")
    name = url.rsplit("/", 1)[-1]
    container = url.split("/")[-2] if url.count("/") >= 4 else ""
    if container != "inbox" or not name:
        logging.info("ignored event for %s", url)
        return
    if name == "poisonpill.json":  # the one deliberate failure: Event Grid retries, then dead-letters to `deadletter/` (build #14 exercise)
        raise RuntimeError("poisonpill.json: intentional failure to exercise Event Grid dead-lettering")
    bsc = BlobServiceClient(ACCOUNT_URL, credential=cred)
    blob = bsc.get_blob_client("inbox", name)
    try:
        raw = blob.download_blob().readall()
    except ResourceNotFoundError:
        # Event Grid may redeliver an event for a blob the first delivery already quarantined or the loader already removed.
        # That is a no-op, not an error: raising here would make Event Grid retry and eventually dead-letter a non-event.
        logging.info("blob %s is gone (already handled); event acknowledged", name)
        return
    sha = hashlib.sha256(raw).hexdigest()
    row = {"sha256": sha, "file_name": name, "blob_url": url, "size_bytes": len(raw), "received_at": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z",
           "stage": "validated", "outcome": None, "reason": None, "dataset_id": None, "rows": None, "run_by": "func-azportfolio-b14"}
    cid, contract = pick_contract(name)
    if not contract:
        ok, reason, info = False, f"no contract matches this file name ({len(CONTRACTS)} contract(s) loaded)", {}
    else:
        try:
            doc = json.loads(raw.decode("utf-8"))
            ok, reason, info = check(doc, contract, name)
        except (UnicodeDecodeError, ValueError) as e:
            ok, reason, info = False, f"not valid JSON: {str(e)[:80]}", {}
    row.update(dataset_id=info.get("dataset_id"), rows=info.get("rows"))
    if ok:
        q = QueueClient(QUEUE_URL, "ingest-load", credential=cred, message_encode_policy=TextBase64EncodePolicy())
        q.send_message(json.dumps({"sha256": sha, "file_name": name, "blob_url": url, "dataset_id": info["dataset_id"], "contract": cid, "year": info["year"], "set": info["set"]}))
        row.update(outcome="queued", reason="passed contract " + cid)
    else:
        qc = bsc.get_blob_client("quarantine", name)
        qc.upload_blob(raw, overwrite=True)
        bsc.get_blob_client("quarantine", name + ".reason.txt").upload_blob(reason.encode("utf-8"), overwrite=True)
        blob.delete_blob()
        row.update(outcome="quarantined", reason=reason)
    ledger.set(json.dumps(row))
    logging.info("validated %s -> %s (%s)", name, row["outcome"], row["reason"])
