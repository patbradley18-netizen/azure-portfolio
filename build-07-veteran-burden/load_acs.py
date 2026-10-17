"""load_acs.py - load a raw ACS5 county pull into col.measure as its own dataset. Build #6 step 2b; build #7 adds variable sets.

Raw stays raw: codes are the Census variable IDs, values are what the API returned, metric names come from the
labels file fetch_acs.py saved from the API's metadata. Negative sentinel codes (-666666666 etc.) load as
value NULL with text 'SUPPRESSED'. Same OPENJSON bulk path as load_snapshots.py. Auth by env token.
Run: python load_acs.py [year] [set]     (defaults 2023 shelter; dataset_id acs5_<year> for shelter, acs5_<year>_vet for veterans)
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build-06-cost-of-living"))
from load_snapshots import connect, DDL  # noqa: E402  (build #6 owns the schema)

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2023
SET = sys.argv[2] if len(sys.argv) > 2 else "shelter"
DATA = Path(__file__).parent / "data"
SRC = DATA / f"acs5_{YEAR}_{SET}_county.json"
LABELS = DATA / f"acs5_{YEAR}_{SET}_labels.json"
DS = f"acs5_{YEAR}" if SET == "shelter" else f"acs5_{YEAR}_vet"
UNITS = {"B25064_001E": "USD/month", "B25077_001E": "USD", "B25088_002E": "USD/month", "B19013_001E": "USD/year"}


def clean_label(lbl: str) -> str:
    return lbl.replace("Estimate!!", "").replace("!!", " > ").replace("Total:", "Total")[:80]


def main():
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    header, body = raw[0], raw[1:]
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

    conn = connect()
    cur = conn.cursor()
    cur.execute(DDL)
    cur.executemany("""MERGE col.county AS t USING (VALUES (?,?,?)) AS s(fips,name,state_fips) ON t.fips=s.fips
        WHEN NOT MATCHED THEN INSERT (fips,name,state_fips) VALUES (s.fips,s.name,s.state_fips);""", counties)
    cur.execute("""MERGE col.dataset AS t USING (VALUES (?,?,?,?,?)) AS s(dataset_id,tool,vintage,as_of,source_file) ON t.dataset_id=s.dataset_id
        WHEN MATCHED THEN UPDATE SET vintage=s.vintage, as_of=s.as_of, source_file=s.source_file, loaded_at=SYSUTCDATETIME()
        WHEN NOT MATCHED THEN INSERT (dataset_id,tool,vintage,as_of,source_file) VALUES (s.dataset_id,s.tool,s.vintage,s.as_of,s.source_file);""",
                (DS, "census", f"ACS 5-year {YEAR}", time.strftime("%Y-%m-%d"), SRC.name))
    cur.executemany("""MERGE col.metric AS t USING (VALUES (?,?,?,?)) AS s(dataset_id,code,name,unit) ON t.dataset_id=s.dataset_id AND t.code=s.code
        WHEN MATCHED THEN UPDATE SET name=s.name, unit=s.unit
        WHEN NOT MATCHED THEN INSERT (dataset_id,code,name,unit) VALUES (s.dataset_id,s.code,s.name,s.unit);""",
                    [(DS, c, clean_label(labels.get(c, c)), UNITS.get(c, "people")) for c in codes])
    cur.execute("DELETE FROM col.measure WHERE dataset_id = ?", (DS,))
    t0 = time.time()
    for i in range(0, len(rows), 20000):
        cur.execute("""INSERT INTO col.measure (fips,dataset_id,code,value,text)
                       SELECT j.f, ?, j.c, j.v, j.t FROM OPENJSON(?) WITH (f CHAR(5) '$.f', c NVARCHAR(30) '$.c', v FLOAT '$.v', t NVARCHAR(40) '$.t') AS j""",
                    (DS, json.dumps(rows[i:i + 20000])))
    conn.commit()
    print(f"{DS}: {len(rows):,} rows in {time.time() - t0:.0f}s; suppressed: {sum(1 for r in rows if r['t'])}")
    cur.execute("SELECT code, COUNT(value), COUNT(*) - COUNT(value) AS nulls FROM col.measure WHERE dataset_id = ? GROUP BY code ORDER BY code", (DS,))
    for r in cur.fetchall():
        print(r)


if __name__ == "__main__":
    main()
