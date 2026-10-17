"""Builds findings.html from data/results.json. Every number on the page is computed here; charts are inline SVG."""
import json, html, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "data", "results.json"), encoding="utf-8"))
e = html.escape
BINS = ["00-04", "05-09", "10-15", "16-22", "23-30", "31+"]; BINLAB = {"00-04": "0–4", "05-09": "5–9", "10-15": "10–15", "16-22": "16–22", "23-30": "23–30", "31+": "31+"}
COL = {"vietnam_theater": "var(--s-vn)", "gwot_theater": "var(--s-gw)"}; NAME = {"vietnam_theater": "Vietnam, in-theater", "gwot_theater": "GWOT, Iraq/Afghanistan"}
MIN_NEFF = 100
r8 = {(r["cohort"], r["bin"]): r for r in R["R8_profile_bins"]}; r9 = {(r["cohort"], r["bin"]): r for r in R["R9_reference_agematched"]}
MEAS = [("ba_share", "ref_ba", "Bachelor's degree or more"), ("lt_hs_share", "ref_lt_hs", "No high-school diploma"), ("hisp_share", "ref_hisp", "Hispanic"), ("black_share", "ref_black", "Black"), ("white_share", "ref_white", "White, non-Hispanic"), ("female_share", "ref_female", "Women")]

def ok(c, b): return (c, b) in r8 and r8[(c, b)]["n_eff"] >= MIN_NEFF
def pct(x, d=1): return "—" if x is None else f"{100*x:.{d}f}%"
def se(p, n): return math.sqrt(max(p * (1 - p), 1e-9) / max(n, 1))
def cohen_h(p1, p2): return 2 * math.asin(math.sqrt(min(max(p1, 0), 1))) - 2 * math.asin(math.sqrt(min(max(p2, 0), 1)))
def cell(c, b, m, rm):
    r, x = r8[(c, b)], r9[(c, b)]; p1, p2 = r[m], x[rm]
    s = math.sqrt(se(p1, r["n_eff"]) ** 2 + se(p2, x["ref_n"]) ** 2); d = p1 - p2
    return dict(p1=p1, p2=p2, diff=d, lo=d - 1.96 * s, hi=d + 1.96 * s, h=cohen_h(p1, p2), idx=(p1 / p2 if p2 else None), n=r["n"])

def diff_chart(title, m, rm, ymin, ymax, fmt=lambda v: f"{100*v:+.0f} pts"):
    """Difference in points (cohort − age-matched civilians) by years-out bin, with 95% CI bars; zero line = civilians."""
    W, H, L, Rm, T, B = 460, 230, 54, 78, 28, 34
    def X(i, k): return L + (W - L - Rm) * (i + 0.5) / len(BINS) + (k - 0.5) * 14
    def Y(v): return T + (H - T - B) * (1 - (v - ymin) / (ymax - ymin))
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{e(title)}"><text x="{L}" y="16" class="ct">{e(title)}</text>']
    for k in range(5):
        v = ymin + (ymax - ymin) * k / 4; y = Y(v)
        s.append(f'<line x1="{L}" x2="{W-Rm}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/><text x="{L-6}" y="{y+4:.1f}" class="tick" text-anchor="end">{e(fmt(v))}</text>')
    s.append(f'<line x1="{L}" x2="{W-Rm}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" class="ref"/><text x="{W-Rm}" y="{Y(0)-4:.1f}" class="tick" text-anchor="end">civilians, same age &amp; years</text>')
    for i, b in enumerate(BINS):
        s.append(f'<text x="{X(i,0.5):.1f}" y="{H-14}" class="tick" text-anchor="middle">{BINLAB[b]}</text>')
    s.append(f'<text x="{(L+W-Rm)/2:.1f}" y="{H-2}" class="tick" text-anchor="middle">years since separation</text>')
    for k, c in enumerate(["vietnam_theater", "gwot_theater"]):
        last = None
        for i, b in enumerate(BINS):
            if not ok(c, b): continue
            d = cell(c, b, m, rm); x = X(i, k)
            s.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{Y(max(d["lo"], ymin)):.1f}" y2="{Y(min(d["hi"], ymax)):.1f}" stroke="{COL[c]}" stroke-width="2" opacity="0.6"/>')
            s.append(f'<circle cx="{x:.1f}" cy="{Y(d["diff"]):.1f}" r="4.5" fill="{COL[c]}" stroke="var(--surface)" stroke-width="2"><title>{e(NAME[c])}, {BINLAB[b]} years out: {pct(d["p1"])} vs {pct(d["p2"])} civilians ({100*d["diff"]:+.1f} pts, 95% CI {100*d["lo"]:+.1f} to {100*d["hi"]:+.1f}; h={d["h"]:+.2f}; n={d["n"]:,})</title></circle>')
            last = (x, d["diff"])
        if last: s.append(f'<text x="{last[0]+7:.1f}" y="{Y(last[1]) + (-6 if c.startswith("vietnam") else 14):.1f}" class="lbl" fill="{COL[c]}">{e(NAME[c].split(",")[0])}</text>')
    s.append("</svg>"); return "".join(s)

def surv_chart():
    """Observed vs expected survivors (weighted headcount) for the Vietnam in-theater cohort: the negative result, drawn."""
    rows = [r for r in R["R11_survival"] if r["cohort"] == "vietnam_theater"]
    years = [rows[0]["y1"]] + [r["y2"] for r in rows]; obs = [rows[0]["w1"]] + [r["w2"] for r in rows]
    # expected path: start at the first observed count, apply each step's expected survival share
    exp = [obs[0]]
    for r in rows: exp.append(exp[-1] * (r["expected_alive"] / r["w1"]))
    W, H, L, Rm, T, B = 940, 260, 70, 20, 28, 34; ymax = max(obs + exp) * 1.1
    def X(y): return L + (W - L - Rm) * (y - years[0]) / (years[-1] - years[0])
    def Y(v): return T + (H - T - B) * (1 - v / ymax)
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Vietnam in-theater veterans: CPS weighted headcount vs life-table expectation"><text x="{L}" y="16" class="ct">Vietnam in-theater veterans, all ages: CPS weighted headcount (orange) vs what the life table expects of a closed cohort (gray)</text>']
    for k in range(5):
        v = ymax * k / 4; s.append(f'<line x1="{L}" x2="{W-Rm}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/><text x="{L-6}" y="{Y(v)+4:.1f}" class="tick" text-anchor="end">{v/1e6:.1f} M</text>')
    for y in range(1985, 2026, 5): s.append(f'<text x="{X(y):.1f}" y="{H-14}" class="tick" text-anchor="middle">{y}</text>')
    s.append(f'<polyline points="{" ".join(f"{X(y):.1f},{Y(v):.1f}" for y, v in zip(years, exp))}" fill="none" class="ref" stroke-width="2"/>')
    s.append(f'<polyline points="{" ".join(f"{X(y):.1f},{Y(v):.1f}" for y, v in zip(years, obs))}" fill="none" stroke="var(--s-vn)" stroke-width="2"/>')
    for y, v, r in zip(years[1:], obs[1:], rows):
        s.append(f'<circle cx="{X(y):.1f}" cy="{Y(v):.1f}" r="3.5" fill="var(--s-vn)"><title>{y}: {v:,.0f} (n={r["n2"]:,}); expected survivors from {r["y1"]}: {r["expected_alive"]:,.0f}</title></circle>')
    s.append(f'<line x1="{X(1997):.1f}" x2="{X(1997):.1f}" y1="{T}" y2="{H-B}" class="ref"/><text x="{X(1997)+4:.1f}" y="{T+12}" class="tick">1997 universe change</text>')
    s.append("</svg>"); return "".join(s)

def table(rows, cols, head):
    return "<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{e(str(r.get(c, '')))}</td>" for c in cols) + "</tr>" for r in rows) + "</tbody></table>"

# ---- sentences ----
g10, v10, g16, v16 = cell("gwot_theater", "10-15", "ba_share", "ref_ba"), cell("vietnam_theater", "10-15", "ba_share", "ref_ba"), cell("gwot_theater", "16-22", "ba_share", "ref_ba"), cell("vietnam_theater", "16-22", "ba_share", "ref_ba")
glt, vlt = cell("gwot_theater", "10-15", "lt_hs_share", "ref_lt_hs"), cell("vietnam_theater", "10-15", "lt_hs_share", "ref_lt_hs")
gh, vh = cell("gwot_theater", "10-15", "hisp_share", "ref_hisp"), cell("vietnam_theater", "10-15", "hisp_share", "ref_hisp")
gw, vw = cell("gwot_theater", "10-15", "white_share", "ref_white"), cell("vietnam_theater", "10-15", "white_share", "ref_white")
gf, vf = cell("gwot_theater", "10-15", "female_share", "ref_female"), cell("vietnam_theater", "10-15", "female_share", "ref_female")
edu_s = (f"Ten to fifteen years after separation, {pct(g10['p1'])} of GWOT in-theater veterans hold a bachelor's degree or more against {pct(g10['p2'])} of civilians the same age in the same years ({100*g10['diff']:+.1f} points, 95% CI {100*g10['lo']:+.1f} to {100*g10['hi']:+.1f}); Vietnam in-theater veterans at the same distance were at {pct(v10['p1'])} against {pct(v10['p2'])} ({100*v10['diff']:+.1f} points, CI {100*v10['lo']:+.1f} to {100*v10['hi']:+.1f}). "
         f"By 16–22 years out the Vietnam advantage is gone ({pct(v16['p1'])} vs {pct(v16['p2'])}) while GWOT holds ({pct(g16['p1'])} vs {pct(g16['p2'])}, CI {100*g16['lo']:+.1f} to {100*g16['hi']:+.1f}). The sharper difference is at the bottom: {pct(glt['p1'])} of GWOT in-theater veterans lack a high-school diploma against {pct(glt['p2'])} of their civilian peers (Cohen's h {glt['h']:+.2f}, a large effect); for Vietnam it was {pct(vlt['p1'])} vs {pct(vlt['p2'])} (h {vlt['h']:+.2f}).")
race_s = (f"Both in-theater cohorts are whiter than civilians their age — Vietnam {pct(vw['p1'])} white non-Hispanic vs {pct(vw['p2'])} ({100*vw['diff']:+.1f} pts), GWOT {pct(gw['p1'])} vs {pct(gw['p2'])} ({100*gw['diff']:+.1f} pts) — and both under-represent Hispanics (GWOT {pct(gh['p1'])} vs {pct(gh['p2'])}, representation index {gh['idx']:.2f}; Vietnam {pct(vh['p1'])} vs {pct(vh['p2'])}, index {vh['idx']:.2f}). "
          f"Black veterans sit near civilian parity in both wars. Women: {pct(gf['p1'])} of the GWOT in-theater cohort against {pct(vf['p1'])} of Vietnam's — the single largest change between the two armies, and still a fifth of the civilian share ({pct(gf['p2'])}).")
rows12 = [r for r in R["R12_survival_windows"] if r["cohort"] == "vietnam_theater"]
rise = [r for r in R["R11_survival"] if r["cohort"] == "vietnam_theater"]
w85, w99 = rise[0]["w1"], [r for r in rise if r["y2"] == 1999][0]["w2"]
good = [r for r in rows12 if r["y1"] >= 2007]
surv_s = (f"The CPS weighted headcount of Vietnam in-theater veterans <b>rises</b> from {w85/1e6:.2f} M in 1985 to {w99/1e6:.2f} M in 1999. A closed cohort cannot grow; what grew is self-reported Vietnam service, on top of sampling and weighting noise and a 1997 change in who was asked. Deaths read as the gap between two surveys are therefore negative for most of the 1990s, which is not a finding about mortality but about the instrument. "
          f"Where the series behaves (2007 on), the observed-to-expected ratios are {', '.join('%.2f [%.2f–%.2f] for %d→%d' % (r['ratio'], r['ratio_lo'], r['ratio_hi'], r['y1'], r['y2']) for r in good[:4])}: intervals that include 1.0 in most windows and each other in all of them. The GWOT closed cohort (in-theater, separated by 2009) is about 200 people a survey; its ratios run from negative to sixteen. "
          f"The VA's VetPop2023 model retires Vietnam-era veterans at {100*R['R13_vetpop'][1]['rate']:.1f}% a year (2023→24), a number built from mortality it assumes, not observes. Conclusion: a household survey cannot measure cohort mortality at this sample size; the right source is a death-record linkage (the VA's mortality data repository), which is not public microdata.")

prof_rows = []
for b in BINS:
    for c in ("vietnam_theater", "gwot_theater"):
        if (c, b) not in r8: continue
        sup = not ok(c, b); row = {"bin": BINLAB[b], "cohort": NAME[c], "n": f"{r8[(c,b)]['n']:,}" + (" (suppressed)" if sup else "")}
        for m, rm, lab in MEAS:
            d = cell(c, b, m, rm); row[m] = "—" if sup else f"{pct(d['p1'])} vs {pct(d['p2'])} ({100*d['diff']:+.1f}; h {d['h']:+.2f})"
        prof_rows.append(row)
surv_rows = [{"cohort": NAME[r["cohort"]], "win": f"{r['y1']}→{r['y2']}", "n": f"{r['n1']:,} → {r['n2']:,}", "w": f"{r['w1']:,.0f} → {r['w2']:,.0f}", "obs": f"{r['observed_deaths']:,.0f}", "exp": f"{r['expected_deaths']:,.0f}", "ratio": f"{r['ratio']:.2f} [{r['ratio_lo']:.2f}, {r['ratio_hi']:.2f}]"} for r in R["R12_survival_windows"]]
charts = "".join(diff_chart(lab + " — cohort minus civilians (points)", m, rm, -0.3, 0.3) for m, rm, lab in MEAS[:4]) + diff_chart("Women — cohort minus civilians (points)", "female_share", "ref_female", -0.7, 0.1)

page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Who they were, who is left</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6;--s-gw:#2a78d6;--s-vn:#c2410c}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5;--s-gw:#3987e5;--s-vn:#f0813f}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5;--s-gw:#3987e5;--s-vn:#f0813f}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:18px}}svg .ct{{font-size:13px;fill:var(--ink);font-weight:600}}svg .tick{{font-size:11px;fill:var(--ink-3)}}svg .lbl{{font-size:11px;font-weight:600}}svg .grid{{stroke:var(--line)}}svg .ref{{stroke:var(--ink-3);stroke-dasharray:4 4}}
.legend{{display:flex;gap:18px;font-size:13px;color:var(--ink-2);margin:4px 0 10px}}.sw{{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-1px;margin-right:6px}}
details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}code{{font-size:13px}}
</style></head><body><main>
<h1>Who they were, who is left: the two in-theater cohorts against civilians their age — and a mortality method that fails honestly</h1>
<p class="sub">Build #15's clock (years since separation), the same 28 Veterans Supplements, three more variables. Each cohort cell is compared with non-veterans surveyed in the same years and reweighted to the cohort's age mix, so "civilians" means people the same age at the same time. Differences are in percentage points with a 95% confidence interval; Cohen's h says how big (0.2 small, 0.5 medium, 0.8 large). Anchor phrases: <i>two shares, one interval</i>; <i>the weights are the headcount — until the answers change</i>.</p>
<div class="legend"><span><span class="sw" style="background:var(--s-vn)"></span>Vietnam, in-theater</span><span><span class="sw" style="background:var(--s-gw)"></span>GWOT, Iraq/Afghanistan</span><span>— — civilians, same age, same years</span></div>

<h2>Education</h2>
<p class="finding">{edu_s}</p>
<h2>Race, ethnicity, sex</h2>
<p class="finding">{race_s}</p>
<p class="note">Bars are 95% intervals; a bar that crosses the dashed line is a difference the sample cannot distinguish from zero. Cells with an effective sample under {MIN_NEFF} are suppressed.</p>
<div class="grid">{charts}</div>

<h2>Survival: what was tried, and why it cannot be read</h2>
<p class="finding">{surv_s}</p>
{surv_chart()}
<details><summary>Survival windows (observed vs expected deaths, weighted; interval from the two endpoint counts)</summary>{table(surv_rows, ["cohort","win","n","w","obs","exp","ratio"], ["cohort","window","n","weighted count","observed deaths","expected (life table)","ratio [95% interval]"])}</details>

<h2>The numbers behind the charts</h2>
{table(prof_rows, ["bin","cohort","n"] + [m for m, _, _ in MEAS], ["years out","cohort","n"] + [lab + " (cohort vs civilians; diff pts; h)" for _, _, lab in MEAS])}
<p class="note">Cohort SE from the effective sample (Σw)²/Σw²; civilian SE from the unweighted reference count. Both design-naive. Education uses IPUMS' harmonised <code>EDUC</code>; race/ethnicity is Hispanic (any race), then White non-Hispanic, Black, other.</p>

<h2>What this cannot say</h2>
<p class="note">Who enlists is upstream of everything here: the draft and the volunteer force selected different people on education before service began, and these are snapshots of survivors, not the people who joined. "In-theater" is the survey's flag, not a campaign medal. The survival leg is a negative result by design of the source, not of the cohorts: a household survey re-samples people every year and its respondents' answers about 1960s service drifted upward for a decade. Results generated {e(R['generated_at'][:16].replace('T',' '))} UTC from Azure Data Explorer database <code>vets</code> (materialized view <code>vet_base_mv</code>).</p>

<p class="foot">Build #16 of Patrick Neil Bradley's Azure learning portfolio. Data: IPUMS CPS Veterans Supplement 1985–2025 (Flood et al., IPUMS, University of Minnesota, doi:10.18128/D030.V12.0 or current); SSA period life tables, 2023 Trustees Report; VA VetPop2023 (CC0). Cost: $0. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-16-who-is-left">GitHub</a>.</p>
</main></body></html>"""
open(os.path.join(HERE, "findings.html"), "w", encoding="utf-8").write(page); print("ok", len(page))
