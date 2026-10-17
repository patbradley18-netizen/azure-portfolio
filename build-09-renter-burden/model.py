"""model.py - Build #9: same sequence of controls as build #8, the right outcome, plus state fixed effects.

Outcome: share of renter households paying 30%+ of income in rent (B25070), percentage points.
Weight: renter households with a computed ratio (so the result describes renters, not land or all residents).
Specs: M1 vet_share; M2 + 65+ share; M3 + owner share; M4 + log income, log pop; M5 = M4 + state fixed effects.
Also fits M4 on the build #8 outcome (TSCI county renter nut) for the same counties, so the two measures can be compared.
Writes data/model.json. Run: python model.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

HERE = Path(__file__).parent
R = json.loads((HERE / "data/results.json").read_text(encoding="utf-8"))
df = pd.DataFrame(R["Q17"]["rows"]).dropna(subset=["tsci_renter_burden"])
df["log_income"] = np.log(df["income"])
df["log_pop"] = np.log(df["pop"])

BASE = {
    "M1 veteran share only": ["vet_share"],
    "M2 + age (65+ share)": ["vet_share", "share_65plus"],
    "M3 + ownership (owner share)": ["vet_share", "share_65plus", "owner_share"],
    "M4 + log income, log population": ["vet_share", "share_65plus", "owner_share", "log_income", "log_pop"],
}
state_dummies = pd.get_dummies(df["state_abbr"], prefix="st", drop_first=True, dtype=float)


def fit(y, xs, fe=False):
    X = df[xs].copy()
    if fe:
        X = pd.concat([X, state_dummies], axis=1)
    X = sm.add_constant(X)
    return sm.WLS(df[y], X, weights=df["renter_households"]).fit(cov_type="HC1")


def pack(f, xs):
    keep = ["const"] + xs
    return {"n": int(f.nobs), "r2": round(float(f.rsquared), 3),
            "coef": {k: round(float(f.params[k]), 4) for k in keep}, "se": {k: round(float(f.bse[k]), 4) for k in keep},
            "p": {k: round(float(f.pvalues[k]), 4) for k in keep}}


out = {"n_counties": int(len(df)), "weights": "renter households with computed ratio (B25070_001E - B25070_011E)", "se": "HC1 robust",
       "state_fe_count": int(state_dummies.shape[1]), "outcomes": {}}
for y in ("burdened_30plus_pct", "severe_50plus_pct"):
    out["outcomes"][y] = {}
    for name, xs in BASE.items():
        f = fit(y, xs)
        out["outcomes"][y][name] = pack(f, xs)
        print(f"{y:20s} {name:34s} N={int(f.nobs)} R2={f.rsquared:.3f}  vet_share={f.params['vet_share']:+.3f} (p={f.pvalues['vet_share']:.3f})")
    xs = BASE["M4 + log income, log population"]
    f = fit(y, xs, fe=True)
    out["outcomes"][y]["M5 + state fixed effects"] = pack(f, xs)
    print(f"{y:20s} {'M5 + state fixed effects':34s} N={int(f.nobs)} R2={f.rsquared:.3f}  vet_share={f.params['vet_share']:+.3f} (p={f.pvalues['vet_share']:.3f})")

# comparison: build #8's outcome on the same counties and weights
xs = BASE["M4 + log income, log population"]
f = fit("tsci_renter_burden", xs)
out["outcomes"]["tsci_renter_burden (build #8 outcome, same counties)"] = {"M4 + log income, log population": pack(f, xs)}
print(f"{'tsci_renter_burden':20s} {'M4 (comparison)':34s} N={int(f.nobs)} R2={f.rsquared:.3f}  vet_share={f.params['vet_share']:+.3f} (p={f.pvalues['vet_share']:.3f})")
(HERE / "data/model.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("wrote data/model.json")
