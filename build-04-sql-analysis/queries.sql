-- Build #4: the queries a Business Analyst writes against builds #1 and #2.
-- Each block starts with the business question. Runner splits on the "-- Q" markers.
-- Database: aid (free Azure SQL). Schemas: bls (build #2), dbo (build #1). Entra sign-in; no password.

-- Q1 | Veteran vs nonveteran unemployment gap by year: when has it favored veterans, and by how much?
WITH yr AS (
  SELECT YEAR(period) AS yr, series_id, AVG(value) AS avg_rate
  FROM bls.observations
  WHERE series_id IN ('LNU04049526','LNU04049601')
  GROUP BY YEAR(period), series_id)
SELECT v.yr,
       ROUND(v.avg_rate,1) AS veterans,
       ROUND(n.avg_rate,1) AS nonveterans,
       ROUND(v.avg_rate - n.avg_rate,1) AS gap_pts,
       CASE WHEN v.avg_rate < n.avg_rate THEN 'veterans lower' ELSE 'veterans higher' END AS who_is_lower
FROM yr v JOIN yr n ON n.yr = v.yr AND n.series_id = 'LNU04049601'
WHERE v.series_id = 'LNU04049526'
ORDER BY v.yr;

-- Q2 | Gulf War-era II vs all veterans: how big was the post-2008 spike, and how long did it take to close?
WITH g AS (
  SELECT period, value AS gw2 FROM bls.observations WHERE series_id = 'LNU04066408'),
     a AS (
  SELECT period, value AS all_vets FROM bls.observations WHERE series_id = 'LNU04049526'),
     j AS (
  SELECT g.period, g.gw2, a.all_vets, g.gw2 - a.all_vets AS excess FROM g JOIN a ON a.period = g.period),
     pk AS (
  SELECT TOP 1 period AS peak_period, gw2 AS peak_gw2, all_vets AS peak_all, excess AS peak_excess
  FROM j WHERE period >= '2008-01-01' ORDER BY gw2 DESC)
SELECT pk.peak_period, pk.peak_gw2, pk.peak_all, ROUND(pk.peak_excess,1) AS peak_excess_pts,
       (SELECT MIN(period) FROM j WHERE period > pk.peak_period AND excess <= 1.0) AS first_month_within_1pt,
       DATEDIFF(month, pk.peak_period, (SELECT MIN(period) FROM j WHERE period > pk.peak_period AND excess <= 1.0)) AS months_to_close_to_1pt,
       (SELECT ROUND(AVG(excess),1) FROM j WHERE period >= DATEADD(month,-12,(SELECT MAX(period) FROM j))) AS excess_last_12m
FROM pk;

-- Q3 | Same-month year-over-year change (the honest way to read NSA data): latest reading vs the same month last year, every series.
WITH latest AS (SELECT MAX(period) AS p FROM bls.observations)
SELECT s.series_id, s.measure, s.population,
       o.period AS latest_period, o.value AS latest_value,
       y.value AS same_month_last_year,
       ROUND(o.value - y.value,1) AS yoy_change_pts
FROM bls.series s
JOIN latest l ON 1=1
JOIN bls.observations o ON o.series_id = s.series_id AND o.period = l.p
LEFT JOIN bls.observations y ON y.series_id = s.series_id AND y.period = DATEADD(year,-1,l.p)
ORDER BY s.measure, s.population;

-- Q4 | Recessions in the data: for 2008-10 and 2020, the peak month and months back to the pre-recession level, per group.
WITH ep AS (
  SELECT 'Great Recession' AS episode, CAST('2007-12-01' AS date) AS pre_month, CAST('2008-01-01' AS date) AS win_start, CAST('2012-12-01' AS date) AS win_end
  UNION ALL
  SELECT 'COVID-19', '2020-02-01', '2020-03-01', '2023-12-01'),
     base AS (
  SELECT e.episode, o.series_id, o.value AS pre_value
  FROM ep e JOIN bls.observations o ON o.period = e.pre_month
  WHERE o.series_id IN ('LNU04049526','LNU04049601','LNU04066408')),
     peak AS (
  SELECT e.episode, o.series_id, MAX(o.value) AS peak_value
  FROM ep e JOIN bls.observations o ON o.period BETWEEN e.win_start AND e.win_end
  WHERE o.series_id IN ('LNU04049526','LNU04049601','LNU04066408')
  GROUP BY e.episode, o.series_id),
     peak_month AS (
  SELECT p.episode, p.series_id, p.peak_value, MIN(o.period) AS peak_period
  FROM peak p JOIN ep e ON e.episode = p.episode
  JOIN bls.observations o ON o.series_id = p.series_id AND o.value = p.peak_value AND o.period BETWEEN e.win_start AND e.win_end
  GROUP BY p.episode, p.series_id, p.peak_value),
     recov AS (
  SELECT pm.episode, pm.series_id, MIN(o.period) AS recovered_period
  FROM peak_month pm JOIN base b ON b.episode = pm.episode AND b.series_id = pm.series_id
  JOIN bls.observations o ON o.series_id = pm.series_id AND o.period > pm.peak_period AND o.value <= b.pre_value
  GROUP BY pm.episode, pm.series_id)
SELECT pm.episode, s.population, b.pre_value, pm.peak_period, pm.peak_value,
       ROUND(pm.peak_value - b.pre_value,1) AS rise_pts,
       r.recovered_period, DATEDIFF(month, pm.peak_period, r.recovered_period) AS months_peak_to_recovery
FROM peak_month pm
JOIN base b ON b.episode = pm.episode AND b.series_id = pm.series_id
JOIN bls.series s ON s.series_id = pm.series_id
LEFT JOIN recov r ON r.episode = pm.episode AND r.series_id = pm.series_id
ORDER BY pm.episode, s.population;

-- Q5 | Producers vs amplifiers: which account categories write the templates, and which do the retweeting?
WITH prod AS (
  SELECT top_category AS category, COUNT(*) AS templates_written
  FROM dbo.templates GROUP BY top_category),
     amp AS (
  SELECT source_category AS category, SUM(weight) AS retweets_sent, COUNT(DISTINCT source) AS retweeting_accounts
  FROM dbo.edges GROUP BY source_category)
SELECT COALESCE(p.category, a.category) AS category,
       COALESCE(p.templates_written,0) AS templates_written,
       COALESCE(a.retweets_sent,0) AS retweets_sent,
       COALESCE(a.retweeting_accounts,0) AS retweeting_accounts,
       CASE WHEN COALESCE(a.retweets_sent,0) = 0 THEN NULL
            ELSE ROUND(1.0 * COALESCE(p.templates_written,0) / a.retweets_sent, 3) END AS templates_per_retweet
FROM prod p FULL OUTER JOIN amp a ON a.category = p.category
ORDER BY retweets_sent DESC;

-- Q6 | Template lifetime: what share of each category's templates were one-day blasts, and how long did the rest live?
SELECT t.top_category AS category,
       COUNT(*) AS templates,
       SUM(CASE WHEN b.days_active = 1 THEN 1 ELSE 0 END) AS one_day_blasts,
       ROUND(100.0 * SUM(CASE WHEN b.days_active = 1 THEN 1 ELSE 0 END) / COUNT(*),1) AS blast_share_pct,
       MAX(b.days_active) AS longest_days,
       ROUND(AVG(CASE WHEN b.days_active > 1 THEN 1.0 * b.days_active END),1) AS avg_days_when_multi_day
FROM dbo.templates t JOIN dbo.bursts b ON b.body = t.body
GROUP BY t.top_category
ORDER BY templates DESC;

-- Q7 | Data quality: does each weekly function run reproduce the same template set? (Fills in as runs accumulate.)
SELECT run_id, MIN(run_time) AS run_time, COUNT(*) AS rows_written,
       MAX(n_authors) AS max_authors, SUM(n_tweets) AS template_posts,
       MAX(english_originals) AS english_originals,
       SUM(CASE WHEN key_phrases IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_key_phrases
FROM dbo.template_runs
GROUP BY run_id
ORDER BY run_time;