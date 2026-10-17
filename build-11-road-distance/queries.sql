-- Build #11: how much does straight-line lie? Road miles (OSRM, OpenStreetMap) vs STDistance for a capped sample.
-- Reads col.county_access (materialised build #10 join) and col.route_ledger (one row per router call).
-- ratio = road miles / straight-line miles; the "detour index". 1.0 = the road is the crow's line; 1.3 is a common planning rule of thumb.

-- Q22 | The detour index: road miles over straight-line miles to the nearest VA medical center, by straight-line band
WITH r AS (
  SELECT fips, dest_sta_no, road_meters / 1609.344 AS road_miles, travel_seconds / 60.0 AS travel_min
  FROM col.route_ledger WHERE road_meters IS NOT NULL),
j AS (
  SELECT a.fips, a.county, a.state_abbr, a.veterans, a.vamc_miles, r.road_miles, r.travel_min, r.road_miles / NULLIF(a.vamc_miles, 0) AS ratio,
         CASE WHEN a.vamc_miles <= 30 THEN '0-30' WHEN a.vamc_miles <= 60 THEN '30-60' WHEN a.vamc_miles <= 100 THEN '60-100' ELSE '100+' END AS band
  FROM col.county_access a JOIN r ON r.fips = a.fips AND r.dest_sta_no = a.vamc_sta_no)
SELECT COALESCE(band, 'all') AS band, COUNT(*) AS counties, SUM(veterans) AS veterans,
       ROUND(AVG(ratio), 3) AS mean_ratio,
       ROUND(SUM(veterans * ratio) / SUM(veterans), 3) AS vet_weighted_ratio,
       ROUND(MIN(ratio), 2) AS min_ratio, ROUND(MAX(ratio), 2) AS max_ratio,
       ROUND(AVG(vamc_miles), 1) AS mean_straight_miles, ROUND(AVG(road_miles), 1) AS mean_road_miles, ROUND(AVG(travel_min), 0) AS mean_drive_minutes,
       ROUND(100.0 * SUM(CASE WHEN ratio > 1.5 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_counties_ratio_over_1_5
FROM j
GROUP BY ROLLUP(band)
ORDER BY CASE band WHEN '0-30' THEN 1 WHEN '30-60' THEN 2 WHEN '60-100' THEN 3 WHEN '100+' THEN 4 ELSE 5 END;

-- Q23 | Where the crow lies most: the 25 sampled counties with the largest detour index (at least 20 straight-line miles)
WITH r AS (
  SELECT fips, dest_sta_no, road_meters / 1609.344 AS road_miles, travel_seconds / 60.0 AS travel_min
  FROM col.route_ledger WHERE road_meters IS NOT NULL)
SELECT TOP 25 a.fips, a.county, a.state_abbr, a.veterans, a.vamc_name, ROUND(a.vamc_miles, 1) AS straight_miles,
       ROUND(r.road_miles, 1) AS road_miles, ROUND(r.road_miles / a.vamc_miles, 2) AS ratio, ROUND(r.travel_min, 0) AS drive_minutes
FROM col.county_access a JOIN r ON r.fips = a.fips AND r.dest_sta_no = a.vamc_sta_no
WHERE a.vamc_miles >= 20
ORDER BY ratio DESC;

-- Q24 | Build #10's base counties, corrected: straight-line vs road vs drive time to the nearest VA medical center
WITH r AS (
  SELECT fips, dest_sta_no, road_meters / 1609.344 AS road_miles, travel_seconds / 60.0 AS travel_min
  FROM col.route_ledger WHERE road_meters IS NOT NULL),
q20 AS (
  SELECT TOP 25 fips FROM col.county_access WHERE veterans >= 5000 AND vamc_miles > 60 ORDER BY vet_share DESC)
SELECT a.county, a.state_abbr, a.veterans, ROUND(a.vet_share, 1) AS vet_share, a.vamc_name,
       ROUND(a.vamc_miles, 1) AS straight_miles, ROUND(r.road_miles, 1) AS road_miles, ROUND(r.road_miles / a.vamc_miles, 2) AS ratio,
       ROUND(r.travel_min, 0) AS drive_minutes, ROUND(a.site_miles, 1) AS nearest_site_straight_miles
FROM col.county_access a JOIN q20 ON q20.fips = a.fips LEFT JOIN r ON r.fips = a.fips AND r.dest_sta_no = a.vamc_sta_no
ORDER BY a.vet_share DESC;

-- Q25 | The ledger, reconciled: calls by batch and status; the cap is the contract
SELECT batch_id, COUNT(*) AS calls, SUM(CASE WHEN http_status = 200 AND road_meters IS NOT NULL THEN 1 ELSE 0 END) AS routed,
       SUM(CASE WHEN http_status <> 200 OR road_meters IS NULL THEN 1 ELSE 0 END) AS failed,
       MIN(called_at) AS first_call, MAX(called_at) AS last_call
FROM col.route_ledger GROUP BY batch_id ORDER BY first_call;

-- Q26 | Every routed county: the rows behind the scatter
WITH r AS (
  SELECT fips, dest_sta_no, road_meters / 1609.344 AS road_miles, travel_seconds / 60.0 AS travel_min
  FROM col.route_ledger WHERE road_meters IS NOT NULL)
SELECT a.fips, a.county, a.state_abbr, a.veterans, ROUND(a.vamc_miles, 1) AS straight_miles, ROUND(r.road_miles, 1) AS road_miles,
       ROUND(r.road_miles / NULLIF(a.vamc_miles, 0), 3) AS ratio, ROUND(r.travel_min, 0) AS drive_minutes
FROM col.county_access a JOIN r ON r.fips = a.fips AND r.dest_sta_no = a.vamc_sta_no
ORDER BY a.vamc_miles;
