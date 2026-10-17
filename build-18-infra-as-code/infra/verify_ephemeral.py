"""Verifies an ephemeral deployment from its outputs: every resource exists with the properties the template promised, and the
two role assignments resolve to the identity. Exit code is the verdict. Reads `az` JSON passed on stdin (see run_ephemeral.ps1)."""
import json, sys
d = json.load(sys.stdin)
def arr(x):  # PowerShell's ConvertTo-Json wraps arrays as {value, Count} (build #14 lesson)
    return x["value"] if isinstance(x, dict) and "value" in x else x
for k in ("roles", "containers", "queues"):
    d[k] = arr(d[k])
checks = []
def expect(name, cond, detail=""):
    checks.append(cond); print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{detail}]"))
sa, kv, roles, topic, containers, queues = d["storage"], d["vault"], d["roles"], d["topic"], d["containers"], d["queues"]
expect("storage: shared-key access off", sa["allowSharedKeyAccess"] is False)
expect("storage: no public blob access", sa["allowBlobPublicAccess"] is False)
expect("storage: TLS 1.2", sa["minimumTlsVersion"] == "TLS1_2")
expect("containers inbox + quarantine", sorted(c["name"] for c in containers) == ["inbox", "quarantine"], str(containers))
expect("queue ingest-load", [q["name"] for q in queues] == ["ingest-load"], str(queues))
expect("vault: RBAC mode", kv["properties"]["enableRbacAuthorization"] is True)
expect("vault: soft delete 7 days", kv["properties"]["softDeleteRetentionInDays"] == 7)
pid = d["principalId"]
expect("role: blob data contributor for the identity", any(r["principalId"] == pid and r["roleDefinitionName"] == "Storage Blob Data Contributor" for r in roles), str([r["roleDefinitionName"] for r in roles]))
expect("role: queue data contributor for the identity", any(r["principalId"] == pid and r["roleDefinitionName"] == "Storage Queue Data Contributor" for r in roles))
expect("event grid system topic on the account", topic["source"].lower().endswith(sa["name"].lower()) and topic["provisioningState"] == "Succeeded")
print(f"{sum(checks)}/{len(checks)} passed"); sys.exit(0 if all(checks) else 1)
