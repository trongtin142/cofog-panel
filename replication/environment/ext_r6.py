"""Environmental-spending study, central and subnational spending in place of the share, and the panel
model on the countries covered by both this paper and the World Observatory.

    python ext_r6.py [--main PATH_TO_env_federalism.py] [--out DIR] [--sample-rule baseline|gaps]

--sample-rule gaps codes the coverage gaps of env_samples.py as missing before estimation. Writes
r6_split.csv, r6_wofi_panel.csv and r6_results.json to --out.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--main", default=str(HERE / "env_federalism.py"))
ap.add_argument("--out", default=str(HERE / "output"))
ap.add_argument("--sample-rule", default="baseline", choices=["baseline", "gaps"])
args = ap.parse_args()
ANALYSIS = Path(args.main).resolve().parent
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("pc", ANALYSIS / "env_federalism.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)
sys.path.insert(0, str(HERE))
import env_samples as ps  # noqa: E402

CTRL = pc.CONTROLS


def lincom(r, w: dict) -> tuple:
    b, V = r.params, r.cov_params()
    k = list(w)
    a = np.array([w[x] for x in k])
    est = float(a @ b[k].values)
    se = float(np.sqrt(a @ V.loc[k, k].values @ a))
    return est, se, float(2 * stats.norm.sf(abs(est / se)))


def main():
    p = pc.build_panel()
    ge = pc.ge_reference(p)["LMIC"]
    s = pc._sample(p).copy()
    if args.sample_rule == "gaps":
        gaps = ps.coverage_gaps(pc, pc._sample(pc.gaps_as_zero(p)))
        s = s[~s["ISO"].isin(gaps)]
    need = pc.BASE_NEEDED + ["SUB"]
    res = {"ge_ref": ge, "sample_rule": args.sample_rule}

    # R6a
    a = s[(s["SUB"] > 0) & (s["SUB"] < 1)].copy()
    a["lnC"] = np.log(a["ENV_L1"] * (1 - a["SUB"]))
    a["lnS"] = np.log(a["ENV_L1"] * a["SUB"])
    f = f"lnPM ~ lnC + lnS + lnC:GE + lnS:GE + GE + {CTRL} + C(YEAR) + C(SUBREGION)"
    r, d = pc._fit(f, a, need + ["lnC", "lnS"])
    rows = []
    for lab, w in [("ln subnational spending", {"lnS": 1, "lnS:GE": ge}),
                   ("ln central spending", {"lnC": 1, "lnC:GE": ge}),
                   ("Difference, subnational minus central", {"lnS": 1, "lnS:GE": ge, "lnC": -1, "lnC:GE": -ge})]:
        e, se, pv = lincom(r, w)
        rows.append({"Term": lab, "Elasticity_at_GE_ref": round(e, 3), "se": round(se, 3), "p": round(pv, 4)})
    for k in ["lnS:GE", "lnC:GE"]:
        rows.append({"Term": f"Interaction {k}", "Elasticity_at_GE_ref": round(float(r.params[k]), 3),
                     "se": round(float(r.bse[k]), 3), "p": round(float(r.pvalues[k]), 4)})
    rb, db = pc._fit(pc.BASE, d, need)
    me, pme = pc.effect_25pp(rb, ge)
    split = pd.DataFrame(rows)
    split.attrs = {}
    split.to_csv(OUT / "r6_split.csv", index=False)
    res["split"] = {"N": int(r.nobs), "Countries": int(d["ISO"].nunique()),
                    "baseline_same_obs": {"N": int(rb.nobs), "SUB": round(float(rb.params["SUB"]), 3),
                                          "SUB:GE": round(float(rb.params["SUB:GE"]), 3),
                                          "ME25": me, "p_ME25": pme}}

    # R6b
    w = pd.read_csv(ANALYSIS / "output" / "ESM1_TableS3_sngwofi_comparison.csv")
    w = w[(w["In_sample"] == 1) & w["SUB_2019"].notna() & w["WOFI_share"].notna()]
    iso = sorted(w["ISO3"])
    res["wofi_countries"] = len(iso)
    out = []
    b = s[s["ISO"].isin(iso)].copy()
    for lab, data in [("Paper's share, all years", b),
                      ("World Observatory share of 2019, all years",
                       b.assign(SUB=b["ISO"].map(w.set_index("ISO3")["WOFI_share"])))]:
        rr, dd = pc._fit(pc.BASE, data, need)
        m, pm = pc.effect_25pp(rr, ge)
        out.append({"Row": lab, "N": int(rr.nobs), "Countries": int(dd["ISO"].nunique()),
                    "SUB": round(float(rr.params["SUB"]), 3), "se_SUB": round(float(rr.bse["SUB"]), 3),
                    "p_SUB": round(float(rr.pvalues["SUB"]), 4),
                    "SUB:GE": round(float(rr.params["SUB:GE"]), 3), "se_SUB:GE": round(float(rr.bse["SUB:GE"]), 3),
                    "p_SUB:GE": round(float(rr.pvalues["SUB:GE"]), 4), "ME25": m, "p_ME25": pm,
                    "GE_mean": round(float(dd["GE"].mean()), 2),
                    "countries_negative_mean_GE": int((dd.groupby("ISO")["GE"].mean() < 0).sum())})
    wp = pd.DataFrame(out)
    wp.to_csv(OUT / "r6_wofi_panel.csv", index=False)
    (OUT / "r6_results.json").write_text(json.dumps(res, indent=1), encoding="utf8")
    pd.set_option("display.width", 250)
    print(split.to_string(index=False))
    print(wp.to_string(index=False))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
