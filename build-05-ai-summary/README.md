# Build #5: Summarize a public report with Azure AI, with cost controls

**Anchor phrase: estimate, cap, ledger, verify.**

Live page: https://stazportfoliob1.z14.web.core.windows.net/build-05-ai-summary/

## The problem

AI services bill per unit of text, and the bill arrives after the call. A Business Analyst who hands a 100-page report to an API without an estimate has no idea what it will cost and no way to check whether the summary is true. This build puts the controls in front of the call: estimate the records, refuse to run past a cap, record what was actually billed, and verify every number in the output against the source before publishing.

Source document: BLS news release *Employment Situation of Veterans, 2025* (USDL-26-0666, 28 April 2026), 12,187 characters, public domain.

## Azure services used and why

| Service | Tier | Why |
|---|---|---|
| Azure AI Language (`lang-azportfolio-b1`, Germany West Central) | **F0 (free)**, 5,000 text records/month | Key phrase extraction, named entity recognition, sentiment: the salience signals for the summary |
| Entra ID token (`az account get-access-token --resource https://cognitiveservices.azure.com`) | n/a | Auth with no key on disk; role **Cognitive Services User** on the resource |

No new resources were created. The Language resource already existed from build #1.

## Architecture

```
vet_release.txt ──► estimate.py ──► estimate.json (docs, records, F0 share, S-tier $)
                                        │
                         ledger.json ◄──┤ gate: run cap 200, month cap 1,000
                                        ▼
                                  run_extract.py ──► Azure AI Language (F0)
                                        │             key phrases · entities · sentiment
                                        ▼
                                  extract.json (+ billed records → ledger.json)
                                        │
                                  build_summary.py ──► summary.json (8 verbatim sentences)
                                        │
                                  verify.py ──► verify.json  PASS/FAIL (exit code)
                                        │
                                  build_findings.py ──► findings.html ──► GitHub Actions ──► live site
```

## What it cost

| Item | Cost |
|---|---|
| 39 text records (3 documents × 13 records × 3 features) | $0.00 on F0 (0.78% of the monthly allowance) |
| Same run on the paid S tier | $0.039 |
| **Total** | **$0.00** |

The estimator predicted 39 records; the API's own `transaction_count` reported 39. Budget alert on the subscription stays at $10.

## The tier gate (the finding that changed the design)

The plan was to call Azure's extractive and abstractive summarization. On F0 both return `PermissionDenied: Principal does not have access to API/Operation` while key phrases succeed with the same token and roles. The docs confirm it: *"To use the Analyze feature, you'll need a Language resource with the standard (S) pricing tier."* S is pay-per-record from the first call, so it is out under this portfolio's rules.

The redesign keeps the skill (cost controls) and swaps the feature: the free-tier features provide the salience signal, and the summary is assembled locally from verbatim sentences. That makes the summary verifiable by exact match, which an abstractive summary never is.

## How to run

```
python estimate.py        # no network; writes data/estimate.json
python run_extract.py     # needs LANG_ACCESS_TOKEN and LANGUAGE_ENDPOINT in env; writes extract.json, ledger.json
python build_summary.py   # writes data/summary.json
python verify.py          # exit 0 = PASS; writes data/verify.json
python build_findings.py  # writes findings.html
```

Token: `az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv` into the env var, never a file.

## What I learned

1. **Read the tier gate before designing the pipeline.** One sentence in the quickstart ("Analyze needs S") would have saved the first half-day. RBAC was never the problem; the error message just looked like one.
2. **Estimate in the API's own unit.** Azure Language bills "text records" (1,000-character units per document per feature), not calls or tokens. Once the estimator counts the way the meter counts, estimate and bill match exactly.
3. **A cap is a refusal, not a warning.** `run_extract.py` exits before the first request if the estimate would breach the run or month cap. Warnings get ignored; exits do not.
4. **Write the bill from the response, not the estimate.** `show_stats=True` returns the transaction count the service charged. The ledger stores that number.
5. **Verbatim beats fluent.** Because every bullet is an exact sentence from the source, `verify.py` can prove it by string match. An abstractive summary would need a human read.
6. **Density, not count, and respect the inverted pyramid.** Scoring sentences by raw entity hits picked the longest sentences and missed the headline. Hits per 10 words plus a first-paragraph bonus fixed it.
7. **Sentence splitting has sharp edges.** "U.S." split the headline in half and the all-caps title glued onto it. Protect abbreviations; drop header lines.
8. **A feature being available is not a reason to report it.** Sentiment scored every section "negative" because of the vocabulary. It is shown on the page as a discarded signal, with the reason.
9. **Entity spans need post-processing.** "(71.3 percent" and the release number "0666" came back as Quantities. Normalise before matching.

## Cleanup

Nothing new to delete. `lang-azportfolio-b1` (F0) stays for later builds at $0. To remove it: Azure portal → Resource groups → `rg-azportfolio-b1` → `lang-azportfolio-b1` → Delete.

## Files

| File | Purpose |
|---|---|
| `estimate.py` | Chunk the source like the API bills it; estimate records, free-tier share and S-tier cost |
| `run_extract.py` | Gate against ledger and caps, call key phrases / entities / sentiment, record billed records |
| `build_summary.py` | Score sentences with the API's key phrases and quantities; keep 8 verbatim in source order |
| `verify.py` | Exact-match every bullet and every number against the source; exit code is the verdict |
| `build_findings.py` | Render `findings.html` from the JSON outputs; no hand-typed numbers |
| `data/vet_release.txt` | Source text (public domain) |
| `data/*.json` | estimate, ledger, extract, summary, verify outputs (committed; `data/*.log` ignored) |
| `test_f0.py` | The one-record test that exposed the tier gate |
