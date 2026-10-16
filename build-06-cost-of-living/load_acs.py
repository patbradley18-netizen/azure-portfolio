"""load_acs.py - Build #6 step 2b: load the raw ACS5 county pull into col.measure as its own dataset.

Raw stays raw: codes are the Census variable IDs, values are what the API returned.
Census uses negative sentinel codes for suppressed/unavailable estimates (-666666666 etc.);
those load as value NULL with text 'SUPPRESSED', so a join can see them instead of a fake number.
Same OPENJSON bulk path as load_snapshots.py. Auth by env token. Run: python load_acs.py [year]
"""
import json
import os
import sys
import time
from pathlib import Path

from load_snapshots import connect, DDL

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2023
SRC = Path(__file__).parent / "data" / f"acs5_{YEAR}_county.json"
DS = f"acs5_{YEAR}"
METRICS = {
    "B25064_001E": ("median gross rent", "USD/month"), "B25077_001E": ("median home value", "USD"),
    "B25088_002E": ("median owner cost, with mortgage", "USD/month"), "B19013_001E": ("median household income", "USD/year"),
    "B01003_001E": ("total population", "people"),
}


def main():
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    header, body = raw[0], raw[1:]
    ix = {h: i for i, h in enumerate(header)}
    rows, counties = [], []
    for r in body:
        fips = r[ix["state"]] + r[ix["county"]]
        counties.append((fips, r[ix["NAME"]][:80], r[ix["state"]]))
        for code in METRICS:
            v = r[ix[code]]
            if v is None or v == "" or float(v) < 0:
                rows.append({"f": fips, "c": code, "v": None, "t": "SUPPRESSED" if v not in (None, "") else "MISSING"})
            else:
                rows.append({"f": fips, "c": code, "v": float(v), "t": None})

    conn = connect()
    cur = conn.cursor()
    cur.execute(DDL)
    # counties that exist in ACS but not in the snapshots get a row too (FK needs it)
    cur.executemany("""MERGE col.county AS t USING (VALUES (?,?,?)) AS s(fips,name,state_fips) ON t.fips=s.fips
        WHEN NOT MATCHED THEN INSERT (fips,name,state_fips) VALUES (s.fips,s.name,s.state_fips);""", counties)
    cur.execute("""MERGE col.dataset AS t USING (VALUES (?,?,?,?,?)) AS s(dataset_id,tool,vintage,as_of,source_file) ON t.dataset_id=s.dataset_id
        WHEN MATCHED THEN UPDATE SET vintage=s.vintage, as_of=s.as_of, source_file=s.source_file, loaded_at=SYSUTCDATETIME()
        WHEN NOT MATCHED THEN INSERT (dataset_id,tool,vintage,as_of,source_file) VALUES (s.dataset_id,s.tool,s.vintage,s.as_of,s.source_file);""",
                (DS, "census", f"ACS 5-year {YEAR}", time.strftime("%Y-%m-%d"), SRC.name))
    cur.executemany("""MERGE col.metric AS t USING (VALUES (?,?,?,?)) AS s(dataset_id,code,name,unit) ON t.dataset_id=s.dataset_id AND t.code=s.code
        WHEN MATCHED THEN UPDATE SET name=s.name, unit=s.unit
        WHEN NOT MATCHED THEN INSERT (dataset_id,code,name,unit) VALUES (s.dataset_id,s.code,s.name,s.unit);""",
                    [(DS, c, n, u) for c, (n, u) in METRICS.items()])
    cur.execute("DELETE FROM col.measure WHERE dataset_id = ?", (DS,))
    t0 = time.time()
    cur.execute("""INSERT INTO col.measure (fips,dataset_id,code,value,text)
                   SELECT j.f, ?, j.c, j.v, j.t FROM OPENJSON(?) WITH (f CHAR(5) '$.f', c NVARCHAR(30) '$.c', v FLOAT '$.v', t NVARCHAR(40) '$.t') AS j""",
                (DS, json.dumps(rows)))
    conn.commit()
    print(f"{DS}: {len(rows):,} rows in {time.time() - t0:.0f}s; suppressed: {sum(1 for r in rows if r['t'])}")
    cur.execute("SELECT code, COUNT(value), COUNT(*) - COUNT(value) AS nulls FROM col.measure WHERE dataset_id = ? GROUP BY code ORDER BY code", (DS,))
    for r in cur.fetchall():
        print(r)


if __name__ == "__main__":
    main()
