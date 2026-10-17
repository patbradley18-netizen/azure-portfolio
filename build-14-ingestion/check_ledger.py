"""check_ledger.py - what the gates decided: the ledger, newest first."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build-06-cost-of-living"))
from load_snapshots import connect
c = connect().cursor()
c.execute("SELECT TOP 20 ledger_id, file_name, LEFT(sha256,8), stage, outcome, LEFT(reason,90), dataset_id, rows, run_by, received_at FROM col.ingest_ledger ORDER BY ledger_id DESC")
for r in c.fetchall(): print(r, flush=True)
