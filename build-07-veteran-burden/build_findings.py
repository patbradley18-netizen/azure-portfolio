"""Builds findings.html from data/results.json. Every number in every sentence is computed from the result rows, not typed."""
import html
import json
from pathlib import Path

HERE = Path(__file__).parent
R = json.loads((HERE / "data/results.json").read_text(encoding="utf-8"))
e = html.escape
MONEY = {"median_income", "rent", "home_value"}
BIG = {"adults", "veterans", "nonveterans", "population"}


def cell(v, c):
    if v is None:
        return '<td class="num">–</td>'
    if isinstance(v, float):
        if c in MONEY:
            return f'<td class="num">${v:,.0f}</td>'
        if c in BIG or v == int(v) and abs(v) >= 1000:
            return f'<td class="num">{v:,.0f}</td>'
        return f'<td class="num">{v:,.1f}</td>'
    if isinstance(v, int):
        return f'<td class="num">{v:,}</td>'
    return f'<td>{e(str(v))}</td>'


def table(q, max_rows=40):
    cols = R[q]["columns"]
    rows = R[q]["rows"][:max_rows]
    th = "".join(f'<th{" class=num" if any(isinstance(r[c], (int, float)) for r in rows) else ""}>{e(c)}</th>' for c in cols)
    tr = "".join("<tr>" + "".join(cell(r[c], c) for c in cols) + "</tr>" for r in rows)
    return f'<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


def block(q, finding, caveat, pattern):
    return f'''<section class="q">
<h2>{e(q)}. {e(R[q]["question"])}</h2>
<p class="finding">{finding}</p>
<p class="note">{caveat}</p>
{table(q)}
<details><summary>Query ({e(pattern)})</summary><pre>{e(R[q]["sql"])}</pre></details>
</section>'''


# Q8
r8 = R["Q8"]["rows"]
tot_a = sum(r["adults"] for r in r8); tot_v = sum(r["veterans"] for r in r8)
hi = next(r for r in r8 if r["band"].startswith("4"))
f8 = (f"Veterans are <b>{100*tot_v/tot_a:.1f}%</b> of {tot_a/1e6:.0f}M adult civilians. {hi['counties']} counties are 12%+ veteran, but they hold only "
      f"{100*hi['adults']/tot_a:.1f}% of adults; the under-5% band ({r8[0]['counties']} counties) holds {100*r8[0]['adults']/tot_a:.0f}% — the big metros.")
# Q9
r9 = R["Q9"]["rows"]
q1, q5 = r9[0], r9[-1]
mid = r9[1:]
f9 = (f"<b>No.</b> The lowest-veteran-share quintile carries the heaviest burden: renter {q1['renter_burden_pct']:.1f}%, owner {q1['owner_burden_pct']:.1f}%, "
      f"on rent of ${q1['rent']:,.0f} and home values of ${q1['home_value']:,.0f}. Quintiles 2–5 sit in a {min(r['renter_burden_pct'] for r in mid):.1f}–{max(r['renter_burden_pct'] for r in mid):.1f}% band "
      f"for renters and {min(r['owner_burden_pct'] for r in mid):.1f}–{max(r['owner_burden_pct'] for r in mid):.1f}% for owners. Veteran share does not track heavier shelter cost; the first quintile is the metro effect.")
# Q10
r10 = R["Q10"]["rows"]
above = sum(1 for r in r10 if r["renter_burden_pct"] >= q5["renter_burden_pct"])
f10 = (f"The top 20 are military-base counties (Onslow/Lejeune, Okaloosa/Eglin, Bell/Hood, Cumberland/Bragg…) at {r10[-1]['vet_share_pct']:.1f}–{r10[0]['vet_share_pct']:.1f}% veteran. "
       f"Their renter burden runs {min(r['renter_burden_pct'] for r in r10):.1f}–{max(r['renter_burden_pct'] for r in r10):.1f}%; {above} of 20 are above their quintile's average of {q5['renter_burden_pct']:.1f}%. "
       f"Ordinary burden, extraordinary veteran share: base towns, not retirement towns.")
# Q11
r11 = R["Q11"]["rows"]
old_v = sum(r["pct_of_veterans"] for r in r11 if r["age_band"] in ("65-74", "75+"))
old_n = sum(r["pct_of_nonveterans"] for r in r11 if r["age_band"] in ("65-74", "75+"))
f11 = (f"<b>{old_v:.0f}% of veterans are 65 or older</b> against {old_n:.0f}% of nonveterans; only {r11[0]['pct_of_veterans']:.1f}% of veterans are under 35 versus {r11[0]['pct_of_nonveterans']:.1f}%. "
       f"Any county-level veteran comparison is partly an age comparison, and older households are likelier to own outright — which lowers measured owner burden.")
# Q12
r12 = R["Q12"]["rows"]
by_age = {}
for r in r12:
    by_age.setdefault(r["age_tercile"], []).append(r)
lows = [by_age[a][0]["renter_burden_pct"] for a in sorted(by_age)]
highs = [by_age[a][-1]["renter_burden_pct"] for a in sorted(by_age)]
f12 = (f"Holding the 65+ share roughly constant, the <b>lowest</b>-veteran-share tercile is the most burdened in all three age groups "
       f"(renter {lows[0]:.1f}%, {lows[1]:.1f}%, {lows[2]:.1f}% vs {highs[0]:.1f}%, {highs[1]:.1f}%, {highs[2]:.1f}% for the highest). Age does not rescue the hypothesis: "
       f"at county level, more veterans means slightly lower shelter burden, not higher.")

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Veteran Burden Cut</title>
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
<h1>Do veteran-heavy counties carry heavier shelter costs? No — and here is the check that says so</h1>
<p class="sub">Build #6 built a county cost-of-living warehouse and had to admit it could not make the veteran cut. One more table (Census ACS 5-year 2023, B21001, civilian veterans by sex and age) closes that gap. Five T-SQL questions, including the one that tests whether the answer is just age. Anchor phrase: the join Q6 couldn't make. Expand any query to read the T-SQL.</p>
{block("Q8", f8, "B21001 counts civilian adults 18+ by veteran status; active-duty personnel are excluded by definition, which matters for base counties in Q10. Bands are the curator's.", "conditional-aggregation pivot, CASE banding")}
{block("Q9", f9, "Quintiles of county veteran share (equal county counts, unequal population). Burdens, income, rent and home value are population-weighted from the TSCI snapshot and the raw Census population. Quintile 1 is where the large metros sit, which is the whole story.", "NTILE(5) window, three-dataset join, pop-weighted averages")}
{block("Q10", f10, "Minimum 10,000 adults to keep tiny counties out. TSCI composite >100 means above the national shelter nut. Veteran share here counts people who have left service and stayed near the base.", "TOP 20 with a threshold, three-way JOIN")}
{block("Q11", f11, "Same table, both sexes summed per age band, national totals. This is the build #2 caveat (veterans are older) measured instead of asserted.", "CTE lookup table + correlated subqueries + window share")}
{block("Q12", f12, "Counties split into terciles of 65+ share, then into veteran-share terciles within each. A stratified comparison, not a model: it removes the coarse age effect and nothing else. Income, urbanity and housing tenure remain unaddressed.", "nested NTILE(3) with PARTITION BY, pop-weighted burden")}
<p class="foot">Data: U.S. Census Bureau ACS 5-year 2023, tables B21001, B01003 (public domain); TSCI snapshot from <a href="https://patrickneilbradley.com/tcbi-tsci-methodology.html">patrickneilbradley.com</a> (author's own, non-commercial). Build #7 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Azure SQL Database (free offer), Key Vault (existing). Cost: $0. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-07-veteran-burden">GitHub</a>.</p>
</main></body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8")
print("ok", len(page))
