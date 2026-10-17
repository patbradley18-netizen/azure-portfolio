"""fetch_acs.py - pull raw ACS5 county inputs. Build #6 step 2a; extended in build #7 with named variable sets.

The Census API requires a key (checked 2026-10-16: unkeyed requests return a "Missing Key" page).
Key by env CENSUS_API_KEY, sourced from Key Vault secret census-api-key at run time; never on disk, never in the repo.
Raw stays raw: the response is saved as-is. Variable labels are fetched from the API's own metadata and saved
beside the data, so nothing about what a code means comes from memory.

Sets:
  shelter  B25064_001E B25077_001E B25088_002E B19013_001E B01003_001E   (TSCI inputs)
  veterans B21001: civilian population 18+ by veteran status, total and by sex x age band
  tenure   B25003: occupied housing units by tenure (total, owner-occupied, renter-occupied)   (build #8)
Run: CENSUS_API_KEY=... python fetch_acs.py [year] [set]   (defaults: 2023 shelter)
"""
import json
import os
import pathlib
import sys
import urllib.request

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2023
SET = sys.argv[2] if len(sys.argv) > 2 else "shelter"
SETS = {
    "shelter": ["B25064_001E", "B25077_001E", "B25088_002E", "B19013_001E", "B01003_001E"],
    "veterans": ["B21001_001E", "B21001_002E", "B21001_003E"]
                + [f"B21001_{n:03d}E" for n in (7, 8, 10, 11, 13, 14, 16, 17, 19, 20)]      # male: age-band total, veteran
                + [f"B21001_{n:03d}E" for n in (25, 26, 28, 29, 31, 32, 34, 35, 37, 38)],   # female: age-band total, veteran
    "tenure": ["B25003_001E", "B25003_002E", "B25003_003E"],
}
VARS = SETS[SET]
KEY = os.environ.get("CENSUS_API_KEY") or sys.exit("needs CENSUS_API_KEY in env (from Key Vault secret census-api-key)")
BASE = f"https://api.census.gov/data/{YEAR}/acs/acs5"
OUT = pathlib.Path(__file__).parent / "data" / f"acs5_{YEAR}_{SET}_county.json"
LABELS = pathlib.Path(__file__).parent / "data" / f"acs5_{YEAR}_{SET}_labels.json"
UA = {"User-Agent": "azure-portfolio build-08 (patrickneilbradley.com)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.status, r.read()


# 1. labels from the API's metadata (no key needed for these static files)
labels = {}
for v in VARS:
    st, body = get(f"{BASE}/variables/{v}.json")
    labels[v] = json.loads(body).get("label", "?") if st == 200 else "?"
    print(f"{v}: {labels[v]}")
LABELS.write_text(json.dumps(labels, indent=2), encoding="utf-8")

# 2. data, one call, all counties
st, body = get(f"{BASE}?get=NAME,{','.join(VARS)}&for=county:*&key={KEY}")
print("HTTP", st, len(body), "bytes")
OUT.write_bytes(body)
try:
    rows = json.loads(body)
except ValueError:
    sys.exit("not JSON; first 300 bytes:\n" + body[:300].decode("utf-8", "replace"))
print(f"{len(rows) - 1:,} counties; first: {rows[1][:6]} ...")
