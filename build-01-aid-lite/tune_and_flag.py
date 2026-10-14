# tune_and_flag.py - stage 1, part 2.
# (1) Choose the cluster count k with evidence (silhouette score), not a guess.
# (2) Add a second, rule-based signal: a nonsense hashtag stuck in front of a headline.
# (3) Check whether the two signals agree.

import re
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

SAMPLE = 5000
K_OPTIONS = [10, 15, 20, 30, 40]

# ---- Load the same sample as cluster_sample.py (same random_state => same rows) ----
df = pd.read_csv(
    "data/IRAhandle_tweets_1.csv",
    usecols=["author", "content", "publish_date", "account_category", "language", "retweet"],
)
df = df[(df["language"] == "English") & (df["retweet"] == 0)].dropna(subset=["content"])
df = df.sample(SAMPLE, random_state=42).reset_index(drop=True)
df["content"] = df["content"].astype(str)

model = SentenceTransformer("all-MiniLM-L6-v2")
vectors = model.encode(df["content"].tolist(), show_progress_bar=False)

# ---- (1) Pick k. Silhouette: 1 = perfectly separated clusters, 0 = overlapping. ----
print("\n== Silhouette by k (higher is better) ==")
results = {}
for k in K_OPTIONS:
    km = KMeans(n_clusters=k, random_state=42, n_init="auto").fit(vectors)
    score = silhouette_score(vectors, km.labels_, sample_size=3000, random_state=42)
    results[k] = (score, km.labels_)
    print(f"k={k:>3}: silhouette={score:.3f}")
best_k = max(results, key=lambda k: results[k][0])
print(f"Best k by silhouette: {best_k}")
df["cluster"] = results[best_k][1]

# ---- (2) Rule: leading nonsense hashtag. ----
# Pattern: tweet STARTS with "#word " where word is 3-8 lowercase letters.
# "Nonsense" = that hashtag appears rarely in the whole file (a real campaign tag repeats; junk doesn't).
full = pd.read_csv("data/IRAhandle_tweets_1.csv", usecols=["content"]).dropna()
lead = full["content"].astype(str).str.extract(r"^#([a-z]{3,8})\s", expand=False)
tag_counts = lead.value_counts()
common_tags = set(tag_counts[tag_counts >= 20].index)   # tags seen 20+ times = real recurring tags

def leading_junk_tag(text):
    m = re.match(r"^#([a-z]{3,8})\s", text)
    return bool(m) and m.group(1) not in common_tags

df["junk_prefix"] = df["content"].apply(leading_junk_tag)
print(f"\n== Rule: leading junk hashtag ==")
print(f"Flagged: {df['junk_prefix'].sum()} of {len(df)} tweets ({df['junk_prefix'].mean():.1%})")
print("By account category:")
print(df.groupby("account_category")["junk_prefix"].agg(["sum", "mean"]).round(3).to_string())

# ---- (3) Do the signals agree? Cluster "tightness" = how pure it is on account_category. ----
purity = df.groupby("cluster")["account_category"].agg(lambda s: s.value_counts().iloc[0] / len(s))
flag_rate = df.groupby("cluster")["junk_prefix"].mean()
size = df.groupby("cluster").size()
summary = pd.DataFrame({"size": size, "purity": purity.round(2), "junk_prefix_rate": flag_rate.round(2)})
summary = summary.sort_values("junk_prefix_rate", ascending=False)
print(f"\n== Per-cluster (k={best_k}): purity vs. junk-prefix rate ==")
print(summary.to_string())
corr = summary["purity"].corr(summary["junk_prefix_rate"])
print(f"\nCorrelation purity <-> junk_prefix_rate across clusters: {corr:.2f}")

# Examples of flagged tweets, for the README
print("\n== 5 flagged examples ==")
for t in df[df["junk_prefix"]]["content"].head(5):
    print("  -", t[:140])

df.to_csv("data/sample_clusters_v2.csv", index=False)
summary.to_csv("data/cluster_summary_v2.csv")
print("\nSaved data/sample_clusters_v2.csv and data/cluster_summary_v2.csv")
