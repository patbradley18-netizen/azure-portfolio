"""estimate.py - Step 2 of build #5: estimate cost BEFORE calling Azure AI Language.

Reads data/vet_release.txt, chunks it the way the API will bill it, and writes
data/estimate.json with: documents, text records per feature, free-tier share,
and what the same run would cost on the paid S tier.

No network calls. No keys. Run: python estimate.py
"""
import json
import math
import pathlib
import re

SRC = pathlib.Path(__file__).parent / "data" / "vet_release.txt"
OUT = pathlib.Path(__file__).parent / "data" / "estimate.json"

# Billing facts (Azure AI Language, verified 2026-10-16)
RECORD_CHARS = 1000          # 1 text record = up to 1,000 characters
MAX_DOC_CHARS = 5000         # keep each document under the sync-API per-doc limit (5,120)
F0_RECORDS_PER_MONTH = 5000  # free tier allowance
S_TIER_USD_PER_1000 = 1.00   # standard features (key phrases, entities, sentiment), first 500K records
FEATURES = ["key_phrases", "entities", "sentiment"]


def chunk_paragraphs(text: str, max_chars: int = MAX_DOC_CHARS) -> list[str]:
    """Group paragraphs into documents no longer than max_chars."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    docs, cur = [], ""
    for p in paras:
        if cur and len(cur) + 2 + len(p) > max_chars:
            docs.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        docs.append(cur)
    return docs


def records_for(doc: str) -> int:
    return max(1, math.ceil(len(doc) / RECORD_CHARS))


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    docs = chunk_paragraphs(text)
    per_doc = [{"doc_id": i, "chars": len(d), "records": records_for(d)} for i, d in enumerate(docs)]
    records_per_feature = sum(d["records"] for d in per_doc)
    total_records = records_per_feature * len(FEATURES)
    est = {
        "source": SRC.name,
        "source_chars": len(text),
        "documents": len(docs),
        "per_doc": per_doc,
        "features": FEATURES,
        "records_per_feature": records_per_feature,
        "total_records_per_run": total_records,
        "f0_allowance_per_month": F0_RECORDS_PER_MONTH,
        "f0_share_of_month_pct": round(100 * total_records / F0_RECORDS_PER_MONTH, 2),
        "s_tier_cost_usd_if_paid": round(total_records / 1000 * S_TIER_USD_PER_1000, 4),
    }
    OUT.write_text(json.dumps(est, indent=2), encoding="utf-8")
    print(f"source: {est['source_chars']:,} chars -> {est['documents']} documents")
    print(f"records per feature: {records_per_feature}  x {len(FEATURES)} features = {total_records} records/run")
    print(f"free tier: {est['f0_share_of_month_pct']}% of the 5,000/month allowance")
    print(f"same run on S tier would cost: ${est['s_tier_cost_usd_if_paid']:.4f}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
