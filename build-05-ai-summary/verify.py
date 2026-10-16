"""verify.py - Step 4b of build #5: the fact check. Nothing ships unless this passes.

Three checks, all against data/vet_release.txt (the only source of truth):
  1. Every bullet is a verbatim sentence of the source (whitespace-normalised).
  2. Every number in every bullet appears in the source.
  3. Every headline quantity the API extracted appears in the source
     (catches the API's sloppy spans like "(71.3 percent" or "0666").

Exit code 0 = PASS, 1 = FAIL. Writes data/verify.json. Run: python verify.py
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
SRC = HERE / "data" / "vet_release.txt"
SUMMARY = HERE / "data" / "summary.json"
OUT = HERE / "data" / "verify.json"

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    src = norm(SRC.read_text(encoding="utf-8"))
    src_numbers = set(NUM.findall(src))
    summ = json.loads(SUMMARY.read_text(encoding="utf-8"))

    report = {"bullets": [], "headline_numbers": [], "pass": True}
    for b in summ["bullets"]:
        text = norm(b["text"])
        verbatim = text in src
        nums = NUM.findall(text)
        missing = [n for n in nums if n not in src_numbers]
        ok = verbatim and not missing
        report["bullets"].append({"text": text[:90], "verbatim": verbatim, "numbers": nums, "missing": missing, "ok": ok})
        report["pass"] &= ok

    for h in summ["headline_numbers"]:
        q = norm(h["quantity"])
        ok = q in src
        report["headline_numbers"].append({"quantity": q, "in_source": ok})
        report["pass"] &= ok

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    n_ok = sum(r["ok"] for r in report["bullets"])
    h_ok = sum(r["in_source"] for r in report["headline_numbers"])
    print(f"bullets verbatim+numbers: {n_ok}/{len(report['bullets'])}")
    print(f"headline quantities in source: {h_ok}/{len(report['headline_numbers'])}")
    for r in report["bullets"]:
        if not r["ok"]:
            print("  FAIL:", r["text"], "verbatim" if not r["verbatim"] else "", r["missing"])
    for r in report["headline_numbers"]:
        if not r["in_source"]:
            print("  FAIL quantity not in source:", r["quantity"])
    print("VERIFY:", "PASS" if report["pass"] else "FAIL")
    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
