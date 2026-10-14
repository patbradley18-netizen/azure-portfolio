# detect.py - the detection logic, kept separate from the Azure Function wrapper so it can be
# tested locally with plain Python and no cloud at all.
import re
import pandas as pd

def body(t: str) -> str:
    """Strip URLs and leading/trailing hashtags; lowercase. What's left is the message."""
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"^(#\w+\s+)+", "", t)
    t = re.sub(r"(\s+#\w+)+\s*$", "", t)
    return t.strip().lower()

def find_templates(df: pd.DataFrame, min_posts: int = 3, min_authors: int = 2) -> pd.DataFrame:
    """Return bodies posted >= min_posts times by >= min_authors distinct accounts."""
    df = df.dropna(subset=["content"])
    df = df[(df["language"] == "English") & (df["retweet"] == 0)].copy()
    df["content"] = df["content"].astype(str)
    df["body"] = df["content"].map(body)
    df = df[df["body"].str.len() >= 25]
    g = df.groupby("body").agg(
        n_tweets=("author", "size"),
        n_authors=("author", "nunique"),
        top_category=("account_category", lambda s: s.value_counts().index[0]),
    )
    out = g[(g["n_tweets"] >= min_posts) & (g["n_authors"] >= min_authors)].reset_index()
    out["body"] = out["body"].str.slice(0, 500)
    return out.sort_values(["n_authors", "n_tweets"], ascending=False).reset_index(drop=True)

def summarize(templates: pd.DataFrame, english_originals: int) -> dict:
    return {
        "templates": int(len(templates)),
        "tweets_in_templates": int(templates["n_tweets"].sum()) if len(templates) else 0,
        "max_authors": int(templates["n_authors"].max()) if len(templates) else 0,
        "templates_10plus": int((templates["n_authors"] >= 10).sum()),
        "english_originals": int(english_originals),
    }