"""sql_setup.py - Build #14 database setup (operator token by env). Idempotent.
Creates col.ingest_ledger (one row per gate decision per file: validated -> queued|quarantined; loaded|duplicate|poison),
the validator's user (INSERT on the ledger only), and - when given a principal name - the loader's user
(SELECT on the ledger + the warehouse tables it writes, EXECUTE on col.sp_load_acs).
Run: python sql_setup.py [loader-principal-name]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build-06-cost-of-living"))
from load_snapshots import connect  # noqa: E402

VALIDATOR = "func-azportfolio-b14"
LOADER = sys.argv[1] if len(sys.argv) > 1 else None

STATEMENTS = [
    """IF OBJECT_ID('col.ingest_ledger') IS NULL
       CREATE TABLE col.ingest_ledger (
         ledger_id INT IDENTITY PRIMARY KEY, sha256 CHAR(64) NOT NULL, file_name NVARCHAR(200) NOT NULL, blob_url NVARCHAR(400) NULL,
         size_bytes BIGINT NULL, received_at DATETIME2 NOT NULL, stage NVARCHAR(16) NOT NULL, outcome NVARCHAR(16) NULL,
         reason NVARCHAR(400) NULL, dataset_id NVARCHAR(40) NULL, rows INT NULL, run_by NVARCHAR(60) NULL);""",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'ix_ingest_ledger_sha') CREATE INDEX ix_ingest_ledger_sha ON col.ingest_ledger (sha256, stage);",
    f"IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '{VALIDATOR}') CREATE USER [{VALIDATOR}] FROM EXTERNAL PROVIDER;",
    f"GRANT INSERT ON col.ingest_ledger TO [{VALIDATOR}];",
]
if LOADER:
    STATEMENTS += [
        f"IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '{LOADER}') CREATE USER [{LOADER}] FROM EXTERNAL PROVIDER;",
        f"GRANT SELECT, INSERT ON col.ingest_ledger TO [{LOADER}];",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON col.measure TO [{LOADER}];",
        f"GRANT SELECT, INSERT, UPDATE ON col.metric TO [{LOADER}];",
        f"GRANT SELECT, INSERT, UPDATE ON col.dataset TO [{LOADER}];",
        f"GRANT SELECT, INSERT ON col.county TO [{LOADER}];",
    ]


def main():
    conn = connect(); cur = conn.cursor()
    for s in STATEMENTS:
        cur.execute(s)
    conn.commit()
    cur.execute("SELECT dp.name, p.permission_name, OBJECT_NAME(p.major_id) FROM sys.database_permissions p JOIN sys.database_principals dp ON dp.principal_id = p.grantee_principal_id WHERE dp.name IN (?, ?) ORDER BY 1, 3", (VALIDATOR, LOADER or ""))
    for r in cur.fetchall():
        print(r)


if __name__ == "__main__":
    main()
