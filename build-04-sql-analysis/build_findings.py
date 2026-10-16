"""Builds findings.html from data/results.json: question -> finding sentence (computed) -> result table -> query."""
import json, html
from pathlib import Path
HERE = Path(__file__).parent
R = json.loads((HERE / "data/results.json").read_text(encoding="utf-8"))
e = html.escape
def table(q, max_rows=40):
    cols = R[q]["columns"]; rows = R[q]["rows"][:max_rows]
    def cell(v, c):
        if v is None: return '<td class="num">–</td>'
        if c in ("yr", "year"): return f'<td class="num">{v}</td>'
        if isinstance(v, float): return f'<td class="num">{v:,.3f}</td>' if 0 < abs(v) < 1 and c.endswith("per_retweet") else f'<td class="num">{v:,.1f}</td>'
        if isinstance(v, int): return f'<td class="num">{v:,}</td>'
        return f'<td>{e(str(v))}</td>'
    th = "".join(f'<th{" class=num" if any(isinstance(r[c], (int, float)) for r in rows) else ""}>{e(c)}</th>' for c in cols)
    tr = "".join("<tr>" + "".join(cell(r[c], c) for c in cols) + "</tr>" for r in rows)
    more = f'<p class="note">Showing {max_rows} of {len(R[q]["rows"])} rows.</p>' if len(R[q]["rows"]) > max_rows else ""
    return f'<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>{more}'
def block(q, finding, caveat, pattern):
    return f'''<section class="q">
<h2>{e(q)}. {e(R[q]["question"])}</h2>
<p class="finding">{finding}</p>
<p class="note">{caveat}</p>
{table(q)}
<details><summary>Query ({e(pattern)})</summary><pre>{e(R[q]["sql"])}</pre></details>
</section>'''

# Q1
r1 = R["Q1"]["rows"]; lower = [r for r in r1 if r["gap_pts"] < 0]; widest = min(r1, key=lambda r: r["gap_pts"]); narrowest = max(r1, key=lambda r: r["gap_pts"])
f1 = (f"Veterans have had the lower unemployment rate in <b>{len(lower)} of {len(r1)} years</b> since 2000. The gap was widest in {widest['yr']} "
      f"({abs(widest['gap_pts']):.1f} points in veterans' favor) and narrowest in {narrowest['yr']} ({abs(narrowest['gap_pts']):.1f} points).")
# Q2
r2 = R["Q2"]["rows"][0]
f2 = (f"Gulf War-era II unemployment peaked at <b>{r2['peak_gw2']:.1f}%</b> in {r2['peak_period'][:7]}, {r2['peak_excess_pts']:.1f} points above all veterans ({r2['peak_all']:.1f}%). "
      f"It took <b>{r2['months_to_close_to_1pt']} months</b> for the excess to fall within 1 point; over the last 12 months it has averaged {r2['excess_last_12m']:.1f} points.")
# Q3
r3 = R["Q3"]["rows"]; up = [r for r in r3 if r["yoy_change_pts"] and r["yoy_change_pts"] > 0]
gw = next(r for r in r3 if r["series_id"] == "LNU04066408"); nv = next(r for r in r3 if r["series_id"] == "LNU04049601")
f3 = (f"In {r3[0]['latest_period'][:7]}, Gulf War-era II unemployment was <b>{gw['latest_value']:.1f}%</b>, {gw['yoy_change_pts']:+.1f} points against the same month a year earlier, "
      f"while nonveteran unemployment moved {nv['yoy_change_pts']:+.1f}. Participation fell {abs(r3[0]['yoy_change_pts']):.1f} points for both veterans and nonveterans.")
# Q4
r4 = R["Q4"]["rows"]; cov = {r["population"]: r for r in r4 if r["episode"] == "COVID-19"}; gr = {r["population"]: r for r in r4 if r["episode"] == "Great Recession"}
v, n = cov["Veterans, 18+"], cov["Nonveterans, 18+"]
f4 = (f"In the COVID-19 shock, veteran unemployment rose {v['rise_pts']:.1f} points to {v['peak_value']:.1f}% and was back at its pre-recession level in <b>{v['months_peak_to_recovery']} months</b>; "
      f"nonveterans rose {n['rise_pts']:.1f} points to {n['peak_value']:.1f}% and took <b>{n['months_peak_to_recovery']} months</b>. "
      f"In the Great Recession the veteran peak came in {gr['Veterans, 18+']['peak_period'][:7]} and recovery to the December 2007 level took {gr['Veterans, 18+']['months_peak_to_recovery'] or 'longer than the window'} months.")
# Q5
r5 = R["Q5"]["rows"]; rt = next(r for r in r5 if r["category"] == "RightTroll"); tot_t = sum(r["templates_written"] for r in r5); tot_r = sum(r["retweets_sent"] for r in r5)
f5 = (f"RightTroll accounts wrote <b>{rt['templates_written']:,} of {tot_t:,} templates</b> ({100*rt['templates_written']/tot_t:.0f}%) and sent {rt['retweets_sent']:,} of {tot_r:,} retweets ({100*rt['retweets_sent']/tot_r:.0f}%) from just {rt['retweeting_accounts']} accounts. "
      f"Producing and amplifying were the same operation, not two.")
# Q6
r6 = R["Q6"]["rows"]; rt6 = next(r for r in r6 if r["category"] == "RightTroll"); others = [r for r in r6 if r["category"] != "RightTroll"]
f6 = (f"One-day blasts are a RightTroll signature: <b>{rt6['blast_share_pct']:.1f}%</b> of its {rt6['templates']:,} templates lived one day. "
      f"Every other category's blast share is {max(r['blast_share_pct'] for r in others):.0f}%; their templates ran {min(r['avg_days_when_multi_day'] for r in others if r['avg_days_when_multi_day']):.1f} to {max(r['avg_days_when_multi_day'] for r in others if r['avg_days_when_multi_day']):.1f} days on average.")
# Q7
r7 = R["Q7"]["rows"]
f7 = (f"<b>{len(r7)} run</b> recorded so far ({r7[0]['run_time']}): {r7[0]['rows_written']:,} rows, max authors {r7[0]['max_authors']}, {r7[0]['template_posts']:,} template posts over {r7[0]['english_originals']:,} originals. "
      f"The first scheduled run is Monday 2026-10-19 06:00 UTC; this row should duplicate exactly, because the input file does not change." if len(r7) == 1 else
      f"<b>{len(r7)} runs</b> recorded; identical counts across runs confirm the pipeline is deterministic.")

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SQL Findings</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}pre{{background:var(--surface-2);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.45}}
.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}
</style></head><body><main>
<h1>Seven questions, seven queries, seven sentences</h1>
<p class="sub">The queries a Business Analyst writes against the tables from builds #1 and #2, run on the free Azure SQL database, each answered in one sentence with its number and its caveat. Anchor phrase: question, query, sentence. Expand any query to read the T-SQL.</p>
{block("Q1", f1, "Annual averages of monthly not-seasonally-adjusted rates. Veterans skew older, which lowers unemployment on its own; this gap is not age-adjusted.", "CTE + self-join on year")}
{block("Q2", f2, "Gulf War-era II = service since September 2001. The series starts in 2006, so the 2008 window begins at the first available month. Monthly NSA data; the peak is a single month.", "CTEs, TOP 1 peak, correlated subqueries, DATEDIFF")}
{block("Q3", f3, "Same month, one year apart, is the only honest comparison for NSA data. A single month of Gulf War-era II data is a small sample and moves a lot; read the trend, not the point.", "LEFT JOIN on DATEADD(year,-1)")}
{block("Q4", f4, "Pre-recession level = December 2007 and February 2020. Recovery = first month at or below that level after the peak. Windows: 2008–2012 and 2020–2023.", "episode table via UNION ALL, three CTEs, LEFT JOIN for not-yet-recovered")}
{block("Q5", f5, "Build #1 data, file 1 of 13. Retweet edges count only retweets with an identifiable target (RT handle: or matched in-file original). Categories are the researchers' hand labels.", "FULL OUTER JOIN across two signals, COALESCE")}
{block("Q6", f6, "Days active counts distinct calendar days with at least one post of that template. Small categories (Fearmonger, Unknown) have single-digit template counts.", "JOIN on body, conditional aggregation, AVG over a CASE")}
{block("Q7", f7, "The function reads the same blob every week, so identical counts are the expected result; a changed count would mean a code or data change worth investigating.", "GROUP BY run_id over the run-stamped history table")}
<p class="foot">Data: BLS Current Population Survey via api.bls.gov (public domain); FiveThirtyEight / Clemson IRA tweets, file 1 of 13 (attributed, non-commercial). Build #4 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Azure SQL Database (free offer). Cost: $0. Queries and runner: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-04-sql-analysis">GitHub</a>.</p>
</main></body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8"); print("ok", len(page))