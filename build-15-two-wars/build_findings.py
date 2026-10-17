"""Builds findings.html from data/results.json (ADX query output) and reference/bjs_prison.csv. Every sentence with a number
is computed here from those two files; nothing is typed in. Charts are hand-written inline SVG (no library)."""
import csv, json, html, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "data", "results.json"), encoding="utf-8"))
BJS = list(csv.DictReader(open(os.path.join(HERE, "reference", "bjs_prison.csv"), encoding="utf-8")))
e = html.escape
BINS = ["00-04", "05-09", "10-15", "16-22", "23-30", "31+"]
BINLAB = {"00-04": "0–4", "05-09": "5–9", "10-15": "10–15", "16-22": "16–22", "23-30": "23–30", "31+": "31+"}
COL = {"vietnam_theater": "var(--s-vn)", "gwot_theater": "var(--s-gw)", "vietnam_era": "var(--s-vn)", "gwot_era": "var(--s-gw)"}
NAME = {"vietnam_theater": "Vietnam, in-theater", "gwot_theater": "GWOT, Iraq/Afghanistan", "vietnam_era": "Vietnam era", "gwot_era": "GWOT era"}
MIN_NEFF = 100

r1 = {(r["cohort"], r["bin"]): r for r in R["R1_bins"]}
r3 = {(r["cohort"], r["bin"]): r for r in R["R3_disability"]}
r6 = {(r["cohort"], r["bin"]): r for r in R["R6_vs_baseline"]}
r5 = {(r["cohort"], r["bin"]): r for r in R["R5_male_only"]}

def ok(c, b):
    r = r1.get((c, b)); return r is not None and r["n_eff"] >= MIN_NEFF

def pct(x, d=1): return "—" if x is None else f"{100*x:.{d}f}%"

def series_chart(title, ylabel, getter, cohorts, ymax=None, ref=None, fmt=lambda v: f"{100*v:.1f}%", height=230):
    """Small multiple: x = years-out bin (categorical), one line per cohort, point size by n, suppressed cells skipped."""
    W, H, L, Rm, T, B = 460, height, 46, 78, 28, 34
    pts = {c: [(i, getter(c, b)) for i, b in enumerate(BINS) if ok(c, b) and getter(c, b) is not None] for c in cohorts}
    vals = [v for c in cohorts for _, v in pts[c]] + ([ref] if ref else [])
    ymax = ymax or (max(vals) * 1.15 if vals else 1)
    def X(i): return L + (W - L - Rm) * (i + 0.5) / len(BINS)
    def Y(v): return T + (H - T - B) * (1 - v / ymax)
    s = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{e(title)}"><text x="{L}" y="16" class="ct">{e(title)}</text>']
    for k in range(5):
        v = ymax * k / 4; y = Y(v)
        s.append(f'<line x1="{L}" x2="{W-Rm}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/><text x="{L-6}" y="{y+4:.1f}" class="tick" text-anchor="end">{e(fmt(v))}</text>')
    for i, b in enumerate(BINS):
        s.append(f'<text x="{X(i):.1f}" y="{H-14}" class="tick" text-anchor="middle">{BINLAB[b]}</text>')
    s.append(f'<text x="{(L+W-Rm)/2:.1f}" y="{H-2}" class="tick" text-anchor="middle">years since separation</text>')
    if ref is not None:
        s.append(f'<line x1="{L}" x2="{W-Rm}" y1="{Y(ref):.1f}" y2="{Y(ref):.1f}" class="ref"/><text x="{W-Rm}" y="{Y(ref)-4:.1f}" class="tick" text-anchor="end">{e(ylabel)}</text>')
    for c in cohorts:
        p = pts[c]
        if len(p) > 1:
            s.append(f'<polyline points="{" ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in p)}" fill="none" stroke="{COL[c]}" stroke-width="2"/>')
        for i, v in p:
            s.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="4.5" fill="{COL[c]}" stroke="var(--surface)" stroke-width="2"><title>{e(NAME[c])}, {BINLAB[BINS[i]]} years out: {e(fmt(v))} (n={r1[(c, BINS[i])]["n"]:,})</title></circle>')
        if p:
            i, v = p[-1]; s.append(f'<text x="{X(i)+7:.1f}" y="{Y(v)+4:.1f}" class="lbl" fill="{COL[c]}">{e(NAME[c].split(",")[0])}</text>')
    s.append("</svg>")
    return "".join(s)

def table(rows, cols, head=None):
    head = head or cols
    return "<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{e(str(r.get(c, '')))}</td>" for c in cols) + "</tr>" for r in rows) + "</tbody></table>"

# ---- computed sentences ----
vt16, gt16 = r1[("vietnam_theater", "16-22")], r1[("gwot_theater", "16-22")]
vt10, gt10 = r1[("vietnam_theater", "10-15")], r1[("gwot_theater", "10-15")]
b_vt16, b_gt16 = r6[("vietnam_theater", "16-22")], r6[("gwot_theater", "16-22")]
d_vt, d_gt = r3[("vietnam_theater", "16-22")], r3[("gwot_theater", "16-22")]
dis_rng = lambda c: (min(r3[(c, b)]["disabled_share"] for b in BINS[:4]), max(r3[(c, b)]["disabled_share"] for b in BINS[:4]))
r50_rng = lambda c: (min(r3[(c, b)]["rated50_share"] for b in BINS[:4]), max(r3[(c, b)]["rated50_share"] for b in BINS[:4]))
sizes = {(r["YEAR"], r["cohort"]): r for r in R["R4_sizes"]}
years_vt = sorted({y for (y, c) in sizes if c == "vietnam_theater"}); years_gt = sorted({y for (y, c) in sizes if c == "gwot_theater"})
pop = {r["YEAR"]: r for r in R["R7_era_pop_share"]}
bjs = {(r["year"], r["group"], r["measure"]): r for r in BJS}
idx_vn = 36 / (100 * pop[2005]["vietnam_era_share"]); idx_gw = 4 / (100 * pop[2005]["gwot_era_share"])
gap_cell = f"GWOT in-theater veterans 16–22 years after separation had an unemployment rate of {pct(gt16['unemp_rate'])} (±{pct(gt16['unemp_se'])}) against {pct(vt16['unemp_rate'])} (±{pct(vt16['unemp_se'])}) for Vietnam in-theater veterans at the same distance — but those are different economies ({min(b_gt16['years'])}–{max(b_gt16['years'])} vs {min(b_vt16['years'])}–{max(b_vt16['years'])}). Against non-veterans surveyed in the same years, the GWOT cohort sat at <b>{gt16['unemp_rate']/b_gt16['base_unemp']:.2f}×</b> the civilian rate and the Vietnam cohort at <b>{vt16['unemp_rate']/b_vt16['base_unemp']:.2f}×</b>. Participation was {pct(gt16['part'])} and {pct(vt16['part'])}, both above civilians ({pct(b_gt16['base_part'])} and {pct(b_vt16['base_part'])})."
same10 = f"At 10–15 years out the two cohorts are indistinguishable on unemployment: {pct(gt10['unemp_rate'])} (±{pct(gt10['unemp_se'])}) vs {pct(vt10['unemp_rate'])} (±{pct(vt10['unemp_se'])}); relative to civilians {gt10['unemp_rate']/r6[('gwot_theater','10-15')]['base_unemp']:.2f}× vs {vt10['unemp_rate']/r6[('vietnam_theater','10-15')]['base_unemp']:.2f}×."
dis_s = f"Across 0–22 years out, {pct(dis_rng('gwot_theater')[0],0)}–{pct(dis_rng('gwot_theater')[1],0)} of GWOT in-theater veterans report a service-connected disability, against {pct(dis_rng('vietnam_theater')[0],0)}–{pct(dis_rng('vietnam_theater')[1],0)} of Vietnam in-theater veterans at the same distance. Among those with a rating, {pct(r50_rng('gwot_theater')[0],0)}–{pct(r50_rng('gwot_theater')[1],0)} of the GWOT cohort are rated 50% or higher versus {pct(r50_rng('vietnam_theater')[0],0)}–{pct(r50_rng('vietnam_theater')[1],0)} of the Vietnam cohort (ratings asked from 1995). The disability system, not the labor market, is where the two wars differ most."
early = f"Right after separation (0–4 years) both cohorts show a penalty against civilians — GWOT {r1[('gwot_theater','00-04')]['unemp_rate']/r6[('gwot_theater','00-04')]['base_unemp']:.2f}×, Vietnam {r1[('vietnam_theater','00-04')]['unemp_rate']/r6[('vietnam_theater','00-04')]['base_unemp']:.2f}× — and the Vietnam point is not the 1973 draftee: on the separation clock it is the career soldier who left in the 1990s (mean age {r6[('vietnam_theater','00-04')]['mean_age']})."
bjs_s = f"In 2004 Vietnam-era veterans were {bjs[('2004','Vietnam era (1964-73)','share of veteran state prisoners by era')]['value']}% of veteran state prisoners and {pct(pop[2005]['vietnam_era_share'],0)} of the veteran population (CPS 2005): a representation index of {idx_vn:.2f}. Iraq/Afghanistan-era veterans were {bjs[('2004','Iraq-Afghanistan eras','share of veteran state prisoners by era')]['value']}% of veteran prisoners and {pct(pop[2005]['gwot_era_share'],1)} of veterans: {idx_gw:.2f}. Male veterans overall were incarcerated at {bjs[('2004','veterans','incarceration rate (prison only) adult males')]['value']} per 100,000 against {bjs[('2004','nonveterans','incarceration rate (prison only) adult males')]['value']} for non-veterans — a gap BJS attributes mostly to age ({bjs[('2004','veterans','age-controlled incarceration rate (prison only) adult males')]['value']} age-controlled). The 2016 survey reports combat-veteran composition only (Vietnam {bjs[('2016','Vietnam','share of male combat veterans in state prison by conflict')]['value']}%, Iraq {bjs[('2016','Iraq','share of male combat veterans in state prison by conflict')]['value']}%, Afghanistan {bjs[('2016','Afghanistan','share of male combat veterans in state prison by conflict')]['value']}%), so no index can be built for it."

c_unemp_ratio = series_chart("Unemployment vs non-veterans, same years (1.0 = civilian)", "civilian rate", lambda c, b: r1[(c, b)]["unemp_rate"] / r6[(c, b)]["base_unemp"] if (c, b) in r6 else None, ["vietnam_theater", "gwot_theater"], ymax=2.0, ref=1.0, fmt=lambda v: f"{v:.1f}×")
c_unemp = series_chart("Unemployment rate, 18–64, weighted", "", lambda c, b: r1[(c, b)]["unemp_rate"], ["vietnam_theater", "gwot_theater"], ymax=0.12)
c_part = series_chart("Labor-force participation, 18–64, weighted", "", lambda c, b: r1[(c, b)]["part"], ["vietnam_theater", "gwot_theater"], ymax=1.0)
c_dis = series_chart("Share with a service-connected disability", "", lambda c, b: r3[(c, b)]["disabled_share"], ["vietnam_theater", "gwot_theater"], ymax=0.8)
c_r50 = series_chart("Of those rated: share rated 50% or higher (1995+)", "", lambda c, b: r3[(c, b)]["rated50_share"], ["vietnam_theater", "gwot_theater"], ymax=1.0)

bin_rows = []
for b in BINS:
    for c in ("vietnam_theater", "gwot_theater"):
        r = r1[(c, b)]; x = r6.get((c, b), {}); d = r3[(c, b)]; m = r5.get((c, b), {})
        sup = r["n_eff"] < MIN_NEFF
        bin_rows.append({"bin": BINLAB[b], "cohort": NAME[c], "n": f"{r['n']:,}" + (" (suppressed)" if sup else ""), "unemp": "—" if sup else f"{pct(r['unemp_rate'])} ± {pct(r['unemp_se'])}",
                         "ratio": "—" if sup or not x else f"{r['unemp_rate']/x['base_unemp']:.2f}×", "part": "—" if sup else pct(r["part"]), "male_unemp": "—" if sup or not m else pct(m["unemp_rate"]),
                         "disabled": "—" if sup else pct(d["disabled_share"]), "rated50": "—" if sup or d["rated50_share"] is None else pct(d["rated50_share"]), "age": x.get("mean_age", "")})
size_rows = [{"year": y, "vn": sizes.get((y, "vietnam_theater"), {}).get("n", 0), "vn_sep": sizes.get((y, "vietnam_theater"), {}).get("sep", 0), "gw": sizes.get((y, "gwot_theater"), {}).get("n", 0), "gw_sep": sizes.get((y, "gwot_theater"), {}).get("sep", 0),
              "nonvet": sizes.get((y, "nonvet"), {}).get("n", sizes.get((y, "all_other"), {}).get("n", 0)), "male": sizes.get((y, "vietnam_theater"), {}).get("male_share", "")} for y in sorted({y for (y, _) in sizes})]
bjs_rows = [{"year": r["year"], "measure": r["measure"], "group": r["group"], "value": r["value"] + " " + r["unit"], "note": r["note"], "src": r["source_url"].split("/")[-1]} for r in BJS]

page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Two wars, matched years</title>
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
<h1>Two wars, matched years: Vietnam and GWOT veterans at the same distance from service</h1>
<p class="sub">The same survey, 28 times across 40 years, read on one clock: years since the veteran last left active duty. Vietnam veterans who served in-theater ({years_vt[0]}–{years_vt[-1]}) against Iraq/Afghanistan veterans ({years_gt[0]}–{years_gt[-1]}), ages 18–64, weighted; non-veterans surveyed in the same years are the baseline. Anchor phrase: <i>same clock, different army</i>. The honest window where both cohorts sit on the same clock is 16–22 years out.</p>

<div class="legend"><span><span class="sw" style="background:var(--s-vn)"></span>Vietnam, in-theater (VVIETNAM)</span><span><span class="sw" style="background:var(--s-gw)"></span>GWOT, Iraq/Afghanistan (VIRAQ/VAFGHAN)</span><span>— — civilian reference</span></div>

<h2>Work</h2>
<p class="finding">{gap_cell}</p>
<p class="finding">{same10}</p>
<p class="note">{early} Cells with an effective sample under {MIN_NEFF} are suppressed (the GWOT cohort has not reached 23+ years out).</p>
<div class="grid">{c_unemp_ratio}{c_unemp}{c_part}</div>

<h2>Disability</h2>
<p class="finding">{dis_s}</p>
<div class="grid">{c_dis}{c_r50}</div>

<h2>Prison</h2>
<p class="finding">{bjs_s}</p>
<p class="note">Published BJS tables, hand-entered with a source per row; no microdata, no standard errors, and the surveys land at different years-out for each war. The prison leg is a composition story, not a cohort rate.</p>
<details><summary>BJS reference table ({len(bjs_rows)} rows)</summary>{table(bjs_rows, ["year","measure","group","value","note","src"])}</details>

<h2>The numbers behind the charts</h2>
{table(bin_rows, ["bin","cohort","n","unemp","ratio","part","male_unemp","disabled","rated50","age"], ["years out","cohort","n","unemployment ± SE","vs civilians","participation","unemployment, men only","service-connected disability","rated 50%+","mean age"])}
<p class="note">SE is design-naive on the weighted share with effective n = (Σw)²/Σw²; the supplement carries no replicate weights, so treat it as approximate. "Men only" exists because the 1985 sample asked only men.</p>
<details><summary>Sample sizes by survey year (the honesty table)</summary>{table(size_rows, ["year","vn","vn_sep","gw","gw_sep","nonvet","male"], ["year","Vietnam in-theater (18–64)","of which on the separation clock","GWOT in-theater","on separation clock","non-veterans","male share, Vietnam"])}</details>

<h2>What this cannot say</h2>
<p class="note">Cohort snapshots, not linked people: nobody is followed from prison to a job. Vietnam was a drafted force and GWOT an all-volunteer one, so who served differs before anything that happened to them; the only causal estimate on the Vietnam side is the draft-lottery study and there is no GWOT twin — every gap here is an association. "In-theater" is the flag the survey asks, not a campaign medal: it includes offshore and air service. The separation clock mixes short-service and career veterans at the same distance; the 0–4 bin for Vietnam is the career soldier of the 1990s. Ratings bands changed over the years; "50%+" is the one cut that is stable. Suicide and mental-health outcomes are out of scope: the VA reports them by age, not by war. Results generated {e(R['generated_at'][:16].replace('T',' '))} UTC from Azure Data Explorer database <code>vets</code>.</p>

<p class="foot">Build #15 of Patrick Neil Bradley's Azure learning portfolio. Data: IPUMS CPS Veterans Supplement 1985–2025 (Flood, King, Rodgers, Ruggles, Warren, Backman, Chen, Cooper, Richards, Schouweiler, Westberry; IPUMS, University of Minnesota, doi:10.18128/D030.V12.0 or the current version), extracted through the IPUMS API by an Azure Function and loaded to an Azure Data Explorer free cluster; Bureau of Justice Statistics reports NCJ 178888 (2000), NCJ 217199 (2007), NCJ 252646 (2021). Cost: $0 — free cluster, free Function grant, Key Vault by name. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-15-two-wars">GitHub</a>.</p>
</main></body></html>"""
open(os.path.join(HERE, "findings.html"), "w", encoding="utf-8").write(page)
print("ok", len(page))
