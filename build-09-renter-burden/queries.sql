-- Build #9: the right outcome. Schema col; Q numbers continue from build #8 (Q13–Q14).
-- B25070: renter-occupied units by gross rent as % of household income. Burdened = 30%+ (codes 007-010); severe = 50%+ (010);
-- denominator = total (001) minus "not computed" (011: no cash rent or zero/negative income). Getting the denominator right IS the lesson.

-- Q15 | From the bands to a rate: share of renter households cost-burdened (30%+) and severely burdened (50%+), nationally and by state
WITH b AS (
  SELECT m.fips, c.state_abbr,
         MAX(CASE WHEN code='B25070_001E' THEN value END) AS total,
         MAX(CASE WHEN code='B25070_011E' THEN value END) AS not_computed,
         SUM(CASE WHEN code IN ('B25070_007E','B25070_008E','B25070_009E','B25070_010E') THEN value ELSE 0 END) AS burdened,
         MAX(CASE WHEN code='B25070_010E' THEN value END) AS severe
  FROM col.measure m JOIN col.county c ON c.fips = m.fips
  WHERE dataset_id = 'acs5_2023_rentburden' GROUP BY m.fips, c.state_abbr)
SELECT COALESCE(state_abbr, 'US') AS geo, COUNT(*) AS counties, SUM(total) AS renter_households, SUM(not_computed) AS not_computed,
       ROUND(100.0*SUM(burdened)/NULLIF(SUM(total)-SUM(not_computed),0),1) AS burdened_30plus_pct,
       ROUND(100.0*SUM(severe)/NULLIF(SUM(total)-SUM(not_computed),0),1) AS severe_50plus_pct,
       ROUND(100.0*SUM(burdened)/NULLIF(SUM(total),0),1) AS burdened_wrong_denominator_pct
FROM b WHERE state_abbr IS NOT NULL
GROUP BY ROLLUP(state_abbr)
ORDER BY CASE WHEN state_abbr IS NULL THEN 0 ELSE 1 END, burdened_30plus_pct DESC;

-- Q16 | Renter-household cost burden by veteran-share quintile (the build #7 question with the right outcome)
WITH v AS (
  SELECT fips, MAX(CASE WHEN code='B21001_001E' THEN value END) AS adults, MAX(CASE WHEN code='B21001_002E' THEN value END) AS veterans
  FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips),
b AS (
  SELECT fips, MAX(CASE WHEN code='B25070_001E' THEN value END) - MAX(CASE WHEN code='B25070_011E' THEN value END) AS computed,
         SUM(CASE WHEN code IN ('B25070_007E','B25070_008E','B25070_009E','B25070_010E') THEN value ELSE 0 END) AS burdened,
         MAX(CASE WHEN code='B25070_010E' THEN value END) AS severe
  FROM col.measure WHERE dataset_id = 'acs5_2023_rentburden' GROUP BY fips),
j AS (
  SELECT v.fips, 100.0*v.veterans/NULLIF(v.adults,0) AS vet_share, b.computed, b.burdened, b.severe,
         NTILE(5) OVER (ORDER BY 100.0*v.veterans/NULLIF(v.adults,0)) AS quintile
  FROM v JOIN b ON b.fips = v.fips WHERE v.adults > 0 AND b.computed > 0)
SELECT quintile, COUNT(*) AS counties, ROUND(MIN(vet_share),1) AS vet_share_min, ROUND(MAX(vet_share),1) AS vet_share_max,
       SUM(computed) AS renter_households, ROUND(100.0*SUM(burdened)/SUM(computed),1) AS burdened_30plus_pct, ROUND(100.0*SUM(severe)/SUM(computed),1) AS severe_50plus_pct
FROM j GROUP BY quintile ORDER BY quintile;

-- Q17 | Feature table v2: renter-household burden as the outcome, renter households as the weight, state for fixed effects
WITH v AS (
  SELECT fips, MAX(CASE WHEN code='B21001_001E' THEN value END) AS adults, MAX(CASE WHEN code='B21001_002E' THEN value END) AS veterans,
         SUM(CASE WHEN code IN ('B21001_016E','B21001_019E','B21001_034E','B21001_037E') THEN value ELSE 0 END) AS adults_65plus
  FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips),
h AS (
  SELECT fips, MAX(CASE WHEN code='B25003_001E' THEN value END) AS households, MAX(CASE WHEN code='B25003_002E' THEN value END) AS owners
  FROM col.measure WHERE dataset_id = 'acs5_2023_tenure' GROUP BY fips),
b AS (
  SELECT fips, MAX(CASE WHEN code='B25070_001E' THEN value END) - MAX(CASE WHEN code='B25070_011E' THEN value END) AS renters_computed,
         SUM(CASE WHEN code IN ('B25070_007E','B25070_008E','B25070_009E','B25070_010E') THEN value ELSE 0 END) AS burdened,
         MAX(CASE WHEN code='B25070_010E' THEN value END) AS severe
  FROM col.measure WHERE dataset_id = 'acs5_2023_rentburden' GROUP BY fips),
a AS (
  SELECT fips, MAX(CASE WHEN code='B19013_001E' THEN value END) AS income, MAX(CASE WHEN code='B01003_001E' THEN value END) AS pop
  FROM col.measure WHERE dataset_id = 'acs5_2023' GROUP BY fips),
t AS (SELECT fips, value AS tsci_renter_burden FROM col.measure WHERE dataset_id = 'tsci_2026-05-12' AND code = 'rb')
SELECT c.fips, c.state_abbr,
       ROUND(100.0*b.burdened/b.renters_computed, 3) AS burdened_30plus_pct,
       ROUND(100.0*b.severe/b.renters_computed, 3) AS severe_50plus_pct,
       t.tsci_renter_burden,
       ROUND(100.0*v.veterans/v.adults, 3) AS vet_share,
       ROUND(100.0*v.adults_65plus/v.adults, 3) AS share_65plus,
       ROUND(100.0*h.owners/h.households, 3) AS owner_share,
       a.income, a.pop, b.renters_computed AS renter_households
FROM col.county c
JOIN v ON v.fips = c.fips JOIN h ON h.fips = c.fips JOIN b ON b.fips = c.fips JOIN a ON a.fips = c.fips LEFT JOIN t ON t.fips = c.fips
WHERE c.state_abbr IS NOT NULL AND v.adults > 0 AND h.households > 0 AND b.renters_computed >= 100 AND a.income IS NOT NULL AND a.pop > 0
ORDER BY c.fips;
