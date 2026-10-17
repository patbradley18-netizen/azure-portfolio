# run_analysis.py - runs each "-- Q" block in queries.sql against the free Azure SQL db and saves results.
# Auth: Entra access token by env (SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME). Retries while the serverless db wakes.
import os, sys, re, json, time, decimal, datetime, mssql_python
from types import SimpleNamespace
from pathlib import Path
HERE = Path(__file__).parent; DATA = HERE / "data"; DATA.mkdir(exist_ok=True)
tok=os.environ.get("SQL_ACCESS_TOKEN"); srv=os.environ.get("SQL_SERVER_NAME"); db=os.environ.get("SQL_DATABASE_NAME")
if not (tok and srv and db): sys.exit("needs SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME")
class TP:
    def get_token(self,*a,**k): return SimpleNamespace(token=tok)
for i in range(3):
    try: conn = mssql_python.connect(f"Server={srv};Database={db};Encrypt=yes;", token_provider=TP()); break
    except Exception as e: print("retry", i+1, type(e).__name__, flush=True); time.sleep(20)
cur = conn.cursor()
text = (HERE / "queries.sql").read_text(encoding="utf-8")
blocks = re.split(r"^-- (Q\d+) \| ", text, flags=re.M)[1:]
def conv(v):
    if isinstance(v, decimal.Decimal): return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)): return v.isoformat()[:10]
    if hasattr(v, "hex") and not isinstance(v, (int, float)): return str(v)
    return v
out = {}
for qid, body in zip(blocks[0::2], blocks[1::2]):
    question, sql = body.split("\n", 1)
    cur.execute(sql.strip().rstrip(";"))
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, [conv(x) for x in r])) for r in cur.fetchall()]
    out[qid] = {"question": question.strip(), "sql": sql.strip(), "columns": cols, "rows": rows}
    print(qid, len(rows), "rows", flush=True)
(DATA / "results.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
conn.close(); print("saved data/results.json")