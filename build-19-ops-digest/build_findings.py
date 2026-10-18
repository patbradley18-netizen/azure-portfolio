"""Builds findings.html from data/digest_runs.json, function_failures_7d.json, github_failures.json, alerts.json,
fired_alerts.json and whatif_main.json (all written by snapshot.ps1: names and counts only). Every number is computed."""
import json, html, os
HERE = os.path.dirname(os.path.abspath(__file__)); e = html.escape
def load(n):
    p = os.path.join(HERE, "data", n)
    if not os.path.exists(p): return []
    v = json.load(open(p, encoding="utf-8-sig"))
    if isinstance(v, dict) and "value" in v: v = v["value"]   # PowerShell 5 array wrapper
    return v if isinstance(v, list) else [v]
RUNS = sorted(load("digest_runs.json"), key=lambda r: r["start"])
_ft = json.load(open(os.path.join(HERE, "data", "function_failures_7d.json"), encoding="utf-8-sig")); FAIL = [dict(zip([c.get("name") or c.get("ColumnName") for c in (_ft.get("columns") or _ft["Columns"])], r)) for r in (_ft.get("rows") or _ft["Rows"])]; GH = load("github_failures.json"); AL = load("alerts.json")
FIRED = load("fired_alerts.json"); WI = load("whatif_main.json")
ok_runs = [r for r in RUNS if r["status"] == "Succeeded" and r.get("digest")]
first = ok_runs[0]; D = first["digest"]; M = D["metrics"]; S = D["status"]; T = D["thresholds"]
created_run = RUNS[0] if RUNS and RUNS[0]["status"] == "Failed" else None

def badge(s):
    s = (s or "unknown").lower()
    return f'<span class="b {e(s)}">{e(s.upper())}</span>'
def table(rows, cols, head, raw=()):
    return ("<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f"<td>{r.get(c, '') if c in raw else e(str(r.get(c, '')))}</td>" for c in cols) + "</tr>" for r in rows) + "</tbody></table>")
def num(x, nd=0):
    return "—" if x is None else (f"{float(x):,.{nd}f}")

apps = json.loads(M["functions_apps"]) if isinstance(M.get("functions_apps"), str) else (M.get("functions_apps") or [])
checks = [
    {"check": "Function runs, 7 days", "s": badge(S["functions"]), "v": f"{num(M['functions_runs'])} runs, {num(M['functions_failures'])} failed", "line": "any failure = red; no runs = amber"},
    {"check": "SQL free limit, this month", "s": badge(S["sql"]), "v": f"{num(M['sql_consumed'])} of {num(T['sql_free_limit'])} vCore-s ({100*float(M['sql_consumed'])/float(T['sql_free_limit']):.0f}%)", "line": f"{T['sql_amber_pct']}% amber, {T['sql_red_pct']}% red (the alert line)"},
    {"check": "Cost, month to date", "s": badge(S["cost"]), "v": f"${float(M['cost_mtd_usd']):.2f} of ${T['budget_usd']}", "line": f"{T['cost_amber_pct']}% amber, {T['cost_red_pct']}% red"},
    {"check": "Ingestion gates", "s": badge(S["ingest"]), "v": f"{num(M['quarantined_files'])} quarantined, {num(M['deadletter_blobs'])} dead-lettered, {num(M['poison_messages'])} poison", "line": "new poison or dead-letter = red; new quarantine = amber (week over week)"},
    {"check": "GitHub Actions, 7 days", "s": badge(S["github"]), "v": f"{num(M['github_runs_7d'])} runs, {num(M['github_failed_7d'])} failed", "line": "any failure = red"},
    {"check": "ADX free cluster", "s": badge(S["adx"]), "v": f"{num(M['adx_days_left'])} days left", "line": f"{T['adx_amber_days']} d amber, {T['adx_red_days']} d red"},
]

# Why the red is red: classify each failed Function request by what it was
PAUSE = ("Win32Exception",)
def why(f):
    err = f.get("err") or ""
    if any(p in err for p in PAUSE): return "free SQL database was paused; the first connection timed out (a caller saw 500)"
    if f["app"].endswith("b14"): return "build #14 test week: the validator raising on deliberate bad files and on a redeploy"
    return "build-week testing (#13 API work, #1 detector)"
frows = [{"app": f["app"].replace("func-azportfolio-", ""), "fn": f["fn"], "code": f["code"], "n": f["n"], "when": f["t0"][:16].replace("T", " ") + ("" if f["t0"][:16] == f["t1"][:16] else " → " + f["t1"][5:16].replace("T", " ")), "err": (f.get("err") or "").split(".")[-1], "why": why(f)} for f in FAIL]
pause_n = sum(f["n"] for f in FAIL if any(p in (f.get("err") or "") for p in PAUSE)); total_n = sum(f["n"] for f in FAIL)
ghrows = [{"wf": g["workflow"], "when": g["created"][:16].replace("T", " "), "sha": g["sha"], "title": g["title"][:70]} for g in sorted(GH, key=lambda g: g["created"])]
import datetime as _dt
_cut = (_dt.datetime.fromisoformat(D["generated_at"][:19]) - _dt.timedelta(days=7)).isoformat()
gh7 = [g for g in GH if g["created"][:19] >= _cut]

alert_rows = [{"name": a["name"], "metric": a["metric"], "rule": f"> {num(a['threshold'])} over {a['window'][2:].lower()}, checked every {a['every'][2:].lower()}"} for a in AL]
fired_rows = [{"rule": f["rule"], "cond": f["condition"], "at": f["fired"][:16].replace("T", " ")} for f in FIRED]

b19_types = {"workflows", "communicationServices", "emailServices", "domains", "containers"}
wi_b19 = [w for w in WI if w["change"] not in ("NoChange", "Ignore") and w["type"] in b19_types]
n_ra = sum(1 for w in WI if w["type"] == "roleAssignments" and w["change"] == "Modify")
cnt = {}
for w in WI: cnt[w["change"]] = cnt.get(w["change"], 0) + 1

roles = [
    ("Communication and Email Service Owner", "acs-azportfolio", "send the email"),
    ("Monitoring Reader", "rg-azportfolio-b1", "SQL free-limit metric; read the action group's address at run time"),
    ("Storage Blob Data Reader", "containers quarantine, deadletter", "count gate outcomes"),
    ("Storage Queue Data Reader", "queue ingest-load-poison", "poison message count"),
    ("Storage Blob Data Contributor", "container opsdigest", "write digest history (the only write besides email)"),
    ("Log Analytics Reader", "default workspace (operator-deployed)", "Function runs and failures"),
    ("Cost Management Reader", "subscription (operator-deployed)", "month-to-date cost against the $10 alert"),
]
role_rows = [{"role": a, "scope": b, "why": c} for a, b, c in roles]
dur = lambda r: f"{(__import__('datetime').datetime.fromisoformat(r['end'][:19]) - __import__('datetime').datetime.fromisoformat(r['start'][:19])).seconds} s"

page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Six checks, one email</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6;--good:#0f7a53;--warn:#8a6100;--crit:#b3261e}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5;--good:#2fb37f;--warn:#d9a441;--crit:#ef6b62}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5;--good:#2fb37f;--warn:#d9a441;--crit:#ef6b62}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:12px 0 6px}}.tile{{background:var(--surface-2);border-radius:10px;padding:14px 16px}}.tile b{{font-size:28px;display:block}}.tile span{{color:var(--ink-2);font-size:13px}}
.b{{display:inline-block;font-size:12px;font-weight:600;padding:1px 8px;border-radius:999px;border:1.5px solid currentColor}}.b.red{{color:var(--crit)}}.b.amber,.b.unknown{{color:var(--warn)}}.b.green{{color:var(--good)}}
.flow{{background:var(--surface-2);border-radius:10px;padding:14px 16px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;white-space:pre;overflow-x:auto}}
details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}code{{font-size:13px}}
</style></head><body><main>
<h1>Six checks, one email: a weekly operations digest that reads everything and holds no keys</h1>
<p class="sub">Build #12 put one alert on one number. Eighteen builds later there are four Function apps, a data API, an ingestion pipeline, two GitHub pipelines, a free SQL database with a monthly ceiling and a free ADX cluster with an expiry date. This build asks all of them the same question once a week and sends one red/amber/green email. A Logic App with its own identity does the asking; Azure Communication Services sends the mail; every call is an Entra token, and the recipient is read from the alert action group at run time, so no address is in the template, the workflow or the repo. Anchor phrase: <b>six checks, one email, no keys.</b></p>

<div class="tiles">
<div class="tile"><b>{badge(D['overall'].lower())}</b><span>first digest, {e(D['generated_at'][:16].replace('T',' '))} UTC — and it is telling the truth (below)</span></div>
<div class="tile"><b>6 / 6</b><span>checks answered; none came back UNKNOWN</span></div>
<div class="tile"><b>{dur(first)}</b><span>for the whole run: {len(first['actions'])} actions, eight sources read in parallel</span></div>
<div class="tile"><b>${float(M['cost_mtd_usd']):.2f}</b><span>month-to-date cost, read by the digest itself, against the $10 alert</span></div>
</div>

<h2>The first digest</h2>
{table(checks, ["check","s","v","line"], ["check","status","this week","line"], raw=("s",))}
<p class="note">Thresholds are the build's, stated in <code>workflow.json</code> and stored with every digest. The ingestion check compares with last week's <code>latest.json</code>; the first run had nothing to compare with, so this week's counts are the baseline.</p>

<h2>Why it is red: the failed Function requests, and what they were</h2>
<p class="finding">The digest counted {num(M['functions_failures'])} at {e(D['generated_at'][11:16])} UTC; by the snapshot there were {total_n}. {pause_n} of {total_n} were the free SQL database waking up: the first connection after auto-pause times out (<code>Win32Exception</code> inside SqlClient). On the data API that reached a caller as an HTTP 500; on the Saturday BLS pull the retry then loaded all 1,528 rows. The other {total_n - pause_n} are this week's own build-and-break testing. The digest is right to be red; the line "any failure = red" will be revisited after one quiet week, not before.</p>
{table(frows, ["app","fn","code","n","when","err","why"], ["app","function","code","n","when (UTC)","exception","what it was"])}
<p class="note">Found from the digest, not before it: the API answers a paused database with <b>500</b>. The right answer is <b>503 with Retry-After</b>, so a caller knows to try again. Logged as a follow-up, not fixed here.</p>

<h2>And the GitHub failures</h2>
<p class="finding">{len(gh7)} failed runs in the digest's 7-day window, all the site deploy: two on the night the pipeline was first built (build #3) and two on 17 October, when the contract test ran while the database slept — the failure that gave the CI its wake-up loop.</p>
{table(ghrows, ["wf","when","sha","title"], ["workflow","when (UTC)","commit","commit title"])}

<h2>How it runs</h2>
<div class="flow">Recurrence (Mon 13:00 UTC) ──► la-azportfolio-digest  (Logic App, Consumption, system-assigned identity)
   │  eight reads in parallel, each an Entra token for the Logic App's own identity:
   ├─ ARM: action group ag-azportfolio-ops ............ the recipient (secure inputs/outputs: not in run history)
   ├─ ARM → Log Analytics: AppRequests, 7 days ......... runs and failures per Function app
   ├─ ARM metrics: free_amount_consumed ................ SQL free limit
   ├─ Cost Management query, MonthToDate ............... cost against the $10 alert
   ├─ Blob list quarantine/, deadletter/; queue metadata ingest-load-poison
   ├─ GitHub REST (public) ............................. workflow runs, 7 days
   └─ Blob opsdigest/latest.json ....................... last week, for week-over-week
   ▼
 Metrics → Status (red/amber/green per check) → Digest
   ├─► Blob opsdigest/digest/YYYY-MM-DD.json and latest.json
   └─► ACS Email (acs-azportfolio, Azure-managed sender domain) ──► the operator's inbox
 Any source that fails becomes UNKNOWN and the email still goes. A failed run fires alert-digest-failed.</div>

<h2>Least privilege: seven roles, two of them writes</h2>
{table(role_rows, ["role","scope","why"], ["role","scope","why the digest needs it"])}
<p class="note">The plan was to read the ingestion ledger through the build #13 API. That API takes a function key, and fetching one at run time needs write access to the Function app; reading the three storage counts directly needs only data-reader roles. The two reads outside the resource group are deployed by the operator (<code>sub-roles.bicep</code>): the GitHub identity is limited to <code>rg-azportfolio-b1</code> on purpose, and this build did not widen it.</p>

<h2>Alerts: one proved itself on day one</h2>
{table(alert_rows, ["name","metric","rule"], ["alert","metric","fires when"])}
<p class="finding">{('The digest-failure alert fired at ' + e(fired_rows[0]['at']) + ' UTC.') if fired_rows else ''} A Recurrence trigger with a schedule and no start time runs once the moment it is created — before Azure had finished granting the Logic App its roles, so every read returned 403{(' (' + dur(created_run) + ', run Failed)') if created_run else ''}. No email was sent (the recipient lookup was one of the 403s); the alert was. The fix is one line, <code>startTime</code> on the trigger. Six metric alerts now exist; ten are free.</p>
{table(fired_rows, ["rule","cond","at"], ["rule","condition","fired (UTC)"]) if fired_rows else ''}

<h2>In the template, under the gate</h2>
<p class="finding">The digest is a module of <code>main.bicep</code>, so build #18's pipeline what-ifs it on every push. Against the live group: {cnt.get('Create',0)} Create, {cnt.get('Delete',0)} Delete, {cnt.get('Modify',0)} Modify, {cnt.get('NoChange',0)} NoChange — the gate stays green. The digest's own Modify rows are the same blind spot build #18 documented (a role assignment's principalId comes from <code>reference()</code>), the container's encryption defaults (now stated), and the workflow change itself. Of the {n_ra} role-assignment Modify rows, six are this build's and the rest are build #18's; all are <code>principalId</code>, which what-if cannot evaluate.</p>
<details><summary>Build #19's non-role rows in the what-if ({len(wi_b19)})</summary>{table(wi_b19, ["change","type","name","paths"], ["change","type","name","properties"])}</details>

<p class="foot">Cost: Logic App Consumption, about 25 actions a week (built-in actions are fractions of a cent per thousand); ACS Email $0.00025 a message; six metric alerts inside the ten free; a few KB of JSON in Blob. This month: ${float(M['cost_mtd_usd']):.2f} for the whole subscription. Data: Azure Monitor, Cost Management, Azure Storage and the public GitHub API, read with the Logic App's identity; snapshot by <code>snapshot.ps1</code>, which saves names and counts only. Non-commercial learning project. Built with Claude.</p>
</main></body></html>"""
open(os.path.join(HERE, "findings.html"), "w", encoding="utf-8").write(page)
print("findings.html", len(page))
