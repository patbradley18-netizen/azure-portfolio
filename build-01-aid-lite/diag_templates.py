# diag_templates.py - quick check: are the junk-prefix tweets reusing a shared body text?
import re, pandas as pd
full = pd.read_csv("data/IRAhandle_tweets_1.csv", usecols=["author","content","account_category","language","retweet"]).dropna(subset=["content"])
full = full[(full["language"]=="English") & (full["retweet"]==0)]
full["content"] = full["content"].astype(str)

# How often do the suspect leading tags appear?
lead = full["content"].str.extract(r"^#([A-Za-z]{3,8})\s", expand=False)
print("Rows with a short leading hashtag:", lead.notna().sum(), "of", len(full))
print("Top 15 leading tags:\n", lead.value_counts().head(15).to_string())

# Body = text with leading hashtags and all URLs/trailing hashtags stripped
def body(t):
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"^(#\w+\s+)+", "", t)
    t = re.sub(r"(\s+#\w+)+\s*$", "", t)
    return t.strip().lower()
full["body"] = full["content"].apply(body)
full = full[full["body"].str.len() >= 25]
g = full.groupby("body").agg(n=("author","size"), authors=("author","nunique"), cats=("account_category", lambda s: s.value_counts().head(2).to_dict()))
multi = g[(g["n"]>=3) & (g["authors"]>=2)].sort_values("n", ascending=False)
print("\nDistinct bodies posted 3+ times by 2+ authors:", len(multi), "| tweets covered:", int(multi['n'].sum()))
print(multi.head(12).to_string())
