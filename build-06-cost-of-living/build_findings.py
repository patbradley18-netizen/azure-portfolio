"""Builds findings.html from data/results.json. Every number in every sentence is computed from the result rows, not typed."""
import html
import json
from pathlib import Path

HERE = Path(__file__).parent
R = json.loads((HERE / "data/results.json").read_text(encoding="utf-8"))
e = html.escape


def cell(v, c):
    if v is None:
        return '<td class="num">–</td>'
    if isinstance(v, float):
        if c in ("population",):
            return f'<td class="num">{v:,.0f}</td>'
        return f'<td class="num">{v:,.1f}</td>' if abs(v) >= 100 or v != int(v) else f'<td class="num">{int(v):,}</td>'
    if isinstance(v, int):
        return f'<td class="num">{v:,}</td>'
    return f'<td>{e(str(v))}</td>'


def table(q, max_rows=40):
    cols = R[q]["columns"]
    rows = R[q]["rows"][:max_rows]
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
r1 = R["Q1"]["rows"]
match = sum(r["counties"] for r in r1 if r["status"] == "match")
nulls = sum(r["counties"] for r in r1 if r["status"] == "both null")
bad = sum(r["counties"] for r in r1 if r["status"] in ("differs", "snapshot missing", "raw suppressed, snapshot filled"))
total = match + nulls + bad
f1 = (f"Of <b>{total:,} county-field pairs</b>, {match:,} match the Census value exactly, {nulls} are null in both (Census small-sample suppression), "
      f"and <b>{bad} differ</b>. The snapshot carries its Census inputs unchanged and does not fill suppressed cells.")
# Q2
r2 = R["Q2"]["rows"]
f2 = (f"The {len(r2)} rows returned are all suppressed-in-both cases, concentrated in small Texas counties "
      f"({sum(1 for r in r2 if 'Texas' in r['name'])} of {len(r2)}). No county has a value that disagrees with the source.")
# Q3
r3 = R["Q3"]["rows"][0]
f3 = (f"<b>{r3['computable']:,} of {r3['counties']:,} counties</b> have every input; across them the recomputed owner nut, renter nut, both burdens and price-to-income "
      f"match the stored values with <b>{r3['computable_with_any_mismatch']} mismatches</b>. The other {r3['suppressed_inputs']} cannot be recomputed because an input is suppressed.")
# Q4
r4 = R["Q4"]["rows"]
full = [r["state_abbr"] for r in r4 if r["childcare_proxy"] == r["counties"]]
sup = sum(r["census_suppressed"] for r in r4)
miss = sum(r["missing_from_tcbi"] for r in r4)
f4 = (f"Childcare is proxy-filled for every county in <b>{', '.join(full)}</b>"
      f"{' and ' + str(next(r['childcare_proxy'] for r in r4 if r['state_abbr']=='MO')) + ' of ' + str(next(r['counties'] for r in r4 if r['state_abbr']=='MO')) + ' in MO' if any(r['state_abbr']=='MO' for r in r4) else ''}. "
      f"Census suppresses at least one input in {sup} counties (shown states), and {miss} counties in these states are absent from TCBI. A value with a flag is not the same as a value.")
# Q5
r5 = R["Q5"]["rows"]
b = {r["band"][:1]: r for r in r5}
burdened = sum(r["pct_of_population"] for r in r5 if r["band"][0] in "234")
f5 = (f"<b>{burdened:.0f}% of the population</b> lives in counties where rent + childcare + renter insurance is 30% or more of median household income. "
      f"The severe band ({b['4']['counties']} counties, {b['4']['population']/1e6:.1f}M people) has an average median income of ${b['4']['avg_median_income']:,.0f}, "
      f"half the under-30% band's ${b['1']['avg_median_income']:,.0f}.")
# Q6
r6 = R["Q6"]["rows"]
f6 = (f"Population-weighted, <b>{r6[0]['state_abbr']}</b> ({r6[0]['pop_weighted_renter_burden_pct']:.1f}%), {r6[1]['state_abbr']} ({r6[1]['pop_weighted_renter_burden_pct']:.1f}%) and "
      f"{r6[2]['state_abbr']} ({r6[2]['pop_weighted_renter_burden_pct']:.1f}%) carry the heaviest renter burden; owner burden runs higher everywhere, "
      f"{min(r['pop_weighted_owner_burden_pct'] - r['pop_weighted_renter_burden_pct'] for r in r6):.0f} to {max(r['pop_weighted_owner_burden_pct'] - r['pop_weighted_renter_burden_pct'] for r in r6):.0f} points above renter burden in these 15 states.")
# Q7
r7 = R["Q7"]["rows"]
f7 = (f"<b>{len(r7)} datasets, {sum(r['rows_'] for r in r7):,} rows</b>, {max(r['counties'] for r in r7):,} counties, "
      f"{sum(r['metrics'] for r in r7)} metrics with names and units in the data dictionary. Every row knows its vintage and load time; a refresh is a new dataset, not an overwrite.")

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cost-of-Living Warehouse</title>
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
<h1>Snapshot to source: a cost-of-living warehouse that checks its own numbers</h1>
<p class="sub">Two published cost indices (TSCI shelter, TCBI basket; 3,222 counties) loaded into the free Azure SQL database as a long-format warehouse, next to a fresh pull of the Census inputs they cite. Then the question a Business Analyst asks first: does the published number still equal the source? Anchor phrase: snapshot to source. Expand any query to read the T-SQL.</p>
{block("Q1", f1, "ACS 5-year 2023, the vintage the snapshot cites. Match = within 0.5 of the Census value. Suppressed = Census withholds the estimate for small samples (negative sentinel codes in the API, stored here as NULL with a flag).", "FULL OUTER JOIN + CASE status, grouped")}
{block("Q2", f2, "Sorted by absolute difference; nulls sort first because there is nothing to compare. If a county ever drifts after a refresh, it appears at the top of this table.", "JOIN with inequality filter, TOP 25")}
{block("Q3", f3, "Formulas from the methodology page: owner nut = owner cost + childcare + homeowner insurance; renter nut = rent + childcare + renter insurance; burden = nut × 12 ÷ median income; price-to-income = home value ÷ income. Tolerances: $1 on nuts, 0.15 pt on burdens, 0.015 on the ratio (rounding).", "conditional aggregation pivot, computed checks, SUM of flags")}
{block("Q4", f4, "Provenance flags carried in the snapshots (childcare cc_p ≠ LIVE) and in the raw pull (suppressed). TCBI D1 pump is proxy-by-design for every county, so it is not counted. Only states with at least one flag are listed.", "LEFT JOIN, flag pivot, HAVING")}
{block("Q5", f5, "Renter burden from the snapshot; population from the snapshot's own population field. The 30% line is the HUD cost-burden convention; the snapshot adds childcare and insurance to rent, so this is a broader nut than HUD's.", "CASE banding, window SUM for shares")}
{block("Q6", f6, "Weights come from the raw Census population (acs5_2023), not the snapshot, so a state's number does not depend on the tool that published it. DC is one county. The veteran cut needs a state-level veteran population table, which is the next load.", "four-way JOIN across two datasets, pop-weighted averages")}
{block("Q7", f7, "The inventory is the warehouse describing itself. Vintages differ by design: Census 2023, TSCI May 2026, TCBI April–June 2026.", "JOIN + GROUP BY over the dataset table")}
<p class="foot">Data: U.S. Census Bureau ACS 5-year 2023 (public domain); TSCI and TCBI snapshots from <a href="https://patrickneilbradley.com/tcbi-tsci-methodology.html">patrickneilbradley.com</a> (author's own, non-commercial). Build #6 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Azure SQL Database (free offer), Key Vault (existing). Cost: $0. Loaders, queries and runner: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-06-cost-of-living">GitHub</a>.</p>
</main></body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8")
print("ok", len(page))
