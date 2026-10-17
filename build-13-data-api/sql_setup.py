"""sql_setup.py - Build #13 one-time database setup (run as the operator, token by env).

Creates: the Function's external-provider user with SELECT on schema col; table col.refresh_run (one row per
orchestration run); procedure col.sp_refresh_access_state (rebuilds col.county_access for one state - the unit of
fan-out); procedures the API reads through (so the Function needs EXECUTE, not ad-hoc query rights).
Nothing here holds a secret; auth is the operator's Entra token, the Function's is its managed identity.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build-06-cost-of-living"))
from load_snapshots import connect  # noqa: E402

FUNC_USER = "func-azportfolio-b13"

STATEMENTS = [
    f"IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '{FUNC_USER}') CREATE USER [{FUNC_USER}] FROM EXTERNAL PROVIDER;",
    f"GRANT SELECT ON SCHEMA::col TO [{FUNC_USER}];",
    """IF OBJECT_ID('col.refresh_run') IS NULL
       CREATE TABLE col.refresh_run (
         run_id NVARCHAR(64) NOT NULL PRIMARY KEY, started_at DATETIME2 NOT NULL, finished_at DATETIME2 NULL,
         states_done INT NOT NULL DEFAULT 0, rows_written INT NOT NULL DEFAULT 0, status NVARCHAR(16) NOT NULL DEFAULT 'running', note NVARCHAR(200) NULL);""",
    f"GRANT SELECT, INSERT, UPDATE ON col.refresh_run TO [{FUNC_USER}];",
    f"GRANT INSERT, DELETE ON col.county_access TO [{FUNC_USER}];",
    """CREATE OR ALTER PROCEDURE col.sp_refresh_access_state @state CHAR(2) AS
       BEGIN
         SET NOCOUNT ON;
         DELETE a FROM col.county_access a JOIN col.county c ON c.fips = a.fips WHERE c.state_abbr = @state;
         WITH v AS (
           SELECT fips, MAX(CASE WHEN code = 'B21001_002E' THEN value END) AS veterans, MAX(CASE WHEN code = 'B21001_001E' THEN value END) AS adults
           FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips),
         u AS (SELECT fips, MIN(urh) AS urh FROM col.facility GROUP BY fips)
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
         WHERE cty.state_abbr = @state AND v.veterans IS NOT NULL;
         SELECT @state AS state_abbr, @@ROWCOUNT AS rows_written;
       END""",
    f"GRANT EXECUTE ON col.sp_refresh_access_state TO [{FUNC_USER}];",
    """CREATE OR ALTER PROCEDURE col.sp_facilities_near @lat FLOAT, @lon FLOAT, @miles FLOAT, @kind NVARCHAR(8) = '', @top INT = 20 AS
       BEGIN
         SET NOCOUNT ON;
         -- out-of-range input returns no rows instead of a geography error, so the API can answer 400 rather than 500
         DECLARE @p GEOGRAPHY = CASE WHEN @lat BETWEEN -90 AND 90 AND @lon BETWEEN -180 AND 180 THEN geography::Point(@lat, @lon, 4326) END;
         SELECT TOP (@top) sta_no, name, kind, city, state, lat, lon, ROUND(@p.STDistance(geo) / 1609.344, 1) AS miles
         FROM col.facility
         WHERE @p IS NOT NULL AND suspended = 'N' AND kind IN ('VAMC','HCC','CBOC','OOS') AND (NULLIF(@kind, '') IS NULL OR kind = @kind)
           AND @p.STDistance(geo) <= @miles * 1609.344
         ORDER BY @p.STDistance(geo);
       END""",
    f"GRANT EXECUTE ON col.sp_facilities_near TO [{FUNC_USER}];",
]


def main():
    conn = connect()
    cur = conn.cursor()
    for s in STATEMENTS:
        cur.execute(s)
    conn.commit()
    cur.execute("SELECT class_desc, permission_name, state_desc FROM sys.database_permissions p JOIN sys.database_principals dp ON dp.principal_id = p.grantee_principal_id WHERE dp.name = ?", (FUNC_USER,))
    print("grants:", cur.fetchall())
    cur.execute("EXEC col.sp_facilities_near @lat = 39.9, @lon = -86.2, @miles = 30, @top = 3")
    print("near Indianapolis:", cur.fetchall())


if __name__ == "__main__":
    main()
