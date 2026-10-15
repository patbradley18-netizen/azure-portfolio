# grant_function_db_user.py - one-time: lets func-azportfolio-b2's managed identity read/write schema bls only.
import os, sys, time, mssql_python
from types import SimpleNamespace
tok=os.environ.get("SQL_ACCESS_TOKEN"); srv=os.environ.get("SQL_SERVER_NAME"); db=os.environ.get("SQL_DATABASE_NAME")
if not (tok and srv and db): sys.exit("needs SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME")
class TP:
    def get_token(self,*a,**k): return SimpleNamespace(token=tok)
for i in range(3):
    try: conn = mssql_python.connect(f"Server={srv};Database={db};Encrypt=yes;", token_provider=TP()); break
    except Exception as e: print("retry", i+1, type(e).__name__, flush=True); time.sleep(20)
cur = conn.cursor()
cur.execute("""
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'func-azportfolio-b2')
  CREATE USER [func-azportfolio-b2] FROM EXTERNAL PROVIDER;
GRANT SELECT, INSERT, UPDATE ON SCHEMA::bls TO [func-azportfolio-b2];
""")
conn.commit()
cur.execute("SELECT state_desc, permission_name FROM sys.database_permissions p JOIN sys.database_principals dp ON dp.principal_id=p.grantee_principal_id WHERE dp.name='func-azportfolio-b2'")
print("grants:", cur.fetchall()); conn.close()