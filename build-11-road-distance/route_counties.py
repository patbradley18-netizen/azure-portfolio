"""route_counties.py - Build #11 steps 2-3: road distance from county population centers to the nearest VA medical center.

Router: the public OSRM demo server (OpenStreetMap data, ODbL; free; no key). Its usage policy is light use,
so this script is polite by construction: one request at a time, a pause between calls, a User-Agent that says
who is asking, and a HARD CAP on calls per run. Azure Maps was the plan; the student subscription's region policy
has no overlap with Azure Maps' regions (see README), so the Azure part of this build is the ledger, not the router.

Pattern from build #5: estimate -> cap -> ledger -> verify.
  estimate: the sample is chosen first and its size printed before any call
  cap:      MAX_CALLS per run; the script refuses to exceed it
  ledger:   every call appended to data/routes.jsonl as it happens, then bulk-loaded to col.route_ledger
  verify:   rows in the ledger == lines in the file == calls made
Sample: all build #10 Q20 counties (>=5,000 veterans, VAMC > 60 mi, top 25 by veteran share) plus a seeded
stratified random sample by straight-line band (0-30, 30-60, 60-100, 100+), total = MAX_CALLS.
Resume-safe: counties already in data/routes.jsonl are skipped, so a second run only fills gaps.
Run: python route_counties.py [--dry]        (SQL token by env; see load_snapshots.connect)
"""
import json
import random
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build-06-cost-of-living"))
from load_snapshots import connect  # noqa: E402

OSRM = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
UA = "azure-portfolio-build11/1.0 (non-commercial learning project; patrickneilbradley.com)"
MAX_CALLS = 900
PAUSE_S = 1.0
SEED = 11
DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)
OUT = DATA / "routes.jsonl"
BATCH = time.strftime("b11-%Y%m%dT%H%M%SZ", time.gmtime())
DRY = "--dry" in sys.argv


def band(m):
    return "0-30" if m <= 30 else "30-60" if m <= 60 else "60-100" if m <= 100 else "100+"


def pick_sample(cur):
    cur.execute("""SELECT a.fips, a.county, a.state_abbr, a.veterans, a.vet_share, a.vamc_sta_no, a.vamc_name, a.vamc_miles,
                          c.lat, c.lon, f.lat, f.lon
                   FROM col.county_access a JOIN col.county_center c ON c.fips = a.fips JOIN col.facility f ON f.sta_no = a.vamc_sta_no""")
    rows = [dict(zip(["fips", "county", "state", "veterans", "vet_share", "vamc_sta_no", "vamc_name", "vamc_miles", "lat", "lon", "vlat", "vlon"], r)) for r in cur.fetchall()]
    q20 = sorted([r for r in rows if r["veterans"] >= 5000 and r["vamc_miles"] > 60], key=lambda r: -r["vet_share"])[:25]
    chosen = {r["fips"]: dict(r, stratum="Q20") for r in q20}
    rng = random.Random(SEED)
    by_band = {}
    for r in rows:
        if r["fips"] not in chosen:
            by_band.setdefault(band(r["vamc_miles"]), []).append(r)
    remaining = MAX_CALLS - len(chosen)
    total = sum(len(v) for v in by_band.values())
    # proportional allocation with a floor of 150 per band so the far bands are not starved
    alloc = {b: max(150, round(remaining * len(v) / total)) for b, v in by_band.items()}
    scale = remaining / sum(alloc.values())
    alloc = {b: int(n * scale) for b, n in alloc.items()}
    for b, v in by_band.items():
        for r in rng.sample(v, min(alloc[b], len(v))):
            chosen[r["fips"]] = dict(r, stratum=b)
    return list(chosen.values())[:MAX_CALLS], {b: len(v) for b, v in by_band.items()}, alloc


def main():
    conn = connect()
    cur = conn.cursor()
    sample, pop, alloc = pick_sample(cur)
    done = {json.loads(l)["fips"] for l in OUT.read_text(encoding="utf-8").splitlines()} if OUT.exists() else set()
    todo = [r for r in sample if r["fips"] not in done]
    print(f"ESTIMATE: sample {len(sample)} counties (Q20 {sum(1 for r in sample if r['stratum']=='Q20')}; bands {alloc} of {pop}); "
          f"already routed {len(done)}; calls this run {len(todo)}; cap {MAX_CALLS}", flush=True)
    if DRY:
        return
    assert len(done) + len(todo) <= MAX_CALLS, "cap would be exceeded"
    s = requests.Session()
    s.headers["User-Agent"] = UA
    made = 0
    with OUT.open("a", encoding="utf-8") as fh:
        for r in todo:
            url = OSRM.format(lon1=r["lon"], lat1=r["lat"], lon2=r["vlon"], lat2=r["vlat"])
            rec = {"fips": r["fips"], "dest_sta_no": r["vamc_sta_no"], "stratum": r["stratum"], "batch_id": BATCH,
                   "called_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "http_status": None, "road_meters": None, "travel_seconds": None}
            for attempt in range(3):
                try:
                    resp = s.get(url, timeout=60)
                    rec["http_status"] = resp.status_code
                    if resp.status_code == 200 and resp.json().get("code") == "Ok":
                        route = resp.json()["routes"][0]
                        rec["road_meters"], rec["travel_seconds"] = route["distance"], route["duration"]
                    break
                except requests.RequestException as e:
                    rec["http_status"] = 0
                    time.sleep(5 * (attempt + 1))
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            made += 1
            if made % 50 == 0:
                print(f"{made}/{len(todo)} calls; last {r['county']} {r['state']}: {rec['http_status']} {rec['road_meters']}", flush=True)
            time.sleep(PAUSE_S)
    # ledger: load everything in the file for this batch (idempotent on the PK)
    recs = [json.loads(l) for l in OUT.read_text(encoding="utf-8").splitlines()]
    cur.execute("DELETE FROM col.route_ledger WHERE batch_id IN (SELECT DISTINCT batch_id FROM OPENJSON(?) WITH (batch_id NVARCHAR(40) '$.batch_id'))", (json.dumps(recs),))
    cur.execute("""INSERT INTO col.route_ledger (fips, dest_sta_no, called_at, http_status, road_meters, travel_seconds, batch_id)
                   SELECT j.fips, j.dest_sta_no, j.called_at, j.http_status, j.road_meters, j.travel_seconds, j.batch_id
                   FROM OPENJSON(?) WITH (fips CHAR(5) '$.fips', dest_sta_no NVARCHAR(7) '$.dest_sta_no', called_at DATETIME2 '$.called_at',
                        http_status INT '$.http_status', road_meters FLOAT '$.road_meters', travel_seconds FLOAT '$.travel_seconds', batch_id NVARCHAR(40) '$.batch_id') AS j""",
                (json.dumps(recs),))
    conn.commit()
    cur.execute("SELECT COUNT(*), SUM(CASE WHEN road_meters IS NOT NULL THEN 1 ELSE 0 END) FROM col.route_ledger")
    n, ok = cur.fetchone()
    print(f"VERIFY: file lines {len(recs)}; ledger rows {n}; routed OK {ok}; calls made this run {made}", flush=True)
    (DATA / "sample_strata.json").write_text(json.dumps({"population_by_band": pop, "allocation": alloc, "q20": 25, "cap": MAX_CALLS, "seed": SEED}, indent=1))


if __name__ == "__main__":
    main()
