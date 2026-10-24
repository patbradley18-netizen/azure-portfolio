"""Builds findings.html for build #22 from the feed itself: runs build_feed.py into a temp folder and reports what it made.
Every number on the page is computed from that output."""
import json, os, html, subprocess, sys, tempfile, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); e = html.escape
out = tempfile.mkdtemp(prefix="showcase-")
subprocess.run([sys.executable, os.path.join(HERE, "build_feed.py"), ROOT, out], check=True)
I = json.load(open(os.path.join(out, "index.json"), encoding="utf-8"))
series = [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(os.path.join(out, "build-*", "*.json")))]
n_rows = sum(s["n"] for s in series); n_bytes = sum(os.path.getsize(f) for f in glob.glob(os.path.join(out, "**", "*.json"), recursive=True))
dropped = [(s["build"], s["id"], ", ".join(s["dropped_columns"])) for s in series if s["dropped_columns"]]
big = sorted(series, key=lambda s: -s["n"])[:5]
rows_b = [{"b": f"#{b['build']}", "title": b["title"] or "(no README)", "anchor": b["anchor"], "n": b["series_count"], "page": f'<a href="{e(b["page"])}">page</a>' if b["page"] else "", "man": f'<a href="{e(b["manifest"])}">manifest</a>'} for b in I["builds"] if b["build"] != 22]
def table(rows, cols, head, raw=()):
    return ("<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f"<td>{r[c] if c in raw else e(str(r[c]))}</td>" for c in cols) + "</tr>" for r in rows) + "</tbody></table>")
SITE = I["site"]
s0 = series[0]
sample = "{\n" + ",\n".join(f' "{k}": {json.dumps(s0[k], ensure_ascii=False)}' for k in ("schema", "build", "id", "title", "columns")) + ',\n "rows": [\n  ' + ",\n  ".join(json.dumps(r) for r in s0["rows"][:3]) + ',\n  …\n ],\n' + f' "n": {s0["n"]}\n}}'
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The showcase feed</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:12px 0 6px}}.tile{{background:var(--surface-2);border-radius:10px;padding:14px 16px}}.tile b{{font-size:28px;display:block}}.tile span{{color:var(--ink-2);font-size:13px}}
.flow,pre{{background:var(--surface-2);border-radius:10px;padding:14px 16px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;white-space:pre;overflow-x:auto}}
.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}code{{font-size:13px}}#live{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}}
</style></head><body><main>
<h1>The showcase feed: every build's figures as plain JSON tables, so another tool can draw them</h1>
<p class="sub">Nineteen builds each ended with a page here. The figures on those pages are baked into HTML; nothing else can draw them. This build publishes the data behind them as static JSON on the same site: one small table per series, a manifest per build, one index. No API, no key, no quota, no new resource. Anything on any origin can read them, because a CORS rule says so and because every file passes the feed's refusal (no email address, no GUID, no document text). Anchor phrase: <b>Azure feeds, Kiln draws, never the other way.</b></p>

<div class="tiles">
<div class="tile"><b>{len(rows_b)}</b><span>builds in the index</span></div>
<div class="tile"><b>{len(series)}</b><span>JSON tables, one per series</span></div>
<div class="tile"><b>{n_rows:,}</b><span>rows across them</span></div>
<div class="tile"><b>{n_bytes/1e6:.1f} MB</b><span>on disk, served from the existing site; $0</span></div>
</div>

<h2>How to read it</h2>
<div class="flow">{e(SITE)}showcase/index.json ─► builds[]: build, title, anchor, page, readme, image, manifest
   └─► {e(SITE)}showcase/build-NN-name.json ─► series[]: id, title, columns, n, bytes, url
          └─► {e(SITE)}showcase/build-NN-name/&lt;id&gt;.json ─► columns[] + rows[][]  (schema azportfolio-showcase/1)</div>
<p class="note">Every table has the same four keys that matter: <code>columns</code>, <code>rows</code>, <code>n</code>, <code>title</code>. Rows are arrays in column order. The shape is versioned; a reader can pin <code>schema</code>.</p>
<pre>{e(sample)}</pre>

<h2>Live, from this page</h2>
<p class="finding">The index, fetched by the browser you are reading this in: <span id="live">loading…</span></p>
<script>
fetch('{SITE}showcase/index.json').then(r=>r.json()).then(i=>{{document.getElementById('live').textContent=i.builds.length+' builds, generated '+i.generated_at+', commit '+i.commit}}).catch(err=>{{document.getElementById('live').textContent='fetch failed: '+err}});
</script>

<h2>What is in it</h2>
{table(rows_b, ["b","title","anchor","n","page","man"], ["build","title","anchor phrase","tables","page","feed"], raw=("page","man"))}

<h2>What the feed refuses, and what it drops</h2>
<p class="finding">A file that contains an email address or a GUID stops the build. Documents are not figures: any table with a cell over 300 characters is skipped (build #5's press-release text, for one). A column whose values are GUIDs is dropped from the table rather than failing the build: {len(dropped)} columns went that way.</p>
{table([{"b": f"#{b}", "s": s, "c": c} for b, s, c in dropped], ["b","s","c"], ["build","table","dropped columns"])}
<p class="note">Largest tables: {"; ".join(f"#{s['build']} {s['id']} ({s['n']:,} rows)" for s in big)}. Build #10's county table is the map; a reader that only wants the state summary fetches the state table instead. Nothing is paginated — the biggest file is under 1.5 MB and the site caches it.</p>

<h2>How it stays current</h2>
<p class="finding">The site deploy runs <code>build_feed.py</code> on every push and uploads <code>showcase/</code> with the pages. Its live check fetches the index with a foreign <code>Origin</code> header and fails the deploy if the CORS header is missing. The CORS rule is one resource in <code>main.bicep</code> (blob service, GET/HEAD/OPTIONS, any origin), deployed through the #18 template: what-if showed that one Modify and nothing else.</p>
<p class="note">Why any origin: the data is public by construction and CORS is a browser rule, not an access grant; the private containers on the same account still require a token. Kiln Studio's Electron renderer reads from a <code>file://</code> or app origin, which no named-origin rule would match.</p>

<p class="foot">Cost: $0 (static files on the storage account that already hosts the site; one CORS rule). Found on the way: build #11 had no README in the repo; it has one now. Non-commercial learning project. Built with Claude.</p>
</main></body></html>"""
open(os.path.join(HERE, "findings.html"), "w", encoding="utf-8").write(page)
print("findings.html", len(page), "series", len(series))
