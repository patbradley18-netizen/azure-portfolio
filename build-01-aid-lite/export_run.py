# export_run.py - pulls the latest stage-2 run out of SQL for the dashboard (adds key phrases + last run time).
import os, json, mssql_python
from types import SimpleNamespace
class TP:
    def get_token(self,*a,**k): return SimpleNamespace(token=os.environ["SQL_ACCESS_TOKEN"])
c = mssql_python.connect(f"Server={os.environ['SQL_SERVER_NAME']};Database={os.environ['SQL_DATABASE_NAME']};Encrypt=yes;", token_provider=TP()).cursor()
c.execute("SELECT TOP 1 run_id, run_time FROM dbo.template_runs ORDER BY run_time DESC"); run_id, run_time = c.fetchone()
c.execute("SELECT rank, body, n_tweets, n_authors, top_category, key_phrases FROM dbo.template_runs WHERE run_id=? AND rank<=15 ORDER BY rank", (run_id,))
rows = [dict(zip(["rank","body","n_tweets","n_authors","top_category","key_phrases"], r)) for r in c.fetchall()]
c.execute("SELECT COUNT(DISTINCT run_id), MIN(run_time) FROM dbo.template_runs"); n_runs, first = c.fetchone()
d = json.load(open("data/dashboard_data.json"))
d["stage2"] = {"last_run_utc": str(run_time), "run_id": str(run_id), "runs": int(n_runs), "first_run_utc": str(first), "top_with_phrases": rows}
json.dump(d, open("data/dashboard_data.json","w"), indent=1, default=str); print("runs:", n_runs, "last:", run_time, "| rows:", len(rows))