-- Build #6: Cost-of-Living warehouse, schema col. Each block is headed "-- Qn | question"; run_analysis.py splits on it.
-- Datasets: tsci_2026-05-12 (snapshot), tcbi_d1..d5 (snapshots), acs5_2023 (raw Census pull, same vintage TSCI cites).

-- Q1 | Does the TSCI snapshot carry the raw Census inputs unchanged? (reconciliation, five fields)
WITH snap AS (
  SELECT fips, code, value FROM col.measure WHERE dataset_id = 'tsci_2026-05-12' AND code IN ('r','hv','oc','i','pop')),
raw AS (
  SELECT fips, CASE code WHEN 'B25064_001E' THEN 'r' WHEN 'B25077_001E' THEN 'hv' WHEN 'B25088_002E' THEN 'oc'
                         WHEN 'B19013_001E' THEN 'i' WHEN 'B01003_001E' THEN 'pop' END AS code, value, text
  FROM col.measure WHERE dataset_id = 'acs5_2023'),
cmp AS (
  SELECT COALESCE(s.fips, r.fips) AS fips, COALESCE(s.code, r.code) AS code, s.value AS snap_value, r.value AS raw_value, r.text AS raw_flag,
         CASE WHEN s.value IS NULL AND r.value IS NULL THEN 'both null'
              WHEN s.value IS NULL THEN 'snapshot missing'
              WHEN r.value IS NULL THEN 'raw suppressed, snapshot filled'
              WHEN ABS(s.value - r.value) < 0.5 THEN 'match'
              ELSE 'differs' END AS status
  FROM snap s FULL OUTER JOIN raw r ON r.fips = s.fips AND r.code = s.code)
SELECT code, status, COUNT(*) AS counties, MIN(fips) AS example_fips
FROM cmp GROUP BY code, status ORDER BY code, status;

-- Q2 | Where the snapshot and raw source differ, which counties and by how much?
WITH snap AS (
  SELECT fips, code, value FROM col.measure WHERE dataset_id = 'tsci_2026-05-12' AND code IN ('r','hv','oc','i','pop')),
raw AS (
  SELECT fips, CASE code WHEN 'B25064_001E' THEN 'r' WHEN 'B25077_001E' THEN 'hv' WHEN 'B25088_002E' THEN 'oc'
                         WHEN 'B19013_001E' THEN 'i' WHEN 'B01003_001E' THEN 'pop' END AS code, value, text
  FROM col.measure WHERE dataset_id = 'acs5_2023')
SELECT TOP 25 c.name, s.code, s.value AS snapshot, r.value AS census, r.text AS census_flag, s.value - r.value AS diff
FROM snap s JOIN raw r ON r.fips = s.fips AND r.code = s.code JOIN col.county c ON c.fips = s.fips
WHERE r.value IS NULL OR ABS(s.value - r.value) >= 0.5
ORDER BY ABS(COALESCE(s.value - r.value, s.value)) DESC;

-- Q3 | Does the snapshot's own arithmetic hold? Recompute nut and burden from inputs and compare to the stored values
WITH w AS (
  SELECT fips,
         MAX(CASE WHEN code='r' THEN value END) AS r, MAX(CASE WHEN code='oc' THEN value END) AS oc,
         MAX(CASE WHEN code='cc_m' THEN value END) AS cc_m, MAX(CASE WHEN code='ho' THEN value END) AS ho,
         MAX(CASE WHEN code='re' THEN value END) AS re, MAX(CASE WHEN code='i' THEN value END) AS i,
         MAX(CASE WHEN code='hv' THEN value END) AS hv,
         MAX(CASE WHEN code='on' THEN value END) AS on_stored, MAX(CASE WHEN code='rn' THEN value END) AS rn_stored,
         MAX(CASE WHEN code='ob' THEN value END) AS ob_stored, MAX(CASE WHEN code='rb' THEN value END) AS rb_stored,
         MAX(CASE WHEN code='p2i' THEN value END) AS p2i_stored
  FROM col.measure WHERE dataset_id = 'tsci_2026-05-12' GROUP BY fips),
chk AS (
  SELECT fips,
         CASE WHEN r IS NULL OR oc IS NULL OR i IS NULL OR hv IS NULL THEN 0 ELSE 1 END AS computable,
         CASE WHEN ABS((oc + cc_m + ho) - on_stored) <= 1 THEN 1 ELSE 0 END AS on_ok,
         CASE WHEN ABS((r + cc_m + re) - rn_stored) <= 1 THEN 1 ELSE 0 END AS rn_ok,
         CASE WHEN ABS(ROUND(on_stored*12.0/NULLIF(i,0)*100,1) - ob_stored) <= 0.15 THEN 1 ELSE 0 END AS ob_ok,
         CASE WHEN ABS(ROUND(rn_stored*12.0/NULLIF(i,0)*100,1) - rb_stored) <= 0.15 THEN 1 ELSE 0 END AS rb_ok,
         CASE WHEN ABS(ROUND(hv/NULLIF(i,0),2) - p2i_stored) <= 0.015 THEN 1 ELSE 0 END AS p2i_ok
  FROM w)
SELECT COUNT(*) AS counties, SUM(computable) AS computable, COUNT(*) - SUM(computable) AS suppressed_inputs,
       SUM(on_ok) AS owner_nut_ok, SUM(rn_ok) AS renter_nut_ok, SUM(ob_ok) AS owner_burden_ok,
       SUM(rb_ok) AS renter_burden_ok, SUM(p2i_ok) AS price_to_income_ok,
       SUM(computable) - SUM(computable*on_ok*rn_ok*ob_ok*rb_ok*p2i_ok) AS computable_with_any_mismatch
FROM chk;

-- Q4 | Which states carry proxy-filled, suppressed, or missing inputs? (provenance, not values)
-- TCBI D1 pump is proxy-by-design for every county (state baseline x rent ratio), so it is not a flag here.
WITH flags AS (
  SELECT c.state_abbr, c.fips,
         MAX(CASE WHEN m.dataset_id='tsci_2026-05-12' AND m.code='cc_p' AND m.text <> 'LIVE' THEN 1 ELSE 0 END) AS childcare_proxy,
         MAX(CASE WHEN m.dataset_id='acs5_2023' AND m.text IS NOT NULL THEN 1 ELSE 0 END) AS census_suppressed,
         1 - MAX(CASE WHEN m.dataset_id='tcbi_d5_2026-M04' THEN 1 ELSE 0 END) AS missing_from_tcbi
  FROM col.county c LEFT JOIN col.measure m ON m.fips = c.fips
  WHERE c.state_abbr IS NOT NULL
  GROUP BY c.state_abbr, c.fips)
SELECT TOP 15 state_abbr, COUNT(*) AS counties, SUM(childcare_proxy) AS childcare_proxy, SUM(census_suppressed) AS census_suppressed, SUM(missing_from_tcbi) AS missing_from_tcbi,
       ROUND(100.0 * SUM(CASE WHEN childcare_proxy + census_suppressed + missing_from_tcbi > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_any_flag
FROM flags GROUP BY state_abbr HAVING SUM(childcare_proxy + census_suppressed + missing_from_tcbi) > 0 ORDER BY pct_any_flag DESC, counties DESC;

-- Q5 | Renter burden: where does rent + childcare + insurance exceed 30% of median income, and how many people live there?
WITH w AS (
  SELECT m.fips, c.name, c.state_abbr,
         MAX(CASE WHEN code='rb' THEN value END) AS renter_burden_pct,
         MAX(CASE WHEN code='ob' THEN value END) AS owner_burden_pct,
         MAX(CASE WHEN code='pop' THEN value END) AS pop,
         MAX(CASE WHEN code='i' THEN value END) AS income
  FROM col.measure m JOIN col.county c ON c.fips = m.fips
  WHERE dataset_id = 'tsci_2026-05-12' GROUP BY m.fips, c.name, c.state_abbr)
SELECT band, COUNT(*) AS counties, SUM(pop) AS population, ROUND(100.0 * SUM(pop) / SUM(SUM(pop)) OVER (), 1) AS pct_of_population,
       ROUND(AVG(income), 0) AS avg_median_income
FROM (SELECT *, CASE WHEN renter_burden_pct >= 50 THEN '4. 50%+ (severe)' WHEN renter_burden_pct >= 40 THEN '3. 40-49%'
                      WHEN renter_burden_pct >= 30 THEN '2. 30-39% (burdened)' ELSE '1. under 30%' END AS band FROM w WHERE renter_burden_pct IS NOT NULL) b
GROUP BY band ORDER BY band;

-- Q6 | Which states carry the heaviest shelter burden, weighted by the raw Census population rather than the snapshot's?
-- (Cross-dataset join: TSCI burdens x acs5_2023 population. The veteran cut needs a state-level veteran population table;
--  that is the next load, not something this query can pretend to have.)
SELECT TOP 15 c.state_abbr, COUNT(*) AS counties,
       ROUND(SUM(rb.value * pop.value) / NULLIF(SUM(pop.value),0), 1) AS pop_weighted_renter_burden_pct,
       ROUND(SUM(ob.value * pop.value) / NULLIF(SUM(pop.value),0), 1) AS pop_weighted_owner_burden_pct,
       ROUND(SUM(ti.value * pop.value) / NULLIF(SUM(pop.value),0), 1) AS pop_weighted_tsci
FROM col.county c
JOIN col.measure rb  ON rb.fips = c.fips AND rb.dataset_id = 'tsci_2026-05-12' AND rb.code = 'rb'
JOIN col.measure ob  ON ob.fips = c.fips AND ob.dataset_id = 'tsci_2026-05-12' AND ob.code = 'ob'
JOIN col.measure ti  ON ti.fips = c.fips AND ti.dataset_id = 'tsci_2026-05-12' AND ti.code = 'ti'
JOIN col.measure pop ON pop.fips = c.fips AND pop.dataset_id = 'acs5_2023' AND pop.code = 'B01003_001E'
WHERE c.state_abbr IS NOT NULL
GROUP BY c.state_abbr ORDER BY pop_weighted_renter_burden_pct DESC;

-- Q7 | Warehouse inventory: what is loaded, from where, with what vintage
SELECT d.dataset_id, d.tool, d.vintage, d.source_file, d.loaded_at, COUNT(DISTINCT m.code) AS metrics, COUNT(DISTINCT m.fips) AS counties, COUNT(*) AS rows_
FROM col.dataset d JOIN col.measure m ON m.dataset_id = d.dataset_id
GROUP BY d.dataset_id, d.tool, d.vintage, d.source_file, d.loaded_at ORDER BY d.tool, d.dataset_id;
