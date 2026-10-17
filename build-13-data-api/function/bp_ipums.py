"""Build #15: two wars, matched years — the IPUMS extract pipeline as a Durable blueprint.

Async-job pattern: submit an IPUMS CPS extract → poll its status on a durable timer (no function sits awake waiting) →
download the finished csv.gz to Blob `ipums/` with the app's identity → queued ingestion into the Azure Data Explorer
free cluster (database `vets`, table `cps_raw`) with the same identity. The IPUMS key is read by name from an app
setting that is a Key Vault reference; the cluster, database and container are names in settings too.

Lives in build #13's app because Flex Consumption allows one app per plan and the subscription throttled plan creates
on 2026-10-17; see build-15-two-wars/README.md.
"""
import datetime as dt
import json
import logging
import os
import tempfile

import azure.durable_functions as df
import azure.functions as func

bp = df.Blueprint()
IPUMS = "https://api.ipums.org"
COLLECTION = "cps"
SAMPLES = ["cps1985_04s", "cps1987_11s", "cps1991_09s", "cps1993_09s", "cps1995_08s", "cps1997_09s", "cps1999_09s",
           "cps2001_08s", "cps2003_08s", "cps2005_08s", "cps2007_08s", "cps2009_08s", "cps2010_07s"] + [f"cps{y}_08s" for y in range(2011, 2026)]
VARIABLES = ["AGE", "SEX", "EMPSTAT", "LABFORCE", "VETSTAT", "VWHEN", "VVIETNAM", "VIRAQ", "VAFGHAN", "VCOMBAT", "VLASTSERVE", "VDISRATE", "VDISABLE", "VTSUPPWT"]


def _headers():
    return {"Authorization": os.environ["IPUMS_API_KEY"], "Content-Type": "application/json"}


def _get(url):
    import requests
    r = requests.get(url, headers=_headers(), timeout=60)
    r.raise_for_status()
    return r.json()


@bp.function_name("ipums_extract_start")
@bp.route(route="ipums/extract", methods=["POST"])
@bp.durable_client_input(client_name="client")
async def ipums_extract_start(req: func.HttpRequest, client) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        body = {}
    job = {"samples": body.get("samples") or SAMPLES, "variables": body.get("variables") or VARIABLES,
           "description": body.get("description") or f"azportfolio build15 {dt.date.today().isoformat()}", "trigger": "http"}
    instance_id = await client.start_new("ipums_orchestrator", None, job)
    return client.create_check_status_response(req, instance_id)


@bp.function_name("ipums_annual")
@bp.timer_trigger(schedule="0 0 4 15 10 *", arg_name="timer", run_on_startup=False)  # 15 Oct 04:00 UTC: the August supplement is out by then
@bp.durable_client_input(client_name="client")
async def ipums_annual(timer: func.TimerRequest, client) -> None:
    instance_id = await client.start_new("ipums_orchestrator", None, {"samples": SAMPLES, "variables": VARIABLES,
                                                                      "description": f"azportfolio build15 annual {dt.date.today().isoformat()}", "trigger": "timer"})
    logging.info("ipums annual extract started %s", instance_id)


@bp.orchestration_trigger(context_name="context")
def ipums_orchestrator(context: df.DurableOrchestrationContext):
    job = context.get_input() or {}
    number = yield context.call_activity("ipums_submit", job)
    polls = 0
    while True:
        status = yield context.call_activity("ipums_status", {"number": number})
        if status == "completed":
            break
        if status in ("failed", "canceled"):
            raise RuntimeError(f"IPUMS extract {number} ended {status}")
        polls += 1
        if polls > 180:  # three hours of one-minute polls
            raise RuntimeError(f"IPUMS extract {number} still {status} after {polls} polls")
        yield context.create_timer(context.current_utc_datetime + dt.timedelta(seconds=60))
    landed = yield context.call_activity("ipums_download", {"number": number})
    retry = df.RetryOptions(first_retry_interval_in_milliseconds=30000, max_number_of_attempts=3)
    ingest = yield context.call_activity_with_retry("adx_ingest", retry, {"number": number, "blob": landed["blob"]})
    return {"extract": number, "polls": polls, **landed, **ingest}


@bp.activity_trigger(input_name="job")
def ipums_submit(job: dict) -> int:
    import requests
    body = {"description": job["description"], "dataStructure": {"rectangular": {"on": "P"}}, "dataFormat": "csv",
            "samples": {s: {} for s in job["samples"]}, "variables": {v: {} for v in job["variables"]}}
    r = requests.post(f"{IPUMS}/extracts?collection={COLLECTION}&version=2", headers=_headers(), data=json.dumps(body), timeout=60)
    r.raise_for_status()
    number = int(r.json()["number"])
    logging.info("ipums extract %s submitted (%s samples)", number, len(job["samples"]))
    return number


@bp.activity_trigger(input_name="q")
def ipums_status(q: dict) -> str:
    return _get(f"{IPUMS}/extracts/{q['number']}?collection={COLLECTION}&version=2")["status"]


@bp.activity_trigger(input_name="q")
def ipums_download(q: dict) -> dict:
    """Streams the finished extract into Blob `ipums/cps_<number>.csv.gz` (plus the codebook) with the app's identity."""
    import requests
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient
    meta = _get(f"{IPUMS}/extracts/{q['number']}?collection={COLLECTION}&version=2")
    links = meta["downloadLinks"]
    svc = BlobServiceClient(os.environ["STORAGE_ACCOUNT_URL"], credential=DefaultAzureCredential())
    container = svc.get_container_client(os.environ.get("IPUMS_CONTAINER", "ipums"))
    out = {}
    for key, name in (("data", f"cps_{q['number']:05d}.csv.gz"), ("basicCodebook", f"cps_{q['number']:05d}.cbk")):
        with requests.get(links[key]["url"], headers={"Authorization": os.environ["IPUMS_API_KEY"]}, stream=True, timeout=600) as r:
            r.raise_for_status()
            container.upload_blob(name, r.raw, overwrite=True, length=links[key]["bytes"])
        out[key] = name
    return {"blob": out["data"], "codebook": out["basicCodebook"], "bytes": links["data"]["bytes"], "sha256": links["data"]["sha256"]}


@bp.activity_trigger(input_name="q")
def adx_ingest(q: dict) -> dict:
    """Queued ingestion into the free cluster. The SDK stages the file through Kusto's own storage with the caller's token;
    no SAS of ours, no key. Tag = extract number so the rows can be told apart (and dropped) later."""
    from azure.identity import DefaultAzureCredential
    from azure.kusto.data import KustoConnectionStringBuilder
    from azure.kusto.ingest import IngestionProperties, QueuedIngestClient
    from azure.kusto.data.data_format import DataFormat
    from azure.storage.blob import BlobServiceClient
    cred = DefaultAzureCredential()
    svc = BlobServiceClient(os.environ["STORAGE_ACCOUNT_URL"], credential=cred)
    blob = svc.get_blob_client(os.environ.get("IPUMS_CONTAINER", "ipums"), q["blob"])
    with tempfile.NamedTemporaryFile(suffix=".csv.gz", delete=False) as f:
        blob.download_blob().readinto(f)
        path = f.name
    kcsb = KustoConnectionStringBuilder.with_azure_token_credential(os.environ["ADX_INGEST_URI"], cred)
    client = QueuedIngestClient(kcsb)
    props = IngestionProperties(database=os.environ["ADX_DATABASE"], table=os.environ.get("ADX_TABLE", "cps_raw"), data_format=DataFormat.CSV,
                                ignore_first_record=True, additional_tags=[f"extract:{q['number']}"], drop_by_tags=[f"extract:{q['number']}"])
    result = client.ingest_from_file(path, ingestion_properties=props)
    os.remove(path)
    return {"ingest": str(result.status), "table": props.table, "tag": f"extract:{q['number']}"}
