import os, mssql_python
from types import SimpleNamespace
class TP:
    def get_token(self,*a,**k): return SimpleNamespace(token=os.environ["SQL_ACCESS_TOKEN"])
c = mssql_python.connect(f"Server={os.environ['SQL_SERVER_NAME']};Database={os.environ['SQL_DATABASE_NAME']};Encrypt=yes;", token_provider=TP()).cursor()
c.execute("SELECT run_id, MIN(run_time), COUNT(*), MAX(n_authors), SUM(CASE WHEN key_phrases IS NOT NULL THEN 1 ELSE 0 END) FROM dbo.template_runs GROUP BY run_id")
for r in c.fetchall(): print("run:", r)
c.execute("SELECT TOP 3 rank, body, key_phrases FROM dbo.template_runs WHERE key_phrases IS NOT NULL ORDER BY rank")
for r in c.fetchall(): print(r)