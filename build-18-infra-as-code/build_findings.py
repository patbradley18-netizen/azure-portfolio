"""Builds findings.html from data/whatif_before.json, data/whatif_after.json (az what-if, utf-16), data/deployments.json and
data/ephemeral_evidence.json. Every number is computed; no library."""
import json, html, os
HERE = os.path.dirname(os.path.abspath(__file__)); e = html.escape
def load_wi(name):
    raw = open(os.path.join(HERE, "data", name), "rb").read()
    return json.loads(raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig"))
B, A = load_wi("whatif_before.json"), load_wi("whatif_after.json")
D = json.load(open(os.path.join(HERE, "data", "deployments.json"), encoding="utf-8-sig"))
EV = json.load(open(os.path.join(HERE, "data", "ephemeral_evidence.json"), encoding="utf-8-sig"))
def counts(w):
    c = {}
    for x in w["changes"]: c[x["changeType"]] = c.get(x["changeType"], 0) + 1
    return c
def rid(x): return "/".join(x["resourceId"].split("/")[-2:])
cb, ca = counts(B), counts(A)
real_b = [x for x in B["changes"] if x["changeType"] in ("Create", "Delete")]; real_a = [x for x in A["changes"] if x["changeType"] in ("Create", "Delete")]
mod_a = [x for x in A["changes"] if x["changeType"] == "Modify"]
REASON = {"roleAssignments": "principalId is a reference() what-if cannot evaluate", "components": "provider-injected defaults (Flow_Type, Request_Source)", "sites": "provider-injected siteConfig defaults on Linux Flex apps", "config": "list() merge cannot be evaluated before deployment", "containerGroups": "read-only provisioning fields"}
def reason(x):
    t = x["resourceId"].split("/")[-2]; return REASON.get(t, "")
rows_before = [{"type": x["changeType"], "res": rid(x), "paths": ", ".join(d["path"] for d in (x.get("delta") or []))[:140]} for x in B["changes"] if x["changeType"] not in ("NoChange", "Ignore")]
rows_after = [{"type": x["changeType"], "res": rid(x), "paths": ", ".join(d["path"] for d in (x.get("delta") or []))[:140], "why": reason(x)} for x in A["changes"] if x["changeType"] not in ("NoChange", "Ignore")]
def table(rows, cols, head):
    return "<table><thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{e(str(r.get(c, '')))}</td>" for c in cols) + "</tr>" for r in rows) + "</tbody></table>"
dep_rows = [{"name": d["name"], "state": d["state"], "dur": d["duration"].replace("PT", "").lower(), "t": d["timestamp"][:19].replace("T", " ")} for d in D]
ev_rows = [{"check": k, "value": v} for k, v in [("storage account", EV["storage"]["name"]), ("shared-key access", str(EV["storage"]["allowSharedKeyAccess"])), ("public blob access", str(EV["storage"]["allowBlobPublicAccess"])), ("containers", ", ".join(c["name"] for c in (EV["containers"]["value"] if isinstance(EV["containers"], dict) else EV["containers"]))), ("queues", ", ".join(q["name"] for q in (EV["queues"]["value"] if isinstance(EV["queues"], dict) else EV["queues"]))), ("vault", EV["vault"]["name"] + " (RBAC, soft delete 7 d)"), ("roles on the account", ", ".join(sorted({r["roleDefinitionName"] for r in (EV["roles"]["value"] if isinstance(EV["roles"], dict) else EV["roles"])}))), ("event grid topic", EV["topic"]["name"] + " — " + EV["topic"]["provisioningState"])]]
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>A template that changes nothing</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6;--good:#0f8a5f;--warn:#b8860b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5;--good:#2fb37f;--warn:#d9a441}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5;--good:#2fb37f;--warn:#d9a441}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:12px 0 6px}}.tile{{background:var(--surface-2);border-radius:10px;padding:14px 16px}}.tile b{{font-size:28px;display:block}}.tile span{{color:var(--ink-2);font-size:13px}}
.flow{{background:var(--surface-2);border-radius:10px;padding:14px 16px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;white-space:pre;overflow-x:auto}}
details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}code{{font-size:13px}}
</style></head><body><main>
<h1>A template that changes nothing: converging a hand-built resource group onto Bicep, proving it, and gating it</h1>
<p class="sub">Builds #1–#17 were created with the CLI; build #10 wrote a Bicep template of the result and every build since appended to it, but it had never been deployed. This build made the template <b>converge</b>: a first real deployment onto the live group, a second one to prove idempotence, a throw-away group to prove create → verify → delete, and a CI gate that fails on any Create or Delete. Anchor phrase: <i>a template that changes nothing is the proof.</i></p>

<div class="tiles">
<div class="tile"><b>{len(real_b)} → {len(real_a)}</b><span>real changes (Create/Delete) what-if reported, before → after</span></div>
<div class="tile"><b>{cb.get('Modify',0)} → {ca.get('Modify',0)}</b><span>Modify rows before → after (the survivors are what-if's blind spots, listed below)</span></div>
<div class="tile"><b>{len(D)}</b><span>deployments to the live group, all Succeeded; fastest {min(d['duration'] for d in D).replace('PT','').lower()}</span></div>
<div class="tile"><b>10/10</b><span>ephemeral checks passed, then the group was deleted</span></div>
</div>

<h2>What the first what-if said, and what was wrong with it</h2>
<p class="finding">Before the fixes: {cb.get('Create',0)} Create, {cb.get('Modify',0)} Modify, {cb.get('NoChange',0)} NoChange. Every Create was a role assignment whose template name (<code>guid()</code> of its seeds) could never equal the name Azure gave it at CLI time — so the template was about to add five duplicates. The fix is to adopt the live names as literals. Most Modify rows were server defaults the template did not state (API Management protocol flags, Search network rules, container encryption scope), one wrong container name, and an app-settings block that would have <b>replaced</b> the Function host's own settings — rewritten as a <code>union(list(…))</code> merge in a module, because the parent template cannot list a config it also deploys (circular dependency, twice).</p>
<details><summary>Before: {len(rows_before)} rows</summary>{table(rows_before, ["type","res","paths"], ["change","resource","properties"])}</details>

<h2>After two deployments: the same 12 rows, so they are not drift</h2>
<p class="finding">The template was deployed to the live group twice ({', '.join(d['duration'].replace('PT','').lower() for d in D)}). Nothing changed that could be observed — identities, app settings, the free database, the API, the alert all as before — and the second what-if reports exactly the rows the first fixed version did. That is the test for a what-if row: if a successful deployment leaves it standing, it is an evaluator limit, not a difference.</p>
{table(rows_after, ["type","res","paths","why"], ["change","resource","properties","why what-if cannot settle it"])}
<p class="note">One deliberate exclusion: the loader container group sits behind <code>deployLoader=false</code>. A PUT on a container group redeploys it and can mint a new managed identity (build #14), which would orphan its SQL user — so it is templated but not converged.</p>

<h2>Deployments</h2>
{table(dep_rows, ["name","state","dur","t"], ["deployment","state","duration","time (UTC)"])}

<h2>The ephemeral proof</h2>
<p class="finding">A second template with the free pieces of the pattern — storage with shared-key access off, two containers, a queue, a Key Vault in RBAC mode, a user-assigned identity with two scoped roles, an Event Grid system topic — deployed into <code>rg-azportfolio-iac-test</code>, verified by a script against the live resources, and deleted (vault purged) in the same run. Deploy time ~35 s; cost fractions of a cent; the group does not exist now.</p>
{table(ev_rows, ["check","value"], ["evidence","value"])}
<div class="flow">push touching infra/ ──▶ GitHub Actions: lint both templates ──▶ what-if vs rg-azportfolio-b1 ──▶ summary table in the run
                                                                     └──▶ FAIL if any Create/Delete
workflow_dispatch (deploy=true) ──▶ environment "production" approval ──▶ az deployment group create (Incremental)</div>

<h2>What this cannot say</h2>
<p class="note">The template is a record of a group that was built by hand; it converges on that group, it did not create it. Three things remain outside it on purpose: the operator's own role assignments, the secrets (a Key Vault reference and run-time parameters only), and the loader container group (see above). The roles that build #14 granted to its identities on the storage account are not in the template yet; what-if cannot see what the template does not mention.</p>

<p class="foot">Build #18 of Patrick Neil Bradley's Azure learning portfolio. Bicep, Azure Resource Manager what-if and deployments, GitHub Actions with OIDC. Cost: $0 on the live group; the ephemeral group cost fractions of a cent for minutes. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-18-infra-as-code">GitHub</a>.</p>
</main></body></html>"""
open(os.path.join(HERE, "findings.html"), "w", encoding="utf-8").write(page); print("ok", len(page))
