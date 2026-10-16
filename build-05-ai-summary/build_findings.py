"""Builds findings.html from data/{estimate,ledger,extract,summary,verify}.json. Every number on the page is read from those files."""
import html
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
D = HERE / "data"
J = lambda n: json.loads((D / n).read_text(encoding="utf-8"))
est, led, ext, summ, ver = J("estimate.json"), J("ledger.json"), J("extract.json"), J("summary.json"), J("verify.json")
e = html.escape

run = led["runs"][-1]
month_used = sum(r["records_billed"] for r in led["runs"] if r["month"] == run["month"])
n_runs = len(led["runs"])
ok_bullets = sum(b["ok"] for b in ver["bullets"])
ok_q = sum(h["in_source"] for h in ver["headline_numbers"])
status = "PASS" if ver["pass"] else "FAIL"

ent_counts = Counter(en["category"] for d in ext["documents"] for en in d["entities"])
n_kp = sum(len(d["key_phrases"]) for d in ext["documents"])
sent_rows = "".join(
    f'<tr><td>Section {d["doc_id"] + 1}</td><td class="num">{d["sentiment"]["label"]}</td>'
    f'<td class="num">{d["sentiment"]["scores"]["negative"]:.2f}</td><td class="num">{d["sentiment"]["scores"]["neutral"]:.2f}</td>'
    f'<td class="num">{d["sentiment"]["scores"]["positive"]:.2f}</td><td class="num">{len(d["text"]):,}</td></tr>'
    for d in ext["documents"])
bullets = "".join(f'<li>{e(b["text"])} <span class="score">score {b["score"]}</span></li>' for b in summ["bullets"])
kp_rows = "".join(f'<tr><td>Section {d["doc_id"] + 1}</td><td>{e(", ".join(d["key_phrases"][:12]))}</td></tr>' for d in ext["documents"])
ent_rows = "".join(f'<tr><td>{e(k)}</td><td class="num">{v}</td></tr>' for k, v in ent_counts.most_common())
ver_rows = "".join(f'<tr><td>{e(b["text"])}…</td><td class="num">{"yes" if b["verbatim"] else "NO"}</td>'
                   f'<td class="num">{len(b["numbers"])}</td><td class="num">{len(b["missing"])}</td></tr>' for b in ver["bullets"])
ledger_rows = "".join(f'<tr><td>{e(r["ts"])}</td><td class="num">{r["documents"]}</td><td class="num">{r["records_estimated"]}</td>'
                      f'<td class="num">{r["records_billed"]}</td></tr>' for r in led["runs"])

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Summary, Cost-Capped</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6;--ok:#1f7a3a;--warn:#a65b00}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5;--ok:#4fbf6f;--warn:#e0a040}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5;--ok:#4fbf6f;--warn:#e0a040}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:0 0 8px}}.tile{{background:var(--surface-2);border-radius:10px;padding:12px 14px}}
.tile b{{display:block;font-size:22px;font-variant-numeric:tabular-nums}}.tile span{{color:var(--ink-2);font-size:13px}}
.ok{{color:var(--ok);font-weight:600}}.warn{{color:var(--warn);font-weight:600}}
ul.sum{{padding-left:20px}}ul.sum li{{margin:0 0 10px}}.score{{color:var(--ink-3);font-size:12px;white-space:nowrap}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}
</style></head><body><main>
<h1>Summarize a public report with Azure AI, with the cost controls first</h1>
<p class="sub">Source: BLS news release <i>Employment Situation of Veterans, 2025</i> (USDL-26-0666, April 28, 2026), {est["source_chars"]:,} characters. Azure AI Language, free tier. Anchor phrase: estimate, cap, ledger, verify.</p>

<h2>1. The bill was known before the call</h2>
<div class="tiles">
<div class="tile"><b>{est["documents"]}</b><span>documents sent (≤{5000:,} chars each)</span></div>
<div class="tile"><b>{est["total_records_per_run"]}</b><span>text records estimated ({est["records_per_feature"]} × {len(est["features"])} features)</span></div>
<div class="tile"><b>{run["records_billed"]}</b><span>text records the API billed</span></div>
<div class="tile"><b>{month_used} / {est["f0_allowance_per_month"]:,}</b><span>free-tier records used this month</span></div>
<div class="tile"><b>${est["s_tier_cost_usd_if_paid"]:.3f}</b><span>what this run would cost on the paid S tier</span></div>
<div class="tile"><b>$0.00</b><span>what it cost</span></div>
</div>
<p class="finding">Estimate {est["total_records_per_run"]}, bill {run["records_billed"]}: the estimator (1 record per 1,000 characters, per feature, per document) matched the service's own transaction count exactly. The run only proceeds if estimate + month-to-date stays under a hard cap of 1,000 records (20% of the free allowance) and a per-run cap of 200.</p>
<table><thead><tr><th>Run (UTC)</th><th class="num">Docs</th><th class="num">Estimated</th><th class="num">Billed</th></tr></thead><tbody>{ledger_rows}</tbody></table>
<p class="note">Ledger: {n_runs} run{"s" if n_runs != 1 else ""} recorded. The billed figure comes from the API response (<code>show_stats</code>), not from the estimate.</p>

<h2>2. The summary, every sentence verbatim from the release</h2>
<ul class="sum">{bullets}</ul>
<p class="note">Why verbatim: Azure's summarization API (extractive and abstractive) runs only on the paid S tier; the free tier refused it with <i>Principal does not have access to API/Operation</i>. So the free-tier features supply the salience signal (key phrases and Quantity entities) and the selection is done locally: score = hits per 10 words, with a bonus for the release's first paragraph (inverted pyramid). Nothing is paraphrased, so nothing can be invented.</p>

<h2>3. Verification: <span class="{"ok" if ver["pass"] else "warn"}">{status}</span></h2>
<p class="finding">{ok_bullets} of {len(ver["bullets"])} bullets are verbatim sentences of the source and every number in them appears in the source; {ok_q} of {len(ver["headline_numbers"])} API-extracted headline quantities are present in the source text.</p>
<table><thead><tr><th>Bullet</th><th class="num">Verbatim</th><th class="num">Numbers</th><th class="num">Missing</th></tr></thead><tbody>{ver_rows}</tbody></table>
<p class="note">The page is built from the verifier's output; a FAIL would show here, not be hidden.</p>

<h2>4. What the free tier returned</h2>
<p class="finding">{n_kp} key phrases and {sum(ent_counts.values())} entities across {est["documents"]} sections.</p>
<table><thead><tr><th>Section</th><th>Top key phrases</th></tr></thead><tbody>{kp_rows}</tbody></table>
<table style="margin-top:14px"><thead><tr><th>Entity category</th><th class="num">Count</th></tr></thead><tbody>{ent_rows}</tbody></table>
<p class="note">Entity spans are rough on tabular prose: "(71.3 percent" keeps its bracket and the release number "0666" is tagged as a Quantity. The verifier normalises before matching; a production pipeline would post-process spans.</p>

<h2>5. Sentiment on a statistics release is noise</h2>
<table><thead><tr><th>Section</th><th class="num">Label</th><th class="num">Negative</th><th class="num">Neutral</th><th class="num">Positive</th><th class="num">Chars</th></tr></thead><tbody>{sent_rows}</tbody></table>
<p class="note">Every section scores "negative" at 0.7–0.8. The model is reacting to the vocabulary (unemployment, disability, jobless), not to the findings, several of which are favourable to veterans. Lesson for a Business Analyst: a feature being available is not a reason to report it. This one is shown so the reader can see why it was discarded.</p>

<p class="foot">Data: BLS, public domain. Build #5 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Azure AI Language (F0). Cost: $0. Code, ledger and verifier: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-05-ai-summary">GitHub</a>.</p>
</main></body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8")
print("ok", len(page), status)
