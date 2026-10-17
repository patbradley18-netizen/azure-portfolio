"""materialize.py - Build #11 step 1: compute build #10's nearest-neighbour join once and keep it.

Build #10's Q19-Q21 each re-ran the spatial pass (174 s for four queries). This writes one row per county
to col.county_access and everything downstream reads it. Replace-on-load. Also creates the route ledger
table that step 3 fills: one row per Azure Maps Route call, so the bill can be reconciled line by line.
Auth: Entra token by env (SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME); build #6's connect() with retries.
Run: python materialize.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build-06-cost-of-living"))
from load_snapshots import connect  # noqa: E402

DDL = """
DROP TABLE IF EXISTS col.county_access;
CREATE TABLE col.county_access (
  fips CHAR(5) NOT NULL PRIMARY KEY, county NVARCHAR(80) NOT NULL, state_abbr CHAR(2) NOT NULL, center_kind NVARCHAR(16) NOT NULL,
  veterans FLOAT NULL, adults FLOAT NULL, vet_share FLOAT NULL,
  vamc_sta_no NVARCHAR(7) NOT NULL, vamc_name NVARCHAR(150) NOT NULL, vamc_miles FLOAT NOT NULL,
  site_sta_no NVARCHAR(7) NOT NULL, site_name NVARCHAR(150) NOT NULL, site_kind NVARCHAR(8) NOT NULL, site_miles FLOAT NOT NULL,
  urh NVARCHAR(2) NULL, computed_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME());
IF OBJECT_ID('col.route_ledger') IS NULL
CREATE TABLE col.route_ledger (
  fips CHAR(5) NOT NULL, dest_sta_no NVARCHAR(7) NOT NULL, called_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
  http_status INT NOT NULL, road_meters FLOAT NULL, travel_seconds FLOAT NULL, batch_id NVARCHAR(40) NOT NULL,
  CONSTRAINT pk_route_ledger PRIMARY KEY (fips, dest_sta_no, called_at));
"""

FILL = """
WITH v AS (
  SELECT fips, MAX(CASE WHEN code = 'B21001_002E' THEN value END) AS veterans, MAX(CASE WHEN code = 'B21001_001E' THEN value END) AS adults
  FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips),
u AS (SELECT fips, MIN(urh) AS urh FROM col.facility GROUP BY fips)  -- VAST urban/rural code of the county's own sites, where any
INSERT INTO col.county_access (fips, county, state_abbr, center_kind, veterans, adults, vet_share,
                               vamc_sta_no, vamc_name, vamc_miles, site_sta_no, site_name, site_kind, site_miles, urh)
SELECT c.fips, c.name, cty.state_abbr, c.center_kind, v.veterans, v.adults, 100.0 * v.veterans / NULLIF(v.adults, 0),
       m.sta_no, m.name, m.miles, s.sta_no, s.name, s.kind, s.miles, u.urh
FROM col.county_center c
JOIN col.county cty ON cty.fips = c.fips
JOIN v ON v.fips = c.fips
LEFT JOIN u ON u.fips = c.fips
CROSS APPLY (SELECT TOP 1 f.sta_no, f.name, c.geo.STDistance(f.geo) / 1609.344 AS miles
             FROM col.facility f WHERE f.kind = 'VAMC' AND f.suspended = 'N' ORDER BY c.geo.STDistance(f.geo)) m
CROSS APPLY (SELECT TOP 1 f.sta_no, f.name, f.kind, c.geo.STDistance(f.geo) / 1609.344 AS miles
             FROM col.facility f WHERE f.kind IN ('VAMC','HCC','CBOC','OOS') AND f.suspended = 'N' ORDER BY c.geo.STDistance(f.geo)) s
WHERE cty.state_abbr IS NOT NULL AND v.veterans IS NOT NULL;
"""


def main():
    conn = connect()
    cur = conn.cursor()
    cur.execute(DDL)
    t0 = time.time()
    cur.execute(FILL)
    conn.commit()
    cur.execute("SELECT COUNT(*), SUM(veterans), ROUND(SUM(veterans * vamc_miles) / SUM(veterans), 1) FROM col.county_access")
    print(f"col.county_access: {cur.fetchone()} in {time.time() - t0:.0f}s (rows, veterans, weighted VAMC miles — must match build #10 Q19: 3144, 16,569,149, 35.9)", flush=True)
    cur.execute("SELECT COUNT(*) FROM col.route_ledger")
    print("route_ledger rows:", cur.fetchone()[0])


if __name__ == "__main__":
    main()
