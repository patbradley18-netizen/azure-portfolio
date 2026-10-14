# test_conn.py - connection smoke test. Token comes from the SQL_ACCESS_TOKEN env var (never a file).
import os, sys, time
import mssql_python
from types import SimpleNamespace
tok = os.environ.get("SQL_ACCESS_TOKEN"); srv = os.environ.get("SQL_SERVER_NAME"); db = os.environ.get("SQL_DATABASE_NAME")
if not (tok and srv and db): sys.exit("needs SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME")
class TP:
    def get_token(self, *a, **k): return SimpleNamespace(token=tok)
t0 = time.time()
try:
    conn = mssql_python.connect(f"Server={srv};Database={db};Encrypt=yes;", token_provider=TP())
    cur = conn.cursor(); cur.execute("SELECT DB_NAME(), SUSER_NAME(), @@VERSION"); r = cur.fetchone()
    print(f"CONNECTED in {time.time()-t0:.1f}s | db={r[0]} | user={r[1]} | {r[2][:40]}")
    conn.close()
except Exception as e:
    print(f"FAILED after {time.time()-t0:.1f}s: {e}")