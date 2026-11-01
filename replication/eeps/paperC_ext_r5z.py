"""Environmental-spending study, zero shares and the measurement basis of environmental spending.

The main sample codes coverage gaps as missing (env_federalism.build_panel). Rows: coverage gaps coded as zero
(108 countries), without the central-only countries, reported zeros also coded as missing, bounds for the zeros of
the central-only countries (on the construction with coverage gaps coded as zero), the exclusion of post-socialist countries, tier and central-only indicators, ln ENV on a
single basis, and two descriptive tables (federal and populous countries outside the sample, countries by
tercile of effectiveness).

    python paperC_ext_r5z.py [--main PATH_TO_env_federalism.py] [--out DIR]

Reads the panel of env_federalism.py and output/ESM1_TableS4_central_only_in_sngwofi.csv (written by
paperC_esm_wofi.py). Writes r5z_*.csv and r5z_details.json to --out (default output).
"""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--main", default=str(HERE / "env_federalism.py"))
ap.add_argument("--out", default=str(HERE / "output"))
args = ap.parse_args()
ANALYSIS = Path(args.main).resolve().parent
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("pc", ANALYSIS / "env_federalism.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)
import paperC_samples as ps  # noqa: E402  (next to env_federalism.py, on sys.path after the import above)

POST_SOCIALIST = ["ARM", "AZE", "BLR", "EST", "GEO", "KAZ", "KGZ", "LVA", "LTU", "MDA", "RUS", "TJK", "TKM",
                  "UKR", "UZB", "ALB", "BGR", "CZE", "HUN", "POL", "ROU", "SVK", "SVN", "HRV", "BIH", "SRB",
                  "MNE", "MKD", "XKX", "MNG"]
POPULOUS = ["IND", "CHN", "USA", "IDN", "PAK", "NGA", "BRA", "BGD", "RUS", "MEX"]
CTRL_TERMS = ["lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]


def env_rows() -> pd.DataFrame:
    h = pd.read_csv(pc.HARMONISED, dtype={"DIV": str})
    return h[h["DIV"] == "05"].copy()


def classes(e: pd.DataFrame) -> pd.DataFrame:
    """Reported zeros (as in paperC_ext_r4.classes) and the unconsolidated sum central + state + local, keyed by
    estimation year (spending year + 1)."""
    ever = e[["EVER_SG", "EVER_LG"]].astype(bool)
    sub = e[[pc.SG, pc.LG]].fillna(0).sum(axis=1)
    complete_levels = ~((ever["EVER_SG"] & e[pc.SG].isna()) | (ever["EVER_LG"] & e[pc.LG].isna()))
    e = e.assign(ZERO_REPORTED=ever.any(axis=1) & complete_levels & (sub == 0))
    central = e[pc.CGSS].fillna(e[[pc.CGXSS, pc.SSF]].sum(axis=1, min_count=1).where(e[pc.CGXSS].notna()))
    central = central.fillna(e[[pc.BCG, pc.EBCG, pc.SSF]].sum(axis=1, min_count=1))
    e["ENV_UNC"] = sub + central
    out = e[["ISO", "YEAR", "ZERO_REPORTED", "ENV_UNC"]].copy()
    out["YEAR"] = out["YEAR"] + 1
    return out.rename(columns={"ZERO_REPORTED": "ZERO_REPORTED_L1", "ENV_UNC": "ENV_UNC_L1"})


def row(label, group, formula, data, needed, ge_ref, keys=("SUB", "SUB:GE")):
    r, d = pc._fit(formula, data, needed)
    me, pme = pc.effect_25pp(r, ge_ref)
    out = {"Group": group, "Row": label, "N": int(r.nobs), "Countries": int(d["ISO"].nunique()),
           "R2": round(r.rsquared, 3)}
    for k in keys:
        out[k], out[f"se_{k}"], out[f"p_{k}"] = (round(float(r.params[k]), 3), round(float(r.bse[k]), 3),
                                                 round(float(r.pvalues[k]), 4))
    out["ME25"], out["p_ME25"] = me, pme
    out["countries_zero_mean_share"] = int((d.groupby("ISO")["SUB"].mean() == 0).sum())
    return out


def main():
    p0 = pc.build_panel()
    ge_ref = pc.ge_reference(p0)["LMIC"]
    e = env_rows()
    p = pc.add_other_shares(p0).merge(classes(e), on=["ISO", "YEAR"], how="left")
    pz = pc.gaps_as_zero(p)                      # coverage gaps coded as zero (108 countries)
    base = pc._sample(p)                         # main sample: coverage gaps coded as missing
    base0 = pc._sample(pz)
    nosub = sorted(base0.loc[base0["NOSUB"] == 1, "ISO"].unique())      # central-only countries, 108 panel
    gaps = sorted(base0.loc[base0["COVGAP"] == 1, "ISO"].unique())      # coverage gaps
    assert gaps == ps.COVERAGE_GAPS, sorted(set(gaps) ^ set(ps.COVERAGE_GAPS))

    # central-only countries with subnational data for another function, and with subnational total outlays
    h = pd.read_csv(pc.HARMONISED, dtype={"DIV": str}, usecols=["ISO", "DIV", "EVER_SG", "EVER_LG"])
    div_ever = h[h["DIV"] != "05"].groupby("ISO")[["EVER_SG", "EVER_LG"]].any().any(axis=1)
    other_fn = sorted(i for i in nosub if bool(div_ever.get(i, False)))
    t = pc.harmonised_total()
    tot_ever = t.groupby("ISO")[["EVER_SG", "EVER_LG"]].any().any(axis=1)
    with_tot = sorted(i for i in nosub if bool(tot_ever.get(i, False)))

    s = p[p["COMPLETE_L1"]].copy()
    s0 = pz[pz["COMPLETE_L1"]].copy()
    need = pc.BASE_NEEDED + ["SUB"]
    F = pc.BASE
    rows = [row("Baseline: coverage gaps coded as missing", "A", F, s, need, ge_ref)]
    rows.append(row("Coverage gaps coded as zero", "A", F, s0, need, ge_ref))
    rows.append(row("Without the central-only countries", "A", F, s[s["NOSUB"] == 0], need, ge_ref))
    a3 = s.copy()
    a3.loc[a3["ZERO_REPORTED_L1"] == True, "SUB"] = np.nan
    rows.append(row("Reported subnational zeros also coded as missing", "A", F, a3, need, ge_ref))
    rows.append(row("Reported subnational zeros also coded as missing, GG values only", "A", F,
                    a3[a3["TIER_L1"] == "T1"], need, ge_ref))

    # bounds: the zeros of the central-only countries, including the coverage gaps, replaced by other values
    w = pd.read_csv(ANALYSIS / "output" / "ESM1_TableS4_central_only_in_sngwofi.csv").set_index("ISO3")
    wofi = {"NIC": float(w.loc["NIC", "WOFI_share"]),
            "CIV": float(w.loc["CIV", "WOFI_pctGDP_S13M"] / w.loc["CIV", "WOFI_pctGDP_S13"])}
    b1 = s0.copy()
    m = b1["ISO"].isin(with_tot) & b1["SUB"].notna()
    # same-year share of total outlays, else the country mean of that share over its years
    tot_mean = s0.groupby("ISO")["SUBTOT"].transform("mean")
    b1_missing_subtot = int((m & s0["SUBTOT"].isna()).sum())
    no_tot = sorted(set(s0.loc[m & tot_mean.isna(), "ISO"]))  # no share of total outlays in any sample year
    b1.loc[m, "SUB"] = s0.loc[m, "SUBTOT"].fillna(tot_mean[m]).fillna(0)
    for iso, v in wofi.items():
        b1.loc[(b1["ISO"] == iso) & b1["SUB"].notna(), "SUB"] = v
    assert b1["SUB"].notna().sum() == s0["SUB"].notna().sum()
    rows.append(row("Central-only countries at alternative values: share of total outlays, World Observatory",
                    "B", F, b1, need, ge_ref))
    rep = base0[base0["NOSUB"] == 0]
    reg_mean = rep.groupby("REGION")["SUB"].mean()
    b2 = b1.copy()
    # every central-only country without an observed share of total outlays or a World Observatory value
    # Countries without subnational government keep their true zero (paperC_samples.NO_SUBNATIONAL_GOVERNMENT)
    rest = (b2["ISO"].isin(set(nosub) - (set(with_tot) - set(no_tot)) - set(wofi) - set(ps.NO_SUBNATIONAL_GOVERNMENT))
            & b2["SUB"].notna())
    b2.loc[rest, "SUB"] = b2.loc[rest, "REGION"].map(reg_mean)
    rows.append(row("High values: as above, other central-only countries at the regional mean", "B", F, b2, need,
                    ge_ref))

    # post-socialist countries
    ps_in = sorted(set(base["ISO"]) & set(POST_SOCIALIST))
    rows.append(row("Excl. post-socialist countries", "C", F, s[~s["ISO"].isin(POST_SOCIALIST)], need, ge_ref))
    rows.append(row("Excl. post-socialist countries, coverage gaps coded as zero", "C", F,
                    s0[~s0["ISO"].isin(POST_SOCIALIST)], need, ge_ref))

    # measurement basis of total environmental spending
    rows.append(row("Adds tier indicators", "D", F.replace("+ GE +", "+ GE + T2 + T3 +"), s, need, ge_ref))
    rows.append(row("Adds tier and central-only indicators", "D", F.replace("+ GE +", "+ GE + T2 + T3 + NOSUB +"),
                    s, need + ["NOSUB"], ge_ref))
    rows.append(row("Without ln ENV", "D", F.replace("lnENV + ", ""), s, need, ge_ref))
    d4 = s.copy()
    d4["lnENVU"] = np.log(d4["ENV_UNC_L1"].where(d4["ENV_UNC_L1"] > 0))
    rows.append(row("ln ENV as the unconsolidated sum of central, state and local government", "D",
                    F.replace("lnENV +", "lnENVU +"), d4, need + ["lnENVU"], ge_ref))
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "r5z_results.csv", index=False)

    # E1: federal and populous countries outside the sample
    raw_iso = set(e["ISO"])
    pos = set(e.loc[e["VALUE"] > 0, "ISO"])
    comp = set(e.loc[(e["VALUE"] > 0) & (e["COMPLETE"] == True), "ISO"])
    share_ok = set(e.loc[(e["VALUE"] > 0) & (e["COMPLETE"] == True) & pc.subnational_share(e).notna(), "ISO"])
    in_p = set(p0["ISO"])
    in_s = set(base["ISO"])
    recs = []
    for iso in sorted(set(pc.FEDERAL) | set(POPULOUS)):
        if iso in in_s:
            reason = "in sample"
        elif iso in gaps:
            reason = "coverage gap: COFOG data for central government alone, share coded as missing"
        elif iso not in raw_iso:
            reason = "no COFOG 05 record"
        elif iso not in pos:
            reason = "COFOG 05 reported as zero or not positive in every year"
        elif iso not in comp:
            reason = "no complete value"
        elif iso not in share_ok:
            cc = e[(e["ISO"] == iso) & (e["VALUE"] > 0) & (e["COMPLETE"] == True)]
            no_sub = not (cc["EVER_SG"].astype(bool) | cc["EVER_LG"].astype(bool)).any()
            no_cen = cc[[pc.CGSS, pc.CGXSS, pc.BCG]].isna().all(axis=1).all()
            reason = ("general government values only, without subsector values" if no_sub and no_cen else
                      "share missing in every complete year")
        elif iso not in in_p:
            reason = "no positive value in 1995-2022 with covariates"
        else:
            ss = p[(p["ISO"] == iso) & p["COMPLETE_L1"] & p["SUB"].notna()]
            miss = [v for v in pc.BASE_NEEDED if ss[v].isna().all()]
            reason = "missing in the years with a share: " + ", ".join(miss)
        ee = e[e["ISO"] == iso]
        recs.append({"ISO3": iso, "Federal": int(iso in pc.FEDERAL), "Populous": int(iso in POPULOUS),
                     "Reason": reason, "COFOG05_years": int(ee["VALUE"].notna().sum()),
                     "positive_years": int((ee["VALUE"] > 0).sum()),
                     "complete_positive_years": int(((ee["VALUE"] > 0) & (ee["COMPLETE"] == True)).sum()),
                     "tiers": ",".join(sorted(ee["TIER"].dropna().unique()))})
    fed = pd.DataFrame(recs)
    fed.to_csv(OUT / "r5z_federations.csv", index=False)

    # E2: countries of the main sample by tercile of country-mean GE
    c = base.groupby("ISO").agg(GE=("GE", "mean"), SUB=("SUB", "mean"), NOSUB=("NOSUB", "max"))
    c["T"] = pd.qcut(c["GE"], 3, labels=False) + 1
    terc = c.groupby("T").apply(lambda g: pd.Series({
        "GE_from": round(g["GE"].min(), 2), "GE_to": round(g["GE"].max(), 2), "Countries": len(g),
        "Central_only": int(g["NOSUB"].sum()),
        "Zero_mean_share_not_central_only": int(((g["SUB"] == 0) & (g["NOSUB"] == 0)).sum()),
        "Positive_mean_share": int((g["SUB"] > 0).sum()),
        "Post_socialist_positive": int(((g["SUB"] > 0) & g.index.isin(POST_SOCIALIST)).sum())}))
    terc.to_csv(OUT / "r5z_terciles.csv")

    zr = base[base["ZERO_REPORTED_L1"] == True]
    det = {"ge_ref": ge_ref, "central_only": nosub, "coverage_gaps": gaps, "other_function": other_fn,
           "central_only_in_main_sample": sorted(base.loc[base["NOSUB"] == 1, "ISO"].unique()),
           "with_subnational_total_outlays": with_tot, "wofi_values": {k: round(v, 4) for k, v in wofi.items()},
           "b1_obs_subtot_missing": b1_missing_subtot, "b1_countries_without_subtot": no_tot,
           "b1_subtot_country_means": {i: round(float(b1.loc[(b1["ISO"] == i), "SUB"].mean()), 3)
                                       for i in with_tot},
           "b2_region_means": {k: round(float(v), 3) for k, v in reg_mean.items()},
           "reported_zero_obs": int(len(zr)),
           "reported_zero_countries": {i: int(n) for i, n in zr.groupby("ISO").size().items()},
           "reported_zero_country_obs_in_sample": {i: int((base["ISO"] == i).sum()) for i in zr["ISO"].unique()},
           "post_socialist_in_sample": ps_in,
           "post_socialist_obs": int(base["ISO"].isin(POST_SOCIALIST).sum()),
           "gaps_obs_in_panel_with_gaps": int(base0["ISO"].isin(gaps).sum())}
    (OUT / "r5z_details.json").write_text(json.dumps(det, indent=1), encoding="utf8")
    pd.set_option("display.width", 250)
    print(res.drop(columns=["Group"]).to_string(index=False))
    print(fed.to_string(index=False))
    print(terc.to_string())
    print(json.dumps(det, indent=1))


if __name__ == "__main__":
    main()
