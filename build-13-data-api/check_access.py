"""check_access.py - after an orchestration: row count, veterans, weighted miles, computed_at range (must match build #10 Q19 when complete)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build-06-cost-of-living"))
from load_snapshots import connect
c = connect().cursor()
c.execute("SELECT COUNT(*), SUM(veterans), ROUND(SUM(veterans*vamc_miles)/SUM(veterans),1), MIN(computed_at), MAX(computed_at) FROM col.county_access"); print(c.fetchone(), flush=True)
c.execute("SELECT state_abbr, COUNT(*) FROM col.county_access GROUP BY state_abbr ORDER BY state_abbr"); r = c.fetchall(); print(len(r), 'states;', r[:5], flush=True)
c.execute("SELECT run_id, states_done, rows_written, status FROM col.refresh_run ORDER BY started_at DESC"); print(c.fetchall(), flush=True)
