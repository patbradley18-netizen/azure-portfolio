# load_bls.py - creates schema bls (series, observations) in the free Azure SQL db and upserts data/*.csv.
# Auth: Entra access token by env (SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME); nothing on disk.
# Idempotent: MERGE on (series_id, period), so re-running never duplicates. Retries while the serverless db wakes.
import os, sys, time, mssql_python, pandas as pd
from types import SimpleNamespace
from pathlib import Path
DATA = Path(__file__).parent / "data"
tok=os.environ.get("SQL_ACCESS_TOKEN"); srv=os.environ.get("SQL_SERVER_NAME"); db=os.environ.get("SQL_DATABASE_NAME")
if not (tok and srv and db): sys.exit("needs SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME")
class TP:
    def get_token(self,*a,**k): return SimpleNamespace(token=tok)
def connect():
    for i in range(3):
        try: return mssql_python.connect(f"Server={srv};Database={db};Encrypt=yes;", token_provider=TP())
        except Exception as e: print("connect retry", i+1, type(e).__name__, flush=True); time.sleep(20)
    raise SystemExit("could not connect")
conn = connect(); cur = conn.cursor()
cur.execute("IF SCHEMA_ID('bls') IS NULL EXEC('CREATE SCHEMA bls')"); conn.commit()
cur.execute("""
IF OBJECT_ID('bls.series') IS NULL CREATE TABLE bls.series (
  series_id CHAR(11) NOT NULL PRIMARY KEY, measure NVARCHAR(60), population NVARCHAR(60),
  seasonal CHAR(3), units NVARCHAR(20), source NVARCHAR(60));
IF OBJECT_ID('bls.observations') IS NULL CREATE TABLE bls.observations (
  series_id CHAR(11) NOT NULL, period DATE NOT NULL, value DECIMAL(6,1) NOT NULL,
  footnotes NVARCHAR(200) NULL, loaded_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
  CONSTRAINT PK_bls_obs PRIMARY KEY (series_id, period),
  CONSTRAINT FK_bls_obs_series FOREIGN KEY (series_id) REFERENCES bls.series(series_id));
""")
conn.commit()
s = pd.read_csv(DATA / "bls_series.csv")
cur.executemany("""MERGE bls.series AS t USING (VALUES (?,?,?,?,?,?)) AS s(series_id,measure,population,seasonal,units,source)
  ON t.series_id = s.series_id
  WHEN MATCHED THEN UPDATE SET measure=s.measure, population=s.population, seasonal=s.seasonal, units=s.units, source=s.source
  WHEN NOT MATCHED THEN INSERT (series_id,measure,population,seasonal,units,source) VALUES (s.series_id,s.measure,s.population,s.seasonal,s.units,s.source);""",
  [tuple(r) for r in s[["series_id","measure","population","seasonal","units","source"]].itertuples(index=False)])
o = pd.read_csv(DATA / "bls_observations.csv"); o["footnotes"] = o["footnotes"].fillna("")
rows = [(r.series_id, r.period, float(r.value), r.footnotes[:200] or None) for r in o.itertuples(index=False)]
q = """MERGE bls.observations AS t USING (VALUES (?,?,?,?)) AS s(series_id,period,value,footnotes)
  ON t.series_id = s.series_id AND t.period = s.period
  WHEN MATCHED AND (t.value <> s.value) THEN UPDATE SET value=s.value, footnotes=s.footnotes, loaded_at=SYSUTCDATETIME()
  WHEN NOT MATCHED THEN INSERT (series_id,period,value,footnotes) VALUES (s.series_id,s.period,s.value,s.footnotes);"""
for i in range(0, len(rows), 500): cur.executemany(q, rows[i:i+500])
conn.commit()
cur.execute("SELECT series_id, COUNT(*), MIN(period), MAX(period) FROM bls.observations GROUP BY series_id ORDER BY series_id")
for r in cur.fetchall(): print(r)
conn.close()