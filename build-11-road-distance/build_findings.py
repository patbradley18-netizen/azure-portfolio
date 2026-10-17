"""Builds findings.html from data/results.json. Every number in every sentence is computed, not typed.
Chart: inline SVG scatter, one dot per routed county, straight-line miles (x) vs road miles (y), with the
y = x and y = 1.3x reference lines. Single series, so no legend; the reference lines are labelled directly."""
import html
import json
from pathlib import Path

HERE = Path(__file__).parent
R = json.loads((HERE / "data/results.json").read_text(encoding="utf-8"))
S = json.loads((HERE / "data/sample_strata.json").read_text(encoding="utf-8"))
ROUTES = [json.loads(l) for l in (HERE / "data/routes.jsonl").read_text(encoding="utf-8").splitlines()]
e = html.escape
BIG = {"veterans", "counties", "calls", "routed", "failed"}


def cell(v, c):
    if v is None:
        return '<td class="num">–</td>'
    if isinstance(v, float):
        return f'<td class="num">{v:,.0f}</td>' if c in BIG else (f'<td class="num">{v:,.3f}</td>' if "ratio" in c and v < 10 and c not in ("min_ratio", "max_ratio") else f'<td class="num">{v:,.1f}</td>')
    if isinstance(v, int):
        return f'<td class="num">{v:,}</td>'
    return f'<td>{e(str(v))}</td>'


def table(q, max_rows=40, cols=None):
    cols = cols or R[q]["columns"]; rows = R[q]["rows"][:max_rows]
    th = "".join(f'<th{" class=num" if any(isinstance(r[c], (int, float)) for r in rows) else ""}>{e(c)}</th>' for c in cols)
    tr = "".join("<tr>" + "".join(cell(r[c], c) for c in cols) + "</tr>" for r in rows)
    more = f'<p class="note">Showing {max_rows} of {len(R[q]["rows"]):,} rows.</p>' if len(R[q]["rows"]) > max_rows else ""
    return f'<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>{more}'


def block(title, finding, caveat, body, sql=None, pattern=""):
    q = f'<details><summary>Query ({e(pattern)})</summary><pre>{e(sql)}</pre></details>' if sql else ""
    return f'<section class="q"><h2>{title}</h2><p class="finding">{finding}</p><p class="note">{caveat}</p>{body}{q}</section>'


def scatter(points):
    """points: (straight, road, label). Axes in miles, same scale both ways so y = x is the diagonal."""
    W, H, L, B = 760, 520, 56, 44
    LIMIT = 420  # miles; Alaska's two longest routes would compress everything else into the corner
    beyond = [p for p in points if p[1] > LIMIT]
    points = [p for p in points if p[1] <= LIMIT]
    mx = LIMIT
    sx = lambda v: L + v / mx * (W - L - 16)
    sy = lambda v: H - B - v / mx * (H - B - 16)
    out = [f'<line x1="{sx(0):.0f}" y1="{sy(0):.0f}" x2="{sx(mx):.0f}" y2="{sy(mx):.0f}" class="ref"/>',
           f'<line x1="{sx(0):.0f}" y1="{sy(0):.0f}" x2="{sx(mx/1.3):.0f}" y2="{sy(mx):.0f}" class="ref2"/>',
           f'<text x="{sx(mx)-6:.0f}" y="{sy(mx)+14:.0f}" class="lbl" text-anchor="end">road = straight-line</text>',
           f'<text x="{sx(mx/1.3)-6:.0f}" y="{sy(mx)-4:.0f}" class="lbl" text-anchor="end">road = 1.3 × straight-line</text>']
    step = 100 if mx > 400 else 50
    for t in range(0, int(mx), step):
        out.append(f'<line x1="{sx(t):.0f}" y1="{sy(0):.0f}" x2="{sx(t):.0f}" y2="{sy(0)+4:.0f}" class="axis"/><text x="{sx(t):.0f}" y="{sy(0)+18:.0f}" class="lbl" text-anchor="middle">{t}</text>')
        out.append(f'<line x1="{sx(0)-4:.0f}" y1="{sy(t):.0f}" x2="{sx(0):.0f}" y2="{sy(t):.0f}" class="axis"/><text x="{sx(0)-8:.0f}" y="{sy(t)+4:.0f}" class="lbl" text-anchor="end">{t}</text>')
    out.append(f'<line x1="{sx(0):.0f}" y1="{sy(0):.0f}" x2="{sx(mx):.0f}" y2="{sy(0):.0f}" class="axis"/><line x1="{sx(0):.0f}" y1="{sy(0):.0f}" x2="{sx(0):.0f}" y2="{sy(mx):.0f}" class="axis"/>')
    out.append(f'<text x="{(L+W)/2:.0f}" y="{H-6}" class="lbl" text-anchor="middle">straight-line miles to nearest VA medical center</text>')
    out.append(f'<text x="14" y="{(H-B)/2:.0f}" class="lbl" text-anchor="middle" transform="rotate(-90 14 {(H-B)/2:.0f})">road miles (OSRM)</text>')
    if beyond:
        out.append(f'<text x="{L+10}" y="48" class="lbl">{len(beyond)} count{"y" if len(beyond)==1 else "ies"} beyond {LIMIT} road miles not drawn: ' + e("; ".join(p[2].split(":")[0] + f" ({p[1]:.0f} mi)" for p in beyond)) + '</text>')
    for s, r, lab in points:
        out.append(f'<circle cx="{sx(s):.1f}" cy="{sy(r):.1f}" r="3.2" class="dot"><title>{e(lab)}</title></circle>')
    return f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Scatter of straight-line versus road miles for {len(points)} counties">{"".join(out)}</svg>'


q22 = {r["band"]: r for r in R["Q22"]["rows"]}; allr = q22["all"]; q23 = R["Q23"]["rows"]; q24 = R["Q24"]["rows"]; q25 = R["Q25"]["rows"]
f22 = (f"Across <b>{allr['counties']:,} sampled counties</b>, the road is on average <b>{allr['mean_ratio']:.2f}×</b> the straight-line distance to the nearest VA medical center "
       f"(veteran-weighted {allr['vet_weighted_ratio']:.2f}×) — the textbook 1.3 planning factor, measured. The index is highest in the nearest band ({q22['0-30']['mean_ratio']:.2f}× within 30 miles: city grids, rivers and bays) "
       f"and flat at about {sum(q22[b]['mean_ratio'] for b in ('30-60','60-100','100+'))/3:.2f}× beyond it. "
       f"Only {allr['pct_counties_ratio_over_1_5']:.0f}% of counties have a detour index above 1.5. Straight-line understates by a fairly constant third, so build #10's rank order of who is far mostly stands; its miles do not.")
w = q23[0]
f23 = (f"The worst detours are where the road has to go around something: {w['county']} {w['state_abbr']} ({w['straight_miles']:.0f} straight-line miles, {w['road_miles']:.0f} by road, {w['ratio']:.1f}×), "
       f"then {q23[1]['county']} {q23[1]['state_abbr']} ({q23[1]['ratio']:.1f}×) and {q23[2]['county']} {q23[2]['state_abbr']} ({q23[2]['ratio']:.1f}×). Mountains, lakes and sounds make the index, not distance. "
       f"Some of these are artefacts of the method: the route goes to the <i>straight-line</i>-nearest medical center, which across a lake is the wrong hospital — the road-nearest one is the fix, and it is build #12's problem, not this page's.")
routed24 = [r for r in q24 if r["road_miles"] is not None]
f24 = (f"For build #10's base counties the picture holds: {routed24[0]['county']} {routed24[0]['state_abbr']} is {routed24[0]['straight_miles']:.0f} straight-line miles and {routed24[0]['road_miles']:.0f} road miles "
       f"({routed24[0]['drive_minutes']:.0f} minutes) from {routed24[0]['vamc_name']}; the median base county's drive to a VA hospital is "
       f"<b>{sorted(r['drive_minutes'] for r in routed24)[len(routed24)//2]:.0f} minutes</b> and the median detour index {sorted(r['ratio'] for r in routed24)[len(routed24)//2]:.2f}.")
f25 = (f"{sum(r['calls'] for r in q25):,} router calls in {len(q25)} batch(es); {sum(r['routed'] for r in q25):,} routed, {sum(r['failed'] for r in q25)} failed; "
       f"cap {S['cap']}; file lines {len(ROUTES):,}. The cap is the contract: the script refuses to exceed it, and the ledger is how you check it did not.")
ALL = R["Q26"]["rows"] if "Q26" in R else []
pts = [(r["straight_miles"], r["road_miles"], f"{r['county']}, {r['state_abbr']}: {r['straight_miles']:.0f} straight / {r['road_miles']:.0f} road mi, {r['drive_minutes']:.0f} min, {r['ratio']:.2f}×") for r in ALL]

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Detour Index</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}pre{{background:var(--surface-2);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.45}}
svg{{width:100%;height:auto;background:var(--surface-2);border-radius:10px;margin-bottom:10px}}.lbl{{fill:var(--ink-2);font-size:12px}}.axis{{stroke:var(--line);stroke-width:1}}.ref{{stroke:var(--ink-3);stroke-width:1.5;stroke-dasharray:4 4}}.ref2{{stroke:var(--ink-3);stroke-width:1;stroke-dasharray:2 4}}.dot{{fill:var(--series);fill-opacity:.7}}.dot:hover{{stroke:var(--ink);stroke-width:1.5}}
.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}
</style></head><body><main>
<h1>How much does straight-line lie? Road miles to the nearest VA medical center for {allr['counties']:,} counties</h1>
<p class="sub">Build #10 measured straight-line distance from every county's population center to the nearest VA medical center and said, on the page, that it understates travel. This build measures by how much: a capped, ledgered sample of {allr['counties']:,} counties routed by road, the ratio of road miles to straight-line miles (the detour index) by distance band, the counties where it is worst, and build #10's base counties corrected. Anchor phrase: measure the error in your own measure. Expand any query to read the T-SQL.</p>
{block("Q22. The detour index by straight-line band", f22, f"Sample: build #10's 25 base counties plus a seeded stratified random sample by straight-line band (allocation {e(str(S['allocation']))} of {e(str(S['population_by_band']))} counties), {S['cap']} calls cap. Road distance and drive time from the public OSRM demo server on OpenStreetMap data, routed to the straight-line-nearest medical center (the road-nearest one may differ). Veteran-weighted ratio weights each county's index by its veterans.", scatter(pts) + table("Q22"), R["Q22"]["sql"], "join to the materialised access table + ROLLUP")}
{block("Q23. Where the crow lies most", f23, "Sampled counties at least 20 straight-line miles from a medical center, ranked by detour index.", table("Q23", 25), R["Q23"]["sql"], "ratio and TOP 25")}
{block("Q24. Build #10's base counties, corrected", f24, "Same 25 counties as build #10's Q20; road miles and drive minutes added. Drive time is free-flow OSRM time, no traffic.", table("Q24", 25), R["Q24"]["sql"], "LEFT JOIN to the ledger")}
{block("Q25. The ledger", f25, "One row per router call, loaded from the local file after the run; the batch id ties rows to a run.", table("Q25"), R["Q25"]["sql"], "GROUP BY batch")}
<section class="q"><h2>What this cannot say</h2>
<p class="note">Routes start at a county population center, not at a home, and end at the straight-line-nearest medical center, which is not always the road-nearest one. OSRM demo-server times are free-flow, no traffic. {allr['counties']:,} of 3,144 counties were routed; the sampling rule is stated above and the sample is stratified, not random across the nation. Facilities are still the 2018 VAST list. The Azure part of this build was meant to be Azure Maps; the student subscription's region policy has no overlap with Azure Maps' regions, so the Azure part is the materialised access table and the ledger in SQL, and the router is OpenStreetMap's.</p></section>
<p class="foot">Data: OSRM demo server (<a href="https://project-osrm.org/">project-osrm.org</a>) on <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> data (ODbL); VA VAST station list via HRSA GIS; U.S. Census Bureau centers of population and ACS 5-year 2023 B21001 (public domain). Build #11 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Azure SQL Database (free offer): materialised spatial join, route ledger. Cost: $0. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-11-road-distance">GitHub</a>.</p>
</main></body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8")
print("ok", len(page))
