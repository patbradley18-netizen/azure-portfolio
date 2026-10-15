"""AID stage 4, step 1: fetch Congressional Record daily-edition granules from govinfo.gov (public domain).

No API key: the package metadata (mods.xml) and granule text (html) are open URLs.
Keeps HOUSE, SENATE and EXTENSIONS granules; skips the Daily Digest. Writes one JSONL per
sitting day to data/crec/YYYY-MM-DD.jsonl with: date, granule_id, chamber, title, members
(name/party/state from GPO metadata), text. Resume-safe: a day with an existing file is skipped.

Run: python -u fetch_crec.py 2017-08-01 2018-12-31
"""
import sys, re, json, time, html as htmllib
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "data" / "crec"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "aid-lite-research (student portfolio; contact via github.com/patbradley18-netizen)"}
NS = {"m": "http://www.loc.gov/mods/v3"}
KEEP = {"HOUSE", "SENATE", "EXTENSIONS"}
PAUSE = 0.25  # seconds between requests: polite, ~4 req/s

def get(url, retries=3):
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return None

def granules(day):
    raw = get(f"https://www.govinfo.gov/metadata/pkg/CREC-{day}/mods.xml")
    if raw is None: return None
    if b"<mods" not in raw[:2000]:
        # govinfo answers non-sitting days with an HTML "cannot be found" page and status 200
        if b"cannot be found" in raw or b"Error" in raw[:3000]: return None
        time.sleep(30); raw = get(f"https://www.govinfo.gov/metadata/pkg/CREC-{day}/mods.xml")
        if raw is None or b"<mods" not in raw[:2000]: return None
    root = ET.fromstring(raw)
    out = []
    for rel in root.findall("m:relatedItem", NS):
        ext = rel.find("m:extension", NS)
        if ext is None: continue
        cls = ext.findtext("m:granuleClass", default="", namespaces=NS)
        gid = ext.findtext("m:accessId", default="", namespaces=NS)
        if cls not in KEEP or not gid: continue
        title = ext.findtext("m:searchTitle", default="", namespaces=NS)
        members = [{"name": " ".join(" ".join(cm.itertext()).split()), "party": cm.get("party", ""), "state": cm.get("state", ""), "chamber": cm.get("chamber", "")}
                   for cm in ext.findall("m:congMember", NS)]
        out.append({"granule_id": gid, "chamber": cls, "title": title, "members": members})
    return out

def text_of(day, gid):
    raw = get(f"https://www.govinfo.gov/content/pkg/CREC-{day}/html/{gid}.htm")
    if raw is None: return ""
    t = re.sub(r"<[^>]+>", "", raw.decode(errors="replace"))
    return htmllib.unescape(t).strip()

def main(start, end):
    d, end = date.fromisoformat(start), date.fromisoformat(end)
    while d <= end:
        day = d.isoformat(); f = OUT / f"{day}.jsonl"
        if f.exists():
            d += timedelta(days=1); continue
        gl = granules(day); time.sleep(PAUSE)
        if gl is None:
            f.touch()  # no sitting that day; empty marker so we don't re-ask
            d += timedelta(days=1); continue
        with f.open("w", encoding="utf-8") as fh:
            for g in gl:
                g["date"] = day; g["text"] = text_of(day, g["granule_id"]); time.sleep(PAUSE)
                fh.write(json.dumps(g, ensure_ascii=False) + "\n")
        print(day, len(gl), "granules", flush=True)
        d += timedelta(days=1)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])