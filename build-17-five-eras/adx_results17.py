"""Creates era_base_mv (if needed) and runs R15–R18 → data/results.json. Auth: KUSTO_TOKEN."""
import json, os, re, time, datetime as dt
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
CLUSTER = os.environ.get("ADX_CLUSTER_URI", "https://kvc-1267rvs0jur9k7ncmj.southcentralus.kusto.windows.net")
DB = "vets"; HERE = os.path.dirname(os.path.abspath(__file__))
# working-age windows per era (years in which the cohort is 18–64 and reasonably complete)
WINDOWS = '''let windows = datatable(era:string, y0:int, y1:int) ["wwii",1968,1990, "korea",1968,2000, "vietnam",1968,2025, "era7590",1975,2025, "gulfwar1",1991,2025, "post911",2006,2025];'''
SUMS = "n=sum(n), w=sum(w), sumw2=sum(sumw2), female=sum(female_w), female_den=sum(female_den_w), hisp=sum(hisp_w), hisp_den=sum(hisp_den_w), white=sum(white_w), black=sum(black_w), race=sum(race_w), born=sum(born_w), natur=sum(natur_w), noncit=sum(noncit_w), cit=sum(cit_w), foreign=sum(foreign_w), secondgen=sum(secondgen_w), nativepar=sum(nativepar_w), nat=sum(nat_w), lt=sum(lt_hs_w), ba=sum(ba_w), educ=sum(educ_w), multi=sum(multi_w)"
SHARES = "n_eff=round(w*w/sumw2), female_share=round(female/female_den,4), hisp_share=round(hisp/hisp_den,4), white_share=round(white/race,4), black_share=round(black/race,4), born_share=round(born/cit,4), natur_share=round(natur/cit,4), noncit_share=round(noncit/cit,4), foreign_share=round(foreign/nat,4), secondgen_share=round(secondgen/nat,4), lt_hs_share=round(lt/educ,4), ba_share=round(ba/educ,4), multi_share=round(multi/w,4), n_cit=cit, n_nat=nat, n_female=female_den, n_hisp=hisp_den"
QUERIES = {
 # era cohorts pooled over their working-age window, 18–64 — and the age-matched civilian reference built from the cohort's own (year, ageband) mix
 "R15_era_pooled": WINDOWS + '''
  let coh = era_base_mv | where ageband != "65+" | join kind=inner windows on era | where YEAR between (y0 .. y1);
  let cohort = coh | summarize ''' + SUMS + ''' by era | extend ''' + SHARES + ''';
  let civ = era_base_mv | where ageband != "65+" | summarize ''' + SUMS + ''' by YEAR, ageband | extend ''' + SHARES + ''';
  let ref = coh | summarize cw=sum(w) by era, YEAR, ageband | join kind=inner civ on YEAR, ageband
    | summarize ref_n=sum(n), ref_female=sumif(cw*female_share, isfinite(female_share))/sumif(cw, isfinite(female_share)), ref_hisp=sumif(cw*hisp_share, isfinite(hisp_share))/sumif(cw, isfinite(hisp_share)), ref_white=sum(cw*white_share)/sum(cw), ref_black=sum(cw*black_share)/sum(cw), ref_born=sum(cw*born_share)/sum(cw), ref_natur=sum(cw*natur_share)/sum(cw), ref_noncit=sum(cw*noncit_share)/sum(cw), ref_foreign=sum(cw*foreign_share)/sum(cw), ref_secondgen=sum(cw*secondgen_share)/sum(cw), ref_lt_hs=sum(cw*lt_hs_share)/sum(cw), ref_ba=sum(cw*ba_share)/sum(cw), years=array_sort_asc(make_set(YEAR)) by era;
  cohort | join kind=inner ref on era | project-away era1 | order by era asc''',
 "R16_era_years": '''union (era_base_mv | where ageband != "65+"), (era_base_mv | where ageband != "65+" | extend era = "population") | summarize ''' + SUMS + ''' by era, YEAR | extend ''' + SHARES + ''' | project era, YEAR, n, n_eff, female_share, hisp_share, white_share, black_share, born_share, noncit_share, foreign_share, lt_hs_share, ba_share, multi_share | order by era asc, YEAR asc''',
 "R17_citizen_years": '''era_base_mv | where YEAR >= 1994 and ageband != "65+" | summarize ''' + SUMS + ''' by era, YEAR | extend ''' + SHARES + ''' | project era, YEAR, n_cit, born_share, natur_share, noncit_share, foreign_share, secondgen_share | order by era asc, YEAR asc''',
 "R18_sizes": '''era_base_mv | summarize n=sum(n), w=round(sum(w)) by era, YEAR | order by era asc, YEAR asc''',
 "R19_all_ages": WINDOWS + '''
  let coh = era_base_mv | join kind=inner windows on era | where YEAR between (y0 .. y1);
  let cohort = coh | summarize ''' + SUMS + ''' by era | extend ''' + SHARES + ''';
  let civ = era_base_mv | summarize ''' + SUMS + ''' by YEAR, ageband | extend ''' + SHARES + ''';
  let ref = coh | summarize cw=sum(w) by era, YEAR, ageband | join kind=inner civ on YEAR, ageband
    | summarize ref_n=sum(n), ref_female=sumif(cw*female_share, isfinite(female_share))/sumif(cw, isfinite(female_share)), ref_hisp=sumif(cw*hisp_share, isfinite(hisp_share))/sumif(cw, isfinite(hisp_share)), ref_white=sum(cw*white_share)/sum(cw), ref_black=sum(cw*black_share)/sum(cw), ref_born=sum(cw*born_share)/sum(cw), ref_noncit=sum(cw*noncit_share)/sum(cw), ref_foreign=sum(cw*foreign_share)/sum(cw), ref_lt_hs=sum(cw*lt_hs_share)/sum(cw), ref_ba=sum(cw*ba_share)/sum(cw) by era;
  cohort | join kind=inner ref on era | project-away era1 | order by era asc''',
}
def main():
    c = KustoClient(KustoConnectionStringBuilder.with_token_provider(CLUSTER, lambda: os.environ["KUSTO_TOKEN"]))
    src = open(os.path.join(HERE, "kql", "functions17.kql"), encoding="utf-8").read()
    c.execute_mgmt(DB, ".drop materialized-view era_base_mv ifexists")
    for stmt in re.split(r"\n(?=\.create)", src):
        stmt = stmt.strip()
        if not stmt.startswith(".create"): continue
        stmt = stmt[:stmt.rindex("}") + 1]
        try:
            c.execute_mgmt(DB, stmt)
        except Exception as ex:
            print("statement error:", str(ex)[:500]); raise
    for i in range(40):
        try:
            st = c.execute_mgmt(DB, ".show materialized-view era_base_mv").primary_results[0][0]
            if st["IsHealthy"] and st["LastRun"] and str(st["LastRun"]) != "None":
                print("view ready; last run", st["LastRun"]); break
            print("view not ready (healthy=%s)" % st["IsHealthy"])
        except Exception as ex:
            print("view not visible yet", str(ex)[:60])
        time.sleep(15)
    out = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z", "cluster": CLUSTER, "database": DB}
    for k, q in QUERIES.items():
        try:
            rs = c.execute(DB, q).primary_results[0]
        except Exception as ex:
            print("FAILED", k, str(ex)[:600]); raise
        cols = [col.column_name for col in rs.columns]
        out[k] = [dict(zip(cols, row)) for row in rs]; print(k, len(out[k]), "rows")
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "data", "results.json"), "w"), indent=1, default=str); print("written results.json")
if __name__ == "__main__":
    main()
