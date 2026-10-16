"""run_extract.py - Step 3 of build #5: call Azure AI Language with a hard cap and a ledger.

Order of operations (the cost-control pattern):
  1. Load the estimate (estimate.py must run first).
  2. Load the ledger (data/ledger.json) - records already used this month.
  3. GATE: refuse to run if estimate + used > MONTH_CAP, or estimate > RUN_CAP.
  4. Call key phrases, entities, sentiment per document (F0-permitted, sync API).
  5. Record the API's own transaction count (show_stats) in the ledger - the bill, not the guess.
  6. Write data/extract.json for build_summary.py / verify.py.

Auth: Entra token from env LANG_ACCESS_TOKEN (never a key). Endpoint from env LANGUAGE_ENDPOINT.
Run: python run_extract.py
"""
import datetime as dt
import json
import os
import pathlib
import sys

from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AccessToken

from estimate import chunk_paragraphs, SRC

HERE = pathlib.Path(__file__).parent
EST = HERE / "data" / "estimate.json"
LEDGER = HERE / "data" / "ledger.json"
OUT = HERE / "data" / "extract.json"

RUN_CAP = 200      # records: one run must never exceed this
MONTH_CAP = 1000   # records: self-imposed ceiling, 20% of the 5,000 free allowance
BATCH = 5          # documents per request (sync limits are 10 for these features; 5 keeps requests small)


class Cred:
    def get_token(self, *a, **k):
        return AccessToken(os.environ["LANG_ACCESS_TOKEN"], 2**31 - 1)


def month_key() -> str:
    return dt.date.today().strftime("%Y-%m")


def load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"runs": []}


def used_this_month(ledger: dict) -> int:
    return sum(r["records_billed"] for r in ledger["runs"] if r["month"] == month_key())


def gate(est: dict, ledger: dict) -> None:
    need, used = est["total_records_per_run"], used_this_month(ledger)
    print(f"gate: need {need} records, used {used} this month, caps run={RUN_CAP} month={MONTH_CAP}")
    if need > RUN_CAP:
        sys.exit(f"ABORT: estimate {need} exceeds RUN_CAP {RUN_CAP}")
    if used + need > MONTH_CAP:
        sys.exit(f"ABORT: {used} + {need} would exceed MONTH_CAP {MONTH_CAP}")
    print("gate: PASS")


def batches(items, n):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def main() -> None:
    est = json.loads(EST.read_text(encoding="utf-8"))
    ledger = load_ledger()
    gate(est, ledger)

    docs = chunk_paragraphs(SRC.read_text(encoding="utf-8"))
    assert len(docs) == est["documents"], "source changed since estimate.py ran - re-run estimate.py"

    client = TextAnalyticsClient(os.environ["LANGUAGE_ENDPOINT"], Cred())
    results = [{"doc_id": i, "text": d} for i, d in enumerate(docs)]
    billed = 0

    for start in range(0, len(docs), BATCH):
        chunk = docs[start:start + BATCH]
        kp = client.extract_key_phrases(chunk, language="en", show_stats=True)
        ne = client.recognize_entities(chunk, language="en", show_stats=True)
        se = client.analyze_sentiment(chunk, language="en", show_stats=True)
        for j, (a, b, c) in enumerate(zip(kp, ne, se)):
            r = results[start + j]
            r["key_phrases"] = [] if a.is_error else a.key_phrases
            r["entities"] = [] if b.is_error else [
                {"text": e.text, "category": e.category, "subcategory": e.subcategory,
                 "offset": e.offset, "length": e.length, "confidence": round(e.confidence_score, 3)}
                for e in b.entities]
            r["sentiment"] = None if c.is_error else {
                "label": c.sentiment,
                "scores": {k: round(v, 3) for k, v in
                           {"positive": c.confidence_scores.positive,
                            "neutral": c.confidence_scores.neutral,
                            "negative": c.confidence_scores.negative}.items()}}
            for res in (a, b, c):
                if not res.is_error and res.statistics:
                    billed += res.statistics.transaction_count
        print(f"batch {start // BATCH + 1}: docs {start}-{start + len(chunk) - 1} done, billed so far {billed}")

    ledger["runs"].append({
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "month": month_key(),
        "records_estimated": est["total_records_per_run"],
        "records_billed": billed,
        "documents": len(docs),
    })
    LEDGER.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    OUT.write_text(json.dumps({"source": est["source"], "run_ts": ledger["runs"][-1]["ts"],
                               "documents": results}, indent=2), encoding="utf-8")
    print(f"estimated {est['total_records_per_run']} / billed {billed} records; "
          f"month total now {used_this_month(ledger)} of cap {MONTH_CAP}")
    print(f"wrote {OUT} and {LEDGER}")


if __name__ == "__main__":
    main()
