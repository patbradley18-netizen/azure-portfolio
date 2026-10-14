"""AID stage 3, signal D: narrative bursts.

For each template (stage 2 definition: same body, >=3 posts, >=2 authors),
count posts per day. Finding: most templates are posted on ONE day only
("one-day blast"), so a median-based burst score is meaningless (median =
peak). We report blast share, days active, peak day, and the daily timeline
of template posts vs all originals instead.

Run: python analyze_bursts.py
Writes data/bursts.csv, data/daily_volume.csv, data/bursts_summary.json.
"""
import sys, json
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE / "function"))
from detect import find_templates, body

def main():
    df = pd.read_csv(DATA / "IRAhandle_tweets_1.csv", low_memory=False)
    df = df[(df["language"] == "English") & (df["retweet"] == 0)].copy()
    df["day"] = pd.to_datetime(df["publish_date"], format="%m/%d/%Y %H:%M", errors="coerce").dt.normalize()
    df = df.dropna(subset=["day"])
    df["b"] = df["content"].astype(str).map(body)
    t = find_templates(df.rename(columns={}))
    tb = set(t["body"])
    tp = df[df["b"].isin(tb)]
    print(f"English originals: {len(df):,}   template posts: {len(tp):,}   templates: {len(tb):,}")

    daily = tp.groupby(["b", "day"]).size().reset_index(name="n")
    rows = []
    for b, g in daily.groupby("b"):
        med = g["n"].median()
        peak = g.loc[g["n"].idxmax()]
        burst_days = int((g["n"] >= 3 * med).sum())
        rows.append({"body": b, "days_active": len(g), "median_per_day": float(med),
                     "peak_day": peak["day"].date().isoformat(), "peak_count": int(peak["n"]),
                     "burst_score": round(float(peak["n"] / med), 1), "burst_days": burst_days,
                     "total": int(g["n"].sum())})
    bursts = pd.DataFrame(rows).sort_values(["peak_count", "days_active"], ascending=False)
    bursts.to_csv(DATA / "bursts.csv", index=False)

    vol = (df.groupby("day").size().rename("all_originals").to_frame()
             .join(tp.groupby("day").size().rename("template_posts")).fillna(0).astype(int)
             .reset_index())
    vol["day"] = vol["day"].dt.date.astype(str)
    vol.to_csv(DATA / "daily_volume.csv", index=False)
    top_days = vol.sort_values("template_posts", ascending=False).head(10)

    summary = {
        "templates": int(len(bursts)),
        "single_day_templates": int((bursts["days_active"] == 1).sum()),
        "median_days_active": float(bursts["days_active"].median()),
        "blast_share_pct": round(float((bursts["days_active"] == 1).mean() * 100), 1),
        "multi_day_templates": int((bursts["days_active"] > 1).sum()),
        "max_days_active": int(bursts["days_active"].max()),
        "template_posts": int(len(tp)),
        "peak_day": str(top_days.iloc[0]["day"]), "peak_day_template_posts": int(top_days.iloc[0]["template_posts"]),
        "peak_day_share_pct": round(float(top_days.iloc[0]["template_posts"] / top_days.iloc[0]["all_originals"] * 100), 1),
        "date_min": vol["day"].min(), "date_max": vol["day"].max(),
        "top_bursts": bursts.head(20).to_dict(orient="records"),
        "top_days": top_days.to_dict(orient="records"),
        "daily_volume": vol.to_dict(orient="records"),
    }
    (DATA / "bursts_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("top_bursts", "top_days", "daily_volume")}, indent=1))
    print("\nLongest-running templates:\n", bursts.sort_values("days_active", ascending=False).head(10)[["body", "days_active", "peak_day", "peak_count", "total"]].to_string(index=False))
    print("\nBusiest template days:\n", top_days.to_string(index=False))

if __name__ == "__main__":
    main()