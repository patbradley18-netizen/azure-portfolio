"""fetch_acs.py - Build #6 step 2a: pull the raw ACS5 county inputs the TSCI snapshot was built from.

One request, all counties, five variables. The Census API requires a key (checked 2026-10-16:
unkeyed requests return a "Missing Key" page). Key by env CENSUS_API_KEY, sourced from Key Vault
secret census-api-key at run time; never on disk, never in the repo. Saves the raw response as-is to data/acs5_<year>_county.json. No transformation here:
raw stays raw, so the warehouse can show exactly what the source said.

Variables (from the methodology one-pager):
  B25064_001E median gross rent            B25077_001E median home value
  B25088_002E median owner cost, mortgaged  B19013_001E median household income
  B01003_001E total population
Run: CENSUS_API_KEY=... python fetch_acs.py [year]   (default 2023, the vintage TSCI used)
"""
import json
import os
import pathlib
import sys
import urllib.request

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2023
VARS = ["B25064_001E", "B25077_001E", "B25088_002E", "B19013_001E", "B01003_001E"]
KEY = os.environ.get("CENSUS_API_KEY") or sys.exit("needs CENSUS_API_KEY in env (from Key Vault secret census-api-key)")
URL = f"https://api.census.gov/data/{YEAR}/acs/acs5?get=NAME,{','.join(VARS)}&for=county:*&key={KEY}"
OUT = pathlib.Path(__file__).parent / "data" / f"acs5_{YEAR}_county.json"

req = urllib.request.Request(URL, headers={"User-Agent": "azure-portfolio build-06 (patrickneilbradley.com)"})
with urllib.request.urlopen(req, timeout=60) as r:
    body = r.read()
    print("HTTP", r.status, len(body), "bytes")
OUT.write_bytes(body)
try:
    rows = json.loads(body)
except ValueError:
    sys.exit("not JSON; first 600 bytes:\n" + body[:600].decode("utf-8", "replace"))
print(f"{len(rows) - 1:,} counties; header: {rows[0]}")
print("first:", rows[1])
