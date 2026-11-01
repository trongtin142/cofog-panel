"""
Environmental-spending study: columns (4) and (5) of Table 2, with every coefficient of the table.

    python paperC_ext_r3_table2.py [--main PATH_TO_env_federalism.py] [--out DIR]

(4) coverage gaps coded as zero (the construction with 108 countries), (5) general government (GG, tier T1)
values only, and (4x, for the text and Table 5) without the countries in which only central government reports
environmental spending. All use the specification of Table 2, column 3. Writes tabC2_cols45.csv.
"""
import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--main", default=str(HERE / "env_federalism.py"))
ap.add_argument("--out", default=str(HERE / "output"))
args = ap.parse_args()

spec = importlib.util.spec_from_file_location("pc", args.main)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)
OUT = Path(args.out)
NEED = pc.BASE_NEEDED + ["SUB"]


def me25(r, ge):
    b, V = r.params, r.cov_params()
    m = b["SUB"] + b["SUB:GE"] * ge
    se = np.sqrt(V.loc["SUB", "SUB"] + ge ** 2 * V.loc["SUB:GE", "SUB:GE"] + 2 * ge * V.loc["SUB", "SUB:GE"])
    return round(100 * (np.exp(0.25 * m) - 1), 1), float(2 * stats.norm.sf(abs(m / se)))


p = pc.build_panel()
s = p[p["COMPLETE_L1"]]
G_REF = pc.ge_reference(p)["LMIC"]  # median GE of low- and middle-income countries
rows = []
s0 = pc.gaps_as_zero(p)[lambda x: x["COMPLETE_L1"]]
for col, label, d in (("4", "Coverage gaps coded as zero", s0),
                      ("5", "GG values only (T1)", s[s["TIER_L1"] == "T1"]),
                      ("4x", "Without central-only countries", s[s["NOSUB"] == 0])):
    r, dd = pc._fit(pc.BASE, d, NEED)
    row = {"Column": col, "Sample": label, "N": int(r.nobs), "Countries": int(dd["ISO"].nunique()),
           "R2": round(r.rsquared, 3)}
    for k in ("lnENV", "SUB", "SUB:GE", "GE"):
        row[k], row[f"se_{k}"], row[f"p_{k}"] = round(r.params[k], 3), round(r.bse[k], 3), round(r.pvalues[k], 4)
    row["ME25_LMIC"], row["p_ME25_LMIC"] = me25(r, G_REF)
    row["p_ME25_LMIC"] = round(row["p_ME25_LMIC"], 4)
    rows.append(row)
t = pd.DataFrame(rows)
t.to_csv(OUT / "tabC2_cols45.csv", index=False)
print(t.T.to_string())
