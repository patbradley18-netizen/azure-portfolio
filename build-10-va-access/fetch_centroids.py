"""fetch_centroids.py - Build #10 step 1b: county centers of population from the 2020 Census.

Why this file and not the Gazetteer: the Gazetteer's INTPTLAT/LONG is a geographic interior point.
CenPop2020_Mean_CO.txt is the population-weighted mean center, which is the point that says "where
people in this county live" - the right origin for a distance-to-care question. Public domain; no key.
Vintage: 2020 Census (ACS 2023 veterans are 2019-2023 five-year estimates; the gap is stated on the page).
Run: python fetch_centroids.py        -> data/county_centroids.json
"""
import csv
import datetime as dt
import io
import json
from pathlib import Path

import requests

URL = "https://www2.census.gov/geo/docs/reference/cenpop2020/county/CenPop2020_Mean_CO.txt"
CT_GAZ = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_gaz_counties_09.txt"
DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)


def main():
    r = requests.get(URL, timeout=120)
    r.raise_for_status()
    text = r.content.decode("utf-8-sig")
    rows = [{"fips": x["STATEFP"] + x["COUNTYFP"], "name": x["COUNAME"], "state_name": x["STNAME"],
             "pop2020": int(x["POPULATION"]), "lat": float(x["LATITUDE"]), "lon": float(x["LONGITUDE"]), "center_kind": "cenpop2020"}
            for x in csv.DictReader(io.StringIO(text))]
    # Connecticut: ACS 2023 reports nine planning regions (09110-09190); the 2020 centers file has the eight legacy
    # counties (09001-09015), which no longer join. Fallback for CT only: the 2023 Gazetteer's internal point
    # (a geographic point, not population-weighted). Flagged in center_kind; on the Dataset Card as D-014.
    rows = [x for x in rows if not x["fips"].startswith("09")]
    g = requests.get(CT_GAZ, timeout=120)
    g.raise_for_status()
    for x in csv.DictReader(io.StringIO(g.content.decode("utf-8-sig")), delimiter="\t"):
        x = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in x.items()}
        rows.append({"fips": x["GEOID"], "name": x["NAME"], "state_name": "Connecticut", "pop2020": None,
                     "lat": float(x["INTPTLAT"]), "lon": float(x["INTPTLONG"]), "center_kind": "gaz2023_intpt"})
    rows.sort(key=lambda x: x["fips"])
    card = {"source": URL, "license": "US Census Bureau, public domain", "vintage": "2020 Census centers of population",
            "pulled_at": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z", "rows": len(rows),
            "puerto_rico_rows": sum(1 for x in rows if x["fips"].startswith("72")),
            "ct_planning_regions_from_gazetteer": sum(1 for x in rows if x["center_kind"] == "gaz2023_intpt")}
    (DATA / "county_centroids.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")
    (DATA / "county_centroids_card.json").write_text(json.dumps(card, indent=1), encoding="utf-8")
    print(json.dumps(card, indent=1))


if __name__ == "__main__":
    main()
