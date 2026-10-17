"""Creates the raw table in the ADX free cluster and ingests one extract file (tagged by extract number).
Auth: an Entra token in env KUSTO_TOKEN (from `az account get-access-token --resource https://api.kusto.windows.net`).
Usage: python adx_setup.py data/cps_00002.csv.gz 2
"""
import os, sys, time
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.data_format import DataFormat
from azure.kusto.ingest import IngestionProperties, QueuedIngestClient

CLUSTER = os.environ.get("ADX_CLUSTER_URI", "https://kvc-1267rvs0jur9k7ncmj.southcentralus.kusto.windows.net")
INGEST = os.environ.get("ADX_INGEST_URI", CLUSTER.replace("https://", "https://ingest-"))
DB = os.environ.get("ADX_DATABASE", "vets")
COLS = [("YEAR", "int"), ("SERIAL", "long"), ("MONTH", "int"), ("HWTFINL", "real"), ("CPSID", "long"), ("PERNUM", "int"), ("WTFINL", "real"),
        ("CPSIDP", "long"), ("CPSIDV", "long"), ("AGE", "int"), ("SEX", "int"), ("VETSTAT", "int"), ("EMPSTAT", "int"), ("LABFORCE", "int"),
        ("VCOMBAT", "int"), ("VDISABLE", "int"), ("VDISRATE", "int"), ("VLASTSERVE", "int"), ("VTSUPPWT", "real"), ("VWHEN", "int"),
        ("VIRAQ", "int"), ("VAFGHAN", "int"), ("VVIETNAM", "int")]

def tok():
    return os.environ["KUSTO_TOKEN"]

def main(path, number):
    q = KustoClient(KustoConnectionStringBuilder.with_token_provider(CLUSTER, tok))
    q.execute_mgmt(DB, ".create table cps_raw (" + ", ".join(f"{c}:{t}" for c, t in COLS) + ")")
    q.execute_mgmt(DB, ".alter table cps_raw policy ingestionbatching '{\"MaximumBatchingTimeSpan\":\"00:00:30\"}'")
    # header check: the file's first line must match COLS in order (CSV mapping is ordinal)
    import gzip
    with gzip.open(path, "rt") as f:
        header = [h.strip('"') for h in f.readline().strip().split(",")]
    assert header == [c for c, _ in COLS], f"header mismatch: {header}"
    ing = QueuedIngestClient(KustoConnectionStringBuilder.with_token_provider(INGEST, tok))
    props = IngestionProperties(database=DB, table="cps_raw", data_format=DataFormat.CSV, ignore_first_record=True,
                                additional_tags=[f"extract:{number}"], drop_by_tags=[f"extract:{number}"])
    r = ing.ingest_from_file(path, ingestion_properties=props)
    print("queued:", r.status)
    for i in range(40):
        time.sleep(15)
        n = q.execute(DB, f"cps_raw | where extent_tags() has 'extract:{number}' | count").primary_results[0][0][0]
        print("rows so far", n)
        if n >= 3580995:
            break
    print(q.execute(DB, "cps_raw | summarize n=count(), vets=countif(VETSTAT==2) by YEAR | order by YEAR asc").primary_results[0])

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
