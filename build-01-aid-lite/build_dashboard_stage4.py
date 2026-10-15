"""Inserts the stage-4 section (narrative persistence: null result) into dashboard.html from data/persistence_summary.json."""
import json, html
from pathlib import Path
HERE = Path(__file__).parent
s = json.loads((HERE / "data/persistence_summary.json").read_text())
e = html.escape
def kpi(v, t): return f'<div class="kpi"><b>{v}</b><span>{t}</span></div>'
months = s["by_month"]; W, H, pad = 900, 170, 36
ymax = max(max(m["hit_t"], m["hit_b"]) for m in months) * 100 * 1.15
def pts(key): return " ".join(f"{pad + i*(W-2*pad)/(len(months)-1):.1f},{H-pad - m[key]*100/ymax*(H-2*pad):.1f}" for i, m in enumerate(months))
ticks = "".join(f'<text x="{pad + i*(W-2*pad)/(len(months)-1):.1f}" y="{H-10}" font-size="10" text-anchor="middle" fill="var(--ink-3)">{m["month"][2:]}</text>' for i, m in enumerate(months) if i % 2 == 0)
svg = (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Share of speech chunks resembling a troll template vs the control, by month">'
       f'<line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="var(--line)"/>'
       f'<text x="{pad}" y="{pad-14}" font-size="11" fill="var(--ink-2)">% of chunks scoring ≥ {s["threshold"]}: templates (solid) vs random troll tweets (dashed)</text>'
       f'<polyline points="{pts("hit_t")}" fill="none" stroke="var(--series)" stroke-width="2"/>'
       f'<polyline points="{pts("hit_b")}" fill="none" stroke="var(--ink-3)" stroke-width="1.5" stroke-dasharray="5 4"/>'
       f'<text x="{W-pad}" y="{pad-14}" font-size="11" text-anchor="end" fill="var(--ink-3)">y-axis top = {ymax:.1f}%</text>{ticks}</svg>')
party = {p["party"]: p for p in s["by_party"]}
top = s["top_templates"][:8]
sec = f'''<!-- stage4:start -->
<h2>Did the themes reach the floor of Congress? No measurable trace.</h2>
<p class="note">Stage 4. Every speech in the Congressional Record from August 2017 to December 2018 ({s["chunks"]:,} chunks of ~200 words, public domain) was scored for similarity to the 1,642 troll templates, and, as a control, to 1,642 random non-template tweets from the same accounts. Anchor phrase: politics resembles politics. Without the control this would have looked like a finding.</p>
<div class="kpis">
{kpi(f"{s['mean_template']:.3f}", "average similarity to the troll templates")}
{kpi(f"{s['mean_baseline']:.3f}", "average similarity to the random control (higher)")}
{kpi(f"{s['hit_template_pct']:.2f}%", f"of chunks resemble a template (≥ {s['threshold']})")}
{kpi(f"+{s['overall_lift_pts']:.2f} pts", "lift over the control. Democrats +" + f"{party['D']['lift_pts']:.2f}" + ", Republicans +" + f"{party['R']['lift_pts']:.2f}")}
</div>
<p class="note" style="margin-top:14px">By month. The two lines never separate; no month shows a lift above 1.3 points.</p>
{svg}
<h2>What the "matches" actually are: shared topics</h2>
<p class="note">Templates most often scored as the nearest neighbour of a speech chunk. Every one is a news topic Congress was debating anyway. The single highest-scoring chunk in the corpus is a member arguing the Mueller investigation is <i>not</i> a witch hunt, matched to the template "the truth about mueller's crooked witch hunt": similarity sees the topic, not the stance.</p>
<table><thead><tr><th>Template</th><th>Category</th><th class=num>Chunks matched</th></tr></thead><tbody>
{"".join(f"<tr><td>{e(t['best_template'][:110])}</td><td>{e(t['template_cat'])}</td><td class=num>{t['chunks_matched']}</td></tr>" for t in top)}
</tbody></table>
<p class="note" style="margin-top:14px">Azure part: the 1,642 templates are indexed as vectors in Azure AI Search (free tier, index <code>aid-templates</code>) so any sentence can be checked against them. The full sweep above ran locally: the free tier holds about 30k vectors, not 188k. No names of speakers are shown anywhere; party and month only.</p>
<!-- stage4:end -->
'''
d = (HERE / "dashboard.html").read_text(encoding="utf-8")
if "<!-- stage4:start -->" in d:
    a, b = d.index("<!-- stage4:start -->"), d.index("<!-- stage4:end -->") + len("<!-- stage4:end -->\n"); d = d[:a] + sec + d[b:]
else:
    d = d.replace('<p class="foot">', sec + '<p class="foot">')
d = d.replace("<title>AID Lite: Stages 1 to 3</title>", "<title>AID Lite: Stages 1 to 4</title>")
d = d.replace("<h1>Algorithmic Influence Detector, stages 1 to 3</h1>", "<h1>Algorithmic Influence Detector, stages 1 to 4</h1>")
d = d.replace("Stage 3 adds who amplified whom and when the blasts happened.</p>", "Stage 3 adds who amplified whom and when the blasts happened. Stage 4 tests whether the themes reached the Congressional Record, against a control; they did not.</p>")
d = d.replace("Azure services: Blob Storage, Azure SQL Database (free offer), Azure Functions (Flex Consumption), Azure AI Language (F0). Cost: $0.", "Azure services: Blob Storage, Azure SQL Database (free offer), Azure Functions (Flex Consumption), Azure AI Language (F0), Azure AI Search (free). Congressional Record text: U.S. Government Publishing Office, public domain. Cost: $0.")
(HERE / "dashboard.html").write_text(d, encoding="utf-8"); print("dashboard updated", len(d))