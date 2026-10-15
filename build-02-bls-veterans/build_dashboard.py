"""Builds dashboard.html from data/bls_observations.csv (no external scripts, inline SVG)."""
import pandas as pd, html
from pathlib import Path
HERE = Path(__file__).parent
df = pd.read_csv(HERE / "data/bls_observations.csv", parse_dates=["period"])
S = {"LNU04049526": ("Veterans", "var(--series)"), "LNU04049601": ("Nonveterans", "var(--ink-3)"), "LNU04066408": ("Gulf War-era II veterans", "var(--series-2)")}
P = {"LNU01349526": ("Veterans", "var(--series)"), "LNU01349601": ("Nonveterans", "var(--ink-3)")}
latest = df[df.period == df.period.max()].set_index("series_id")["value"]
lp = df.period.max().strftime("%B %Y")
def chart(keys, title, ymin, ymax, h=240):
    W, pad = 900, 40
    x0, x1 = df.period.min(), df.period.max(); span = (x1 - x0).days
    def X(t): return pad + (t - x0).days / span * (W - 2 * pad)
    def Y(v): return h - pad - (v - ymin) / (ymax - ymin) * (h - 2 * pad)
    lines, legend = [], []
    for i, k in enumerate(keys):
        d = df[df.series_id == k].sort_values("period"); name, col = (S | P)[k]
        pts = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in zip(d.period, d.value))
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{1.8 if i == 0 else 1.4}" stroke-linejoin="round"/>')
        legend.append(f'<tspan fill="{col}">&#9644; {html.escape(name)}</tspan>')
    years = "".join(f'<text x="{X(pd.Timestamp(y, 1, 1)):.1f}" y="{h-10}" font-size="10" text-anchor="middle" fill="var(--ink-3)">{y}</text>' for y in range(2000, 2027, 2))
    grid = "".join(f'<line x1="{pad}" x2="{W-pad}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="var(--line)"/><text x="{pad-6}" y="{Y(v)+3:.1f}" font-size="10" text-anchor="end" fill="var(--ink-3)">{v}</text>' for v in range(ymin, ymax + 1, (ymax - ymin) // 4))
    return (f'<svg viewBox="0 0 {W} {h}" width="100%" role="img" aria-label="{html.escape(title)}">{grid}{"".join(lines)}'
            f'<text x="{pad}" y="{pad-16}" font-size="11">{"   ".join(legend)}</text>{years}</svg>')
def kpi(v, t): return f'<div class="kpi"><b>{v}</b><span>{t}</span></div>'
page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Veteran Employment Pipeline</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6;--series-2:#c8641e}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5;--series-2:#e07a30}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5;--series-2:#e07a30}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:36px 0 4px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}.kpi{{background:var(--surface-2);border-radius:10px;padding:14px 16px}}.kpi b{{display:block;font-size:30px;line-height:1.1;font-weight:600}}.kpi span{{color:var(--ink-2);font-size:13px}}
svg text{{fill:var(--ink)}}.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}
</style></head><body><main>
<h1>Veteran employment, pulled weekly from BLS</h1>
<p class="sub">Five Current Population Survey series for veterans and nonveterans, 18 and over, January 2000 to {lp}. An Azure Function pulls them every Saturday with a registered BLS key held in Key Vault, and upserts into Azure SQL. Not seasonally adjusted: compare the same month across years, not adjacent months.</p>
<div class="kpis">
{kpi(f"{latest['LNU04049526']:.1f}%", f"veteran unemployment, {lp}")}
{kpi(f"{latest['LNU04049601']:.1f}%", f"nonveteran unemployment, {lp}")}
{kpi(f"{latest['LNU04066408']:.1f}%", f"Gulf War-era II veterans, {lp}")}
{kpi(f"{latest['LNU01349526']:.1f}%", "veteran labor-force participation")}
</div>
<h2>Unemployment rate, 2000 to {lp}</h2>
<p class="note">Veterans have run below nonveterans for most of the period; the Gulf War-era II series (veterans who served after September 2001) is younger and more volatile, and starts in 2006.</p>
{chart(["LNU04049526", "LNU04049601", "LNU04066408"], "Unemployment rate by veteran status", 0, 16)}
<h2>Labor-force participation</h2>
<p class="note">Veteran participation is far below nonveteran participation. Read this as age, not willingness: the veteran population skews older, and many are retired. A fair comparison would hold age constant; this series does not.</p>
{chart(["LNU01349526", "LNU01349601"], "Labor-force participation rate by veteran status", 40, 72, 200)}
<p class="foot">Source: U.S. Bureau of Labor Statistics, Current Population Survey, series LNU04049526, LNU04066408, LNU04049601, LNU01349526, LNU01349601 (monthly, not seasonally adjusted), via api.bls.gov. Build #2 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Functions (Flex Consumption), Key Vault, SQL Database (free offer). Cost: $0.</p>
</main></body></html>'''
(HERE / "dashboard.html").write_text(page, encoding="utf-8"); print("ok", len(page))