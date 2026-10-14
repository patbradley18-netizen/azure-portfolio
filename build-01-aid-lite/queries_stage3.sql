-- Stage 3 analyst questions, T-SQL against the free Azure SQL db "aid". Entra sign-in, no password.

-- 1. Hubs: who got retweeted the most, inside vs outside the dataset?
SELECT TOP 20 target,
       SUM(weight) AS retweets,
       COUNT(DISTINCT source) AS distinct_retweeters,
       MAX(kind) AS kind
FROM dbo.edges
GROUP BY target
ORDER BY retweets DESC;

-- 2. Brokers: who retweeted the most distinct handles?
SELECT TOP 20 source, source_category,
       COUNT(DISTINCT target) AS distinct_handles,
       SUM(weight) AS retweets
FROM dbo.edges
GROUP BY source, source_category
ORDER BY distinct_handles DESC;

-- 3. Cross-faction amplification: which category retweets which?
SELECT e.source_category, h.category AS target_category, SUM(e.weight) AS retweets
FROM dbo.edges e
JOIN (SELECT DISTINCT source AS handle, source_category AS category FROM dbo.edges) h
  ON h.handle = e.target
WHERE e.kind = 'internal'
GROUP BY e.source_category, h.category
ORDER BY retweets DESC;

-- 4. One-day blasts: share of templates active on exactly one day
SELECT COUNT(*) AS templates,
       SUM(CASE WHEN days_active = 1 THEN 1 ELSE 0 END) AS one_day,
       CAST(100.0 * SUM(CASE WHEN days_active = 1 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,1)) AS one_day_pct,
       MAX(days_active) AS longest
FROM dbo.bursts;

-- 5. Peak days: when did template copies dominate the day's output?
SELECT TOP 10 day, all_originals, template_posts,
       CAST(100.0 * template_posts / NULLIF(all_originals, 0) AS DECIMAL(5,1)) AS template_share_pct
FROM dbo.daily_volume
ORDER BY template_posts DESC;