"""Environmental-spending study, variants of the subnational share (supplementary material).

B1 drops reported zeros of state and local government, F uses the consolidated financing share 1 - central/GG
for general government years. Both start from the baseline rule of env_federalism.subnational_share.

    python ext_r4.py [--out DIR]
"""
import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(HERE / "output"))
OUT = Path(ap.parse_args().out)

spec = importlib.util.spec_from_file_location("pc", HERE / "env_federalism.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


def classes() -> pd.DataFrame:
    """Reported zeros (B) and the financing share for T1 years, keyed by estimation year (spending year + 1)."""
    h = pd.read_csv(pc.HARMONISED, dtype={"DIV": str})
    e = h[h["DIV"] == "05"].copy()
    ever = e[["EVER_SG", "EVER_LG"]].astype(bool)
    reported = [lv for lv in (pc.SG, pc.LG)]
    sub = e[reported].fillna(0).sum(axis=1)
    has_level = ever.any(axis=1)
    complete_levels = ~((ever["EVER_SG"] & e[pc.SG].isna()) | (ever["EVER_LG"] & e[pc.LG].isna()))
    e["ZERO_REPORTED"] = has_level & complete_levels & (sub == 0)
    central = e[pc.CGSS].fillna(e[[pc.CGXSS, pc.SSF]].sum(axis=1, min_count=1).where(e[pc.CGXSS].notna()))
    central = central.fillna(e[[pc.BCG, pc.EBCG, pc.SSF]].sum(axis=1, min_count=1))
    fin = (1 - central / e[pc.GG]).clip(0, 1)
    e["SUB_F"] = np.where((e["TIER"] == "T1") & e[pc.GG].gt(0) & central.notna(), fin, np.nan)
    out = e[["ISO", "YEAR", "ZERO_REPORTED", "SUB_F"]].copy()
    out["YEAR"] = out["YEAR"] + 1
    return out.rename(columns={"ZERO_REPORTED": "ZERO_REPORTED_L1", "SUB_F": "SUB_F_L1"})


def table2_row(p: pd.DataFrame, label: str, ge_ref: float) -> dict:
    s = pc._sample(p)
    r, dd = pc._fit(pc.BASE, p[p["COMPLETE_L1"]], pc.BASE_NEEDED + ["SUB"])
    me, pme = pc.effect_25pp(r, ge_ref)
    return {"Variant": label, "N": int(r.nobs), "Countries": int(dd["ISO"].nunique()),
            "R2": round(r.rsquared, 3),
            "SUB": round(r.params["SUB"], 3), "se_SUB": round(r.bse["SUB"], 3), "p_SUB": round(r.pvalues["SUB"], 4),
            "SUB:GE": round(r.params["SUB:GE"], 3), "se_SUB:GE": round(r.bse["SUB:GE"], 3),
            "p_SUB:GE": round(r.pvalues["SUB:GE"], 4), "ME25_LMIC": me, "p_ME25_LMIC": pme,
            "GE_ref": ge_ref, "sample_rows": int(len(s))}


def main():
    p0 = pc.build_panel()
    ge_ref = pc.ge_reference(p0)["LMIC"]
    cl = classes()
    p = p0.merge(cl, on=["ISO", "YEAR"], how="left")
    b1 = p.copy()
    b1.loc[b1["ZERO_REPORTED_L1"] == True, "SUB"] = np.nan
    f = p.copy()
    t1 = f["TIER_L1"] == "T1"
    f.loc[t1, "SUB"] = f.loc[t1, "SUB_F_L1"]
    # Coverage gaps stay missing, as in the baseline: their GG values give a financing share of zero by construction
    f.loc[f["COVGAP"] == 1, "SUB"] = np.nan
    rows = [table2_row(p0, "Baseline", ge_ref),
            table2_row(b1, "B1: reported zeros of state and local government excluded", ge_ref),
            table2_row(f, "F: consolidated financing share for general government years", ge_ref)]
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "r4_share_variants.csv", index=False)

    print(t.to_string(index=False))


if __name__ == "__main__":
    main()
