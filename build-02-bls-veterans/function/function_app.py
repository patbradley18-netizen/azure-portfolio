"""Build #2: weekly BLS veteran-employment pull into Azure SQL (schema bls), via a SQL output binding (upsert on PK).

Secrets: BLS_API_KEY is a Key Vault reference resolved by the platform through the app's managed identity;
the SQL connection string uses Active Directory Managed Identity. No key or password exists in this code or settings.
Schedule: Saturdays 12:00 UTC (the Employment Situation lands the first Friday; veterans table A-5 ships with it).
"""
import os, json, logging, datetime as dt, urllib.request
import azure.functions as func

app = func.FunctionApp()
SERIES = ["LNU04049526", "LNU04066408", "LNU04049601", "LNU01349526", "LNU01349601"]
API = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

@app.function_name("weekly_bls_pull")
@app.timer_trigger(schedule="0 0 12 * * 6", arg_name="timer", run_on_startup=False)
@app.sql_output(arg_name="rows", command_text="bls.observations", connection_string_setting="SqlConnectionString")
def weekly_bls_pull(timer: func.TimerRequest, rows: func.Out[str]) -> None:
    year = dt.date.today().year
    body = {"seriesid": SERIES, "startyear": str(year - 1), "endyear": str(year)}
    key = os.environ.get("BLS_API_KEY")
    if key: body["registrationkey"] = key
    else: logging.warning("BLS_API_KEY not resolved; running unregistered")
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.load(r)
    if res["status"] != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS {res['status']}: {res.get('message')}")
    out = []
    for s in res["Results"]["series"]:
        for d in s["data"]:
            if not d["period"].startswith("M") or d["period"] == "M13" or d["value"] in ("-", ""): continue
            out.append({"series_id": s["seriesID"], "period": f"{d['year']}-{int(d['period'][1:]):02d}-01",
                        "value": float(d["value"]),
                        "footnotes": ("; ".join(f.get("text", "") for f in d.get("footnotes", []) if f))[:200] or None})
    latest = max(o["period"] for o in out) if out else None
    logging.info("bls_pull rows=%d series=%d latest=%s registered=%s", len(out), len(res["Results"]["series"]), latest, bool(key))
    rows.set(json.dumps(out))