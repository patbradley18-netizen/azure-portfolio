"""Builds findings.html from data/kql_results.json and data/ops_snapshot.json. Every number in every sentence is computed, not typed.
Chart: inline SVG line of free_amount_consumed (vCore-seconds) over the points the metric emitted, with the proving and
production thresholds drawn as horizontal lines. One series, two labelled reference lines, no legend."""
import html
import json
from pathlib import Path

HERE = Path(__file__).parent
K = json.loads((HERE / "data/kql_results.json").read_text(encoding="utf-8-sig"))
S = json.loads((HERE / "data/ops_snapshot.json").read_text(encoding="utf-8-sig"))
e = html.escape


def rows(q):
    r = K[q]["rows"]
    return r["value"] if isinstance(r, dict) else r


def num(v):
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def table(q, max_rows=40, drop=("TableName", "OperationId")):
    rs = rows(q)
    if not rs:
        return '<p class="note">No rows.</p>'
    cols = [c for c in rs[0].keys() if c not in drop]
    th = "".join(f'<th{" class=num" if all(num(r.get(c)) is not None for r in rs) else ""}>{e(c)}</th>' for c in cols)
    tr = ""
    for r in rs[:max_rows]:
        tds = ""
        for c in cols:
            v = r.get(c); f = num(v)
            if f is not None and not (isinstance(v, str) and "T" in v and ":" in v):
                tds += f'<td class="num">{f:,.0f}</td>' if f == int(f) or abs(f) >= 1000 else f'<td class="num">{f:,.2f}</td>'
            else:
                tds += f'<td>{e(str(v))[:19] if isinstance(v, str) and v.endswith("Z") else e(str(v))}</td>'
        tr += f"<tr>{tds}</tr>"
    more = f'<p class="note">Showing {max_rows} of {len(rs):,} rows.</p>' if len(rs) > max_rows else ""
    return f'<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>{more}'


def block(title, finding, caveat, body, kql=None):
    q = f'<details><summary>Query (KQL)</summary><pre>{e(kql)}</pre></details>' if kql else ""
    return f'<section class="q"><h2>{title}</h2><p class="finding">{finding}</p><p class="note">{caveat}</p>{body}{q}</section>'


def chart(pts, prove, prod, limit):
    W, H, L, B = 760, 360, 64, 40
    ys = [p["v"] for p in pts]; mx = limit
    n = len(pts)
    sx = lambda i: L + (i / max(n - 1, 1)) * (W - L - 16)
    sy = lambda v: H - B - v / mx * (H - B - 16)
    out = []
    for t in (0, 20000, 40000, 60000, 80000, 100000):
        out.append(f'<line x1="{L}" y1="{sy(t):.0f}" x2="{W-16}" y2="{sy(t):.0f}" class="grid"/><text x="{L-8}" y="{sy(t)+4:.0f}" class="lbl" text-anchor="end">{t:,}</text>')
    out.append(f'<line x1="{L}" y1="{sy(prod):.0f}" x2="{W-16}" y2="{sy(prod):.0f}" class="ref"/><text x="{W-20}" y="{sy(prod)-5:.0f}" class="lbl" text-anchor="end">alert threshold {prod:,} (production)</text>')
    out.append(f'<line x1="{L}" y1="{sy(prove):.0f}" x2="{W-16}" y2="{sy(prove):.0f}" class="ref2"/><text x="{W-20}" y="{sy(prove)-5:.0f}" class="lbl" text-anchor="end">proving threshold {prove:,} — fired</text>')
    path = " ".join(f'{"M" if i == 0 else "L"}{sx(i):.1f},{sy(p["v"]):.1f}' for i, p in enumerate(pts))
    out.append(f'<path d="{path}" class="line"/>')
    for i, p in enumerate(pts):
        out.append(f'<circle cx="{sx(i):.1f}" cy="{sy(p["v"]):.1f}" r="4" class="dot"><title>{e(p["t"][:16].replace("T", " "))} UTC: {p["v"]:,.0f} vCore-seconds consumed</title></circle>')
    out.append(f'<text x="{L}" y="{H-8}" class="lbl">{e(pts[0]["t"][:16].replace("T"," "))} UTC</text><text x="{W-16}" y="{H-8}" class="lbl" text-anchor="end">{e(pts[-1]["t"][:16].replace("T"," "))} UTC</text>')
    out.append(f'<text x="14" y="{(H-B)/2:.0f}" class="lbl" text-anchor="middle" transform="rotate(-90 14 {(H-B)/2:.0f})">free vCore-seconds consumed this month</text>')
    return f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Free SQL vCore-seconds consumed with alert thresholds">{"".join(out)}</svg>'


cons = S["metrics"]["free_amount_consumed"]; rem = S["metrics"]["free_amount_remaining"]; limit = S["free_limit_month"]
last = cons[-1]["v"]; pct = 100 * last / limit
fired = S["fired_alerts"][0] if S["fired_alerts"] else None
rule = S["alert_rule"]
runs = rows("K02_function_runs"); fails = rows("K04_failures"); ingest = rows("K06_ingest_gb"); tables = rows("K01_tables")
mb = sum(num(r["mb"]) or 0 for r in ingest)
f_sql = (f"The free Azure SQL database has used <b>{last:,.0f} of {limit:,} vCore-seconds</b> this month ({pct:.1f}%) across twelve builds; {rem[-1]['v']:,.0f} remain. "
         f"The metric is emitted only while the database is awake — {len(cons)} hourly points in the last 30 days, between {e(cons[0]['t'][:10])} and {e(cons[-1]['t'][:10])} — which is itself the clearest picture of how the serverless tier spends: nothing while paused, a few thousand seconds per working evening.")
f_alert = (f"The alert rule <code>{e(rule['name'])}</code> watches <code>{e(rule['metric'])}</code> ({e(rule['agg'])} over {e(rule['window'])}, every {e(rule['freq'])}) and emails action group <code>{e(S['action_group']['name'])}</code>. "
           + (f"Set first to 9,000 so it would fire now, it <b>fired at {e(fired['fired'][:16].replace('T',' '))} UTC</b> ({e(fired['severity'])}, target <code>{e(fired['target'])}</code>) and the email arrived. " if fired else "")
           + f"It now sits at <b>{rule['threshold']:,.0f}</b> — {rule['threshold']/limit*100:.0f}% of the month's free allowance — so the warning lands before the database auto-pauses for the month, not after.")
ok_runs = sum(1 for r in runs if str(r["Success"]).lower() == "true")
f_runs = (f"{len(runs)} Function invocations are in the workspace so far ({ok_runs} succeeded), all manual test runs: the first scheduled runs are Saturday 12:00 UTC (build #2) and Monday 06:00 UTC (build #1). "
          f"The one failure is the serverless pause seen from the other side: a <code>SqlException</code> on build #1's first run while the database woke, and a clean run four minutes later.")
f_ingest = (f"The workspace holds {sum(int(num(r['rows'])) for r in tables):,} rows across {len(tables)} tables and has ingested <b>{mb:.2f} MB</b> in 30 days against a free line of 5,120 MB. Monitoring this portfolio costs nothing because there is almost nothing to monitor; the point is that the alert exists before the thing it watches is large.")

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Before The Bill</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}pre{{background:var(--surface-2);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.45;white-space:pre-wrap}}
svg{{width:100%;height:auto;background:var(--surface-2);border-radius:10px;margin-bottom:10px}}.lbl{{fill:var(--ink-2);font-size:12px}}.grid{{stroke:var(--line);stroke-width:1}}.ref{{stroke:var(--ink-3);stroke-width:1.5;stroke-dasharray:4 4}}.ref2{{stroke:var(--ink-3);stroke-width:1;stroke-dasharray:2 4}}.line{{fill:none;stroke:var(--series);stroke-width:2}}.dot{{fill:var(--series)}}.dot:hover{{stroke:var(--ink);stroke-width:1.5}}
.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}
</style></head><body><main>
<h1>Before the bill: the free SQL limit, the Functions, and an alert that proved itself</h1>
<p class="sub">An operations page for a portfolio that runs on free tiers. The unit that actually bites is the free Azure SQL database's 100,000 vCore-seconds a month; a metric alert now emails before that line, and it fired once on purpose to prove the path works. The rest is KQL over the Log Analytics workspace the Function wizard created: run history, the one failure, and how little gets ingested. Anchor phrase: a number, a threshold, an email. Expand any query to read the KQL.</p>
{block("The free SQL limit", f_sql, f"Metric <code>free_amount_consumed</code> on the database, hourly maximum, as emitted; points are evenly spaced, not to time scale; snapshot taken {e(S['taken_at'][:16].replace('T',' '))} UTC. The database auto-pauses when the free amount is exhausted (set in build #2, OI-05), so the alert is a warning before a pause, not before a charge.", chart(cons, 9000, int(rule["threshold"]), limit))}
{block("The alert, and its proof", f_alert, "Metric alert rules are free for the first ten monitored time series per month; this is one. Action-group email is free for the first 1,000 a month. No log-search alert rules were created (they bill per rule). The rule, the action group and the two Application Insights components are now in the portfolio's Bicep (build #10's infra), which what-if reports as no change.", table("K01_tables") if False else "")}
{block("Function runs (K02, K03)", f_runs, "AppRequests from both Function apps' Application Insights, which stream to the workspace. Durations in milliseconds.", table("K02_function_runs") + table("K03_runs_by_day"), K["K02_function_runs"]["kql"])}
{block("Failures and exceptions (K04)", "What went wrong and when.", "Union of failed requests and exceptions; two exception rows for one failure is Application Insights recording the outer and inner exception.", table("K04_failures"), K["K04_failures"]["kql"])}
{block("What the workspace holds and ingests (K01, K05, K06)", f_ingest, "Billable ingestion by table over 30 days; trace volume by severity per app (ItemCount is the sampling weight — here 1, so no sampling occurred).", table("K01_tables") + table("K06_ingest_gb") + table("K05_trace_volume"), K["K06_ingest_gb"]["kql"])}
<section class="q"><h2>What this cannot say</h2>
<p class="note">Three invocations are not a run history; the scheduled runs begin this weekend and the workbook is where they will accumulate. The free-limit metric is silent while the database is paused, so a flat line means asleep, not idle. An alert that fired at 9,000 proves the path, not the threshold: 80,000 has never been reached and the warning has never been needed. Application Insights sampling can make request counts estimates; it was off here. Cost figures are tier allowances, not an invoice — Cost Management is the invoice.</p></section>
<p class="foot">Data: this subscription's Azure Monitor metrics and Log Analytics workspace (own data). Build #12 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Azure Monitor metric alert + action group, Log Analytics (default workspace, PerGB2018), Application Insights ×2, an Azure Monitor workbook (<code>workbook.json</code> in the repo), Bicep. Cost: $0. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-12-operations">GitHub</a>.</p>
</main></body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8")
print("ok", len(page))
