"""poison_message.py - put a message on ingest-load that passes the validator's shape but cannot be loaded (the blob it
names does not exist), so the loader fails it on every attempt. With MAX_DEQUEUE=5, five loader runs move it to the
poison queue and the ledger says `poison`. Run from the PC (operator identity: Storage Queue Data Contributor)."""
import base64, json, subprocess, sys
msg = {"sha256": "0" * 64, "file_name": "ghost.json", "blob_url": "https://stazportfoliob1.blob.core.windows.net/inbox/ghost.json",
       "dataset_id": "acs5_2099_ghost", "contract": "acs5_county", "year": 2099, "set": "shelter"}
content = base64.b64encode(json.dumps(msg).encode()).decode()
az = "az.cmd" if sys.platform == "win32" else "az"
r = subprocess.run([az, "storage", "message", "put", "--account-name", "stazportfoliob1", "--auth-mode", "login", "-q", "ingest-load", "--content", content, "-o", "none"], capture_output=True, text=True)
print("queued ghost message" if r.returncode == 0 else r.stderr[:300])
