"""load_snapshots.py - Build #6 step 1: load the TSCI and TCBI snapshot JSON into schema `col` on the free Azure SQL db.

Design: a long/narrow warehouse. One row per (county, dataset, metric). Every row carries the dataset's
vintage and the load time, so a later refresh is a new dataset_id, not an overwrite of history.

  col.county   fips PK, name, state_fips, state_abbr
  col.dataset  dataset_id PK, tool, vintage, as_of, source_file
  col.metric   (dataset_id, code) PK, name, unit
  col.measure  (fips, dataset_id, code) PK, value FLOAT NULL, text NVARCHAR(40) NULL

Load semantics: replace-per-dataset (DELETE the dataset's rows, INSERT fresh). Idempotent.
Auth: Entra token by env (SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME). Nothing on disk.
Run: python load_snapshots.py            (expects data/snapshots/{counties.json,d1_data.json..d5_data.json})
"""
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import mssql_python

DATA = Path(__file__).parent / "data" / "snapshots"
BATCH = 20000  # rows per OPENJSON chunk (~1 MB of JSON per round trip)

# Data dictionary: codes as they appear in the JSON, names from the methodology one-pager (2026-05-12).
TSCI_METRICS = {
    "r": ("median gross rent", "USD/month"), "p": ("rent share of income", "%"), "i": ("median household income", "USD/year"),
    "pop": ("population", "people"), "idx": ("rent index (US=100)", "index"), "hv": ("median home value", "USD"),
    "hvi": ("home value index", "index"), "oc": ("owner cost (mortgage)", "USD/month"), "oci": ("owner cost index", "index"),
    "p2i": ("price-to-income", "ratio"), "cc_w": ("childcare, weekly", "USD/week"), "cc_m": ("childcare, monthly", "USD/month"),
    "cci": ("childcare index", "index"), "cc_y": ("childcare data year", "year"), "ho": ("homeowner insurance, monthly", "USD/month"),
    "hoi": ("homeowner insurance index", "index"), "re": ("renter insurance, monthly", "USD/month"), "rei": ("renter insurance index", "index"),
    "on": ("owner nut = oc + cc_m + ho", "USD/month"), "rn": ("renter nut = r + cc_m + re", "USD/month"),
    "ob": ("owner burden = on*12/i", "%"), "rb": ("renter burden = rn*12/i", "%"), "ti": ("TSCI composite", "index"),
    "cc_p": ("childcare provenance", "flag"), "tag": ("county tag", "flag"),
}
TCBI_METRICS = {
    "d1": {"p": ("gas price", "USD/gal"), "d": ("diesel price", "USD/gal"), "i": ("pump index", "index"), "f": ("county factor f_c", "ratio"),
           "fc": ("clamp ceiling", "ratio"), "r": ("median gross rent", "USD/month"), "sb": ("state baseline gas", "USD/gal"),
           "fl": ("provenance flag", "flag"), "sf": ("state provenance flag", "flag")},
    "d2": {"c": ("pantry basket, weekly", "USD/week"), "sb": ("state baseline pantry", "USD/week"), "i": ("pantry index", "index"),
           "fc": ("clamp ceiling", "ratio"), "r": ("median gross rent", "USD/month"), "region": ("census region", "flag")},
    "d3": {"c": ("plate basket, weekly", "USD/week"), "ca": ("plate per adult", "USD/week"), "sb": ("state baseline plate", "USD/week"),
           "i": ("plate index", "index"), "td": ("thrifty food plan difference", "USD/week")},
    "d4": {"sd": ("sit-down meal", "USD"), "ff": ("fast-food meal", "USD"), "i": ("restaurant index", "index")},
    "d5": {"c01": ("weekly basket C01", "USD/week"), "c01a": ("annual basket C01", "USD/year"), "c02": ("basket share of income", "%"),
           "inc": ("median household income", "USD/year"), "tcbi": ("TCBI composite", "index"), "d5i": ("D5 index", "index"),
           "bd_gas_weekly": ("breakdown: gas", "USD/week"), "bd_pantry_weekly": ("breakdown: pantry", "USD/week"),
           "bd_plate_weekly": ("breakdown: plate", "USD/week"), "bd_restaurant_weekly": ("breakdown: restaurant", "USD/week")},
}
STATE_FIPS_TO_ABBR = {}  # filled from TCBI rows (they carry the abbreviation) for TSCI rows (they carry the FIPS)


def connect():
    tok, srv, db = (os.environ.get(k) for k in ("SQL_ACCESS_TOKEN", "SQL_SERVER_NAME", "SQL_DATABASE_NAME"))
    if not (tok and srv and db):
        sys.exit("needs SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME")

    class TP:
        def get_token(self, *a, **k):
            return SimpleNamespace(token=tok)

    for i in range(4):
        try:
            return mssql_python.connect(f"Server={srv};Database={db};Encrypt=yes;", token_provider=TP())
        except Exception as e:  # serverless db waking up
            print("connect retry", i + 1, type(e).__name__, flush=True)
            time.sleep(20)
    raise SystemExit("could not connect")


DDL = """
IF SCHEMA_ID('col') IS NULL EXEC('CREATE SCHEMA col');
IF OBJECT_ID('col.county') IS NULL CREATE TABLE col.county (
  fips CHAR(5) NOT NULL PRIMARY KEY, name NVARCHAR(80) NOT NULL, state_fips CHAR(2) NOT NULL, state_abbr CHAR(2) NULL);
IF OBJECT_ID('col.dataset') IS NULL CREATE TABLE col.dataset (
  dataset_id NVARCHAR(40) NOT NULL PRIMARY KEY, tool NVARCHAR(10) NOT NULL, vintage NVARCHAR(40) NULL, as_of NVARCHAR(20) NULL,
  source_file NVARCHAR(80) NOT NULL, loaded_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME());
IF OBJECT_ID('col.metric') IS NULL CREATE TABLE col.metric (
  dataset_id NVARCHAR(40) NOT NULL, code NVARCHAR(30) NOT NULL, name NVARCHAR(80) NOT NULL, unit NVARCHAR(20) NOT NULL,
  CONSTRAINT PK_col_metric PRIMARY KEY (dataset_id, code),
  CONSTRAINT FK_col_metric_dataset FOREIGN KEY (dataset_id) REFERENCES col.dataset(dataset_id));
IF OBJECT_ID('col.measure') IS NULL CREATE TABLE col.measure (
  fips CHAR(5) NOT NULL, dataset_id NVARCHAR(40) NOT NULL, code NVARCHAR(30) NOT NULL,
  value FLOAT NULL, text NVARCHAR(40) NULL,
  CONSTRAINT PK_col_measure PRIMARY KEY (fips, dataset_id, code),
  CONSTRAINT FK_col_measure_county FOREIGN KEY (fips) REFERENCES col.county(fips),
  CONSTRAINT FK_col_measure_metric FOREIGN KEY (dataset_id, code) REFERENCES col.metric(dataset_id, code));
"""


def cell(v):
    """Split a JSON value into (value, text)."""
    if v is None:
        return None, None
    if isinstance(v, bool):
        return float(v), None
    if isinstance(v, (int, float)):
        return float(v), None
    return None, str(v)[:40]


def load_tcbi(n: int):
    d = json.loads((DATA / f"d{n}_data.json").read_text(encoding="utf-8"))
    ds = f"tcbi_d{n}_{d.get('as_of', 'na')}"
    rows, counties = [], {}
    for fips, rec in d["counties"].items():
        fips = str(fips).zfill(5)
        counties[fips] = (rec.get("n", ""), fips[:2], rec.get("s"))
        if rec.get("s"):
            STATE_FIPS_TO_ABBR[fips[:2]] = rec["s"]
        flat = {k: v for k, v in rec.items() if k not in ("n", "s", "bd")}
        for k, v in (rec.get("bd") or {}).items():
            flat[f"bd_{k}"] = v
        for k, v in flat.items():
            if k in TCBI_METRICS[f"d{n}"]:
                val, txt = cell(v)
                rows.append((fips, ds, k, val, txt))
    return ds, ("tcbi", d.get("vintage"), d.get("as_of"), f"d{n}_data.json"), TCBI_METRICS[f"d{n}"], counties, rows


def load_tsci():
    d = json.loads((DATA / "counties.json").read_text(encoding="utf-8"))
    ds = "tsci_2026-05-12"
    rows, counties = [], {}
    for fips, rec in d.items():
        fips = str(fips).zfill(5)
        counties[fips] = (rec.get("n", ""), rec.get("s", fips[:2]), STATE_FIPS_TO_ABBR.get(fips[:2]))
        for k, v in rec.items():
            if k in TSCI_METRICS:
                val, txt = cell(v)
                rows.append((fips, ds, k, val, txt))
    return ds, ("tsci", "2026-05-12 publication snapshot", "2026-05-12", "counties.json"), TSCI_METRICS, counties, rows


def main():
    loads = [load_tcbi(n) for n in range(1, 6)]
    loads.append(load_tsci())  # after TCBI so state abbreviations are known

    conn = connect()
    cur = conn.cursor()
    cur.execute(DDL)
    conn.commit()

    # counties: union of all sources; TSCI names ("Autauga County, Alabama") win over TCBI short names
    county = {}
    for ds, meta, metrics, counties, rows in loads:
        for fips, (name, sf, ab) in counties.items():
            prev = county.get(fips)
            county[fips] = (name if (meta[0] == "tsci" or not prev) else prev[0], sf, ab or (prev[2] if prev else None))
    cur.executemany("""MERGE col.county AS t USING (VALUES (?,?,?,?)) AS s(fips,name,state_fips,state_abbr) ON t.fips=s.fips
        WHEN MATCHED THEN UPDATE SET name=s.name, state_fips=s.state_fips, state_abbr=COALESCE(s.state_abbr,t.state_abbr)
        WHEN NOT MATCHED THEN INSERT (fips,name,state_fips,state_abbr) VALUES (s.fips,s.name,s.state_fips,s.state_abbr);""",
                    [(f, n[:80], sf, ab) for f, (n, sf, ab) in county.items()])
    conn.commit()
    print(f"counties: {len(county):,}", flush=True)

    for ds, (tool, vintage, as_of, src), metrics, counties, rows in loads:
        cur.execute("""MERGE col.dataset AS t USING (VALUES (?,?,?,?,?)) AS s(dataset_id,tool,vintage,as_of,source_file) ON t.dataset_id=s.dataset_id
            WHEN MATCHED THEN UPDATE SET vintage=s.vintage, as_of=s.as_of, source_file=s.source_file, loaded_at=SYSUTCDATETIME()
            WHEN NOT MATCHED THEN INSERT (dataset_id,tool,vintage,as_of,source_file) VALUES (s.dataset_id,s.tool,s.vintage,s.as_of,s.source_file);""",
                    (ds, tool, vintage, as_of, src))
        cur.executemany("""MERGE col.metric AS t USING (VALUES (?,?,?,?)) AS s(dataset_id,code,name,unit) ON t.dataset_id=s.dataset_id AND t.code=s.code
            WHEN MATCHED THEN UPDATE SET name=s.name, unit=s.unit
            WHEN NOT MATCHED THEN INSERT (dataset_id,code,name,unit) VALUES (s.dataset_id,s.code,s.name,s.unit);""",
                        [(ds, code, name, unit) for code, (name, unit) in metrics.items()])
        cur.execute("DELETE FROM col.measure WHERE dataset_id = ?", (ds,))
        t0 = time.time()
        # Bulk path: ship the rows as ONE JSON string and let SQL Server shred it with OPENJSON.
        # Row-by-row parameter binding ran at ~40 rows/s over the wire; this is one round trip per chunk.
        for i in range(0, len(rows), BATCH):
            payload = json.dumps([{"f": f, "c": c, "v": v, "t": t} for f, _, c, v, t in rows[i:i + BATCH]])
            cur.execute("""INSERT INTO col.measure (fips,dataset_id,code,value,text)
                           SELECT j.f, ?, j.c, j.v, j.t FROM OPENJSON(?) WITH (f CHAR(5) '$.f', c NVARCHAR(30) '$.c', v FLOAT '$.v', t NVARCHAR(40) '$.t') AS j""",
                        (ds, payload))
        conn.commit()
        print(f"{ds}: {len(rows):,} rows in {time.time() - t0:.0f}s", flush=True)

    cur.execute("""SELECT d.dataset_id, d.vintage, COUNT(*) AS rows_, COUNT(DISTINCT m.fips) AS counties
                   FROM col.measure m JOIN col.dataset d ON d.dataset_id = m.dataset_id GROUP BY d.dataset_id, d.vintage ORDER BY d.dataset_id""")
    for r in cur.fetchall():
        print(r)


if __name__ == "__main__":
    main()
