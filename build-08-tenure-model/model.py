"""model.py - Build #8 step 3: four OLS specifications, controls added one at a time, population-weighted.

Reads data/results.json (Q14 is the county table). Writes data/model.json with, per outcome and specification:
coefficients, robust (HC1) standard errors, p-values, R-squared, N. Nothing is interpreted here; build_findings.py
turns the numbers into sentences and the README says what they do and do not mean.

Specs (outcome = renter_burden, then owner_burden; percent points):
  M1  vet_share
  M2  vet_share + share_65plus
  M3  M2 + owner_share
  M4  M3 + log(income) + log(pop)
Weights: county population (so the result describes people, not land). Run: python model.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

HERE = Path(__file__).parent
R = json.loads((HERE / "data/results.json").read_text(encoding="utf-8"))
df = pd.DataFrame(R["Q14"]["rows"])
df["log_income"] = np.log(df["income"])
df["log_pop"] = np.log(df["pop"])

SPECS = {
    "M1 veteran share only": ["vet_share"],
    "M2 + age (65+ share)": ["vet_share", "share_65plus"],
    "M3 + ownership (owner share)": ["vet_share", "share_65plus", "owner_share"],
    "M4 + log income, log population": ["vet_share", "share_65plus", "owner_share", "log_income", "log_pop"],
}
out = {"n_counties": int(len(df)), "weights": "county population (B01003_001E)", "se": "HC1 robust", "outcomes": {}}
for y in ("renter_burden", "owner_burden"):
    out["outcomes"][y] = {}
    for name, xs in SPECS.items():
        X = sm.add_constant(df[xs])
        fit = sm.WLS(df[y], X, weights=df["pop"]).fit(cov_type="HC1")
        out["outcomes"][y][name] = {
            "n": int(fit.nobs), "r2": round(float(fit.rsquared), 3),
            "coef": {k: round(float(v), 4) for k, v in fit.params.items()},
            "se": {k: round(float(v), 4) for k, v in fit.bse.items()},
            "p": {k: round(float(v), 4) for k, v in fit.pvalues.items()},
        }
        b, p = fit.params["vet_share"], fit.pvalues["vet_share"]
        print(f"{y:14s} {name:34s} N={int(fit.nobs)} R2={fit.rsquared:.3f}  vet_share={b:+.3f} (p={p:.3f})")
(HERE / "data/model.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("wrote data/model.json")
