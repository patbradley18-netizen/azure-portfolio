# check_bls.py - row counts per series and latest period; proves upserts don't duplicate. Token by env.
import os, sys, time, mssql_python
from types import SimpleNamespace
tok=os.environ.get("SQL_ACCESS_TOKEN"); srv=os.environ.get("SQL_SERVER_NAME"); db=os.environ.get("SQL_DATABASE_NAME")
class TP:
    def get_token(self,*a,**k): return SimpleNamespace(token=tok)
for i in range(3):
    try: conn = mssql_python.connect(f"Server={srv};Database={db};Encrypt=yes;", token_provider=TP()); break
    except Exception as e: print("retry", i+1, flush=True); time.sleep(20)
cur = conn.cursor()
cur.execute("SELECT COUNT(*), COUNT(DISTINCT CONCAT(series_id, period)), MAX(period) FROM bls.observations"); print("rows, distinct keys, latest:", cur.fetchone())
cur.execute("SELECT series_id, value FROM bls.observations WHERE period = (SELECT MAX(period) FROM bls.observations) ORDER BY series_id"); print(cur.fetchall())
conn.close()