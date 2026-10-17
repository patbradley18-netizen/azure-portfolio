"""Builds findings.html from data/results.json and data/model.json. Every number in every sentence is computed, not typed."""
import html
import json
from pathlib import Path

HERE = Path(__file__).parent
R = json.loads((HERE / "data/results.json").read_text(encoding="utf-8"))
M = json.loads((HERE / "data/model.json").read_text(encoding="utf-8"))
e = html.escape
LABEL = {"const": "intercept", "vet_share": "veteran share (pt)", "share_65plus": "65+ share (pt)", "owner_share": "owner share (pt)",
         "log_income": "log median income", "log_pop": "log population"}
BIG = {"renter_households", "not_computed", "pop", "income"}


def cell(v, c):
    if v is None:
        return '<td class="num">–</td>'
    if isinstance(v, float):
        return f'<td class="num">{v:,.0f}</td>' if c in BIG or (v == int(v) and abs(v) >= 1000) else f'<td class="num">{v:,.1f}</td>'
    if isinstance(v, int):
        return f'<td class="num">{v:,}</td>'
    return f'<td>{e(str(v))}</td>'


def table(q, max_rows=40):
    cols = R[q]["columns"]; rows = R[q]["rows"][:max_rows]
    th = "".join(f'<th{" class=num" if any(isinstance(r[c], (int, float)) for r in rows) else ""}>{e(c)}</th>' for c in cols)
    tr = "".join("<tr>" + "".join(cell(r[c], c) for c in cols) + "</tr>" for r in rows)
    more = f'<p class="note">Showing {max_rows} of {len(R[q]["rows"]):,} rows.</p>' if len(R[q]["rows"]) > max_rows else ""
    return f'<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>{more}'


def model_table(y, title):
    specs = M["outcomes"][y]; names = list(specs)
    rows = ""
    for k in ("vet_share", "share_65plus", "owner_share", "log_income", "log_pop", "const"):
        cells = ""
        for n in names:
            s = specs[n]
            if k in s["coef"]:
                star = "***" if s["p"][k] < 0.001 else "**" if s["p"][k] < 0.01 else "*" if s["p"][k] < 0.05 else ""
                cells += f'<td class="num">{s["coef"][k]:+.3f}{star}<br><span class="se">({s["se"][k]:.3f})</span></td>'
            else:
                cells += '<td class="num">–</td>'
        rows += f"<tr><td>{LABEL[k]}</td>{cells}</tr>"
    rows += "<tr><td>state fixed effects</td>" + "".join(f'<td class="num">{"yes (" + str(M["state_fe_count"]) + ")" if "fixed" in n else "no"}</td>' for n in names) + "</tr>"
    rows += "<tr><td>R²</td>" + "".join(f'<td class="num">{specs[n]["r2"]:.3f}</td>' for n in names) + "</tr>"
    rows += "<tr><td>N counties</td>" + "".join(f'<td class="num">{specs[n]["n"]:,}</td>' for n in names) + "</tr>"
    th = "".join(f"<th class=num>{e(n)}</th>" for n in names)
    return f'<table><thead><tr><th>{e(title)}</th>{th}</tr></thead><tbody>{rows}</tbody></table>'


def block(title, finding, caveat, body, sql=None, pattern=""):
    q = f'<details><summary>Query ({e(pattern)})</summary><pre>{e(sql)}</pre></details>' if sql else ""
    return f'<section class="q"><h2>{title}</h2><p class="finding">{finding}</p><p class="note">{caveat}</p>{body}{q}</section>'


# Q15
r15 = R["Q15"]["rows"]; us = r15[0]; states = r15[1:]
la = next(r for r in states if r["geo"] == "LA")
f15 = (f"Nationally <b>{us['burdened_30plus_pct']:.1f}%</b> of renter households pay 30% or more of income in rent and <b>{us['severe_50plus_pct']:.1f}%</b> pay half or more. "
       f"Use the wrong denominator — include the {us['not_computed']/1e6:.1f}M households with no cash rent or no income — and the headline drops to {us['burdened_wrong_denominator_pct']:.1f}%; "
       f"in Louisiana ({la['geo']}) the gap is {la['burdened_30plus_pct'] - la['burdened_wrong_denominator_pct']:.1f} points. {states[0]['geo']} ({states[0]['burdened_30plus_pct']:.1f}%), {states[1]['geo']} and {states[2]['geo']} lead.")
# Q16
r16 = R["Q16"]["rows"]
f16 = (f"With the right outcome the quintiles are nearly flat: {r16[0]['burdened_30plus_pct']:.1f}% burdened in the lowest-veteran-share quintile against "
       f"{min(r['burdened_30plus_pct'] for r in r16[1:]):.1f}–{max(r['burdened_30plus_pct'] for r in r16[1:]):.1f}% in the other four; severe burden {r16[0]['severe_50plus_pct']:.1f}% vs "
       f"{min(r['severe_50plus_pct'] for r in r16[1:]):.1f}–{max(r['severe_50plus_pct'] for r in r16[1:]):.1f}%. The metro gap that build #7 saw in TSCI's county nut is mostly a measurement artefact.")
# model
b, s = M["outcomes"]["burdened_30plus_pct"], M["outcomes"]["severe_50plus_pct"]
n1, n4, n5 = list(b)[0], list(b)[3], list(b)[4]
cmp = M["outcomes"]["tsci_renter_burden (build #8 outcome, same counties)"]["M4 + log income, log population"]
f_model = (f"For the share of renter households <b>cost-burdened (30%+)</b>, the veteran-share coefficient is {b[n1]['coef']['vet_share']:+.2f} raw and "
           f"<b>{b[n5]['coef']['vet_share']:+.2f}</b> (p = {b[n5]['p']['vet_share']:.2f}) with all controls and state fixed effects: nothing. "
           f"For <b>severe burden (50%+)</b> a coefficient of <b>{s[n5]['coef']['vet_share']:+.2f}</b> survives everything (p &lt; 0.001): about {abs(s[n5]['coef']['vet_share'])*10:.1f} points fewer severely burdened renter households "
           f"across a 10-point difference in veteran share. State fixed effects lift R² from {b[n4]['r2']:.2f} to {b[n5]['r2']:.2f}; states explain more of renter burden than every county control combined.")

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Right Outcome</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}.se{{color:var(--ink-3);font-size:11px}}
details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}pre{{background:var(--surface-2);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.45}}
.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}
</style></head><body><main>
<h1>Measure the renter, not the county: the right outcome, the right denominator, and state fixed effects</h1>
<p class="sub">Builds #7 and #8 used a county cost index as the renter outcome. Census publishes the real thing — gross rent as a share of renter household income, in bands (B25070). This build turns the bands into a rate with the denominator handled explicitly, re-asks the veteran question with that outcome, and adds state fixed effects. Anchor phrase: the right outcome. Expand any query to read the T-SQL.</p>
{block("Q15. From the bands to a rate", f15, "Burdened = bands 30% and above; severe = 50% or more; denominator = total renter households minus “not computed” (no cash rent, or zero/negative income). The last column shows what the wrong denominator would print. Puerto Rico excluded (no state code in the warehouse).", table("Q15", 20), R["Q15"]["sql"], "band arithmetic + GROUP BY ROLLUP")}
{block("Q16. The build #7 question, with the right outcome", f16, "Quintiles of county veteran share as in builds #7–#8; shares are renter-household-weighted within each quintile.", table("Q16"), R["Q16"]["sql"], "NTILE(5), two-dataset join")}
{block("Q17. Feature table v2", f"{len(R['Q17']['rows']):,} counties with at least 100 renter households with a computed ratio; outcome, TSCI comparison column, veteran share, three controls, state, and the renter-household weight.", "Counties with fewer than 100 computed renter households are dropped: a rate on 40 households is noise.", table("Q17", 10), R["Q17"]["sql"], "six-dataset join to a wide table")}
<section class="q"><h2>The model: builds #8's sequence, the right outcome, then state fixed effects</h2>
<p class="finding">{f_model}</p>
<p class="note">Weighted least squares, weights = renter households with a computed ratio, HC1 robust standard errors; *** p&lt;0.001, ** p&lt;0.01, * p&lt;0.05. M5 adds {M["state_fe_count"]} state dummies (coefficients not shown). Same counties, same weights, build #8's TSCI outcome under M4 gives a veteran-share coefficient of {cmp['coef']['vet_share']:+.3f} (p = {cmp['p']['vet_share']:.2f}) — the two measures agree on the headline and disagree on what else matters. Associations, not effects.</p>
{model_table("burdened_30plus_pct", "renter households paying 30%+ (pct pts)")}
{model_table("severe_50plus_pct", "renter households paying 50%+ (pct pts)")}
<p class="note">What state fixed effects do: they compare counties only with other counties in the same state, so anything that varies by state — rent law, housing supply, wages — is removed. What they cannot do: anything that varies within a state and is not in the model. The thread ends here unless a new question appears; four builds on one question is enough.</p>
</section>
<p class="foot">Data: U.S. Census Bureau ACS 5-year 2023, tables B25070, B25003, B21001, B19013, B01003 (public domain); TSCI snapshot from <a href="https://patrickneilbradley.com/tcbi-tsci-methodology.html">patrickneilbradley.com</a> (author's own, non-commercial). Build #9 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Azure SQL Database (free offer), Key Vault (existing); model run locally with statsmodels. Cost: $0. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-09-renter-burden">GitHub</a>.</p>
</main></body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8")
print("ok", len(page))
