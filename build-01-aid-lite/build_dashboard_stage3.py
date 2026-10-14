"""Inserts the stage-3 sections (amplification network, one-day blasts) into dashboard.html.
Reads data/network_summary.json and data/bursts_summary.json. Idempotent: replaces between markers."""
import json, html
from pathlib import Path
HERE = Path(__file__).parent
net = json.loads((HERE / "data/network_summary.json").read_text())
bur = json.loads((HERE / "data/bursts_summary.json").read_text())
e = html.escape
def kpi(v, s): return f'<div class="kpi"><b>{v}</b><span>{s}</span></div>'
def bar(label, v, vmax, fmt):
    return (f'<div class="row" title="{e(label)}: {fmt}"><div class="lab">{e(label)}</div>'
            f'<div class="track"><div class="bar" style="width:{v/vmax*100:.1f}%"></div></div><div class="val">{fmt}</div></div>')

ring_pct = round(net["ring_amplifies_ring"] / net["ring_retweeted_by_others"] * 100)
brokers = net["top_brokers"][:10]; bmax = brokers[0]["distinct_hubs"]
import csv
hubs_in = [dict(h, retweets=int(h["retweets"]), distinct_retweeters=int(h["distinct_retweeters"])) for h in csv.DictReader((HERE / "data/hubs.csv").open(encoding="utf-8")) if h["in_dataset"] == "True"][:8]
hubs_ext = [h for h in net["top_hubs"] if not h["in_dataset"]][:8]
mix = {(m["account_category"], m["target_cat"]): m["n"] for m in net["category_mix"]}
rl, rr, ll, lr = mix.get(("RightTroll","LeftTroll"),0), mix.get(("RightTroll","RightTroll"),0), mix.get(("LeftTroll","LeftTroll"),0), mix.get(("LeftTroll","RightTroll"),0)

# timeline SVG: template posts per day, full range
vol = bur["daily_volume"]; n = len(vol); W, H, pad = 900, 160, 28
ymax = max(v["template_posts"] for v in vol)
pts = " ".join(f"{pad + i*(W-2*pad)/(n-1):.1f},{H-pad - v['template_posts']/ymax*(H-2*pad):.1f}" for i, v in enumerate(vol))
years = [(i, v["day"][:4]) for i, v in enumerate(vol) if v["day"][:4] != vol[i-1]["day"][:4]]  # first year label skipped: too close to 2015
ticks = "".join(f'<text x="{pad + i*(W-2*pad)/(n-1):.1f}" y="{H-8}" font-size="11" fill="var(--ink-3)">{y}</text>' for i, y in years)
peak_i = max(range(n), key=lambda i: vol[i]["template_posts"]); px = pad + peak_i*(W-2*pad)/(n-1)
svg = (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Template posts per day, {vol[0]["day"]} to {vol[-1]["day"]}">'
       f'<line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="var(--line)"/>'
       f'<polyline points="{pts}" fill="none" stroke="var(--series)" stroke-width="1.5" stroke-linejoin="round"/>'
       f'<text x="{px:.1f}" y="{pad-10}" font-size="11" text-anchor="middle" fill="var(--ink-2)">{bur["peak_day"]}: {bur["peak_day_template_posts"]:,}</text>{ticks}</svg>')

sec = f'''<!-- stage3:start -->
<h2>Who amplified whom</h2>
<p class="note">Stage 3, signal C. Every retweet is an arrow from the account that retweeted to the account retweeted. <b>External</b> arrows point at handles outside the dataset (parsed from "RT handle:"). <b>Internal</b> arrows point at another dataset account whose earlier original has the same body text. Being retweeted by these accounts says nothing about the retweeted account; it only shows what the operation chose to boost.</p>
<div class="kpis">
{kpi(f"{net['external_edges']:,}", "retweets of outside handles")}
{kpi(f"{net['internal_edges']:,}", "retweets of another dataset account")}
{kpi(f"{ring_pct}%", "of retweets the 44-account ring received came from the ring itself")}
{kpi(f"{rl:,}", "times a RightTroll account retweeted a LeftTroll account")}
</div>
<h2>Brokers: accounts that retweeted the most distinct handles</h2>
<p class="note">Anchor phrase: hubs and brokers. A broker spreads many sources; a hub is a source many accounts spread. Bars show distinct handles retweeted. The top brokers are all RightTroll accounts with the same naming pattern.</p>
{"".join(bar(b["handle"], b["distinct_hubs"], bmax, f"{b['distinct_hubs']:,}") for b in brokers)}
<h2>Hubs inside the dataset</h2>
<p class="note">Dataset accounts whose originals other dataset accounts retweeted. Cross-faction amplification is real: RightTroll accounts retweeted LeftTroll originals {rl:,} times, their own side {rr:,} times; LeftTroll accounts retweeted LeftTroll {ll:,} times and RightTroll {lr:,} times.</p>
<table><thead><tr><th>Account</th><th>Category</th><th class=num>Retweets received</th><th class=num>Distinct retweeters</th></tr></thead><tbody>
{"".join(f"<tr><td>{e(h['handle'])}</td><td>{e(h['category'])}</td><td class=num>{h['retweets']:,}</td><td class=num>{h['distinct_retweeters']}</td></tr>" for h in hubs_in)}
</tbody></table>
<p class="note" style="margin-top:14px">Most-retweeted outside handles (public accounts, named only as targets of amplification): {", ".join(f"{e(h['handle'])} ({h['retweets']:,})" for h in hubs_ext)}.</p>

<h2>When: one-day blasts</h2>
<p class="note">Stage 3, signal D. The planned burst score (peak day over median day) was useless here, because {bur['blast_share_pct']}% of templates were posted on a single day: median equals peak. The finding is the shape itself. Anchor phrase: one-day blast.</p>
<div class="kpis">
{kpi(f"{bur['blast_share_pct']}%", "of templates were posted on exactly one day")}
{kpi(bur["max_days_active"], "days: the longest any template stayed active")}
{kpi(f"{bur['peak_day_template_posts']:,}", f"template posts on {bur['peak_day']}, the peak day")}
{kpi(f"{bur['peak_day_share_pct']}%", "of all originals that day were template copies")}
</div>
<p class="note" style="margin-top:14px">Template posts per day, {vol[0]["day"]} to {vol[-1]["day"]}. Nearly all of it is one fortnight in August 2017.</p>
{svg}
<!-- stage3:end -->
'''
d = (HERE / "dashboard.html").read_text(encoding="utf-8")
for bad, good in (("â€œ", "\u201c"), ("â€\x9d", "\u201d"), ("â€", "\u201d"), ("â€™", "\u2019")):
    d = d.replace(bad, good)
if "<!-- stage3:start -->" in d:
    a, b = d.index("<!-- stage3:start -->"), d.index("<!-- stage3:end -->") + len("<!-- stage3:end -->\n")
    d = d[:a] + sec + d[b:]
else:
    d = d.replace('<p class="foot">', sec + '<p class="foot">')
d = d.replace("<title>AID Lite: Stage 1</title>", "<title>AID Lite: Stages 1 to 3</title>")
d = d.replace("<h1>Algorithmic Influence Detector, stage 1</h1>", "<h1>Algorithmic Influence Detector, stages 1 to 3</h1>")
d = d.replace("and tags the top messages with key phrases from Azure AI Language.</p>", "and tags the top messages with key phrases from Azure AI Language. Stage 3 adds who amplified whom and when the blasts happened.</p>")
(HERE / "dashboard.html").write_text(d, encoding="utf-8")
print("dashboard updated,", len(d), "chars")