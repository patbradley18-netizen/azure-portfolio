"""Build #13: the warehouse as a product. An HTTP API over schema `col` plus a Durable orchestration that rebuilds
col.county_access state by state (fan-out / fan-in) on a monthly timer.

Reads go through SQL input bindings (parameterised T-SQL or stored procedures) with the app's managed identity:
no driver in the code, no connection string value anywhere but the platform's app setting by name.
Every endpoint returns {"data": ..., "meta": {...}}; errors return {"error": ...} with a proper status code.
"""
import datetime as dt
import json
import logging
import os
import re

import azure.durable_functions as df
import azure.functions as func

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)

from bp_ipums import bp as ipums_bp  # Build #15: IPUMS → Blob → ADX (one app per Flex plan; plan creates throttled)
app.register_functions(ipums_bp)
VERSION = "1.0.0"
SOURCE_NOTE = "Facilities: VA VAST extract 2018-09-29 via HRSA; veterans: ACS 5-year 2023 B21001; county origins: 2020 Census centers of population. Straight-line miles."


def ok(data, **meta):
    meta.update(version=VERSION, generated_at=dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z")
    return func.HttpResponse(json.dumps({"data": data, "meta": meta}, default=str), mimetype="application/json")


def bad(msg, status=400):
    return func.HttpResponse(json.dumps({"error": msg}), status_code=status, mimetype="application/json")


def rows(binding):
    return json.loads(binding) if isinstance(binding, str) else [json.loads(r.to_json()) for r in binding]


# ---------------- read endpoints ----------------
@app.function_name("county_access")
@app.route(route="counties/{fips}/access", methods=["GET"])
@app.sql_input(arg_name="r", command_text="SELECT fips, county, state_abbr, veterans, ROUND(vet_share, 2) AS vet_share, vamc_sta_no, vamc_name, ROUND(vamc_miles, 1) AS vamc_miles, site_sta_no, site_name, site_kind, ROUND(site_miles, 1) AS site_miles, center_kind, computed_at FROM col.county_access WHERE fips = @fips",
               command_type="Text", parameters="@fips={fips}", connection_string_setting="SqlConnectionString")
def county_access(req: func.HttpRequest, r: func.SqlRowList) -> func.HttpResponse:
    fips = req.route_params.get("fips", "")
    if not re.fullmatch(r"\d{5}", fips):
        return bad("fips must be five digits")
    data = rows(r)
    if not data:
        return bad(f"no county {fips}", 404)
    return ok(data[0], source=SOURCE_NOTE)


@app.function_name("state_access")
@app.route(route="states/{state}/access", methods=["GET"])
@app.sql_input(arg_name="r", command_text="SELECT fips, county, veterans, ROUND(vet_share, 2) AS vet_share, vamc_name, ROUND(vamc_miles, 1) AS vamc_miles, site_name, site_kind, ROUND(site_miles, 1) AS site_miles FROM col.county_access WHERE state_abbr = @state ORDER BY vamc_miles DESC",
               command_type="Text", parameters="@state={state}", connection_string_setting="SqlConnectionString")
def state_access(req: func.HttpRequest, r: func.SqlRowList) -> func.HttpResponse:
    state = req.route_params.get("state", "").upper()
    if not re.fullmatch(r"[A-Z]{2}", state):
        return bad("state must be a two-letter code")
    data = rows(r)
    if not data:
        return bad(f"no counties for {state}", 404)
    vets = sum(d["veterans"] or 0 for d in data)
    weighted = sum((d["veterans"] or 0) * d["vamc_miles"] for d in data) / vets if vets else None
    return ok(data, state=state, counties=len(data), veterans=vets, vamc_miles_weighted=round(weighted, 1) if weighted else None, source=SOURCE_NOTE)


@app.function_name("facilities_near")
@app.route(route="facilities/near", methods=["GET"])
@app.sql_input(arg_name="r", command_text="col.sp_facilities_near", command_type="StoredProcedure",
               parameters="@lat={Query.lat},@lon={Query.lon},@miles={Query.miles},@kind={Query.kind},@top={Query.top}", connection_string_setting="SqlConnectionString")
def facilities_near(req: func.HttpRequest, r: func.SqlRowList) -> func.HttpResponse:
    # All five query parameters must be present for the stored-procedure binding; the API Management policy supplies
    # the defaults (miles=60, kind=, top=20) so callers may omit them. Calling the Function directly needs all five.
    try:
        lat, lon = float(req.params.get("lat")), float(req.params.get("lon"))
        miles = float(req.params.get("miles")); top = int(req.params.get("top"))
    except (TypeError, ValueError):
        return bad("lat, lon, miles and top are required numbers (the gateway fills miles, kind and top if omitted)")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or not (0 < miles <= 500) or not (1 <= top <= 100):
        return bad("lat/lon out of range, or miles not in (0, 500], or top not in [1, 100]")
    return ok(rows(r), lat=lat, lon=lon, miles=miles, kind=req.params.get("kind"), source=SOURCE_NOTE)


@app.function_name("refresh_runs")
@app.route(route="refresh/runs", methods=["GET"])
@app.sql_input(arg_name="r", command_text="SELECT TOP 20 run_id, started_at, finished_at, states_done, rows_written, status, note FROM col.refresh_run ORDER BY started_at DESC",
               command_type="Text", parameters="", connection_string_setting="SqlConnectionString")
def refresh_runs(req: func.HttpRequest, r: func.SqlRowList) -> func.HttpResponse:
    return ok(rows(r))


@app.function_name("api_info")
@app.route(route="info", methods=["GET"])
def api_info(req: func.HttpRequest) -> func.HttpResponse:
    return ok({"name": "azportfolio-data", "endpoints": ["GET info", "GET counties/{fips}/access", "GET states/{state}/access", "GET facilities/near?lat&lon&miles&kind&top",
                                                         "GET refresh/runs", "GET ingest/ledger", "POST refresh (starts the orchestration)", "GET refresh/status/{instanceId}"],
               "openapi": "openapi.yaml in the repo", "licence": "data public domain; API non-commercial learning project"})


@app.function_name("ingest_ledger")
@app.route(route="ingest/ledger", methods=["GET"])
@app.sql_input(arg_name="r", command_text="SELECT TOP 50 ledger_id, file_name, LEFT(sha256, 12) AS sha256_prefix, stage, outcome, reason, dataset_id, rows, run_by, received_at FROM col.ingest_ledger ORDER BY ledger_id DESC",
               command_type="Text", parameters="", connection_string_setting="SqlConnectionString")
def ingest_ledger(req: func.HttpRequest, r: func.SqlRowList) -> func.HttpResponse:
    """Build #14: what the ingestion gates decided, newest first (validator and loader rows)."""
    return ok(rows(r), note="stage=validated rows are the validator's decisions (queued|quarantined); stage=loaded rows are the loader's (loaded|duplicate|poison)")


# ---------------- Durable: monthly rebuild of col.county_access, fan-out by state ----------------
STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","DC","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]


@app.function_name("refresh_start")
@app.route(route="refresh", methods=["POST"])
@app.durable_client_input(client_name="client")
async def refresh_start(req: func.HttpRequest, client) -> func.HttpResponse:
    instance_id = await client.start_new("refresh_orchestrator", None, {"trigger": "http"})
    return client.create_check_status_response(req, instance_id)


@app.function_name("refresh_status")
@app.route(route="refresh/status/{instanceId}", methods=["GET"])
@app.durable_client_input(client_name="client")
async def refresh_status(req: func.HttpRequest, client) -> func.HttpResponse:
    st = await client.get_status(req.route_params["instanceId"])
    if st is None:
        return bad("no such instance", 404)
    return ok({"instanceId": st.instance_id, "runtimeStatus": str(st.runtime_status), "createdTime": st.created_time, "lastUpdatedTime": st.last_updated_time, "output": st.output})


@app.function_name("refresh_monthly")
@app.timer_trigger(schedule="0 0 3 1 * *", arg_name="timer", run_on_startup=False)
@app.durable_client_input(client_name="client")
async def refresh_monthly(timer: func.TimerRequest, client) -> None:
    instance_id = await client.start_new("refresh_orchestrator", None, {"trigger": "timer"})
    logging.info("monthly refresh started %s", instance_id)


@app.orchestration_trigger(context_name="context")
def refresh_orchestrator(context: df.DurableOrchestrationContext):
    run_id = context.instance_id
    started = context.current_utc_datetime.isoformat()[:19] + "Z"
    yield context.call_activity("run_record", {"run_id": run_id, "started_at": started, "status": "running"})
    retry = df.RetryOptions(first_retry_interval_in_milliseconds=20000, max_number_of_attempts=4)  # the serverless db wakes slowly
    tasks = [context.call_activity_with_retry("refresh_state", retry, {"state": s}) for s in STATES]  # an object, so the SQL binding can address {state}
    results = yield context.task_all(tasks)
    rows_written = sum(r["rows_written"] for r in results)
    yield context.call_activity("run_record", {"run_id": run_id, "started_at": started, "status": "done", "states_done": len(results), "rows_written": rows_written,
                                               "finished_at": context.current_utc_datetime.isoformat()[:19] + "Z"})
    return {"states": len(results), "rows_written": rows_written}


@app.activity_trigger(input_name="job")
@app.sql_input(arg_name="r", command_text="col.sp_refresh_access_state", command_type="StoredProcedure", parameters="@state={state}", connection_string_setting="SqlConnectionString")
def refresh_state(job: dict, r: func.SqlRowList) -> dict:
    out = rows(r)
    written = int(out[0]["rows_written"]) if out else 0
    if written == 0:
        raise RuntimeError(f"refresh wrote 0 rows for {job.get('state')}: the binding did not resolve or the state has no counties")
    return {"state": job["state"], "rows_written": written}


@app.activity_trigger(input_name="rec")
@app.sql_output(arg_name="row", command_text="col.refresh_run", connection_string_setting="SqlConnectionString")
def run_record(rec: dict, row: func.Out[str]) -> str:
    row.set(json.dumps({k: v for k, v in rec.items() if k in ("run_id", "started_at", "finished_at", "states_done", "rows_written", "status", "note")}))
    return rec["status"]

# ---------------- Build #14: nightly start of the loader container (ACI has no scheduler of its own) ----------------
@app.function_name("loader_nightly")
@app.timer_trigger(schedule="0 0 2 * * *", arg_name="timer", run_on_startup=False)
def loader_nightly(timer: func.TimerRequest) -> None:
    """Starts container group aci-azportfolio-b14 through ARM with this app's managed identity (role: Contributor on the group).
    The loader drains the ingest-load queue and exits; ACI bills per second while it runs."""
    import urllib.request
    from azure.identity import DefaultAzureCredential
    sub, rg, aci = os.environ["AZURE_SUBSCRIPTION_ID"], os.environ.get("ACI_RESOURCE_GROUP", "rg-azportfolio-b1"), os.environ.get("ACI_NAME", "aci-azportfolio-b14")
    token = DefaultAzureCredential().get_token("https://management.azure.com/.default").token
    url = f"https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.ContainerInstance/containerGroups/{aci}/start?api-version=2023-05-01"
    req = urllib.request.Request(url, method="POST", headers={"Authorization": "Bearer " + token, "Content-Length": "0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        logging.info("loader start requested: HTTP %s", r.status)
