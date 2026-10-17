"""load_spatial.py - Build #10 step 2: facilities and county population centers into schema `col` as geography rows.

The Azure skill here is the `geography` type on the free SQL tier: a point column in SRID 4326 (WGS 84),
built from lon/lat with geography::Point(lat, lon, 4326), with a spatial index so nearest-neighbour
queries use the index instead of 1,657 x 3,221 distance calls. STDistance() returns metres on the
ellipsoid - great-circle distance, not road distance (stated on the page).

Tables (replace-on-load, idempotent):
  col.facility       sta_no PK, name, parent, city, state, fips, kind, suspended, opened, visn, urh, lat, lon, geo GEOGRAPHY
  col.county_center  fips PK, name, state_name, pop2020 (NULL for CT regions), center_kind, lat, lon, geo GEOGRAPHY
Auth: Entra token by env (SQL_ACCESS_TOKEN, SQL_SERVER_NAME, SQL_DATABASE_NAME); build #6's connect() with retries.
Run: python load_spatial.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build-06-cost-of-living"))
from load_snapshots import connect  # noqa: E402

DATA = Path(__file__).parent / "data"

DDL = """
IF OBJECT_ID('col.facility') IS NULL
CREATE TABLE col.facility (
  sta_no NVARCHAR(7) NOT NULL PRIMARY KEY, name NVARCHAR(150) NOT NULL, parent NVARCHAR(7) NULL,
  city NVARCHAR(60) NULL, state CHAR(2) NULL, fips CHAR(5) NULL, kind NVARCHAR(8) NOT NULL,
  suspended CHAR(1) NULL, opened DATE NULL, visn NVARCHAR(4) NULL, urh NVARCHAR(2) NULL,
  lat FLOAT NOT NULL, lon FLOAT NOT NULL, geo GEOGRAPHY NOT NULL);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'sx_facility_geo')
CREATE SPATIAL INDEX sx_facility_geo ON col.facility(geo);
DROP TABLE IF EXISTS col.county_center;
CREATE TABLE col.county_center (
  fips CHAR(5) NOT NULL PRIMARY KEY, name NVARCHAR(80) NOT NULL, state_name NVARCHAR(40) NOT NULL,
  pop2020 INT NULL, center_kind NVARCHAR(16) NOT NULL, lat FLOAT NOT NULL, lon FLOAT NOT NULL, geo GEOGRAPHY NOT NULL);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'sx_county_center_geo')
CREATE SPATIAL INDEX sx_county_center_geo ON col.county_center(geo);
"""


def main():
    fac = json.loads((DATA / "vha_facilities.json").read_text(encoding="utf-8"))
    cen = json.loads((DATA / "county_centroids.json").read_text(encoding="utf-8"))
    conn = connect()
    cur = conn.cursor()
    cur.execute(DDL)
    t0 = time.time()
    cur.execute("DELETE FROM col.facility")
    cur.execute("""INSERT INTO col.facility (sta_no,name,parent,city,state,fips,kind,suspended,opened,visn,urh,lat,lon,geo)
        SELECT j.sta_no, j.name, j.parent, j.city, j.state, j.fips, j.kind, j.suspended, j.opened, j.visn, j.urh, j.lat, j.lon,
               geography::Point(j.lat, j.lon, 4326)
        FROM OPENJSON(?) WITH (sta_no NVARCHAR(7) '$.sta_no', name NVARCHAR(150) '$.name', parent NVARCHAR(7) '$.parent',
             city NVARCHAR(60) '$.city', state CHAR(2) '$.state', fips CHAR(5) '$.fips', kind NVARCHAR(8) '$.kind',
             suspended CHAR(1) '$.suspended', opened DATE '$.opened', visn NVARCHAR(4) '$.visn', urh NVARCHAR(2) '$.urh',
             lat FLOAT '$.lat', lon FLOAT '$.lon') AS j""", (json.dumps(fac),))
    cur.execute("DELETE FROM col.county_center")
    cur.execute("""INSERT INTO col.county_center (fips,name,state_name,pop2020,center_kind,lat,lon,geo)
        SELECT j.fips, j.name, j.state_name, j.pop2020, j.center_kind, j.lat, j.lon, geography::Point(j.lat, j.lon, 4326)
        FROM OPENJSON(?) WITH (fips CHAR(5) '$.fips', name NVARCHAR(80) '$.name', state_name NVARCHAR(40) '$.state_name',
             pop2020 INT '$.pop2020', center_kind NVARCHAR(16) '$.center_kind', lat FLOAT '$.lat', lon FLOAT '$.lon') AS j""", (json.dumps(cen),))
    cur.execute("""MERGE col.dataset AS t USING (VALUES (?,?,?,?,?)) AS s(dataset_id,tool,vintage,as_of,source_file) ON t.dataset_id=s.dataset_id
        WHEN MATCHED THEN UPDATE SET vintage=s.vintage, as_of=s.as_of, source_file=s.source_file, loaded_at=SYSUTCDATETIME()
        WHEN NOT MATCHED THEN INSERT (dataset_id,tool,vintage,as_of,source_file) VALUES (s.dataset_id,s.tool,s.vintage,s.as_of,s.source_file);""",
                ("vast_2018_facilities", "hrsa_gis", "VAST extract 2018-09-29", time.strftime("%Y-%m-%d"), "vha_facilities.json"))
    cur.execute("""MERGE col.dataset AS t USING (VALUES (?,?,?,?,?)) AS s(dataset_id,tool,vintage,as_of,source_file) ON t.dataset_id=s.dataset_id
        WHEN MATCHED THEN UPDATE SET vintage=s.vintage, as_of=s.as_of, source_file=s.source_file, loaded_at=SYSUTCDATETIME()
        WHEN NOT MATCHED THEN INSERT (dataset_id,tool,vintage,as_of,source_file) VALUES (s.dataset_id,s.tool,s.vintage,s.as_of,s.source_file);""",
                ("cenpop_2020_county", "census", "2020 Census centers of population", time.strftime("%Y-%m-%d"), "county_centroids.json"))
    conn.commit()
    print(f"loaded {len(fac):,} facilities and {len(cen):,} county centers in {time.time() - t0:.0f}s", flush=True)
    # checks: every point valid; counts by kind; one known distance (Autauga AL center -> Montgomery VAMC should be ~15 mi)
    for sql in ["SELECT COUNT(*), SUM(CASE WHEN geo.STIsValid() = 1 THEN 1 ELSE 0 END) FROM col.facility",
                "SELECT COUNT(*), SUM(CASE WHEN geo.STIsValid() = 1 THEN 1 ELSE 0 END) FROM col.county_center",
                "SELECT kind, COUNT(*) FROM col.facility GROUP BY kind ORDER BY kind",
                """SELECT TOP 1 f.name, ROUND(c.geo.STDistance(f.geo) / 1609.344, 1) AS miles
                   FROM col.county_center c CROSS JOIN col.facility f WHERE c.fips = '01001' AND f.kind = 'VAMC' ORDER BY miles"""]:
        cur.execute(sql)
        print(cur.fetchall(), flush=True)


if __name__ == "__main__":
    main()
