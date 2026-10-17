"""loader.py - Build #14 loader, run as an Azure Container Apps Job (scheduled nightly; started on demand for tests).

Drains the `ingest-load` queue. For each message: idempotency check by SHA-256 against col.ingest_ledger (a hash already
loaded -> outcome `duplicate`, message deleted); re-fetch the blob and re-check the contract (never trust the message);
load with the same OPENJSON path as build #6's loaders, replace-per-dataset; ledger row `loaded` with the row count.
Poison handling is explicit because Storage queues have none: a message whose dequeue_count reaches MAX_DEQUEUE is moved
to `ingest-load-poison` and the ledger says `poison` with the last error. Auth everywhere by the job's managed identity.
"""
import datetime as dt
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import mssql_python
import yaml
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueClient, TextBase64DecodePolicy, TextBase64EncodePolicy

from contract import check

BLOB_URL = os.environ["STORAGE_ACCOUNT_URL"]
QUEUE_URL = os.environ["QUEUE_ACCOUNT_URL"]
SQL_SERVER = os.environ["SQL_SERVER_NAME"]
SQL_DB = os.environ["SQL_DATABASE_NAME"]
MAX_DEQUEUE = int(os.environ.get("MAX_DEQUEUE", "5"))
RUN_BY = os.environ.get("RUN_BY", "caj-azportfolio-b14")
CONTRACTS = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in (Path(__file__).parent / "contracts").glob("*.yaml")}
UNITS = {"B25064_001E": "USD/month", "B25077_001E": "USD", "B25088_002E": "USD/month", "B19013_001E": "USD/year",
         "B25003_001E": "households", "B25003_002E": "households", "B25003_003E": "households"}
cred = DefaultAzureCredential()


def sql_connect():
    tok = cred.get_token("https://database.windows.net/.default").token

    class TP:
        def get_token(self, *a, **k):
            return SimpleNamespace(token=tok)
    for i in range(4):
        try:
            return mssql_python.connect(f"Server={SQL_SERVER};Database={SQL_DB};Encrypt=yes;", token_provider=TP())
        except Exception as e:  # serverless db waking, or something else: say which
            print("connect retry", i + 1, type(e).__name__, str(e)[:300], flush=True)
            if i == 0:
                import socket
                try:
                    socket.create_connection((SQL_SERVER, 1433), timeout=10).close(); print("  tcp 1433 reachable", flush=True)
                except OSError as te:
                    print("  tcp 1433 NOT reachable:", te, flush=True)
            time.sleep(20)
    raise RuntimeError("database did not wake")


def ledger(cur, **row):
    cur.execute("""INSERT INTO col.ingest_ledger (sha256, file_name, blob_url, size_bytes, received_at, stage, outcome, reason, dataset_id, rows, run_by)
                   VALUES (?, ?, ?, ?, SYSUTCDATETIME(), 'loaded', ?, ?, ?, ?, ?)""",
                (row["sha256"], row["file_name"], row.get("blob_url"), row.get("size_bytes"), row["outcome"], (row.get("reason") or "")[:400], row.get("dataset_id"), row.get("rows"), RUN_BY))


def load_acs(cur, doc, dataset_id, year, src_name):
    header, body = doc[0], doc[1:]
    ix = {h: i for i, h in enumerate(header)}
    codes = [c for c in header if c.startswith("B")]
    rows, counties = [], []
    for r in body:
        fips = r[ix["state"]] + r[ix["county"]]
        counties.append((fips, r[ix["NAME"]][:80], r[ix["state"]]))
        for code in codes:
            v = r[ix[code]]
            if v is None or v == "" or float(v) < 0:
                rows.append({"f": fips, "c": code, "v": None, "t": "SUPPRESSED" if v not in (None, "") else "MISSING"})
            else:
                rows.append({"f": fips, "c": code, "v": float(v), "t": None})
    cur.executemany("""MERGE col.county AS t USING (VALUES (?,?,?)) AS s(fips,name,state_fips) ON t.fips=s.fips
        WHEN NOT MATCHED THEN INSERT (fips,name,state_fips) VALUES (s.fips,s.name,s.state_fips);""", counties)
    cur.execute("""MERGE col.dataset AS t USING (VALUES (?,?,?,?,?)) AS s(dataset_id,tool,vintage,as_of,source_file) ON t.dataset_id=s.dataset_id
        WHEN MATCHED THEN UPDATE SET vintage=s.vintage, as_of=s.as_of, source_file=s.source_file, loaded_at=SYSUTCDATETIME()
        WHEN NOT MATCHED THEN INSERT (dataset_id,tool,vintage,as_of,source_file) VALUES (s.dataset_id,s.tool,s.vintage,s.as_of,s.source_file);""",
                (dataset_id, "census", f"ACS 5-year {year}", time.strftime("%Y-%m-%d"), src_name))
    cur.executemany("""MERGE col.metric AS t USING (VALUES (?,?,?,?)) AS s(dataset_id,code,name,unit) ON t.dataset_id=s.dataset_id AND t.code=s.code
        WHEN NOT MATCHED THEN INSERT (dataset_id,code,name,unit) VALUES (s.dataset_id,s.code,s.name,s.unit);""",
                    [(dataset_id, c, c, UNITS.get(c, "people")) for c in codes])  # labels come from the API metadata in the fetch step; the pipeline keeps codes
    cur.execute("DELETE FROM col.measure WHERE dataset_id = ?", (dataset_id,))
    for i in range(0, len(rows), 20000):
        cur.execute("""INSERT INTO col.measure (fips,dataset_id,code,value,text)
                       SELECT j.f, ?, j.c, j.v, j.t FROM OPENJSON(?) WITH (f CHAR(5) '$.f', c NVARCHAR(30) '$.c', v FLOAT '$.v', t NVARCHAR(40) '$.t') AS j""",
                    (dataset_id, json.dumps(rows[i:i + 20000])))
    return len(rows)


def main():
    q = QueueClient(QUEUE_URL, "ingest-load", credential=cred, message_decode_policy=TextBase64DecodePolicy())
    poison = QueueClient(QUEUE_URL, "ingest-load-poison", credential=cred, message_encode_policy=TextBase64EncodePolicy())
    bsc = BlobServiceClient(BLOB_URL, credential=cred)
    conn = sql_connect(); cur = conn.cursor()
    handled = 0
    for msg in q.receive_messages(messages_per_page=8, visibility_timeout=300, max_messages=64):
        handled += 1
        body = json.loads(msg.content)
        name, sha = body["file_name"], body["sha256"]
        print(f"message {name} dequeue_count={msg.dequeue_count}", flush=True)
        try:
            if msg.dequeue_count > MAX_DEQUEUE:
                raise RuntimeError(f"dequeued {msg.dequeue_count} times")
            cur.execute("SELECT TOP 1 outcome FROM col.ingest_ledger WHERE sha256 = ? AND stage = 'loaded' AND outcome = 'loaded'", (sha,))
            if cur.fetchone():
                ledger(cur, sha256=sha, file_name=name, blob_url=body.get("blob_url"), outcome="duplicate", reason="same bytes already loaded", dataset_id=body.get("dataset_id"))
                conn.commit(); q.delete_message(msg); print("  duplicate", flush=True); continue
            raw = bsc.get_blob_client("inbox", name).download_blob().readall()
            if hashlib.sha256(raw).hexdigest() != sha:
                raise RuntimeError("blob bytes changed since validation")
            contract = CONTRACTS[body["contract"]]
            ok, reason, info = check(json.loads(raw.decode("utf-8")), contract, name)
            if not ok:
                raise RuntimeError("contract failed at load time: " + reason)
            n = load_acs(cur, json.loads(raw.decode("utf-8")), info["dataset_id"], info["year"], name)
            ledger(cur, sha256=sha, file_name=name, blob_url=body.get("blob_url"), size_bytes=len(raw), outcome="loaded", reason="replace-per-dataset", dataset_id=info["dataset_id"], rows=n)
            conn.commit()
            bsc.get_blob_client("inbox", name).delete_blob()  # loaded files leave the inbox; the ledger is the record
            q.delete_message(msg); print(f"  loaded {n:,} rows into {info['dataset_id']}", flush=True)
        except Exception as e:  # noqa: BLE001
            conn.rollback()
            err = f"{type(e).__name__}: {str(e)[:200]}"
            print("  failed:", err, flush=True)
            if msg.dequeue_count >= MAX_DEQUEUE:
                poison.send_message(json.dumps({**body, "error": err, "dequeue_count": msg.dequeue_count}))
                ledger(cur, sha256=sha, file_name=name, blob_url=body.get("blob_url"), outcome="poison", reason=err, dataset_id=body.get("dataset_id"))
                conn.commit(); q.delete_message(msg); print("  -> poison queue", flush=True)
            # otherwise: leave it; visibility timeout expires and it comes back with dequeue_count + 1
    print(f"done: {handled} message(s)", flush=True)
    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(); sys.exit(1)
