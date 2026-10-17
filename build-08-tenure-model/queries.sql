-- Build #8: tenure and a model. Schema col; Q numbers continue from build #7 (Q8–Q12).

-- Q13 | Does ownership rise with veteran share? Owner-occupied share of households by veteran-share quintile
WITH v AS (
  SELECT fips, MAX(CASE WHEN code='B21001_001E' THEN value END) AS adults, MAX(CASE WHEN code='B21001_002E' THEN value END) AS veterans
  FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips),
h AS (
  SELECT fips, MAX(CASE WHEN code='B25003_001E' THEN value END) AS households, MAX(CASE WHEN code='B25003_002E' THEN value END) AS owners
  FROM col.measure WHERE dataset_id = 'acs5_2023_tenure' GROUP BY fips),
j AS (
  SELECT v.fips, 100.0*v.veterans/NULLIF(v.adults,0) AS vet_share, h.households, h.owners,
         NTILE(5) OVER (ORDER BY 100.0*v.veterans/NULLIF(v.adults,0)) AS quintile
  FROM v JOIN h ON h.fips = v.fips WHERE v.adults > 0 AND h.households > 0)
SELECT quintile, COUNT(*) AS counties, ROUND(MIN(vet_share),1) AS vet_share_min, ROUND(MAX(vet_share),1) AS vet_share_max,
       SUM(households) AS households, ROUND(100.0*SUM(owners)/SUM(households),1) AS owner_share_pct
FROM j GROUP BY quintile ORDER BY quintile;

-- Q14 | The county table the model reads: one row per county with outcome, treatment and controls
WITH v AS (
  SELECT fips, MAX(CASE WHEN code='B21001_001E' THEN value END) AS adults, MAX(CASE WHEN code='B21001_002E' THEN value END) AS veterans,
         SUM(CASE WHEN code IN ('B21001_016E','B21001_019E','B21001_034E','B21001_037E') THEN value ELSE 0 END) AS adults_65plus
  FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips),
h AS (
  SELECT fips, MAX(CASE WHEN code='B25003_001E' THEN value END) AS households, MAX(CASE WHEN code='B25003_002E' THEN value END) AS owners
  FROM col.measure WHERE dataset_id = 'acs5_2023_tenure' GROUP BY fips),
t AS (
  SELECT fips, MAX(CASE WHEN code='rb' THEN value END) AS renter_burden, MAX(CASE WHEN code='ob' THEN value END) AS owner_burden
  FROM col.measure WHERE dataset_id = 'tsci_2026-05-12' GROUP BY fips),
a AS (
  SELECT fips, MAX(CASE WHEN code='B19013_001E' THEN value END) AS income, MAX(CASE WHEN code='B01003_001E' THEN value END) AS pop
  FROM col.measure WHERE dataset_id = 'acs5_2023' GROUP BY fips)
SELECT c.fips, c.state_abbr,
       t.renter_burden, t.owner_burden,
       ROUND(100.0*v.veterans/v.adults, 3) AS vet_share,
       ROUND(100.0*v.adults_65plus/v.adults, 3) AS share_65plus,
       ROUND(100.0*h.owners/h.households, 3) AS owner_share,
       a.income, a.pop
FROM col.county c
JOIN v ON v.fips = c.fips JOIN h ON h.fips = c.fips JOIN t ON t.fips = c.fips JOIN a ON a.fips = c.fips
WHERE v.adults > 0 AND h.households > 0 AND t.renter_burden IS NOT NULL AND t.owner_burden IS NOT NULL AND a.income IS NOT NULL AND a.pop > 0
ORDER BY c.fips;
