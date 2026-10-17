"""Builds findings.html from data/results.json. Every number computed here; inline SVG."""
import json, html, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "data", "results.json"), encoding="utf-8"))
e = html.escape
ERAS = ["wwii", "korea", "vietnam", "era7590", "gulfwar1", "post911"]
NAME = {"wwii": "World War II", "korea": "Korea", "vietnam": "Vietnam era", "era7590": "May 1975–Jul 1990", "gulfwar1": "Gulf War I (Aug 1990–Aug 2001)", "post911": "Post-9/11"}
SHORT = {"wwii": "WWII", "korea": "Korea", "vietnam": "Vietnam", "era7590": "'75–'90", "gulfwar1": "Gulf War I", "post911": "Post-9/11"}
MEAS = [("female_share", "ref_female", "Women"), ("white_share", "ref_white", "White, non-Hispanic"), ("black_share", "ref_black", "Black"), ("hisp_share", "ref_hisp", "Hispanic"),
        ("born_share", "ref_born", "Born citizens"), ("natur_share", "ref_natur", "Naturalized citizens"), ("noncit_share", "ref_noncit", "Non-citizens"), ("foreign_share", "ref_foreign", "Foreign-born"), ("secondgen_share", "ref_secondgen", "US-born, foreign-born parent(s)"),
        ("lt_hs_share", "ref_lt_hs", "No high-school diploma"), ("ba_share", "ref_ba", "Bachelor's or more")]
CIT = {"born_share", "natur_share", "noncit_share", "foreign_share", "secondgen_share"}
P = {r["era"]: r for r in R["R15_era_pooled"]}
def pct(x, d=1): return "—" if x is None else f"{100*x:.{d}f}%"
def se(p, n): return math.sqrt(max(p * (1 - p), 1e-9) / max(n, 1))
def h(p1, p2): return 2 * math.asin(math.sqrt(min(max(p1, 0), 1))) - 2 * math.asin(math.sqrt(min(max(p2, 0), 1)))
def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None
def cell(era, m, rm):
    r = P[era]; p1, p2 = num(r[m]), num(r[rm])
    if p1 is None or p2 is None: return None
    den = {"female_share": "n_female", "hisp_share": "n_hisp"}.get(m, "n_cit" if m in CIT else None)
    frac = ((num(r[den]) or 0) / r["w"]) if den else 1.0  # share of the cohort's weight that carries the item (citizenship 1994+, women 1988+, Hispanic 1971+)
    n1 = r["n_eff"] * frac
    if n1 < 100: return None
    s = math.sqrt(se(p1, n1) ** 2 + se(p2, r["ref_n"]) ** 2); d = p1 - p2
    return dict(p1=p1, p2=p2, diff=d, lo=d - 1.96 * s, hi=d + 1.96 * s, h=h(p1, p2), idx=(p1 / p2 if p2 else None))

def idx_chart(title, m, rm, lo=0.0, hi=2.0):
    """Representation index by era (1.0 = same share as civilians the same age in the same years), with CI as a bar."""
    W, H, L, Rm, T, B = 460, 230, 54, 16, 28, 34
    def X(i): return L + (W - L - Rm) * (i + 0.5) / len(ERAS)
    def Y(v): return T + (H - T - B) * (1 - (v - lo) / (hi - lo))
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{e(title)}"><text x="{L}" y="16" class="ct">{e(title)}</text>']
    for k in range(5):
        v = lo + (hi - lo) * k / 4; s.append(f'<line x1="{L}" x2="{W-Rm}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/><text x="{L-6}" y="{Y(v)+4:.1f}" class="tick" text-anchor="end">{v:.1f}×</text>')
    s.append(f'<line x1="{L}" x2="{W-Rm}" y1="{Y(1):.1f}" y2="{Y(1):.1f}" class="ref"/><text x="{L+4}" y="{Y(1)+13:.1f}" class="tick">same share as everyone their age</text>')
    for i, era in enumerate(ERAS):
        s.append(f'<text x="{X(i):.1f}" y="{H-14}" class="tick" text-anchor="middle">{e(SHORT[era])}</text>')
        c = cell(era, m, rm)
        if not c or c["idx"] is None: continue
        ilo, ihi = (c["lo"] / c["p2"] + 1, c["hi"] / c["p2"] + 1) if c["p2"] else (c["idx"], c["idx"])
        s.append(f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(min(max(ilo, lo), hi)):.1f}" y2="{Y(min(max(ihi, lo), hi)):.1f}" stroke="var(--series)" stroke-width="2" opacity="0.6"/>')
        s.append(f'<circle cx="{X(i):.1f}" cy="{Y(min(max(c["idx"], lo), hi)):.1f}" r="5" fill="var(--series)" stroke="var(--surface)" stroke-width="2"><title>{e(NAME[era])}: {pct(c["p1"])} vs {pct(c["p2"])} of the population ({100*c["diff"]:+.1f} pts, CI {100*c["lo"]:+.1f} to {100*c["hi"]:+.1f}); index {c["idx"]:.2f}; h {c["h"]:+.2f}</title></circle>')
        s.append(f'<text x="{X(i):.1f}" y="{Y(min(max(c["idx"], lo), hi))-9:.1f}" class="lbl" text-anchor="middle" fill="var(--ink-2)">{c["idx"]:.2f}</text>')
    s.append(f'<text x="{(L+W-Rm)/2:.1f}" y="{H-2}" class="tick" text-anchor="middle">era of service (pooled over the years its veterans were 18–64)</text></svg>'); return "".join(s)

def years_chart(title, m, eras, ymax, fmt=lambda v: f"{100*v:.0f}%"):
    rows = R["R16_era_years"]; W, H, L, Rm, T, B = 940, 250, 54, 90, 28, 34
    pts = {era: [(r["YEAR"], num(r[m])) for r in rows if r["era"] == era and num(r[m]) is not None and r["n_eff"] >= 100] for era in eras}
    civ = [(r["YEAR"], num(r[m])) for r in rows if r["era"] == "population" and num(r[m]) is not None]
    def X(y): return L + (W - L - Rm) * (y - 1968) / (2025 - 1968)
    def Y(v): return T + (H - T - B) * (1 - v / ymax)
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{e(title)}"><text x="{L}" y="16" class="ct">{e(title)}</text>']
    for k in range(5):
        v = ymax * k / 4; s.append(f'<line x1="{L}" x2="{W-Rm}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/><text x="{L-6}" y="{Y(v)+4:.1f}" class="tick" text-anchor="end">{e(fmt(v))}</text>')
    for y in range(1970, 2026, 10): s.append(f'<text x="{X(y):.1f}" y="{H-14}" class="tick" text-anchor="middle">{y}</text>')
    s.append(f'<polyline points="{" ".join(f"{X(y):.1f},{Y(v):.1f}" for y, v in civ)}" fill="none" class="ref" stroke-width="2"/>')
    if civ: s.append(f'<text x="{W-Rm+6}" y="{Y(civ[-1][1])+4:.1f}" class="tick">everyone 18–64</text>')
    COLS = ["#2a78d6", "#c2410c", "#0f8a5f", "#7c3aed", "#b8860b", "#8a8880"]
    for j, era in enumerate(eras):
        p = pts[era]
        if len(p) < 2: continue
        s.append(f'<polyline points="{" ".join(f"{X(y):.1f},{Y(v):.1f}" for y, v in p)}" fill="none" stroke="{COLS[j]}" stroke-width="2"/>')
        s.append(f'<text x="{X(p[-1][0])+5:.1f}" y="{Y(p[-1][1])+4:.1f}" class="lbl" fill="{COLS[j]}">{e(SHORT[era])}</text>')
    s.append("</svg>"); return "".join(s)

def table(rows, cols, head):
    return "<table><thead><tr>" + "".join(f"<th>{e(x)}</th>" for x in head) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{e(str(r.get(c, '')))}</td>" for c in cols) + "</tr>" for r in rows) + "</tbody></table>"

# ---- sentences ----
def s_idx(era, m, rm):
    c = cell(era, m, rm)
    return f"{SHORT[era]} —" if not c else f"{SHORT[era]} {pct(c['p1'])} vs {pct(c['p2'])} (index {c['idx']:.2f}, CI {100*c['lo']:+.1f} to {100*c['hi']:+.1f} pts)"
race_s = ("White non-Hispanic share of each era's veterans against everyone the same age in the same years: " + "; ".join(s_idx(era, "white_share", "ref_white") for era in ERAS) + ". "
          "Black: " + "; ".join(f"{SHORT[era]} {cell(era,'black_share','ref_black')['idx']:.2f}" for era in ERAS if cell(era,'black_share','ref_black')) + ". Hispanic: " + "; ".join(f"{SHORT[era]} {cell(era,'hisp_share','ref_hisp')['idx']:.2f}" for era in ERAS if cell(era,'hisp_share','ref_hisp')) + ".")
women_s = ("Veteran status was asked of men only before 1988, so women are measured from 1988 on — for WWII and Korea that means survivors in their 60s and beyond. Women as a share of each era's veterans: " + "; ".join(f"{SHORT[era]} {pct(cell(era,'female_share','ref_female')['p1'])}" if cell(era,'female_share','ref_female') else f"{SHORT[era]} —" for era in ERAS) + " — against roughly half of the population in every window.")
cit_eras = [era for era in ERAS if cell(era, "noncit_share", "ref_noncit")]
cit_s = ("Citizenship (1994 on, so the older eras are their later survivors): non-citizens are " + "; ".join(f"{SHORT[era]} {pct(cell(era,'noncit_share','ref_noncit')['p1'])} vs {pct(cell(era,'noncit_share','ref_noncit')['p2'])} of the population" for era in cit_eras) +
         ". Naturalized citizens: " + "; ".join(f"{SHORT[era]} {pct(cell(era,'natur_share','ref_natur')['p1'])} vs {pct(cell(era,'natur_share','ref_natur')['p2'])}" for era in cit_eras) +
         ". Foreign-born: " + "; ".join(f"{SHORT[era]} index {cell(era,'foreign_share','ref_foreign')['idx']:.2f}" for era in cit_eras) + "; US-born with a foreign-born parent: " + "; ".join(f"{SHORT[era]} index {cell(era,'secondgen_share','ref_secondgen')['idx']:.2f}" for era in cit_eras) + ".")
edu_s = ("Education: no-diploma share vs the population the same age — " + "; ".join(f"{SHORT[era]} {pct(cell(era,'lt_hs_share','ref_lt_hs')['p1'])} vs {pct(cell(era,'lt_hs_share','ref_lt_hs')['p2'])} (h {cell(era,'lt_hs_share','ref_lt_hs')['h']:+.2f})" for era in ERAS) +
         ". Bachelor's or more — " + "; ".join(f"{SHORT[era]} {pct(cell(era,'ba_share','ref_ba')['p1'])} vs {pct(cell(era,'ba_share','ref_ba')['p2'])}" for era in ERAS) + ".")
multi_s = "From 2006 the survey records up to four periods; the share of each era's veterans who also served in another era: " + "; ".join(f"{SHORT[era]} {pct(P[era]['multi_share'])}" for era in ERAS if max(P[era]['years']) >= 2006) + " (eras whose working-age window ends before 2006 cannot be measured)."

rows = []
for era in ERAS:
    r = P[era]; row = {"era": NAME[era], "years": f"{min(r['years'])}–{max(r['years'])}", "n": f"{r['n']:,}"}
    for m, rm, lab in MEAS:
        c = cell(era, m, rm); row[m] = "—" if not c else f"{pct(c['p1'])} vs {pct(c['p2'])} · {c['idx']:.2f} · {100*c['diff']:+.1f} [{100*c['lo']:+.1f}, {100*c['hi']:+.1f}]"
    rows.append(row)
sizes = {}
for r in R["R18_sizes"]: sizes.setdefault(r["era"], []).append((r["YEAR"], r["n"]))
size_rows = [{"era": NAME.get(era, era), "first": min(v)[0], "last": max(v)[0], "min_n": min(n for _, n in v), "max_n": max(n for _, n in v), "total": sum(n for _, n in v)} for era, v in sizes.items() if era in NAME]

charts = "".join(idx_chart(lab + " — representation index by era", m, rm, 0, 2.2 if m in ("hisp_share","black_share","noncit_share","foreign_share","secondgen_share","natur_share") else 1.6) for m, rm, lab in MEAS if m != "female_share")
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Who was there to serve</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top;white-space:nowrap}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:18px}}svg .ct{{font-size:13px;fill:var(--ink);font-weight:600}}svg .tick{{font-size:11px;fill:var(--ink-3)}}svg .lbl{{font-size:11px;font-weight:600}}svg .grid{{stroke:var(--line)}}svg .ref{{stroke:var(--ink-3);stroke-dasharray:4 4}}
details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}code{{font-size:13px}}
</style></head><body><main>
<h1>Who was there to serve: six eras of veterans against the whole population of the same age at the same time</h1>
<p class="sub">March Current Population Survey, 1968–2025 ({sum(r['total'] for r in size_rows):,} veteran records across the six eras). Each era's veterans are pooled over the years in which they were 18–64 and compared with <b>everyone</b> surveyed in the same years — veterans included — reweighted to the cohort's own age mix, so WWII veterans of 1970 are measured against all 45–55-year-olds of 1970, not against 2025 and not against the minority of men who did not serve. Representation index: share among the era's veterans ÷ share among the population the same age; 1.0 means the same share as everyone their age. Bars are 95% intervals. Anchor phrase: <i>who served, against who was there.</i> This page reports representation; it does not argue who should have served.</p>

<h2>Race and ethnicity</h2>
<p class="finding">{race_s}</p>
<h2>Sex</h2>
<p class="finding">{women_s}</p>
<h2>Citizenship and generation</h2>
<p class="finding">{cit_s}</p>
<h2>Education</h2>
<p class="finding">{edu_s}</p>
<p class="note">{multi_s}</p>
<div class="grid">{charts}</div>

<h2>How each era's composition moved with time</h2>
{years_chart("White non-Hispanic share, 18–64, by survey year", "white_share", ERAS, 1.0)}
{years_chart("Women as a share of veterans, 18–64, by survey year", "female_share", ERAS, 0.25)}
{years_chart("Non-citizen share, 18–64, by survey year (1994 on)", "noncit_share", ERAS, 0.12)}
<p class="note">Lines stop when a cohort's working-age sample falls under an effective 100. An era seen late in its life is its survivors.</p>

<h2>The numbers behind the charts</h2>
{table(rows, ["era","years","n"] + [m for m, _, _ in MEAS], ["era","window","n"] + [lab + " (cohort vs population · index · diff [95% CI])" for _, _, lab in MEAS])}
<details><summary>Sample sizes by era (the honesty table)</summary>{table(size_rows, ["era","first","last","min_n","max_n","total"], ["era","first year","last year","smallest yearly n","largest yearly n","records"])}</details>
<p class="note">Cohort SE from effective n; population SE from the reference count; both design-naive. Citizenship and generation exist from 1994, so for WWII and Korea they describe survivors in their 70s and 80s and are shown for completeness only. Multi-race codes from 2003 fall into "other".</p>

<h2>What this cannot say</h2>
<p class="note">Representation is not selection: a cohort can differ from the population its age because of who volunteered, who was drafted, who was deferred or excluded, who died, who emigrated, and who answers surveys — the survey cannot split those. "Era" is a date range of service, not a deployment; the in-theater cohorts live in builds #15 and #16. The ASEC samples households, so the institutionalised and active-duty populations are absent. Results generated {e(R['generated_at'][:16].replace('T',' '))} UTC from Azure Data Explorer database <code>vets</code> (materialized view <code>era_base_mv</code>); the same tables feed the <a href="https://dataexplorer.azure.com/dashboards">ADX dashboard</a> <code>azportfolio-eras</code>.</p>

<p class="foot">Build #17 of Patrick Neil Bradley's Azure learning portfolio. Data: IPUMS CPS ASEC 1968–2025 (Flood et al., IPUMS, University of Minnesota, doi:10.18128/D030.V12.0 or current). Cost: $0. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-17-five-eras">GitHub</a>.</p>
</main></body></html>"""
open(os.path.join(HERE, "findings.html"), "w", encoding="utf-8").write(page); print("ok", len(page))
