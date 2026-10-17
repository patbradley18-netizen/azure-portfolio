"""Applies kql/functions16.kql (function + materialized view) and runs R8–R12 → data/results.json. Auth: KUSTO_TOKEN."""
import json, os, re, datetime as dt, time
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
CLUSTER = os.environ.get("ADX_CLUSTER_URI", "https://kvc-1267rvs0jur9k7ncmj.southcentralus.kusto.windows.net")
DB = "vets"; HERE = os.path.dirname(os.path.abspath(__file__))
BASE = '''let base = vet_base_mv
  | extend war = case(cohort startswith "vietnam", "vietnam", cohort startswith "gwot", "gwot", ""),
           years_out = iff(isnotnull(sep_year), YEAR - sep_year, iff(cohort startswith "vietnam", YEAR - 1975, int(null)))
  | extend clock = iff(isnotnull(sep_year), "separation", iff(isnotnull(years_out), "era", "")),
           bin = case(isnull(years_out), "", years_out < 0, "before_end", years_out <= 4, "00-04", years_out <= 9, "05-09", years_out <= 15, "10-15", years_out <= 22, "16-22", years_out <= 30, "23-30", "31+"),
           ageband = case(AGE <= 34, "18-34", AGE <= 49, "35-49", AGE <= 64, "50-64", "65+");'''
SHARE = '''| summarize n=sum(n), w=sum(w), sumw2=sum(sumw2), ba=sum(ba_w), lt=sum(lt_hs_w), educ=sum(educ_w), hisp=sum(hisp_w), white=sum(white_w), black=sum(black_w), race=sum(race_w), female=sum(female_w), lf=sum(inlf_w), un=sum(unemp_w)'''
EXT = '''| extend n_eff = w*w/sumw2, ba_share = ba/educ, lt_hs_share = lt/educ, hisp_share = hisp/race, white_share = white/race, black_share = black/race, female_share = female/w, part = lf/w, unemp_rate = un/lf'''
QUERIES = {
 "R8_profile_bins": BASE + '''
  base | where cohort in ("vietnam_theater", "gwot_theater") and clock == "separation" and bin !in ("before_end", "") and AGE between (18 .. 64)
  ''' + SHARE + ''' by cohort, bin ''' + EXT + '''
  | project cohort, bin, n, n_eff=round(n_eff), ba_share=round(ba_share,4), lt_hs_share=round(lt_hs_share,4), hisp_share=round(hisp_share,4), white_share=round(white_share,4), black_share=round(black_share,4), female_share=round(female_share,4)
  | order by cohort asc, bin asc''',
 "R9_reference_agematched": BASE + '''
  let mix = base | where cohort in ("vietnam_theater", "gwot_theater") and clock == "separation" and bin !in ("before_end", "") and AGE between (18 .. 64) | summarize cw=sum(w) by cohort, bin, YEAR, ageband;
  let ref = base | where cohort == "nonvet" and AGE between (18 .. 64) ''' + SHARE + ''' by YEAR, ageband ''' + EXT + ''';
  mix | join kind=inner ref on YEAR, ageband
  | summarize ref_ba=sum(cw*ba_share)/sum(cw), ref_lt_hs=sum(cw*lt_hs_share)/sum(cw), ref_hisp=sum(cw*hisp_share)/sum(cw), ref_white=sum(cw*white_share)/sum(cw), ref_black=sum(cw*black_share)/sum(cw), ref_female=sum(cw*female_share)/sum(cw), ref_n=sum(n) by cohort, bin
  | project cohort, bin, ref_n, ref_ba=round(ref_ba,4), ref_lt_hs=round(ref_lt_hs,4), ref_hisp=round(ref_hisp,4), ref_white=round(ref_white,4), ref_black=round(ref_black,4), ref_female=round(ref_female,4)
  | order by cohort asc, bin asc''',
 "R10_profile_years": BASE + '''
  base | where cohort in ("vietnam_theater", "gwot_theater", "nonvet", "all_other") and AGE between (18 .. 64) ''' + SHARE + ''' by cohort, YEAR ''' + EXT + '''
  | project cohort, YEAR, n, ba_share=round(ba_share,4), lt_hs_share=round(lt_hs_share,4), hisp_share=round(hisp_share,4), white_share=round(white_share,4), black_share=round(black_share,4), female_share=round(female_share,4), mean_age_proxy=0
  | order by cohort asc, YEAR asc''',
 "R11_survival": BASE + '''
  // closed cohorts, all ages: observed headcount at each survey year vs expected survivors from the previous survey year
  let coh = base | where (cohort == "vietnam_theater") or (cohort == "gwot_theater" and sep_year <= 2009 and YEAR >= 2010) | summarize w=sum(w), n=sum(n), sumw2=sum(sumw2) by cohort, YEAR, sex, AGE;
  let years = coh | summarize by YEAR | order by YEAR asc | extend rn = row_number() | project YEAR, rn;
  let nxt = years | join kind=inner (years | project y2=YEAR, rn1=rn - 1) on $left.rn == $right.rn1 | project y1=YEAR, y2;
  coh | join kind=inner nxt on $left.YEAR == $right.y1
  | join kind=leftouter ssa_surv on y1, y2, sex, $left.AGE == $right.age
  | extend p = coalesce(p, 0.0)
  | summarize n1=sum(n), w1=sum(w), sumw2_1=sum(sumw2), expected_alive=sum(w*p) by cohort, y1, y2
  | join kind=inner (coh | summarize n2=sum(n), w2=sum(w), sumw2_2=sum(sumw2) by cohort, YEAR) on cohort, $left.y2 == $right.YEAR
  | extend observed_deaths = w1 - w2, expected_deaths = w1 - expected_alive
  | extend ratio = observed_deaths / expected_deaths, se1 = sqrt(sumw2_1), se2 = sqrt(sumw2_2)
  | extend ratio_lo = (observed_deaths - 1.96*sqrt(se1*se1 + se2*se2)) / expected_deaths, ratio_hi = (observed_deaths + 1.96*sqrt(se1*se1 + se2*se2)) / expected_deaths
  | project cohort, y1, y2, n1, n2, w1=round(w1), w2=round(w2), expected_alive=round(expected_alive), observed_deaths=round(observed_deaths), expected_deaths=round(expected_deaths), ratio=round(ratio,2), ratio_lo=round(ratio_lo,2), ratio_hi=round(ratio_hi,2)
  | order by cohort asc, y1 asc''',
 "R12_survival_windows": BASE + '''
  // same arithmetic over longer gaps (every ~5-year pair available in ssa_surv), to beat the sampling noise
  let coh = base | where (cohort == "vietnam_theater") or (cohort == "gwot_theater" and sep_year <= 2009 and YEAR >= 2010) | summarize w=sum(w), n=sum(n), sumw2=sum(sumw2) by cohort, YEAR, sex, AGE;
  let pairs = datatable(y1:int, y2:int) [1985,1991, 1991,1995, 1995,1999, 1999,2003, 2003,2007, 2007,2011, 2011,2015, 2015,2019, 2019,2023, 2010,2015, 2015,2020, 2020,2025];
  coh | join kind=inner pairs on $left.YEAR == $right.y1
  | join kind=leftouter ssa_surv on y1, y2, sex, $left.AGE == $right.age
  | extend p = coalesce(p, 0.0)
  | summarize n1=sum(n), w1=sum(w), sumw2_1=sum(sumw2), expected_alive=sum(w*p) by cohort, y1, y2
  | join kind=inner (coh | summarize n2=sum(n), w2=sum(w), sumw2_2=sum(sumw2) by cohort, YEAR) on cohort, $left.y2 == $right.YEAR
  | extend observed_deaths = w1 - w2, expected_deaths = w1 - expected_alive
  | extend ratio = observed_deaths / expected_deaths, se = sqrt(sumw2_1 + sumw2_2)
  | extend ratio_lo = (observed_deaths - 1.96*se) / expected_deaths, ratio_hi = (observed_deaths + 1.96*se) / expected_deaths
  | project cohort, y1, y2, n1, n2, w1=round(w1), w2=round(w2), observed_deaths=round(observed_deaths), expected_deaths=round(expected_deaths), ratio=round(ratio,2), ratio_lo=round(ratio_lo,2), ratio_hi=round(ratio_hi,2)
  | order by cohort asc, y1 asc''',
 "R13_vetpop": '''vetpop | where period startswith "Vietnam" and year <= 2030 | summarize veterans=sum(veterans) by year | order by year asc | serialize | extend deaths = prev(veterans) - veterans | extend rate = round(todouble(deaths) / prev(veterans), 4)''',
 "R14_age_mix": BASE + '''base | where cohort in ("vietnam_theater", "gwot_theater") | summarize w=sum(w), n=sum(n), mean_age=sum(w*AGE)/sum(w), female=sum(female_w)/sum(w) by cohort, YEAR | project cohort, YEAR, n, w=round(w), mean_age=round(mean_age,1), female_share=round(female,3) | order by cohort asc, YEAR asc''',
}
def main():
    c = KustoClient(KustoConnectionStringBuilder.with_token_provider(CLUSTER, lambda: os.environ["KUSTO_TOKEN"]))
    src = open(os.path.join(HERE, "kql", "functions16.kql"), encoding="utf-8").read()
    for stmt in re.split(r"\n(?=\.create)", src):
        stmt = stmt.strip()
        if not stmt.startswith(".create"): continue
        if "materialized-view" in stmt and False: pass
        stmt = stmt[:stmt.rindex("}") + 1]  # drop trailing comment lines that belong to the next statement
        if "materialized-view" in stmt:
            try:
                c.execute_mgmt(DB, stmt)
            except Exception as ex:
                print("VIEW statement error:", str(ex)[:600]); raise
        else:
            try:
                c.execute_mgmt(DB, stmt)
            except Exception as ex:
                print("FAILED statement:", stmt[:90].replace("\n", " "))
                print("ERROR:", str(ex)[:800]); raise
    for i in range(30):
        try:
            st = c.execute_mgmt(DB, ".show materialized-view vet_base_mv").primary_results[0][0]
            if st["IsHealthy"] and st["LastRun"] and str(st["LastRun"]) != "None":
                print("view ready; last run", st["LastRun"]); break
            print("view not ready yet (healthy=%s); waiting" % st["IsHealthy"])
        except Exception as ex:
            print("view not visible yet; waiting", str(ex)[:80])
        time.sleep(15)
    out = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z", "cluster": CLUSTER, "database": DB}
    for k, q in QUERIES.items():
        try:
            rs = c.execute(DB, q).primary_results[0]
        except Exception as ex:
            print("FAILED query", k, str(ex)[:800]); raise
        cols = [col.column_name for col in rs.columns]
        out[k] = [dict(zip(cols, row)) for row in rs]
        print(k, len(out[k]), "rows")
    json.dump(out, open(os.path.join(HERE, "data", "results.json"), "w"), indent=1, default=str)
    print("written results.json")
if __name__ == "__main__":
    main()
