"""contract_test.py - the OpenAPI spec is the contract; this checks the live gateway keeps it.
Runs in GitHub Actions after every deploy (public product, no key) and from the PC. Exit code is the verdict.
Checks: envelope shape, status codes, validation errors, a known value (Marion County IN -> Roudebush VAMC), the
gateway's defaults, the public product's 405 on POST, and the response time budget.
"""
import json
import sys
import time
import urllib.error
import urllib.request

GW = "https://apim-azportfolio-b13.azure-api.net/data"
BUDGET_S = 8.0  # cold start on Flex Consumption is allowed; a warm call should be far under this


def call(path, method="GET", _retry=True):
    req = urllib.request.Request(GW + path, method=method, headers={"User-Agent": "azure-portfolio-contract-test"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode()), time.time() - t0
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            body = json.loads(body)
        except ValueError:
            pass
        if e.code == 429 and _retry:  # the public product's limit is shared by every anonymous caller: wait out the window once
            print("429 from the gateway (shared rate limit); waiting 61 s", flush=True)
            time.sleep(61)
            return call(path, method, _retry=False)
        return e.code, body, time.time() - t0


checks = []


def wake():
    """The free SQL database auto-pauses; the first query after a pause can fail or take a minute. Knock until a data
    endpoint answers 200, up to 5 x 20 s, before any check is scored (added after two CI runs failed on a sleeping db)."""
    for i in range(5):
        s, _, t = call("/counties/18097/access")
        if s == 200:
            print(f"db awake after {i} retr{'y' if i == 1 else 'ies'} ({t:.1f}s)", flush=True)
            return
        print(f"wake-up call returned {s}; waiting 20 s", flush=True)
        time.sleep(20)


wake()


def expect(name, cond, detail=""):
    checks.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""), flush=True)


s, b, t = call("/info")
expect("info 200 with envelope", s == 200 and "data" in b and "meta" in b and "version" in b["meta"], f"{s} {str(b)[:120]}")
expect("info under budget", t < BUDGET_S, f"{t:.1f}s")

s, b, t = call("/counties/18097/access")
expect("county 200", s == 200, str(s))
expect("county is Marion IN", s == 200 and b["data"]["county"] == "Marion" and b["data"]["state_abbr"] == "IN")
expect("county nearest VAMC is Roudebush", s == 200 and "Roudebush" in b["data"]["vamc_name"] and 2 <= b["data"]["vamc_miles"] <= 4, str(b.get("data", {}).get("vamc_miles")))
expect("county meta carries source note", s == 200 and "VAST" in b["meta"].get("source", ""))

s, b, _ = call("/counties/abc/access")
expect("bad fips -> 400 with error", s == 400 and "error" in b, f"{s} {b}")
s, b, _ = call("/counties/99999/access")
expect("unknown fips -> 404", s == 404, str(s))

s, b, _ = call("/states/de/access")
expect("state 200, lower-case accepted", s == 200 and b["meta"]["state"] == "DE" and b["meta"]["counties"] == 3, f"{s} {b.get('meta')}")
expect("state rows sorted farthest first", s == 200 and b["data"][0]["vamc_miles"] >= b["data"][-1]["vamc_miles"])

s, b, _ = call("/facilities/near?lat=39.9&lon=-86.2")
expect("near 200 with gateway defaults (miles 60, top 20)", s == 200 and b["meta"]["miles"] == 60.0 and len(b["data"]) <= 20, f"{s} {b.get('meta')}")
expect("near sorted by miles", s == 200 and all(b["data"][i]["miles"] <= b["data"][i + 1]["miles"] for i in range(len(b["data"]) - 1)))
s, b, _ = call("/facilities/near?lat=39.9&lon=-86.2&kind=VAMC&top=1")
expect("near kind filter", s == 200 and len(b["data"]) == 1 and b["data"][0]["kind"] == "VAMC", f"{s} {str(b)[:120]}")
s, b, _ = call("/facilities/near?lat=999&lon=0")
expect("out-of-range -> 400", s == 400, str(s))

s, b, _ = call("/refresh/runs")
expect("runs 200 list", s == 200 and isinstance(b["data"], list))

s, b, _ = call("/refresh", "POST")
expect("public POST refresh -> 405", s == 405, str(s))

failed = [c for c in checks if not c[1]]
print(f"\n{len(checks) - len(failed)}/{len(checks)} passed", flush=True)
sys.exit(1 if failed else 0)
