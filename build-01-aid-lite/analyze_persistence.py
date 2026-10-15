"""AID stage 4, step 3: do the troll templates' themes appear in the Congressional Record, and when?

Phase 1  chunk every granule into ~200-word windows (header lines and procedural stubs dropped), embed locally
         with all-MiniLM-L6-v2 (same model as the index), save data/crec_chunks.csv + data/crec_vecs.npy.
Phase 2  for every chunk: best cosine similarity to the 1,642 templates (signal) and to 1,642 random
         non-template tweets from the same dataset (baseline). Aggregate by month and party.
         "Lift" = share of chunks whose best template score >= T minus the same share for the baseline.

Run: python -u analyze_persistence.py            (both phases; phase 1 is skipped if its outputs exist)
No Azure call: the full sweep is local. AI Search serves the showcase lookups (index_templates.py).
"""
import re, json, sys, glob
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).parent; DATA = HERE / "data"
CHUNK_WORDS, MIN_WORDS, T = 200, 40, 0.60
SKIP_TITLE = re.compile(r"^(PRAYER|PLEDGE OF ALLEGIANCE|ADJOURNMENT|RECESS|MORNING BUSINESS|THE JOURNAL|MESSAGE FROM|EXECUTIVE SESSION|"
                        r"ORDERS? FOR|PROGRAM|ADDITIONAL COSPONSORS|SUBMITTED RESOLUTIONS|ENROLLED BILL|COMMUNICATIONS FROM|"
                        r"PETITIONS AND MEMORIALS|REPORTS OF COMMITTEES|EXECUTIVE AND OTHER COMMUNICATIONS|INTRODUCTION OF BILLS|"
                        r"ADDITIONAL STATEMENTS|NOTICE OF|APPOINTMENT|CONCLUSION OF MORNING BUSINESS|LEGISLATIVE SESSION|RESIGNATION)", re.I)

def clean(text):
    lines = text.split("\n")
    # drop the GPO header (everything through the [www.gpo.gov] line) and page markers
    for i, l in enumerate(lines[:12]):
        if "www.gpo.gov" in l: lines = lines[i+1:]; break
    out = []
    for l in lines:
        s = l.strip()
        if not s or s.startswith("[[Page") or s.startswith("____"): continue
        if s.isupper() and len(s.split()) <= 12: continue   # section headers
        out.append(s)
    return " ".join(out)

def chunks(text):
    w = text.split()
    for i in range(0, len(w), CHUNK_WORDS):
        c = w[i:i+CHUNK_WORDS]
        if len(c) >= MIN_WORDS: yield " ".join(c)

def phase1():
    rows = []
    for f in sorted(glob.glob(str(DATA / "crec" / "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            g = json.loads(line)
            if SKIP_TITLE.match(g["title"] or ""): continue
            m = g["members"][0] if g["members"] else {}
            party = m.get("party") or "none"
            for k, c in enumerate(chunks(clean(g["text"]))):
                rows.append((g["date"], g["chamber"], g["granule_id"], k, party, m.get("state", ""), c))
    df = pd.DataFrame(rows, columns=["date", "chamber", "granule_id", "k", "party", "state", "text"])
    print("chunks:", len(df), "granules:", df["granule_id"].nunique(), flush=True)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    vecs = model.encode(df["text"].tolist(), batch_size=256, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True)
    np.save(DATA / "crec_vecs.npy", vecs.astype(np.float32))
    df.drop(columns=["text"]).to_csv(DATA / "crec_chunks.csv", index=False)
    df[["granule_id", "k", "text"]].to_csv(DATA / "crec_chunk_text.csv", index=False)
    print("embedded:", vecs.shape, flush=True)

def phase2():
    sys.path.insert(0, str(HERE / "function")); from detect import find_templates, body
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    raw = pd.read_csv(DATA / "IRAhandle_tweets_1.csv", low_memory=False)
    t = find_templates(raw).reset_index(drop=True)
    orig = raw[(raw["language"] == "English") & (raw["retweet"] == 0)].copy()
    orig["b"] = orig["content"].astype(str).map(body)
    base = orig[~orig["b"].isin(set(t["body"])) & (orig["b"].str.len() >= 25)].sample(len(t), random_state=42)
    tv = model.encode(t["body"].tolist(), batch_size=128, normalize_embeddings=True, show_progress_bar=False)
    bv = model.encode(base["b"].tolist(), batch_size=128, normalize_embeddings=True, show_progress_bar=False)
    cv = np.load(DATA / "crec_vecs.npy"); meta = pd.read_csv(DATA / "crec_chunks.csv")
    print("scoring", len(meta), "chunks x", len(t), "templates", flush=True)
    best_t, best_i, best_b = np.empty(len(cv)), np.empty(len(cv), dtype=int), np.empty(len(cv))
    for i in range(0, len(cv), 5000):
        s = cv[i:i+5000] @ tv.T; best_t[i:i+5000] = s.max(1); best_i[i:i+5000] = s.argmax(1)
        best_b[i:i+5000] = (cv[i:i+5000] @ bv.T).max(1)
    meta["best_template"] = t["body"].values[best_i]; meta["template_cat"] = t["top_category"].values[best_i]
    meta["score_template"] = best_t; meta["score_baseline"] = best_b
    meta["month"] = meta["date"].str.slice(0, 7)
    meta.to_csv(DATA / "persistence_scores.csv", index=False)

    hit_t, hit_b = meta["score_template"] >= T, meta["score_baseline"] >= T
    by_month = meta.groupby("month").agg(chunks=("k", "size"), mean_t=("score_template", "mean"), mean_b=("score_baseline", "mean"),
                                         hit_t=("score_template", lambda s: (s >= T).mean()), hit_b=("score_baseline", lambda s: (s >= T).mean())).reset_index()
    by_month["lift_pts"] = (by_month["hit_t"] - by_month["hit_b"]) * 100
    by_party = meta[meta["party"].isin(["D", "R"])].groupby("party").agg(chunks=("k", "size"), mean_t=("score_template", "mean"), mean_b=("score_baseline", "mean"),
                                         hit_t=("score_template", lambda s: (s >= T).mean()), hit_b=("score_baseline", lambda s: (s >= T).mean())).reset_index()
    by_party["lift_pts"] = (by_party["hit_t"] - by_party["hit_b"]) * 100
    top_templates = (meta[hit_t].groupby(["best_template", "template_cat"]).size().reset_index(name="chunks_matched")
                        .sort_values("chunks_matched", ascending=False).head(25))
    top_chunks = meta.sort_values("score_template", ascending=False).head(30)[["date", "chamber", "party", "state", "granule_id", "k", "best_template", "score_template", "score_baseline"]]
    summary = {"threshold": T, "chunks": int(len(meta)), "granules": int(meta["granule_id"].nunique()),
               "mean_template": round(float(meta["score_template"].mean()), 4), "mean_baseline": round(float(meta["score_baseline"].mean()), 4),
               "hit_template_pct": round(float(hit_t.mean() * 100), 2), "hit_baseline_pct": round(float(hit_b.mean() * 100), 2),
               "overall_lift_pts": round(float((hit_t.mean() - hit_b.mean()) * 100), 2),
               "by_month": by_month.round(4).to_dict(orient="records"), "by_party": by_party.round(4).to_dict(orient="records"),
               "top_templates": top_templates.to_dict(orient="records"), "top_chunks": top_chunks.round(4).to_dict(orient="records")}
    (DATA / "persistence_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, list)}, indent=1))
    print("\nBy party:\n", by_party.round(3).to_string(index=False))
    print("\nBy month:\n", by_month.round(3).to_string(index=False))
    print("\nTop templates matched:\n", top_templates.head(12).to_string(index=False))

if __name__ == "__main__":
    if not (DATA / "crec_vecs.npy").exists(): phase1()
    phase2()