"""Builds findings.html from data/ops_snapshot.json (the ledger via the API, quarantine reasons, poison and dead-letter
contents, Event Grid delivery metrics, the last container run). Every number is computed, not typed."""
import html
import json
from pathlib import Path

HERE = Path(__file__).parent
S = json.loads((HERE / "data/ops_snapshot.json").read_text(encoding="utf-8-sig"))
CONTRACT = (HERE / "contracts/acs5_county.yaml").read_text(encoding="utf-8")
e = html.escape
L = S["ledger"]
by = lambda stage, outcome: [r for r in L if r["stage"] == stage and r["outcome"] == outcome]
eg = S["eventgrid"]


def table(rows, cols):
    th = "".join(f"<th>{e(c)}</th>" for c in cols)
    tr = "".join("<tr>" + "".join(f"<td>{e(str(r.get(c)) if r.get(c) is not None else '–')}</td>" for c in cols) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def block(title, finding, caveat, body):
    return f'<section class="q"><h2>{title}</h2><p class="finding">{finding}</p><p class="note">{caveat}</p>{body}</section>'


loaded = by("loaded", "loaded"); dup = by("loaded", "duplicate"); poison = by("loaded", "poison"); quar = by("validated", "quarantined"); queued = by("validated", "queued")
f_gate = (f"{len(L)} ledger rows so far. The validator quarantined <b>{len(quar)}</b> file drops and queued <b>{len(queued)}</b>; the loader loaded <b>{len(loaded)}</b>, "
          f"refused <b>{len(dup)}</b> as duplicates (same bytes already loaded) and poisoned <b>{len(poison)}</b>. "
          + (f"The real pull, {e(loaded[0]['file_name'])}, loaded {loaded[0]['rows']:,} rows into {e(loaded[0]['dataset_id'])} — the number build #8 loaded by hand. " if loaded else "")
          + "Every decision names its rule.")
reasons = sorted({(r["reason"] or "")[:80] for r in quar})
f_quar = (f"{len(S['quarantine'])} blobs in <code>quarantine/</code> (each file and its <code>.reason.txt</code>). Reasons seen: " + "; ".join(f"<i>{e(x)}</i>" for x in reasons) + ".")
f_poison = (f"{len(S['poison'])} message(s) in <code>ingest-load-poison</code>. Storage queues have no poison handling of their own: the loader counts dequeues and moves a message after "
            f"the fifth failure, writing the last error to the ledger. " + (f"The one here names a blob that does not exist (<code>{e(json.loads(S['poison'][0]['content']).get('file_name',''))}</code>), put on the queue on purpose." if S["poison"] else "None yet: the ghost message is still being retried."))
f_dl = (f"Event Grid matched <b>{eg.get('MatchedEventCount', 0):.0f}</b> blob-created events on <code>inbox/</code> in the last day, delivered {eg.get('DeliverySuccessCount', 0):.0f}, "
        f"failed {eg.get('DeliveryAttemptFailCount', 0):.0f} delivery attempts and dead-lettered {eg.get('DeadLetteredCount', 0) or 0:.0f}. "
        f"{len(S['deadletter'])} blob(s) in <code>deadletter/</code>. " +
        ("The failed attempts are the build's own mistakes being retried — a validator that raised on a blob already quarantined, a redeploy with unreadable files — plus <code>poisonpill.json</code>, the one file the validator refuses on purpose until Event Grid gives up." ))
aci = S["aci"]
f_aci = (f"The loader is a container image built by GitHub Actions and pulled from GitHub Container Registry, run as an Azure Container Instances group with a system identity. Last run: state <b>{e(str(aci.get('state')))}</b>, exit {aci.get('exit')}. "
         f"A Function timer in build #13's app starts it nightly through ARM; it drains the queue and exits, and ACI bills per second only while it runs.")

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pipeline That Says No</title>
<style>
:root{{color-scheme:light;--surface:#fcfcfb;--surface-2:#f1f0ec;--ink:#0b0b0b;--ink-2:#52514e;--ink-3:#8a8880;--line:#e3e1da;--series:#2a78d6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--ink:#f0efec;--ink-2:#c3c2b7;--ink-3:#8f8e86;--line:#33332f;--series:#3987e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}h1{{font-size:26px;margin:0 0 4px}}.sub{{color:var(--ink-2);margin:0 0 28px}}
h2{{font-size:17px;margin:40px 0 8px}}.finding{{font-size:16px;margin:0 0 6px}}.note{{color:var(--ink-2);font-size:14px;margin:0 0 14px}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto;margin-bottom:10px}}th{{text-align:left;color:var(--ink-2);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px;white-space:nowrap}}td{{padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
pre{{background:var(--surface-2);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.45;white-space:pre-wrap}}details{{margin-top:10px}}summary{{cursor:pointer;color:var(--series);font-size:14px}}
.flow{{background:var(--surface-2);border-radius:10px;padding:14px 16px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;white-space:pre;overflow-x:auto}}
.foot{{margin-top:40px;color:var(--ink-3);font-size:13px;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--series)}}code{{font-size:13px}}
</style></head><body><main>
<h1>The pipeline that says no: event-driven ingestion with a data contract, quarantine, idempotency and poison handling</h1>
<p class="sub">Drop a file in <code>inbox/</code>. Event Grid tells a Function; the Function checks the file against its contract and either queues it, quarantines it with a reason, or records it. A container pulls the queue, refuses bytes it has loaded before, loads the rest with the same OPENJSON path as every earlier build, and moves a message that keeps failing to a poison queue. Every decision is a ledger row the build #13 API serves. Anchor phrase: every file is guilty until the gate clears it. Expand the contract to read the rules.</p>
<div class="flow">inbox/ (blob created) ──► Event Grid system topic ──► validator Function ──┬─► ingest-load queue ──► loader container (ACI) ──► col.measure
                                   │ dead-letter: deadletter/             └─► quarantine/ + reason        │ fails ×5 ──► ingest-load-poison
                                                                   every decision ──► col.ingest_ledger ──► GET /data/ingest/ledger</div>
{block("The ledger", f_gate, "stage=validated rows are the validator's decisions; stage=loaded rows are the loader's. Newest first; via the build #13 API.", table(L[:20], ["ledger_id", "file_name", "stage", "outcome", "reason", "dataset_id", "rows", "run_by", "received_at"]))}
{block("Quarantine", f_quar, "A quarantined file leaves the inbox; the reason file beside it is the first rule it failed.", table([{"blob": k, "reason": v} for k, v in sorted(S["quarantine_reasons"].items())], ["blob", "reason"]) + "<details><summary>The contract (contracts/acs5_county.yaml)</summary><pre>" + e(CONTRACT) + "</pre></details>")}
{block("Poison", f_poison, "Dequeue count is the queue's own counter; the visibility timeout is how long a failed message hides before it returns.", table([{"dequeueCount": p["dequeueCount"], "content": p["content"][:300]} for p in S["poison"]], ["dequeueCount", "content"]) if S["poison"] else "")}
{block("Dead letters", f_dl, "Event Grid retries with backoff for up to 60 minutes / 5 attempts here; what it cannot deliver it writes to deadletter/ with its own identity.", table([{"blob": d} for d in S["deadletter"]], ["blob"]) if S["deadletter"] else "<p class='note'>Nothing dead-lettered at snapshot time.</p>")}
{block("The container", f_aci, "Image: " + e(str(aci.get("image"))) + ". Log tail from the last run below.", "<pre>" + e(S["aci_log_tail"]) + "</pre>")}
<section class="q"><h2>What this cannot say</h2>
<p class="note">One contract covers one file family (raw ACS county pulls); anything else is quarantined by design. The public limits on the ledger endpoint are build #13's. Container Apps Jobs were the plan for the loader: new Container Apps environments on this subscription are express-only in every allowlisted region and express has no jobs, so the loader runs on Azure Container Instances instead — the same image, the same identity pattern, per-second billing in fractions of a cent. The validator re-reads the blob; the loader re-hashes and re-checks it; neither trusts the message. Snapshot taken {e(S["taken_at"][:16].replace("T"," "))} UTC.</p></section>
<p class="foot">Build #14 of Patrick Neil Bradley's Azure learning portfolio. Azure services: Event Grid (system topic, dead-lettering), Queue Storage, Azure Functions (Event Grid trigger, SQL output binding, managed identity), Azure Container Instances (managed identity), GitHub Container Registry via GitHub Actions, Azure SQL Database (free offer), API Management (build #13). Cost: $0 on every free line; Event Grid within 100,000 free operations; ACI and queue operations fractions of a cent. Code: <a href="https://github.com/patbradley18-netizen/azure-portfolio/tree/main/build-14-ingestion">GitHub</a>.</p>
</main></body></html>'''
(HERE / "findings.html").write_text(page, encoding="utf-8")
print("ok", len(page))
