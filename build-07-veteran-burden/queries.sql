-- Build #7: the veteran burden cut. Schema col; datasets tsci_2026-05-12, acs5_2023 (shelter inputs), acs5_2023_vet (B21001).
-- Q numbers continue from build #6 (Q1–Q7) so page and README references stay unambiguous.

-- Q8 | What share of each county's adult civilian population are veterans, and how is that distributed?
WITH v AS (
  SELECT fips,
         MAX(CASE WHEN code='B21001_001E' THEN value END) AS adults,
         MAX(CASE WHEN code='B21001_002E' THEN value END) AS veterans
  FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips)
SELECT band, COUNT(*) AS counties, SUM(adults) AS adults, SUM(veterans) AS veterans,
       ROUND(100.0 * SUM(veterans) / SUM(adults), 1) AS veteran_share_pct
FROM (SELECT *, CASE WHEN 100.0*veterans/NULLIF(adults,0) >= 12 THEN '4. 12%+' WHEN 100.0*veterans/NULLIF(adults,0) >= 8 THEN '3. 8-12%'
                      WHEN 100.0*veterans/NULLIF(adults,0) >= 5 THEN '2. 5-8%' ELSE '1. under 5%' END AS band FROM v WHERE adults > 0) b
GROUP BY band ORDER BY band;

-- Q9 | Do counties with a larger veteran share carry heavier shelter burden? Population-weighted burden by veteran-share quintile
WITH v AS (
  SELECT fips,
         MAX(CASE WHEN code='B21001_001E' THEN value END) AS adults,
         MAX(CASE WHEN code='B21001_002E' THEN value END) AS veterans
  FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips),
t AS (
  SELECT fips,
         MAX(CASE WHEN code='rb' THEN value END) AS renter_burden, MAX(CASE WHEN code='ob' THEN value END) AS owner_burden,
         MAX(CASE WHEN code='i' THEN value END) AS income, MAX(CASE WHEN code='r' THEN value END) AS rent,
         MAX(CASE WHEN code='hv' THEN value END) AS home_value
  FROM col.measure WHERE dataset_id = 'tsci_2026-05-12' GROUP BY fips),
p AS (SELECT fips, value AS pop FROM col.measure WHERE dataset_id = 'acs5_2023' AND code = 'B01003_001E'),
j AS (
  SELECT v.fips, 100.0*v.veterans/NULLIF(v.adults,0) AS vet_share, t.renter_burden, t.owner_burden, t.income, t.rent, t.home_value, p.pop,
         NTILE(5) OVER (ORDER BY 100.0*v.veterans/NULLIF(v.adults,0)) AS quintile
  FROM v JOIN t ON t.fips = v.fips JOIN p ON p.fips = v.fips
  WHERE v.adults > 0 AND t.renter_burden IS NOT NULL AND t.owner_burden IS NOT NULL)
SELECT quintile, COUNT(*) AS counties, ROUND(MIN(vet_share),1) AS vet_share_min, ROUND(MAX(vet_share),1) AS vet_share_max,
       ROUND(SUM(renter_burden*pop)/SUM(pop),1) AS renter_burden_pct, ROUND(SUM(owner_burden*pop)/SUM(pop),1) AS owner_burden_pct,
       ROUND(SUM(income*pop)/SUM(pop),0) AS median_income, ROUND(SUM(rent*pop)/SUM(pop),0) AS rent, ROUND(SUM(home_value*pop)/SUM(pop),0) AS home_value,
       SUM(pop) AS population
FROM j GROUP BY quintile ORDER BY quintile;

-- Q10 | The 20 counties with the highest veteran share (min 10,000 adults): who are they and what do they pay?
WITH v AS (
  SELECT fips,
         MAX(CASE WHEN code='B21001_001E' THEN value END) AS adults,
         MAX(CASE WHEN code='B21001_002E' THEN value END) AS veterans
  FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips),
t AS (
  SELECT fips, MAX(CASE WHEN code='rb' THEN value END) AS renter_burden, MAX(CASE WHEN code='ob' THEN value END) AS owner_burden,
         MAX(CASE WHEN code='i' THEN value END) AS income, MAX(CASE WHEN code='ti' THEN value END) AS tsci
  FROM col.measure WHERE dataset_id = 'tsci_2026-05-12' GROUP BY fips)
SELECT TOP 20 c.name, v.adults, v.veterans, ROUND(100.0*v.veterans/v.adults,1) AS vet_share_pct,
       t.renter_burden AS renter_burden_pct, t.owner_burden AS owner_burden_pct, t.income AS median_income, t.tsci
FROM v JOIN col.county c ON c.fips = v.fips JOIN t ON t.fips = v.fips
WHERE v.adults >= 10000
ORDER BY 100.0*v.veterans/v.adults DESC;

-- Q11 | The honest check: veterans skew older. Age structure of veteran vs nonveteran adults, nationally, from the same table
WITH a AS (
  SELECT code, SUM(value) AS n FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY code),
bands AS (
  SELECT '18-34' AS age_band, 1 AS ord, 'B21001_007E' AS mt, 'B21001_008E' AS mv, 'B21001_025E' AS ft, 'B21001_026E' AS fv UNION ALL
  SELECT '35-54', 2, 'B21001_010E', 'B21001_011E', 'B21001_028E', 'B21001_029E' UNION ALL
  SELECT '55-64', 3, 'B21001_013E', 'B21001_014E', 'B21001_031E', 'B21001_032E' UNION ALL
  SELECT '65-74', 4, 'B21001_016E', 'B21001_017E', 'B21001_034E', 'B21001_035E' UNION ALL
  SELECT '75+',   5, 'B21001_019E', 'B21001_020E', 'B21001_037E', 'B21001_038E'),
x AS (
  SELECT b.age_band, b.ord,
         (SELECT n FROM a WHERE a.code=b.mv) + (SELECT n FROM a WHERE a.code=b.fv) AS veterans,
         (SELECT n FROM a WHERE a.code=b.mt) + (SELECT n FROM a WHERE a.code=b.ft)
           - (SELECT n FROM a WHERE a.code=b.mv) - (SELECT n FROM a WHERE a.code=b.fv) AS nonveterans
  FROM bands b)
SELECT age_band, veterans, nonveterans,
       ROUND(100.0 * veterans / SUM(veterans) OVER (), 1) AS pct_of_veterans,
       ROUND(100.0 * nonveterans / SUM(nonveterans) OVER (), 1) AS pct_of_nonveterans
FROM x ORDER BY ord;

-- Q12 | Within the oldest-skewing counties, does veteran share still track burden? Burden by veteran-share tercile inside each 65+ share tercile
WITH v AS (
  SELECT fips,
         MAX(CASE WHEN code='B21001_001E' THEN value END) AS adults,
         MAX(CASE WHEN code='B21001_002E' THEN value END) AS veterans,
         SUM(CASE WHEN code IN ('B21001_016E','B21001_019E','B21001_034E','B21001_037E') THEN value ELSE 0 END) AS adults_65plus
  FROM col.measure WHERE dataset_id = 'acs5_2023_vet' GROUP BY fips),
t AS (
  SELECT fips, MAX(CASE WHEN code='rb' THEN value END) AS renter_burden, MAX(CASE WHEN code='ob' THEN value END) AS owner_burden
  FROM col.measure WHERE dataset_id = 'tsci_2026-05-12' GROUP BY fips),
p AS (SELECT fips, value AS pop FROM col.measure WHERE dataset_id = 'acs5_2023' AND code = 'B01003_001E'),
j AS (
  SELECT v.fips, 100.0*v.veterans/NULLIF(v.adults,0) AS vet_share, 100.0*v.adults_65plus/NULLIF(v.adults,0) AS share_65plus,
         t.renter_burden, t.owner_burden, p.pop
  FROM v JOIN t ON t.fips = v.fips JOIN p ON p.fips = v.fips
  WHERE v.adults > 0 AND t.renter_burden IS NOT NULL AND t.owner_burden IS NOT NULL),
k AS (
  SELECT *, NTILE(3) OVER (ORDER BY share_65plus) AS age_tercile FROM j),
m AS (
  SELECT *, NTILE(3) OVER (PARTITION BY age_tercile ORDER BY vet_share) AS vet_tercile FROM k)
SELECT age_tercile, vet_tercile, COUNT(*) AS counties, ROUND(AVG(share_65plus),1) AS avg_share_65plus, ROUND(AVG(vet_share),1) AS avg_vet_share,
       ROUND(SUM(renter_burden*pop)/SUM(pop),1) AS renter_burden_pct, ROUND(SUM(owner_burden*pop)/SUM(pop),1) AS owner_burden_pct
FROM m GROUP BY age_tercile, vet_tercile ORDER BY age_tercile, vet_tercile;
