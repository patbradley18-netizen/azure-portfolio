"""Builds findings.html from data/sample_responses.json, data/contract_run.txt and openapi.yaml. Every number is computed, not typed.
The page also calls the live gateway from the browser (public product, no key) when a reader presses a button."""
import html
import json
from pathlib import Path

HERE = Path(__file__).parent
S = json.loads((HERE / "data/sample_responses.json").read_text(encoding="utf-8-sig"))
CT = (HERE / "data/contract_run.txt").read_text(encoding="utf-8-sig", errors="ignore").replace("\x00", "")
SPEC = (HERE / "openapi.yaml").read_text(encoding="utf-8")
e = html.escape
GW = "https://apim-azportfolio-b13.azure-api.net/data"

runs = S["/refresh/runs"]["data"]; good = [r for r in runs if r["rows_written"] > 0]; last = good[0] if good else runs[0]
de = S["/states/DE/access"]; marion = S["/counties/18097/access"]["data"]; near = S["/facilities/near?lat=39.9&lon=-86.2&kind=VAMC&top=3"]["data"]
passed = [l for l in CT.splitlines() if l.startswith("PASS")]; failed = [l for l in CT.splitlines() if l.startswith("FAIL")]
summary = next((l for l in CT.splitlines() if "passed" in l), "")
ct_text = e("\n".join(passed + failed) + ("\n" + summary if summary else ""))
GWJ = json.dumps(GW)
NL = json.dumps("\n")  # the JS string literal "\n"


def pre(obj):
    return f'<pre>{e(json.dumps(obj, indent=1)[:1800])}</pre>'


def block(title, finding, caveat, body):
    return f'<section class="q"><h2>{title}</h2><p class="finding">{finding}</p><p class="note">{caveat}</p>{body}</section>'


def tryit(path):
    return f'<p><button data-path="{e(path)}">GET {e(path)}</button></p><pre class="live" data-for="{e(path)}">press the button: the browser calls the gateway</pre>'


f_api = (f"Five read endpoints and two orchestration endpoints, one Function app behind API Management. A call for Marion County, Indiana returns its nearest medical center "
         f"(<b>{e(marion['vamc_name'])}</b>, {marion['vamc_miles']} straight-line miles) and nearest care site ({e(marion['site_name'])}, {marion['site_miles']} miles); "
         f"a call for Delaware returns {de['meta']['counties']} counties and the veteran-weighted mean of {de['meta']['vamc_miles_weighted']} miles; a point in Indianapolis finds the "
         f"{e(near[0]['name'])} at {near[0]['miles']} miles. Every response carries the data vintage in <code>meta.source</code>.")
f_gw = ("Two products on the same API. <b>public</b>: no key, GET only, 30 calls a minute and 2,000 a day shared by everyone (the Consumption tier has no per-caller counters), "
        "responses cached 5 minutes. <b>keyed</b>: a subscription key, 60 a minute and 20,000 a month, and the right to start the rebuild. The Function's host key lives in a secret "
        "named value in the gateway; the Function answers nobody else. The gateway also fills in <code>miles</code>, <code>kind</code> and <code>top</code> when a caller omits them, "
        "because the stored-procedure binding behind <code>/facilities/near</code> needs all five.")
f_orch = (f"The rebuild is a Durable Functions orchestration: fan out to 51 state activities, each running <code>col.sp_refresh_access_state</code> with retries, fan in to a run record. "
          f"The last good run <b>{e(last['run_id'][:8])}…</b> rebuilt <b>{last['rows_written']:,} rows</b> across {last['states_done']} states in "
          f"{(int(last['finished_at'][17:19]) - int(last['started_at'][17:19])) % 60 + 60 * ((int(last['finished_at'][14:16]) - int(last['started_at'][14:16])) % 60)} seconds; the table matched build #10 to the row afterwards. "
          f"The first run wrote 0 rows and said so: the activity's SQL binding could not address a plain-string input, so the stored procedure ran with an empty state. The fix was an object input; the activity now fails loudly on zero rows.")
f_ct = (f"<b>{len(passed)}/{len(passed) + len(failed)} checks pass</b> against the live gateway: envelope shape, status codes, validation (400, 404, 405), a known value, the gateway's defaults, ordering, a response-time budget. "
        f"The same script runs in GitHub Actions after every deploy; a broken contract fails the build.")

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Warehouse As Product</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
pre{{background:var(--surface-2);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.45;white-space:pre-wrap}}details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}
button{{font:inherit;font-size:13px;padding:6px 12px;border-radius:8px;border:1px solid var(--line);background:var(--surface-2);color:var(--ink);cursor:pointer}}button:hover{{border-color:var(--series)}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}code{{font-size:13px}}
</style></head><body><main>
<h1>The warehouse as a product: a public data API, a gateway with two products, and a rebuild that runs itself</h1>
<p class="sub">Twelve builds produced a county warehouse only its author could query. This one puts an HTTP API on it — Azure Functions with SQL bindings and a managed identity, behind API Management with a keyless public product and a keyed one — and a Durable Functions orchestration that rebuilds the access table state by state every month. The OpenAPI spec is the contract; a test suite holds the gateway to it after every deploy. Anchor phrase: a query becomes an endpoint. The buttons call the live gateway from your browser.</p>
{block("The API", f_api, "Base URL " + e(GW) + ". Read endpoints go through SQL input bindings (parameterised T-SQL or stored procedures); the Function's managed identity has SELECT on schema col and EXECUTE on two procedures, nothing more.", tryit("/counties/18097/access") + tryit("/states/DE/access") + tryit("/facilities/near?lat=39.9&lon=-86.2&kind=VAMC&top=3") + "<details><summary>Sample response, as recorded at build time</summary>" + pre(S["/counties/18097/access"]) + "</details>")}
{block("The gateway", f_gw, "API Management, Consumption tier: first 1,000,000 calls a month free. Policies are XML files in the repo (apim/).", tryit("/info") + "<details><summary>The public product policy</summary><pre>" + e((HERE / "apim/policy-public.xml").read_text(encoding="utf-8")) + "</pre></details>")}
{block("The rebuild", f_orch, "POST /refresh (keyed product) starts it; GET /refresh/status/{id} follows it; GET /refresh/runs lists the run records. A timer starts it at 03:00 UTC on the first of the month.", tryit("/refresh/runs") + "<table><thead><tr><th>run</th><th>started</th><th>finished</th><th>states</th><th>rows</th><th>status</th></tr></thead><tbody>" + "".join(f"<tr><td>{e(r['run_id'][:12])}…</td><td>{e(r['started_at'][:19])}</td><td>{e((r['finished_at'] or '')[:19])}</td><td>{r['states_done']}</td><td>{r['rows_written']:,}</td><td>{e(r['status'])}</td></tr>" for r in runs) + "</tbody></table>")}
{block("The contract", f_ct, "tests/contract_test.py; the public product's shared rate limit is why the suite backs off on 429 instead of failing.", "<pre>" + ct_text + "</pre><details><summary>openapi.yaml</summary><pre>" + e(SPEC) + "</pre></details>")}
<section class="q"><h2>What this cannot say</h2>
<p class="note">The public product's limits are shared by every anonymous caller, not per caller — the Consumption tier has no per-key counters for keyless products — so a busy afternoon can rate-limit a stranger. The orchestration rebuilds a table whose inputs change once a year; the monthly schedule is a demonstration of the pattern, not a need. A cold Flex Consumption app answers the first call in seconds, not milliseconds. Azure Maps was blocked by region policy in build #11; API Management Consumption was not — the difference is the first thing any plan checks now.</p></section>
<p class="foot">Build #13 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Azure Functions (Flex Consumption, Python 3.12, SQL bindings, managed identity), Durable Functions (Azure Storage provider), API Management (Consumption), Azure SQL Database (free offer), GitHub Actions. Data: VA VAST via HRSA, U.S. Census Bureau (public domain). Cost: $0 beyond fractions of a cent of storage transactions. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-13-data-api">GitHub</a>.</p>
</main>
<script>
document.querySelectorAll('button[data-path]').forEach(function (b) {{
  b.addEventListener('click', async function () {{
    var out = document.querySelector('pre.live[data-for="' + b.dataset.path + '"]'); out.textContent = 'calling ' + {GWJ} + b.dataset.path + ' …';
    var t0 = performance.now();
    try {{ var r = await fetch({GWJ} + b.dataset.path); var j = await r.json(); out.textContent = 'HTTP ' + r.status + ' in ' + Math.round(performance.now() - t0) + ' ms' + {NL} + JSON.stringify(j, null, 1).slice(0, 2500); }}
    catch (err) {{ out.textContent = 'error: ' + err; }}
  }});
}});
</script>
</body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8")
print("ok", len(page))
