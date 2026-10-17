"""fetch_facilities.py - Build #10 step 1a: pull the VA facility list (VAST extract) from HRSA's public GIS portal.

Why HRSA and not VA's own API: the Lighthouse Facilities API refused a production key for short-term use
(2026-10-16). HRSA republishes VA's VAST station list as an ArcGIS feature layer: public domain, no key,
every site with lat/lon, county FIPS and type flags. Vintage is the extract date in VHA_EXTRDATE (2018-09-29).
That vintage is the build's main caveat and is written into the output so the card and the page carry it.

Classification used downstream (one label per site, in this priority):
  VAMC   = VHA_VAH (VA hospital) or VHA_NEWVAMC
  HCC    = health care center (large outpatient)
  CBOC   = multi-specialty or primary-care community-based outpatient clinic
  OOS    = other outpatient services
  VETCTR = Vet Center (counseling, not medical care)
  MOBILE = mobile clinic (kept in the file, excluded from distance queries: it has no fixed location)
  OTHER  = domiciliary / community living center (residential; excluded from distance queries)
Run: python fetch_facilities.py        -> data/vha_facilities.json, data/vha_facilities_card.json
"""
import datetime as dt
import json
from pathlib import Path

import requests

URL = "https://gisportal.hrsa.gov/server/rest/services/HealthCareFacilities/VHAFacilities_FS/MapServer/0/query"
FIELDS = ["VHA_STA_NO", "VHA_STA_NAME", "VHA_PAR_STA_NO", "VHA_S_CITY", "VHA_S_STATE", "VHA_FIPS", "VHA_ST",
          "VHA_LAT", "VHA_LON", "VHA_VAH", "VHA_NEWVAMC", "VHA_HCC", "VHA_MSCBOC", "VHA_PCCBOC", "VHA_OOS",
          "VHA_VCTR2", "VHA_MOBILE", "VHA_SUSPENDED", "VHA_OPERA_DAT", "VHA_EXTRDATE", "VHA_VISN", "VHA_URH"]
DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)


# Flag overrides, found by reading the output (build #10 step 3 spot-check). Three rows where the 2018 VAST flags
# disagree with what the site is: 629 New Orleans VAMC (full hospital, opened 2016) is flagged HCC; 508GA Fort
# McPherson and 508GK Trinka Davis (Atlanta clinics) carry the NEWVAMC flag. Listed on the Dataset Card as D-013.
OVERRIDE = {"629": "VAMC", "508GA": "CBOC", "508GK": "CBOC"}


def classify(a):
    if a.get("VHA_STA_NO") in OVERRIDE:
        return OVERRIDE[a["VHA_STA_NO"]]
    if a.get("VHA_MOBILE"):
        return "MOBILE"
    if a.get("VHA_VAH") or a.get("VHA_NEWVAMC"):
        return "VAMC"
    if a.get("VHA_HCC"):
        return "HCC"
    if a.get("VHA_MSCBOC") or a.get("VHA_PCCBOC"):
        return "CBOC"
    if a.get("VHA_OOS"):
        return "OOS"
    if a.get("VHA_VCTR2"):
        return "VETCTR"
    if len(a.get("VHA_STA_NO") or "") == 7:  # 7-char station = satellite clinic of a CBOC (VAST numbering); nine of these carry no flag
        return "CBOC"
    return "OTHER"  # domiciliaries and community living centers: residential programs, not outpatient care sites


def ms_to_date(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date().isoformat() if ms else None


def main():
    rows, offset = [], 0
    while True:  # the layer caps a page at 1,000 features; page until a short page comes back
        r = requests.get(URL, params={"where": "1=1", "outFields": ",".join(FIELDS), "returnGeometry": "false",
                                      "resultOffset": offset, "resultRecordCount": 1000, "f": "json"}, timeout=120)
        r.raise_for_status()
        feats = r.json()["features"]
        rows += [f["attributes"] for f in feats]
        print(f"page at offset {offset}: {len(feats)} rows", flush=True)
        if len(feats) < 1000:
            break
        offset += 1000

    out = []
    for a in rows:
        out.append({"sta_no": a["VHA_STA_NO"], "name": a["VHA_STA_NAME"], "parent": a["VHA_PAR_STA_NO"],
                    "city": a["VHA_S_CITY"], "state": a["VHA_ST"] or a["VHA_S_STATE"], "fips": a["VHA_FIPS"],
                    "lat": a["VHA_LAT"], "lon": a["VHA_LON"], "kind": classify(a), "suspended": a["VHA_SUSPENDED"],
                    "opened": ms_to_date(a["VHA_OPERA_DAT"]), "visn": a["VHA_VISN"], "urh": a["VHA_URH"]})
    extract_dates = sorted({ms_to_date(a["VHA_EXTRDATE"]) for a in rows if a["VHA_EXTRDATE"]})
    kinds = {}
    for o in out:
        kinds[o["kind"]] = kinds.get(o["kind"], 0) + 1
    card = {"source": URL, "source_owner": "HRSA (republishing VA VAST station list)", "license": "US government work, public domain",
            "pulled_at": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z", "vast_extract_dates": extract_dates,
            "rows": len(out), "rows_with_coords": sum(1 for o in out if o["lat"] is not None and o["lon"] is not None),
            "rows_with_fips": sum(1 for o in out if o["fips"]), "suspended": sum(1 for o in out if o["suspended"] == "Y"),
            "kinds": kinds, "states": len({o["state"] for o in out})}
    (DATA / "vha_facilities.json").write_text(json.dumps(out, indent=0), encoding="utf-8")
    (DATA / "vha_facilities_card.json").write_text(json.dumps(card, indent=1), encoding="utf-8")
    print(json.dumps(card, indent=1))


if __name__ == "__main__":
    main()
