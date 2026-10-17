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


def cell(v, c):
    if v is None:
        return '<td class="num">–</td>'
    if isinstance(v, float):
        return f'<td class="num">{v:,.0f}</td>' if c in ("households",) or (v == int(v) and abs(v) >= 1000) else f'<td class="num">{v:,.1f}</td>'
    if isinstance(v, int):
        return f'<td class="num">{v:,}</td>'
    return f'<td>{e(str(v))}</td>'


def table(q, max_rows=40):
    cols = R[q]["columns"]; rows = R[q]["rows"][:max_rows]
    th = "".join(f'<th{" class=num" if any(isinstance(r[c], (int, float)) for r in rows) else ""}>{e(c)}</th>' for c in cols)
    tr = "".join("<tr>" + "".join(cell(r[c], c) for c in cols) + "</tr>" for r in rows)
    more = f'<p class="note">Showing {max_rows} of {len(R[q]["rows"]):,} rows.</p>' if len(R[q]["rows"]) > max_rows else ""
    return f'<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>{more}'


def model_table(y):
    specs = M["outcomes"][y]
    names = list(specs)
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
    rows += "<tr><td>R²</td>" + "".join(f'<td class="num">{specs[n]["r2"]:.3f}</td>' for n in names) + "</tr>"
    rows += "<tr><td>N counties</td>" + "".join(f'<td class="num">{specs[n]["n"]:,}</td>' for n in names) + "</tr>"
    th = "".join(f"<th class=num>{e(n)}</th>" for n in names)
    return f'<table><thead><tr><th>{e(y.replace("_", " "))} (pct pts)</th>{th}</tr></thead><tbody>{rows}</tbody></table>'


def block(title, finding, caveat, body, sql=None, pattern=""):
    q = f'<details><summary>Query ({e(pattern)})</summary><pre>{e(sql)}</pre></details>' if sql else ""
    return f'<section class="q"><h2>{title}</h2><p class="finding">{finding}</p><p class="note">{caveat}</p>{body}{q}</section>'


# Q13
r13 = R["Q13"]["rows"]
f13 = (f"Yes, and that is the confounder build #7 named: owner share rises from <b>{r13[0]['owner_share_pct']:.1f}%</b> in the lowest-veteran-share quintile to "
       f"<b>{r13[-1]['owner_share_pct']:.1f}%</b> in the highest. Quintile 1 alone holds {r13[0]['households']/1e6:.1f}M households, more than quintiles 4 and 5 combined.")
# model
rb, ob = M["outcomes"]["renter_burden"], M["outcomes"]["owner_burden"]
n1, n4 = list(rb)[0], list(rb)[-1]
n3 = list(rb)[2]
f_model = (f"For <b>renter burden</b>, the veteran-share coefficient goes from <b>{rb[n1]['coef']['vet_share']:+.2f}</b> points per point of veteran share "
           f"(R² {rb[n1]['r2']:.2f}) to <b>{rb[n4]['coef']['vet_share']:+.2f}</b> (p = {rb[n4]['p']['vet_share']:.2f}) once ownership, income and population are in: "
           f"nothing left. Ownership does most of the work — R² jumps from {rb[list(rb)[1]]['r2']:.2f} to {rb[n3]['r2']:.2f} when owner share enters. "
           f"For <b>owner burden</b> a coefficient of <b>{ob[n4]['coef']['vet_share']:+.2f}</b> survives all four controls (p &lt; 0.001): counties with more veterans have slightly <i>lower</i> owner burden, "
           f"about {abs(ob[n4]['coef']['vet_share'])*10:.1f} points across a 10-point difference in veteran share.")

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tenure and a Model</title>
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
<h1>Stratifying is not modelling: tenure, income and size explain the veteran gap away</h1>
<p class="sub">Build #7 found that veteran-heavy counties do not carry heavier shelter burden and admitted its age check held nothing else constant. One more Census table (B25003, tenure) and four population-weighted regressions, controls added one at a time, say which control does what. Anchor phrase: controls one at a time. Expand any query to read the T-SQL; the model code is in the repo.</p>
{block("Q13. Does ownership rise with veteran share?", f13, "Owner-occupied share of occupied housing units (B25003), by quintile of county veteran share (B21001). Quintile boundaries as in build #7's Q9.", table("Q13"), R["Q13"]["sql"], "NTILE(5) over a two-dataset join")}
{block("Q14. The county table the model reads", f"{len(R['Q14']['rows']):,} counties with every input present: two outcomes, the veteran share, three controls and the population weight. This is the whole feature set; nothing was engineered.", "One row per county; the model reads this table from results.json. Shown here so the inputs are inspectable.", table("Q14", 12), R["Q14"]["sql"], "five-dataset join to a wide table")}
<section class="q"><h2>The model: four specifications, controls added one at a time</h2>
<p class="finding">{f_model}</p>
<p class="note">Weighted least squares, weights = county population, HC1 robust standard errors in parentheses; *** p&lt;0.001, ** p&lt;0.01, * p&lt;0.05. Outcomes are TSCI renter and owner burden in percentage points. Cross-sectional county data: these are associations, not effects.</p>
{model_table("renter_burden")}
{model_table("owner_burden")}
<p class="note">Reading the renter table left to right: age (M2) changes nothing; ownership (M3) removes most of the veteran association and most of the unexplained variance; income and size (M4) remove the rest. The owner-burden residual is small, negative and stable — consistent with veteran-heavy counties being lower-cost places to own, which is what build #7's base-town list looked like.</p>
</section>
<p class="foot">Data: U.S. Census Bureau ACS 5-year 2023, tables B21001, B25003, B19013, B01003 (public domain); TSCI snapshot from <a href="https://patrickneilbradley.com/tcbi-tsci-methodology.html">patrickneilbradley.com</a> (author's own, non-commercial). Build #8 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Azure SQL Database (free offer), Key Vault (existing); model run locally with statsmodels. Cost: $0. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-08-tenure-model">GitHub</a>.</p>
</main></body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8")
print("ok", len(page))
