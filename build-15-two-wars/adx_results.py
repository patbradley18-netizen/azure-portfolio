"""Applies kql/functions.kql to the cluster and runs the result queries → data/results.json (committed, force-added).
Auth: KUSTO_TOKEN in env. Usage: python adx_results.py"""
import json, os, re, datetime as dt
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder

CLUSTER = os.environ.get("ADX_CLUSTER_URI", "https://kvc-1267rvs0jur9k7ncmj.southcentralus.kusto.windows.net")
DB = os.environ.get("ADX_DATABASE", "vets")
HERE = os.path.dirname(os.path.abspath(__file__))

QUERIES = {
 "R1_bins": """vet_base() | where cohort in ("vietnam_theater", "gwot_theater", "vietnam_era", "gwot_era") and clock == "separation" and bin !in ("before_end")
   | summarize n=count(), sumw=sum(w), sumw2=sum(w*w), lf=sumif(w, inlf), un=sumif(w, unemp and inlf), emp=sumif(w, employed) by war, cohort, bin
   | extend n_eff = sumw*sumw/sumw2, part = lf/sumw, unemp_rate = un/lf
   | extend part_se = sqrt(part*(1-part)/n_eff), unemp_se = sqrt(unemp_rate*(1-unemp_rate)/(n_eff*part))
   | project war, cohort, bin, n, n_eff=round(n_eff), part=round(part,4), part_se=round(part_se,4), unemp_rate=round(unemp_rate,4), unemp_se=round(unemp_se,4)
   | order by cohort asc, bin asc""",
 "R1_baseline": """vet_base() | where cohort == "nonvet"
   | summarize n=count(), sumw=sum(w), sumw2=sum(w*w), lf=sumif(w, inlf), un=sumif(w, unemp and inlf) by YEAR
   | extend n_eff = sumw*sumw/sumw2, part = lf/sumw, unemp_rate = un/lf
   | project YEAR, n, part=round(part,4), unemp_rate=round(unemp_rate,4) | order by YEAR asc""",
 "R2_years": """vet_base() | where cohort in ("vietnam_theater", "gwot_theater", "vietnam_era", "gwot_era", "nonvet", "all_other")
   | summarize n=count(), sumw=sum(w), sumw2=sum(w*w), lf=sumif(w, inlf), un=sumif(w, unemp and inlf), yo=avgif(todouble(years_out), clock=="separation"), yo_era=avgif(todouble(years_out), clock=="era"), sep_share=countif(clock=="separation")*1.0/count() by YEAR, war, cohort
   | extend n_eff = sumw*sumw/sumw2, part = lf/sumw, unemp_rate = un/lf
   | extend part_se = sqrt(part*(1-part)/n_eff), unemp_se = sqrt(unemp_rate*(1-unemp_rate)/(n_eff*part))
   | project YEAR, war, cohort, n, n_eff=round(n_eff), years_out_mean=round(yo,1), years_out_era=round(yo_era,1), sep_share=round(sep_share,3), part=round(part,4), part_se=round(part_se,4), unemp_rate=round(unemp_rate,4), unemp_se=round(unemp_se,4)
   | order by cohort asc, YEAR asc""",
 "R3_disability": """vet_base() | where cohort in ("vietnam_theater", "gwot_theater", "vietnam_era", "gwot_era") and clock == "separation" and bin !in ("before_end")
   | summarize n=count(), sumw=sumif(w, disabled_known), dis=sumif(w, disabled and disabled_known), sumw_r=sumif(w, rate_known), r50=sumif(w, rated50 and rate_known), n_r=countif(rate_known) by war, cohort, bin
   | extend disabled_share = dis/sumw, rated50_share = iff(n_r > 0, r50/sumw_r, real(null))
   | project war, cohort, bin, n, n_rated=n_r, disabled_share=round(disabled_share,4), rated50_share=round(rated50_share,4) | order by cohort asc, bin asc""",
 "R4_sizes": """vet_base() | summarize n=count(), weighted=round(sum(w)), sep=countif(clock=="separation"), era=countif(clock=="era"), male_share=round(countif(male)*1.0/count(),3), bottom_coded=countif(bottom_coded) by YEAR, cohort | order by YEAR asc, cohort asc""",
 "R6_vs_baseline": """let base = vet_base() | where cohort == "nonvet" | summarize b_lf=sumif(w, inlf), b_un=sumif(w, unemp and inlf), b_w=sum(w) by YEAR | extend b_unemp = b_un/b_lf, b_part = b_lf/b_w;
   vet_base() | where cohort in ("vietnam_theater", "gwot_theater", "vietnam_era", "gwot_era") and clock == "separation" and bin !in ("before_end")
   | summarize cw=sum(w), age=avg(todouble(AGE)) by war, cohort, bin, YEAR
   | join kind=inner base on YEAR
   | summarize base_unemp=round(sum(cw*b_unemp)/sum(cw),4), base_part=round(sum(cw*b_part)/sum(cw),4), mean_age=round(sum(cw*age)/sum(cw),1), years=array_sort_asc(make_set(YEAR)) by war, cohort, bin
   | order by cohort asc, bin asc""",
 "R7_era_pop_share": """cps_raw | where VTSUPPWT > 0 and VETSTAT == 2 and YEAR in (2005, 2016, 2025)
   | summarize vets=sum(VTSUPPWT), vietnam_era=sumif(VTSUPPWT, VWHEN==4), gwot_era=sumif(VTSUPPWT, VWHEN==1), vietnam_theater=sumif(VTSUPPWT, VVIETNAM==2), gwot_theater=sumif(VTSUPPWT, VIRAQ==1 or VAFGHAN==1), n=count() by YEAR
   | extend vietnam_era_share=round(vietnam_era/vets,3), gwot_era_share=round(gwot_era/vets,3), vietnam_theater_share=round(vietnam_theater/vets,3), gwot_theater_share=round(gwot_theater/vets,3)
   | project YEAR, n, vets=round(vets), vietnam_era_share, gwot_era_share, vietnam_theater_share, gwot_theater_share | order by YEAR asc""",
 "R5_male_only": """vet_base() | where male and cohort in ("vietnam_theater", "gwot_theater") and clock == "separation" and bin !in ("before_end")
   | summarize n=count(), sumw=sum(w), sumw2=sum(w*w), lf=sumif(w, inlf), un=sumif(w, unemp and inlf) by cohort, bin
   | extend n_eff = sumw*sumw/sumw2, part = lf/sumw, unemp_rate = un/lf
   | project cohort, bin, n, n_eff=round(n_eff), part=round(part,4), unemp_rate=round(unemp_rate,4) | order by cohort asc, bin asc""",
}

def main():
    c = KustoClient(KustoConnectionStringBuilder.with_token_provider(CLUSTER, lambda: os.environ["KUSTO_TOKEN"]))
    src = open(os.path.join(HERE, "kql", "functions.kql"), encoding="utf-8").read()
    for stmt in re.split(r"\n(?=\.create-or-alter)", src):
        stmt = stmt.strip()
        if stmt.startswith(".create-or-alter"):
            c.execute_mgmt(DB, stmt)
    out = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z", "cluster": CLUSTER, "database": DB}
    for k, q in QUERIES.items():
        rs = c.execute(DB, q).primary_results[0]
        cols = [col.column_name for col in rs.columns]
        out[k] = [dict(zip(cols, row)) for row in rs]
        print(k, len(out[k]), "rows")
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "data", "results.json"), "w"), indent=1, default=str)
    print("written results.json")

if __name__ == "__main__":
    main()
