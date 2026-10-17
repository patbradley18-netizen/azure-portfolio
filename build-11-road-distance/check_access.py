"""check_access.py - one-line sanity check of col.county_access and the ledger (counts must match build #10 Q19)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build-06-cost-of-living"))
from load_snapshots import connect
c = connect().cursor()
for q in ("SELECT COUNT(*), SUM(veterans), ROUND(SUM(veterans*vamc_miles)/SUM(veterans),1) FROM col.county_access",
          "SELECT COUNT(*) FROM col.route_ledger"):
    c.execute(q); print(c.fetchone(), flush=True)
