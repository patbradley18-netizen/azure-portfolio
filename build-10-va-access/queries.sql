-- Build #10: Can veterans reach the VA? Spatial T-SQL on the free db.
-- Pattern: CROSS APPLY (SELECT TOP 1 ... ORDER BY STDistance) = nearest-neighbour join; the spatial index serves it.
-- Distance = STDistance() in metres on WGS 84, divided by 1609.344 = straight-line miles. Not road miles.
-- "Care site" = VAMC, HCC, CBOC, OOS (fixed outpatient or inpatient care); mobile, Vet Centers, residential excluded.
-- Veterans = ACS 5-year 2023 B21001_002E (civilian veterans 18+), dataset acs5_2023_vet, already in col.measure.

-- Q18 | Nearest VA medical center and nearest VA care site for every county, with the county's veterans
WITH vets AS (
  SELECT fips, value AS veterans FROM col.measure WHERE dataset_id = 'acs5_2023_vet' AND code = 'B21001_002E'),
adults AS (
  SELECT fips, value AS adults FROM col.measure WHERE dataset_id = 'acs5_2023_vet' AND code = 'B21001_001E')
SELECT c.fips, c.name AS county, c.state_name, cty.state_abbr, c.pop2020, v.veterans,
       ROUND(100.0 * v.veterans / NULLIF(a.adults, 0), 2) AS vet_share,
       m.name AS nearest_vamc, m.state AS vamc_state, ROUND(m.miles, 1) AS vamc_miles,
       s.name AS nearest_site, s.kind AS site_kind, ROUND(s.miles, 1) AS site_miles, c.center_kind
FROM col.county_center c
JOIN col.county cty ON cty.fips = c.fips
JOIN vets v ON v.fips = c.fips
JOIN adults a ON a.fips = c.fips
CROSS APPLY (SELECT TOP 1 f.name, f.state, c.geo.STDistance(f.geo) / 1609.344 AS miles
             FROM col.facility f WHERE f.kind = 'VAMC' AND f.suspended = 'N' ORDER BY c.geo.STDistance(f.geo)) m
CROSS APPLY (SELECT TOP 1 f.name, f.kind, c.geo.STDistance(f.geo) / 1609.344 AS miles
             FROM col.facility f WHERE f.kind IN ('VAMC','HCC','CBOC','OOS') AND f.suspended = 'N' ORDER BY c.geo.STDistance(f.geo)) s
WHERE cty.state_abbr IS NOT NULL AND v.veterans IS NOT NULL
ORDER BY c.fips;

-- Q19 | Veteran-weighted mean distance to the nearest VA medical center and nearest care site, by state
WITH vets AS (
  SELECT fips, value AS veterans FROM col.measure WHERE dataset_id = 'acs5_2023_vet' AND code = 'B21001_002E'),
d AS (
  SELECT c.fips, cty.state_abbr, v.veterans, m.miles AS vamc_miles, s.miles AS site_miles
  FROM col.county_center c
  JOIN col.county cty ON cty.fips = c.fips
  JOIN vets v ON v.fips = c.fips
  CROSS APPLY (SELECT TOP 1 c.geo.STDistance(f.geo) / 1609.344 AS miles FROM col.facility f
               WHERE f.kind = 'VAMC' AND f.suspended = 'N' ORDER BY c.geo.STDistance(f.geo)) m
  CROSS APPLY (SELECT TOP 1 c.geo.STDistance(f.geo) / 1609.344 AS miles FROM col.facility f
               WHERE f.kind IN ('VAMC','HCC','CBOC','OOS') AND f.suspended = 'N' ORDER BY c.geo.STDistance(f.geo)) s
  WHERE cty.state_abbr IS NOT NULL AND v.veterans IS NOT NULL)
SELECT COALESCE(state_abbr, 'US') AS geo, COUNT(*) AS counties, SUM(veterans) AS veterans,
       ROUND(SUM(veterans * vamc_miles) / NULLIF(SUM(veterans), 0), 1) AS vamc_miles_weighted,
       ROUND(SUM(veterans * site_miles) / NULLIF(SUM(veterans), 0), 1) AS site_miles_weighted,
       ROUND(100.0 * SUM(CASE WHEN vamc_miles <= 30 THEN veterans ELSE 0 END) / NULLIF(SUM(veterans), 0), 1) AS pct_vets_vamc_within_30,
       ROUND(100.0 * SUM(CASE WHEN vamc_miles <= 60 THEN veterans ELSE 0 END) / NULLIF(SUM(veterans), 0), 1) AS pct_vets_vamc_within_60,
       ROUND(100.0 * SUM(CASE WHEN site_miles <= 30 THEN veterans ELSE 0 END) / NULLIF(SUM(veterans), 0), 1) AS pct_vets_site_within_30
FROM d
GROUP BY ROLLUP(state_abbr)
ORDER BY CASE WHEN state_abbr IS NULL THEN 0 ELSE 1 END, vamc_miles_weighted DESC;

-- Q20 | The 25 veteran-densest counties (vet share, >= 5,000 veterans) whose nearest VA medical center is beyond 60 miles
WITH vets AS (
  SELECT fips, MAX(CASE WHEN code = 'B21001_002E' THEN value END) AS veterans,
         MAX(CASE WHEN code = 'B21001_001E' THEN value END) AS adults
  FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips)
SELECT TOP 25 c.fips, c.name AS county, cty.state_abbr, v.veterans, ROUND(100.0 * v.veterans / NULLIF(v.adults, 0), 1) AS vet_share,
       m.name AS nearest_vamc, ROUND(m.miles, 1) AS vamc_miles, s.kind AS nearest_site_kind, ROUND(s.miles, 1) AS site_miles
FROM col.county_center c
JOIN col.county cty ON cty.fips = c.fips
JOIN vets v ON v.fips = c.fips
CROSS APPLY (SELECT TOP 1 f.name, c.geo.STDistance(f.geo) / 1609.344 AS miles FROM col.facility f
             WHERE f.kind = 'VAMC' AND f.suspended = 'N' ORDER BY c.geo.STDistance(f.geo)) m
CROSS APPLY (SELECT TOP 1 f.kind, c.geo.STDistance(f.geo) / 1609.344 AS miles FROM col.facility f
             WHERE f.kind IN ('VAMC','HCC','CBOC','OOS') AND f.suspended = 'N' ORDER BY c.geo.STDistance(f.geo)) s
WHERE cty.state_abbr IS NOT NULL AND v.veterans >= 5000 AND m.miles > 60
ORDER BY vet_share DESC;

-- Q21 | Distance bands: how many veterans live within 30, 30-60, 60-100, 100+ straight-line miles of a VA medical center and of any care site
WITH vets AS (
  SELECT fips, value AS veterans FROM col.measure WHERE dataset_id = 'acs5_2023_vet' AND code = 'B21001_002E'),
d AS (
  SELECT c.fips, v.veterans, m.miles AS vamc_miles, s.miles AS site_miles
  FROM col.county_center c
  JOIN col.county cty ON cty.fips = c.fips
  JOIN vets v ON v.fips = c.fips
  CROSS APPLY (SELECT TOP 1 c.geo.STDistance(f.geo) / 1609.344 AS miles FROM col.facility f
               WHERE f.kind = 'VAMC' AND f.suspended = 'N' ORDER BY c.geo.STDistance(f.geo)) m
  CROSS APPLY (SELECT TOP 1 c.geo.STDistance(f.geo) / 1609.344 AS miles FROM col.facility f
               WHERE f.kind IN ('VAMC','HCC','CBOC','OOS') AND f.suspended = 'N' ORDER BY c.geo.STDistance(f.geo)) s
  WHERE cty.state_abbr IS NOT NULL AND v.veterans IS NOT NULL),
bands AS (
  SELECT 'VAMC' AS target, CASE WHEN vamc_miles <= 30 THEN '0-30' WHEN vamc_miles <= 60 THEN '30-60' WHEN vamc_miles <= 100 THEN '60-100' ELSE '100+' END AS band,
         veterans, 1 AS counties FROM d
  UNION ALL
  SELECT 'care site', CASE WHEN site_miles <= 30 THEN '0-30' WHEN site_miles <= 60 THEN '30-60' WHEN site_miles <= 100 THEN '60-100' ELSE '100+' END,
         veterans, 1 FROM d)
SELECT target, band, SUM(counties) AS counties, SUM(veterans) AS veterans,
       ROUND(100.0 * SUM(veterans) / SUM(SUM(veterans)) OVER (PARTITION BY target), 1) AS pct_of_veterans
FROM bands
GROUP BY target, band
ORDER BY target, CASE band WHEN '0-30' THEN 1 WHEN '30-60' THEN 2 WHEN '60-100' THEN 3 ELSE 4 END;
