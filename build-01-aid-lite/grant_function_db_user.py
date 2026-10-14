# grant_function_db_user.py - one-time: lets the Function's managed identity read/write the aid database.
import os, sys, mssql_python
from types import SimpleNamespace
tok=os.environ.get("SQL_ACCESS_TOKEN"); srv=os.environ.get("SQL_SERVER_NAME"); db=os.environ.get("SQL_DATABASE_NAME")
if not (tok and srv and db): sys.exit("needs SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME")
class TP:
    def get_token(self,*a,**k): return SimpleNamespace(token=tok)
conn = mssql_python.connect(f"Server={srv};Database={db};Encrypt=yes;", token_provider=TP()); cur = conn.cursor()
cur.execute("""
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'func-azportfolio-b1')
  CREATE USER [func-azportfolio-b1] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [func-azportfolio-b1];
ALTER ROLE db_datawriter ADD MEMBER [func-azportfolio-b1];
""")
conn.commit()
cur.execute("SELECT dp.name, STRING_AGG(r.name, ', ') FROM sys.database_principals dp JOIN sys.database_role_members m ON m.member_principal_id=dp.principal_id JOIN sys.database_principals r ON r.principal_id=m.role_principal_id WHERE dp.name='func-azportfolio-b1' GROUP BY dp.name")
print("db user:", cur.fetchall()); conn.close()