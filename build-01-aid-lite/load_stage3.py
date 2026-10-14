# load_stage3.py - loads stage-3 outputs (edges, bursts, daily_volume) into Azure SQL.
# Auth: Entra access token passed by environment (SQL_ACCESS_TOKEN), never on disk. Idempotent: truncates then reloads.
import os, sys, time, mssql_python, pandas as pd
from types import SimpleNamespace
from pathlib import Path
DATA = Path(__file__).parent / "data"
tok=os.environ.get("SQL_ACCESS_TOKEN"); srv=os.environ.get("SQL_SERVER_NAME"); db=os.environ.get("SQL_DATABASE_NAME")
if not (tok and srv and db): sys.exit("needs SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME")
class TP:
    def get_token(self,*a,**k): return SimpleNamespace(token=tok)
def connect():
    for i in range(3):  # serverless db may be paused on first touch (lesson 8)
        try: return mssql_python.connect(f"Server={srv};Database={db};Encrypt=yes;", token_provider=TP())
        except Exception as e:
            print("connect retry", i+1, type(e).__name__); time.sleep(20)
    raise SystemExit("could not connect")
conn = connect(); cur = conn.cursor()
cur.execute("""
IF OBJECT_ID('dbo.edges') IS NULL CREATE TABLE dbo.edges (
  source NVARCHAR(40) NOT NULL, target NVARCHAR(40) NOT NULL, kind NVARCHAR(10) NOT NULL,
  source_category NVARCHAR(40), weight INT NOT NULL,
  CONSTRAINT PK_edges PRIMARY KEY (source, target, kind, source_category));
IF OBJECT_ID('dbo.bursts') IS NULL CREATE TABLE dbo.bursts (
  body NVARCHAR(500) NOT NULL, days_active INT, peak_day DATE, peak_count INT, total INT,
  CONSTRAINT PK_bursts PRIMARY KEY (body));
IF OBJECT_ID('dbo.daily_volume') IS NULL CREATE TABLE dbo.daily_volume (
  day DATE NOT NULL PRIMARY KEY, all_originals INT, template_posts INT);
""")
conn.commit()
def load(table, df, cols):
    cur.execute(f"TRUNCATE TABLE dbo.{table}")
    rows = [tuple(r) for r in df[cols].itertuples(index=False)]
    q = f"INSERT INTO dbo.{table} ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})"
    for i in range(0, len(rows), 1000):
        cur.executemany(q, rows[i:i+1000])
    conn.commit()
    cur.execute(f"SELECT COUNT(*) FROM dbo.{table}"); print(table, "rows:", cur.fetchone()[0])
e = pd.read_csv(DATA / "edges.csv").rename(columns={"account_category": "source_category"})
e["source_category"] = e["source_category"].fillna("Unknown")
e = e.groupby(["source","target","kind","source_category"], as_index=False)["weight"].sum()
load("edges", e, ["source","target","kind","source_category","weight"])
b = pd.read_csv(DATA / "bursts.csv"); b["body"] = b["body"].str.slice(0, 500); b = b.drop_duplicates("body")
load("bursts", b, ["body","days_active","peak_day","peak_count","total"])
v = pd.read_csv(DATA / "daily_volume.csv")
load("daily_volume", v, ["day","all_originals","template_posts"])
conn.close()