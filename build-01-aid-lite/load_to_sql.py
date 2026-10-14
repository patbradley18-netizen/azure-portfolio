# load_to_sql.py - stage 1, step 5.
# Writes the stage-1 results into Azure SQL:
#   posts      : the 5,000-tweet sample with its cluster number
#   templates  : bodies posted 3+ times by 2+ accounts (the coordination signal)
# Secrets rule: server/database are NAMES from environment variables; sign-in is
# Microsoft Entra device code. No password, key or connection string in this file.

import os, re, sys
import pandas as pd
import mssql_python
from azure.identity import DeviceCodeCredential

# ---- Preflight: every required setting must be present BY NAME before we touch anything ----
REQUIRED = ["SQL_SERVER_NAME", "SQL_DATABASE_NAME"]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    sys.exit(f"needs {', '.join(missing)} - set them in the environment before running")
SERVER = os.environ["SQL_SERVER_NAME"]
DB = os.environ["SQL_DATABASE_NAME"]

# ---- Build the two tables in pandas first ----
posts = pd.read_csv("data/sample_clusters.csv")
posts["content"] = posts["content"].astype(str).str.slice(0, 1000)
posts = posts[["author", "publish_date", "account_category", "content", "cluster"]]

full = pd.read_csv("data/IRAhandle_tweets_1.csv",
                   usecols=["author", "content", "account_category", "language", "retweet"]).dropna(subset=["content"])
full = full[(full["language"] == "English") & (full["retweet"] == 0)]
full["content"] = full["content"].astype(str)
def body(t):
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"^(#\w+\s+)+", "", t)
    t = re.sub(r"(\s+#\w+)+\s*$", "", t)
    return t.strip().lower()
full["body"] = full["content"].apply(body)
full = full[full["body"].str.len() >= 25]
g = full.groupby("body").agg(n_tweets=("author", "size"), n_authors=("author", "nunique"),
                             top_category=("account_category", lambda s: s.value_counts().index[0]))
templates = g[(g["n_tweets"] >= 3) & (g["n_authors"] >= 2)].reset_index()
templates["body"] = templates["body"].str.slice(0, 500)
print(f"posts: {len(posts)} rows | templates: {len(templates)} rows")

# ---- Connect. DeviceCodeCredential prints a code; the operator signs in once in a browser. ----
# Token path (preferred when available): SQL_ACCESS_TOKEN comes from `az account get-access-token`
# on the host, passed through the environment only. Falls back to a device-code sign-in.
if os.environ.get("SQL_ACCESS_TOKEN"):
    from types import SimpleNamespace
    class _Tok:
        def get_token(self, *a, **k): return SimpleNamespace(token=os.environ["SQL_ACCESS_TOKEN"])
    cred = _Tok()
else:
    cred = DeviceCodeCredential(prompt_callback=lambda url, code, exp: print(f"SIGN IN: open {url} and enter code {code}", flush=True))
conn = mssql_python.connect(f"Server={SERVER};Database={DB};Encrypt=yes;", token_provider=cred)
cur = conn.cursor()

# ---- Tables (idempotent) ----
cur.execute("""
IF OBJECT_ID('dbo.posts') IS NULL
CREATE TABLE dbo.posts (
  id INT IDENTITY PRIMARY KEY, author NVARCHAR(100), publish_date NVARCHAR(40),
  account_category NVARCHAR(40), content NVARCHAR(1000), cluster INT);
IF OBJECT_ID('dbo.templates') IS NULL
CREATE TABLE dbo.templates (
  id INT IDENTITY PRIMARY KEY, body NVARCHAR(500), n_tweets INT, n_authors INT, top_category NVARCHAR(40));
""")
cur.execute("DELETE FROM dbo.posts; DELETE FROM dbo.templates;")

# ---- Load ----
cur.executemany("INSERT INTO dbo.posts (author, publish_date, account_category, content, cluster) VALUES (?,?,?,?,?)",
                [tuple(r) for r in posts.itertuples(index=False)])
cur.executemany("INSERT INTO dbo.templates (body, n_tweets, n_authors, top_category) VALUES (?,?,?,?)",
                [tuple(r) for r in templates.itertuples(index=False)])
conn.commit()

# ---- Verify by reading back ----
for t in ("posts", "templates"):
    cur.execute(f"SELECT COUNT(*) FROM dbo.{t}")
    print(f"dbo.{t}: {cur.fetchone()[0]} rows in Azure SQL")
conn.close()
print("done - connection closed (auto-pause can start)")