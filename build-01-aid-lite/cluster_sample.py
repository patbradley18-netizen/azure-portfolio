# cluster_sample.py - stage 1, first look.
# Reads a sample of tweets, turns each into a vector (embedding),
# groups similar vectors (clustering), and prints what each group says.

import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

SAMPLE = 5000          # small on purpose; first run should finish in a few minutes
CLUSTERS = 20          # a guess; we tune this later

# 1. Load. Only English, only original posts (not retweets), only the columns we need.
df = pd.read_csv(
    "data/IRAhandle_tweets_1.csv",
    usecols=["author", "content", "publish_date", "account_category", "language", "retweet"],
)
df = df[(df["language"] == "English") & (df["retweet"] == 0)].dropna(subset=["content"])
df = df.sample(SAMPLE, random_state=42).reset_index(drop=True)
print(f"Rows after filtering and sampling: {len(df)}")

# 2. Embed. all-MiniLM-L6-v2 is small, free, and downloads once (~90 MB).
model = SentenceTransformer("all-MiniLM-L6-v2")
vectors = model.encode(df["content"].tolist(), show_progress_bar=True)
print(f"Vector shape: {vectors.shape}")   # expect (5000, 384)

# 3. Cluster. KMeans puts every tweet into one of CLUSTERS groups.
km = KMeans(n_clusters=CLUSTERS, random_state=42, n_init="auto")
df["cluster"] = km.fit_predict(vectors)

# 4. Read the results. For each cluster: size, which troll categories, three example tweets.
for c in range(CLUSTERS):
    sub = df[df["cluster"] == c]
    cats = sub["account_category"].value_counts().head(3).to_dict()
    print(f"\n=== Cluster {c}: {len(sub)} tweets | categories: {cats}")
    for text in sub["content"].head(3):
        print("  -", str(text)[:140])

df.to_csv("data/sample_clusters.csv", index=False)
print("\nSaved data/sample_clusters.csv")
