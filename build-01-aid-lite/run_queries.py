# run_queries.py - stage 1, step 6: the analyst's questions, answered in SQL.
# Reads dbo.posts and dbo.templates in Azure SQL; writes data/dashboard_data.json for the page.
# Secrets rule: names from env vars; token from env var (memory only) or device-code sign-in.

import os, sys, json
import mssql_python
from azure.identity import DeviceCodeCredential

for k in ("SQL_SERVER_NAME", "SQL_DATABASE_NAME"):
    if not os.environ.get(k): sys.exit(f"needs {k}")
if os.environ.get("SQL_ACCESS_TOKEN"):
    from types import SimpleNamespace
    class _Tok:
        def get_token(self, *a, **k): return SimpleNamespace(token=os.environ["SQL_ACCESS_TOKEN"])
    cred = _Tok()
else:
    cred = DeviceCodeCredential(prompt_callback=lambda u, c, e: print(f"SIGN IN: open {u} and enter code {c}", flush=True))

conn = mssql_python.connect(f"Server={os.environ['SQL_SERVER_NAME']};Database={os.environ['SQL_DATABASE_NAME']};Encrypt=yes;", token_provider=cred)
cur = conn.cursor()

def q(sql):
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

QUERIES = {
# Q1. Which messages were pushed by the most accounts? (amplification rings)
"top_templates": """
SELECT TOP 15 body, n_tweets, n_authors, top_category
FROM dbo.templates
ORDER BY n_authors DESC, n_tweets DESC;""",

# Q2. How concentrated is coordination by account type?
"by_category": """
SELECT top_category,
       COUNT(*)        AS templates,
       SUM(n_tweets)   AS tweets_in_templates,
       MAX(n_authors)  AS max_accounts_on_one_message
FROM dbo.templates
GROUP BY top_category
ORDER BY tweets_in_templates DESC;""",

# Q3. Did the embedding clusters land on the hand-made labels? (purity per cluster)
"cluster_purity": """
WITH c AS (
  SELECT cluster, account_category, COUNT(*) AS n,
         ROW_NUMBER() OVER (PARTITION BY cluster ORDER BY COUNT(*) DESC) AS rn
  FROM dbo.posts GROUP BY cluster, account_category),
 t AS (SELECT cluster, COUNT(*) AS size FROM dbo.posts GROUP BY cluster)
SELECT t.cluster, t.size, c.account_category AS top_category,
       CAST(ROUND(100.0 * c.n / t.size, 1) AS DECIMAL(5,1)) AS purity_pct
FROM t JOIN c ON c.cluster = t.cluster AND c.rn = 1
ORDER BY purity_pct DESC;""",

# Q4. Headline numbers
"kpis": """
SELECT (SELECT COUNT(*) FROM dbo.posts)                 AS sample_posts,
       (SELECT COUNT(*) FROM dbo.templates)             AS templates,
       (SELECT SUM(n_tweets) FROM dbo.templates)        AS tweets_in_templates,
       (SELECT MAX(n_authors) FROM dbo.templates)       AS max_accounts_one_message,
       (SELECT COUNT(*) FROM dbo.templates WHERE n_authors >= 10) AS templates_10plus_accounts;""",
}

out = {}
for name, sql in QUERIES.items():
    rows = q(sql)
    out[name] = rows
    print(f"\n== {name} ({len(rows)} rows) ==")
    for r in rows[:8]:
        print("  ", {k: (v[:60] + "..." if isinstance(v, str) and len(v) > 60 else v) for k, v in r.items()})
conn.close()

out["source"] = {"dataset": "FiveThirtyEight / Clemson IRA tweets, file 1", "english_originals_in_file": 84270,
                 "note": "templates = identical body text (URLs and leading/trailing hashtags stripped) posted 3+ times by 2+ accounts"}
with open("data/dashboard_data.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
print("\nSaved data/dashboard_data.json")