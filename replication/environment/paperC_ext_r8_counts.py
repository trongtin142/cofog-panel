"""Environmental-spending study, sample construction and the position of the reference point (Table 1, panel A).

Writes r8_sample_flow.csv, the countries and observations left at each step from the COFOG extract to the main
sample, and r8_counts.json, the share of main-sample observations below the GE reference point, the countries
whose mean GE lies below it, the association at the median GE of low- and middle-income countries in the main
sample, the income groups of the main sample and the low-effectiveness counts of Section 1.

    python paperC_ext_r8_counts.py [--out DIR]
"""
import argparse
import importlib.util
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(HERE / "output"))
OUT = Path(ap.parse_args().out)

spec = importlib.util.spec_from_file_location("pc", HERE / "env_federalism.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)
import paperC_samples as ps  # noqa: E402  (next to env_federalism.py, on sys.path after the import above)

# Post-socialist countries, as in paperC_ext_r5z.py
POST_SOCIALIST = ["ARM", "AZE", "BLR", "EST", "GEO", "KAZ", "KGZ", "LVA", "LTU", "MDA", "RUS", "TJK", "TKM",
                  "UKR", "UZB", "ALB", "BGR", "CZE", "HUN", "POL", "ROU", "SVK", "SVN", "HRV", "BIH", "SRB",
                  "MNE", "MKD", "XKX", "MNG"]


def flow(p: pd.DataFrame) -> pd.DataFrame:
    h = pd.read_csv(pc.HARMONISED, dtype={"DIV": str})
    e = h[h["DIV"] == "05"]
    c = p[p["COMPLETE_L1"]]
    col1 = c.dropna(subset=pc.BASE_NEEDED)
    s0 = pc._sample(pc.gaps_as_zero(p))
    s = pc._sample(p)
    steps = [("COFOG data on environmental protection in the extract", set(e["ISO"]), None),
             ("Positive lagged spending in 1996-2023 with covariate records", set(p["ISO"]), None),
             ("Complete value of environmental spending", set(c["ISO"]), None),
             ("PM2.5, GE and the controls available (Table 2, column 1)", set(col1["ISO"]), len(col1)),
             ("Subnational share computable, coverage gaps coded as zero (Table 2, column 4)", set(s0["ISO"]),
              len(s0)),
             ("Main sample, coverage gaps coded as missing (Table 2, column 3)", set(s["ISO"]), len(s))]
    rows, prev = [], None
    for label, iso, n in steps:
        lost = sorted(prev - iso) if prev is not None else []
        rows.append({"Step": label, "Countries": len(iso), "Observations": n, "Countries_lost": len(lost),
                     "Lost_ISO": " ".join(lost) if len(lost) <= 5 else ""})
        prev = iso
    return pd.DataFrame(rows).astype({"Observations": "Int64"})


def main():
    p = pc.build_panel()
    ge = pc.ge_reference(p)["LMIC"]
    f = flow(p)
    f.to_csv(OUT / "r8_sample_flow.csv", index=False)
    s = pc._sample(p)
    s0 = pc._sample(pc.gaps_as_zero(p))
    inc = pc.income_groups()
    lmic = ["Low income", "Lower middle income", "Upper middle income"]
    cm = s.groupby("ISO")["GE"].mean()
    below = sorted(cm.index[cm < ge])
    cm0 = s0.groupby("ISO")["GE"].mean()
    neg0 = set(cm0.index[cm0 < 0])
    gaps = set(ps.COVERAGE_GAPS)
    lm = float(s.loc[s["ISO"].map(inc).isin(lmic), "GE"].median())
    r3 = pc.table_main(p)[1]["(3) + SUB x GE"][0]
    out = {
        "ge_ref": ge,
        "share_obs_main_ge_below_ref": round(float((s["GE"] < ge).mean()), 3),
        "obs_main_ge_below_ref": int((s["GE"] < ge).sum()),
        "countries_main_mean_ge_below_ref": len(below),
        "countries_main_mean_ge_below_ref_post_socialist": len(set(below) & set(POST_SOCIALIST)),
        "lmic_median_ge_main_sample": round(lm, 3),
        # % change in PM2.5 for a share 25 pp higher, and its p-value, at that median (Table 2, column 3)
        "effect_25pp_at_lmic_median_main_sample": [float(x) for x in pc.effect_25pp(r3, lm)],
        "income_groups_main_sample": s.drop_duplicates("ISO")["ISO"].map(inc).value_counts().to_dict(),
        "negative_mean_ge_panel108": len(neg0),
        "negative_mean_ge_panel108_coverage_gaps": len(neg0 & gaps),
        "negative_mean_ge_main": int((cm < 0).sum()),
        "ge_quantiles_main": {str(q): round(float(s["GE"].quantile(q)), 2) for q in (0.1, 0.25, 0.5, 0.75)},
    }
    (OUT / "r8_counts.json").write_text(json.dumps(out, indent=1), encoding="utf8")
    print(f.to_string(index=False))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
