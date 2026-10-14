# create_runs_table.py - one-time: table for stage-2 run history. PK required by the SQL output binding.
import os, sys, mssql_python
from types import SimpleNamespace
tok=os.environ.get("SQL_ACCESS_TOKEN"); srv=os.environ.get("SQL_SERVER_NAME"); db=os.environ.get("SQL_DATABASE_NAME")
if not (tok and srv and db): sys.exit("needs SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME")
class TP:
    def get_token(self,*a,**k): return SimpleNamespace(token=tok)
conn = mssql_python.connect(f"Server={srv};Database={db};Encrypt=yes;", token_provider=TP()); cur = conn.cursor()
cur.execute("""
IF OBJECT_ID('dbo.template_runs') IS NULL
CREATE TABLE dbo.template_runs (
  run_id UNIQUEIDENTIFIER NOT NULL, run_time DATETIME2 NOT NULL, rank INT NOT NULL,
  body NVARCHAR(500), n_tweets INT, n_authors INT, top_category NVARCHAR(40),
  key_phrases NVARCHAR(500) NULL, english_originals INT,
  CONSTRAINT PK_template_runs PRIMARY KEY (run_id, rank));
""")
conn.commit()
cur.execute("SELECT name FROM sys.tables ORDER BY name"); print("tables:", [r[0] for r in cur.fetchall()])
conn.close()