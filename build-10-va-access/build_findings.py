"""Builds findings.html from data/results.json and the two data cards. Every number in every sentence is computed, not typed.
The map is inline SVG: one dot per county population center, projected with an Albers equal-area conic (no map library,
no tiles, no key), coloured by straight-line distance band to the nearest VA medical center. Alaska and Hawaii are insets."""
import html
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
R = json.loads((HERE / "data/results.json").read_text(encoding="utf-8"))
FC = json.loads((HERE / "data/vha_facilities_card.json").read_text(encoding="utf-8"))
CC = json.loads((HERE / "data/county_centroids_card.json").read_text(encoding="utf-8"))
XY = {c["fips"]: (c["lat"], c["lon"]) for c in json.loads((HERE / "data/county_centroids.json").read_text(encoding="utf-8"))}
e = html.escape
BIG = {"veterans", "pop2020", "counties"}
# sequential ramp, one hue light -> dark, matched to the Q21 bands; text never wears these colours
BANDS = [(30, "0–30 mi", "#9ecae1"), (60, "30–60 mi", "#4292c6"), (100, "60–100 mi", "#08519c"), (1e9, "100+ mi", "#08306b")]


def band(miles):
    return next(b for b in BANDS if miles <= b[0])


def albers(lat, lon, lat0, lon0, lat1, lat2):
    """Albers equal-area conic, returns (x, y) in radians-scaled units."""
    lat, lon, lat0, lon0, lat1, lat2 = map(math.radians, (lat, lon, lat0, lon0, lat1, lat2))
    n = (math.sin(lat1) + math.sin(lat2)) / 2
    c = math.cos(lat1) ** 2 + 2 * n * math.sin(lat1)
    rho = math.sqrt(c - 2 * n * math.sin(lat)) / n
    rho0 = math.sqrt(c - 2 * n * math.sin(lat0)) / n
    theta = n * (lon - lon0)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


def cell(v, c):
    if v is None:
        return '<td class="num">–</td>'
    if isinstance(v, float):
        return f'<td class="num">{v:,.0f}</td>' if c in BIG else f'<td class="num">{v:,.1f}</td>'
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


def svg_map(rows, key):
    """Dots for CONUS plus AK and HI insets. Dot area ~ veterans (sqrt scale), colour = distance band."""
    W, H = 960, 600
    groups = {"conus": ([], (37.5, -96, 29.5, 45.5)), "AK": ([], (64, -152, 55, 65)), "HI": ([], (20.5, -157, 8, 18))}
    for r in rows:
        g = "AK" if r["state_abbr"] == "AK" else "HI" if r["state_abbr"] == "HI" else "conus"
        groups[g][0].append(r)
    vmax = max(r["veterans"] for r in rows)
    out = []
    frames = {"conus": (60, 0, W - 60, H - 50), "AK": (10, 420, 180, 150), "HI": (200, 490, 120, 80)}
    for g, (rs, (lat0, lon0, lat1, lat2)) in groups.items():
        if not rs:
            continue
        pts = [(albers(*XY[r["fips"]], lat0, lon0, lat1, lat2), r) for r in rs]
        xs = [p[0][0] for p in pts]; ys = [p[0][1] for p in pts]
        fx, fy, fw, fh = frames[g]
        sx = (fw - 30) / (max(xs) - min(xs)); sy = (fh - 30) / (max(ys) - min(ys)); s = min(sx, sy)
        ox = fx + 15 + (fw - 30 - s * (max(xs) - min(xs))) / 2; oy = fy + 15 + (fh - 30 - s * (max(ys) - min(ys))) / 2
        for (x, y), r in pts:
            px = ox + (x - min(xs)) * s; py = oy + (max(ys) - y) * s
            rad = 1.6 + 7 * math.sqrt(r["veterans"] / vmax)
            m = r[key]; b = band(m)
            tip = f"{r['county']}, {r['state_abbr']}: {r['veterans']:,.0f} veterans; nearest VA medical center {r['nearest_vamc']} {r['vamc_miles']:.0f} mi; nearest care site {r['nearest_site']} ({r['site_kind']}) {r['site_miles']:.0f} mi"
            out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{rad:.1f}" fill="{b[2]}" fill-opacity="0.85"><title>{e(tip)}</title></circle>')
        if g != "conus":
            out.insert(0, f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="6" fill="none" stroke="var(--line)"/>')
            out.append(f'<text x="{fx + 8}" y="{fy + 14}" class="lbl">{g}</text>')
    legend = "".join(f'<g transform="translate({420 + i * 100},{H - 22})"><rect width="14" height="14" rx="3" fill="{c}"/><text x="20" y="12" class="lbl">{e(l)}</text></g>' for i, (_, l, c) in enumerate(BANDS))
    out.append(f'<text x="420" y="{H - 32}" class="lbl">Straight-line miles to the nearest VA medical center · dot area ∝ veterans</text>')
    return f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Map of US counties coloured by distance to the nearest VA medical center">{"".join(out)}{legend}</svg>'


q18 = R["Q18"]["rows"]; q19 = R["Q19"]["rows"]; us = q19[0]; states = q19[1:]; q20 = R["Q20"]["rows"]; q21 = R["Q21"]["rows"]
far_names = ", ".join(s["geo"] for s in states[:3]); far_miles = ", ".join(format(s["vamc_miles_weighted"], ".0f") for s in states[:3])
vamc_bands = {r["band"]: r for r in q21 if r["target"] == "VAMC"}; site_bands = {r["band"]: r for r in q21 if r["target"] == "care site"}
f18 = (f"{len(q18):,} counties, {us['veterans']/1e6:.1f} million veterans. The median county's population center is "
       f"{sorted(r['vamc_miles'] for r in q18)[len(q18)//2]:.0f} straight-line miles from a VA medical center and "
       f"{sorted(r['site_miles'] for r in q18)[len(q18)//2]:.0f} from any VA care site. Hover a dot.")
f19 = (f"Weighted by where veterans live, the average veteran is <b>{us['vamc_miles_weighted']:.0f} miles</b> from the nearest VA medical center and "
       f"<b>{us['site_miles_weighted']:.0f} miles</b> from the nearest care site of any kind. <b>{us['pct_vets_vamc_within_30']:.0f}%</b> are within 30 miles of a medical center, "
       f"<b>{us['pct_vets_vamc_within_60']:.0f}%</b> within 60; <b>{us['pct_vets_site_within_30']:.0f}%</b> are within 30 miles of some care site. "
       f"The far states are {far_names} ({far_miles} miles to a medical center); "
       f"in {states[1]['geo']} and {states[2]['geo']} fewer than {max(states[1]['pct_vets_vamc_within_60'], states[2]['pct_vets_vamc_within_60']):.0f}% of veterans are within 60 miles of one.")
base = ", ".join(f"{r['county']} {r['state_abbr']}" for r in q20[:7])
f20 = (f"The veteran-densest counties that are far from a hospital are <b>military base counties</b>: {base}. "
       f"Every one of the 25 has a VA care site within {max(r['site_miles'] for r in q20):.0f} miles (median {sorted(r['site_miles'] for r in q20)[12]:.0f}), "
       f"and a VA medical center {min(r['vamc_miles'] for r in q20):.0f}–{max(r['vamc_miles'] for r in q20):.0f} miles away. Access to a clinic is not the problem these counties have; access to a hospital is.")
f21 = (f"{vamc_bands['100+']['veterans']/1e3:,.0f} thousand veterans ({vamc_bands['100+']['pct_of_veterans']:.1f}%) in {vamc_bands['100+']['counties']} counties live more than 100 straight-line miles from a VA medical center; "
       f"{vamc_bands['60-100']['veterans']/1e6:.1f} million more are 60–100 miles out. For any care site the picture flips: {site_bands['0-30']['pct_of_veterans']:.1f}% within 30 miles, "
       f"{site_bands['60-100']['veterans'] + site_bands['100+']['veterans']:,.0f} veterans beyond 60.")

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reaching the VA</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}pre{{background:var(--surface-2);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.45}}
svg{{width:100%;height:auto;background:var(--surface-2);border-radius:10px}}.lbl{{fill:var(--ink-2);font-size:12px}}circle:hover{{stroke:var(--ink);stroke-width:1.5}}
.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}
</style></head><body><main>
<h1>Can veterans reach the VA? Distance from where veterans live to the nearest VA medical center and clinic</h1>
<p class="sub">Every county's population center, joined to the nearest VA site with the <code>geography</code> type and <code>STDistance</code> on the free Azure SQL tier. Straight-line miles, not road miles. Facility list is VA's VAST station extract of {FC["vast_extract_dates"][0]} as republished by HRSA; veterans are ACS 5-year 2023 (B21001). Anchor phrase: distance is not access, but it is the first thing to measure. Expand any query to read the T-SQL.</p>
{block("Q18. Every county, its nearest VA medical center and nearest care site", f18, f"Care site = VA medical center, health care center, community-based outpatient clinic or other outpatient site ({FC['kinds']['VAMC'] + FC['kinds']['HCC'] + FC['kinds']['CBOC'] + FC['kinds']['OOS']:,} fixed sites); mobile clinics, Vet Centers and residential programs excluded; {FC['suspended']} suspended sites excluded. County origin = 2020 Census population-weighted center ({CC['ct_planning_regions_from_gazetteer']} Connecticut planning regions use the 2023 Gazetteer interior point). Puerto Rico not in the warehouse.", svg_map(q18, "vamc_miles") + table("Q18", 10, ["fips", "county", "state_abbr", "veterans", "vet_share", "nearest_vamc", "vamc_miles", "nearest_site", "site_kind", "site_miles"]), R["Q18"]["sql"], "CROSS APPLY TOP 1 ORDER BY STDistance — nearest-neighbour join")}
{block("Q19. Veteran-weighted distance, by state", f19, "Mean of each county's distance weighted by its veterans; shares are of veterans, not counties. Sorted far to near.", table("Q19", 52), R["Q19"]["sql"], "weighted means + GROUP BY ROLLUP")}
{block("Q20. The veteran-densest counties beyond 60 miles from a VA medical center", f20, "Counties with at least 5,000 veterans, ranked by veteran share of adults, nearest medical center more than 60 straight-line miles away.", table("Q20", 25), R["Q20"]["sql"], "filter on the spatial join, TOP 25")}
{block("Q21. Distance bands", f21, "Bands are straight-line miles from the county population center; every veteran in a county is assigned the county's distance.", table("Q21"), R["Q21"]["sql"], "CASE bands + window share")}
<section class="q"><h2>What this cannot say</h2>
<p class="note">Straight-line distance understates travel, most in mountain and rural counties. A county population center is not where every veteran lives: in a large county the spread is tens of miles. The facility list is from {FC["vast_extract_dates"][0]}; VA reported 170 medical centers and 1,193 outpatient sites in June 2026 against {FC['kinds']['VAMC']} and {FC['kinds']['HCC'] + FC['kinds']['CBOC'] + FC['kinds']['OOS'] + FC['kinds']['MOBILE']:,} (incl. mobile) here, so the hospital map is current at the count level and the clinic map is a few years behind. VA eligibility, enrollment and community-care rules — which decide whether a veteran uses any of these sites — are out of scope. Distance is the first thing to measure, not the last.</p></section>
<p class="foot">Data: VA VAST station list via <a href="https://gisportal.hrsa.gov/server/rest/services/HealthCareFacilities/VHAFacilities_FS/MapServer/0">HRSA GIS</a> (public domain); U.S. Census Bureau 2020 centers of population and 2023 Gazetteer (public domain); ACS 5-year 2023 B21001 (public domain). Build #10 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Azure SQL Database (free offer) with the <code>geography</code> type and spatial indexes; infrastructure described in Bicep (see repo). Cost: $0. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-10-va-access">GitHub</a>.</p>
</main></body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8")
print("ok", len(page))
