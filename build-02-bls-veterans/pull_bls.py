"""Build #2, step 3: pull the veteran CPS series from the BLS API v2 into data/bls_observations.csv.

Series (verified at api.bls.gov on 2026-10-15; all monthly, not seasonally adjusted, percent):
  LNU04049526  Unemployment rate, total veterans, 18+
  LNU04066408  Unemployment rate, Gulf War-era II veterans, 18+
  LNU04049601  Unemployment rate, nonveterans, 18+
  LNU01349526  Labor force participation rate, total veterans, 18+
  LNU01349601  Labor force participation rate, nonveterans, 18+

Key: read from env var BLS_API_KEY if present (registered: 500 queries/day, 20 years/query).
Without it the API allows 25 queries/day and 10 years/query, enough for this one-time history load.
The key is never written to disk by this script. Run: python pull_bls.py
"""
import os, json, time, urllib.request
from pathlib import Path
import pandas as pd

SERIES = {
    "LNU04049526": ("Unemployment rate", "Veterans, 18+"),
    "LNU04066408": ("Unemployment rate", "Gulf War-era II veterans, 18+"),
    "LNU04049601": ("Unemployment rate", "Nonveterans, 18+"),
    "LNU01349526": ("Labor force participation rate", "Veterans, 18+"),
    "LNU01349601": ("Labor force participation rate", "Nonveterans, 18+"),
}
API = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
DATA = Path(__file__).parent / "data"

def fetch(start, end):
    body = {"seriesid": list(SERIES), "startyear": str(start), "endyear": str(end)}
    key = os.environ.get("BLS_API_KEY")
    if key: body["registrationkey"] = key
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.load(r)
    if res["status"] != "REQUEST_SUCCEEDED":
        raise SystemExit(f"BLS: {res['status']} {res.get('message')}")
    rows = []
    for s in res["Results"]["series"]:
        for d in s["data"]:
            if not d["period"].startswith("M") or d["period"] == "M13": continue
            rows.append({"series_id": s["seriesID"], "year": int(d["year"]), "month": int(d["period"][1:]),
                         "value": (None if d["value"] in ("-", "") else float(d["value"])), "footnotes": "; ".join(f.get("text", "") for f in d.get("footnotes", []) if f)})
    return rows

def main():
    DATA.mkdir(exist_ok=True)
    rows = []
    span = 20 if os.environ.get("BLS_API_KEY") else 10
    for start in range(2000, 2027, span):
        rows += fetch(start, min(start + span - 1, 2026)); time.sleep(1)
    df = pd.DataFrame(rows).dropna(subset=["value"]).drop_duplicates(["series_id", "year", "month"]).sort_values(["series_id", "year", "month"])
    df["period"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1)).dt.date
    df.to_csv(DATA / "bls_observations.csv", index=False)
    meta = pd.DataFrame([{"series_id": k, "measure": v[0], "population": v[1], "seasonal": "NSA", "units": "percent", "source": "BLS CPS via api.bls.gov"} for k, v in SERIES.items()])
    meta.to_csv(DATA / "bls_series.csv", index=False)
    print(f"rows {len(df):,}  series {df.series_id.nunique()}  range {df.period.min()} to {df.period.max()}")
    print(df.groupby("series_id")["value"].agg(["count", "min", "max", "last"]).to_string())

if __name__ == "__main__":
    main()