"""build_summary.py - Step 4a of build #5: build a summary FROM the F0 extractions, locally.

Azure's summarization API needs the paid S tier, so the API gives us salience
signals (key phrases, entities) and we do the selection here:

  1. Split the source into sentences (boxed shutdown notice and boilerplate removed).
  2. Score each sentence = number of API key phrases it contains, +1 for each Quantity
     entity (a sentence with numbers is a finding; one without is framing).
  3. Keep the top N sentences, output them in source order - every bullet is a
     verbatim sentence from the release, so verify.py can check it exactly.
  4. Also write the headline numbers table (Quantity entities with their sentence).

No network calls. Run: python build_summary.py
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
SRC = HERE / "data" / "vet_release.txt"
EXTRACT = HERE / "data" / "extract.json"
OUT = HERE / "data" / "summary.json"

N_BULLETS = 8
MIN_WORDS = 10
LEAD_SENTENCES = 3   # first paragraph of a BLS release = the headline findings
LEAD_BONUS = 5.0


def clean_source(text: str) -> str:
    """Drop header lines, the boxed notice and table-ish lines; join wrapped lines."""
    kept = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("|") or s.startswith("_"):
            continue
        if re.match(r"^(For release|Technical information|Media contact|USDL)", s):
            continue
        if s == s.upper() and re.search(r"[A-Z]{4,}", s):   # all-caps title / section headers
            continue
        if re.search(r"\.{3,}|\s{3,}\d", s):      # table rows / dot leaders
            continue
        kept.append(s)
    return " ".join(kept)


ABBREV = {"U.S.": "U<dot>S<dot>", "a.m.": "a<dot>m<dot>", "p.m.": "p<dot>m<dot>"}


def sentences(text: str) -> list[str]:
    for k, v in ABBREV.items():
        text = text.replace(k, v)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text)
    parts = [p.replace("<dot>", ".").strip() for p in parts]
    return [p for p in parts if len(p.split()) >= MIN_WORDS]


def main() -> None:
    ext = json.loads(EXTRACT.read_text(encoding="utf-8"))
    phrases = {p.lower() for d in ext["documents"] for p in d["key_phrases"]}
    quantities = [e["text"] for d in ext["documents"] for e in d["entities"] if e["category"] == "Quantity"]
    qty_set = {q.strip("() ") for q in quantities if re.search(r"\d", q)}

    sents = sentences(clean_source(SRC.read_text(encoding="utf-8")))
    scored = []
    for i, s in enumerate(sents):
        low = s.lower()
        kp_hits = [p for p in phrases if p in low]
        q_hits = [q for q in qty_set if q in s]
        # density, not raw count: hits per 10 words, so long sentences don't win by length
        score = round(10 * (len(kp_hits) + len(q_hits)) / len(s.split()), 2)
        if i < LEAD_SENTENCES:            # inverted pyramid: the first paragraph IS the headline
            score = round(score + LEAD_BONUS, 2)
        if "see table" in low or "technical note" in low or "co-sponsored" in low:
            score = 0
        scored.append({"idx": i, "text": s, "score": score, "key_phrases": kp_hits[:6], "quantities": q_hits})

    top = sorted(scored, key=lambda r: -r["score"])[:N_BULLETS]
    top.sort(key=lambda r: r["idx"])

    headline = [{"quantity": q, "sentence": next((s["text"] for s in scored if q in s["text"]), None)}
                for q in dict.fromkeys(qty_set) if re.search(r"percent|million", q)]

    out = {"source": SRC.name, "method": "extractive-local: API key phrases + Quantity entities as salience, "
                                           "sentences kept verbatim in source order",
           "candidates": len(sents), "bullets": top, "headline_numbers": headline[:20]}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"{len(sents)} candidate sentences -> {len(top)} bullets")
    for b in top:
        print(f"  [{b['score']:>2}] {b['text'][:110]}...")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
