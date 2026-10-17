"""Builds vets.ssa_qx (year, sex, age, qx) from the four SSA period life tables and vets.vetpop from the VetPop2023
period-of-service file, then ingests both (inline — a few thousand rows). Auth: KUSTO_TOKEN in env."""
import csv, io, os, sys, urllib.request
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
CLUSTER = os.environ.get("ADX_CLUSTER_URI", "https://kvc-1267rvs0jur9k7ncmj.southcentralus.kusto.windows.net")
DB = "vets"; HERE = os.path.dirname(os.path.abspath(__file__))
c = KustoClient(KustoConnectionStringBuilder.with_token_provider(CLUSTER, lambda: os.environ["KUSTO_TOKEN"]))

def ssa_rows():
    for sex, files in (("M", ["PerLifeTables_M_Hist_TR2023.csv", "PerLifeTables_M_Alt2_TR2023.csv"]), ("F", ["PerLifeTables_F_Hist_TR2023.csv", "PerLifeTables_F_Alt2_TR2023.csv"])):
        for fn in files:
            with open(os.path.join(HERE, "reference", "ssa", fn), encoding="utf-8", errors="replace") as f:
                started = False
                for line in f:
                    if line.startswith("Year,x,q(x)"):
                        started = True; continue
                    if not started: continue
                    p = line.strip().split(",")
                    if len(p) < 3 or not p[0].isdigit(): continue
                    y, a = int(p[0]), int(p[1])
                    if 1984 <= y <= 2030 and a <= 110:
                        yield (y, sex, a, float(p[2]))

def vetpop_rows():
    with open(os.path.join(HERE, "reference", "vetpop2023_period_of_service.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            yield (int(r["Date"][:4]), r["Sex"], r["Period of Service"].split(" ", 1)[1].split(" (")[0], int(r["Veterans"].replace(",", "")))

def ingest(table, schema, rows, fmt):
    c.execute_mgmt(DB, f".drop table {table} ifexists")
    c.execute_mgmt(DB, f".create table {table} ({schema})")
    buf, n = [], 0
    for r in rows:
        buf.append(fmt(r)); n += 1
        if len(buf) == 2000:
            c.execute_mgmt(DB, f".ingest inline into table {table} <|\n" + "\n".join(buf)); buf = []
    if buf: c.execute_mgmt(DB, f".ingest inline into table {table} <|\n" + "\n".join(buf))
    print(table, n, "rows")

ingest("ssa_qx", "year:int, sex:string, age:int, qx:real", ssa_rows(), lambda r: f"{r[0]},{r[1]},{r[2]},{r[3]}")
ingest("vetpop", "year:int, sex:string, period:string, veterans:long", vetpop_rows(), lambda r: f'{r[0]},{r[1]},"{r[2]}",{r[3]}')

# survival probability from survey year y1 to y2 for a person of sex s aged a at y1: product of (1 - qx) over the gap years, age advancing
YEARS = [1985, 1987, 1991, 1993, 1995, 1997, 1999, 2001, 2003, 2005, 2007, 2009, 2010] + list(range(2011, 2026))
qx = {}
for r in ssa_rows():
    qx[(r[0], r[1], r[2])] = r[3]
def surv_rows():
    for i, y1 in enumerate(YEARS):
        for y2 in YEARS[i + 1:]:
            for sex in ("M", "F"):
                for a in range(17, 101):
                    p = 1.0
                    for k in range(y1, y2):
                        age = min(a + (k - y1), 110)
                        p *= 1.0 - qx.get((k, sex, age), qx.get((k, sex, 100), 0.4))
                    yield (y1, y2, sex, a, p)
ingest("ssa_surv", "y1:int, y2:int, sex:string, age:int, p:real", surv_rows(), lambda r: f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]:.6f}")
print(c.execute(DB, "ssa_surv | where y1==1991 and y2==1995 and sex=='M' and age in (45, 60, 75) | project age, p").primary_results[0])
print(c.execute(DB, "ssa_qx | summarize n=count(), years=dcount(year), minq=min(qx), maxq=max(qx) by sex").primary_results[0])
print(c.execute(DB, "vetpop | where period startswith 'Vietnam' | summarize sum(veterans) by year | order by year asc | take 4").primary_results[0])
