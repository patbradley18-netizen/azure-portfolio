"""AID stage 3, signal C: amplification network.

Two kinds of edge, both directed retweeter --> retweeted:
  external: body starts with "RT @handle:" or "RT handle:" (the dataset often
            strips the @). Only a minority of retweets carry a handle; the
            handle is usually an outside account the operation boosted)
  internal: a retweet whose body matches an original posted EARLIER by a
            different account in this dataset (troll amplifies troll)
Hubs    = accounts retweeted the most (weighted in-degree).
Brokers = accounts that retweet the most distinct hubs (out-degree).
Ring check = do the 44-account ring members amplify each other?

Run: python analyze_network.py
Writes data/edges.csv, data/hubs.csv, data/brokers.csv, data/network_summary.json.
"""
import re, sys, json
from pathlib import Path
import pandas as pd
import networkx as nx

HERE = Path(__file__).parent
DATA = HERE / "data"
RT_RE = re.compile(r"^\s*RT\s+@?([A-Za-z0-9_]{1,15})\s*:", re.IGNORECASE)  # @ is often stripped in this dataset
sys.path.insert(0, str(HERE / "function"))
from detect import find_templates, body

def main():
    df = pd.read_csv(DATA / "IRAhandle_tweets_1.csv", low_memory=False)
    df = df[df["language"] == "English"].copy()
    df["author_l"] = df["author"].str.lower()
    df["b"] = df["content"].astype(str).map(body)
    df["ts"] = pd.to_datetime(df["publish_date"], format="%m/%d/%Y %H:%M", errors="coerce")
    orig = df[df["retweet"] == 0]
    rts = df[df["retweet"] == 1].copy()

    # external edges
    # (any row, not just retweet==1: some manual RTs and quotes are flagged 0)
    df["target"] = df["content"].astype(str).str.extract(RT_RE, expand=False).str.lower()
    ext = df.dropna(subset=["target"])[["author_l", "target", "account_category"]]
    ext = ext.assign(kind="external")

    # internal edges: retweet body == an earlier original by another account
    first = (orig.sort_values("ts").drop_duplicates("b")[["b", "author_l", "ts"]]
                 .rename(columns={"author_l": "target", "ts": "orig_ts"}))
    m = rts.merge(first, on="b")
    m = m[(m["author_l"] != m["target"]) & (m["ts"] >= m["orig_ts"])]
    inn = m[["author_l", "target", "account_category"]].assign(kind="internal")

    edges = (pd.concat([ext, inn]).rename(columns={"author_l": "source"})
               .groupby(["source", "target", "kind", "account_category"]).size()
               .reset_index(name="weight").sort_values("weight", ascending=False))
    edges.to_csv(DATA / "edges.csv", index=False)
    print(f"English rows {len(df):,}  originals {len(orig):,}  retweets {len(rts):,}")
    print(f"external edges {len(ext):,}  internal edges {len(inn):,}  unique edges {len(edges):,}")

    G = nx.DiGraph()
    for r in edges.itertuples(index=False):
        if G.has_edge(r.source, r.target):
            G[r.source][r.target]["weight"] += r.weight
        else:
            G.add_edge(r.source, r.target, weight=r.weight)

    troll = set(df["author_l"].unique())
    cat = df.groupby("author_l")["account_category"].agg(lambda s: s.mode().iat[0])
    hubs = (pd.DataFrame({"handle": [n for n in G.nodes if G.in_degree(n) > 0]})
              .assign(retweets=lambda d: d["handle"].map(dict(G.in_degree(weight="weight"))),
                      distinct_retweeters=lambda d: d["handle"].map(dict(G.in_degree())),
                      in_dataset=lambda d: d["handle"].isin(troll),
                      category=lambda d: d["handle"].map(cat).fillna("external"))
              .sort_values("retweets", ascending=False))
    hubs.to_csv(DATA / "hubs.csv", index=False)
    brokers = (pd.DataFrame({"handle": [n for n in G.nodes if G.out_degree(n) > 0]})
                 .assign(distinct_hubs=lambda d: d["handle"].map(dict(G.out_degree())),
                         retweets=lambda d: d["handle"].map(dict(G.out_degree(weight="weight"))),
                         category=lambda d: d["handle"].map(cat).fillna("external"))
                 .sort_values(["distinct_hubs", "retweets"], ascending=False))
    brokers.to_csv(DATA / "brokers.csv", index=False)

    # ring check
    t = find_templates(df)
    ring_bodies = set(t[t["n_authors"] == t["n_authors"].max()]["body"])
    ring = set(orig[orig["b"].isin(ring_bodies)]["author_l"])
    ring_out = edges[edges["source"].isin(ring)]
    ring_in = edges[edges["target"].isin(ring)]
    ring_ring = ring_out[ring_out["target"].isin(ring)]

    # category mix of internal amplification (who amplifies whom)
    inn_cat = inn.assign(target_cat=inn["target"].map(cat))
    mix = inn_cat.groupby(["account_category", "target_cat"]).size().reset_index(name="n").sort_values("n", ascending=False)

    summary = {
        "english_rows": int(len(df)), "retweets": int(len(rts)),
        "external_edges": int(len(ext)), "internal_edges": int(len(inn)),
        "unique_edges": int(len(edges)), "nodes": int(G.number_of_nodes()),
        "hubs_in_dataset": int(hubs["in_dataset"].sum()), "hubs_external": int((~hubs["in_dataset"]).sum()),
        "ring_size": len(ring), "ring_retweets_out": int(ring_out["weight"].sum()),
        "ring_retweeted_by_others": int(ring_in["weight"].sum()), "ring_amplifies_ring": int(ring_ring["weight"].sum()),
        "category_mix": mix.to_dict(orient="records"),
        "top_hubs": hubs.head(20).to_dict(orient="records"),
        "top_brokers": brokers.head(20).to_dict(orient="records"),
    }
    (DATA / "network_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, list)}, indent=1))
    print("\nCategory mix (internal):\n", mix.to_string(index=False))
    print("\nTop hubs:\n", hubs.head(12).to_string(index=False))
    print("\nTop brokers:\n", brokers.head(12).to_string(index=False))

if __name__ == "__main__":
    main()