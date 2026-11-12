"""Environmental-spending study, alternative measures of decentralisation and validation of the share.

A. The SNG-WOFI share of environmental protection spending as an independent measure, cross-section of 2019.
B. Agreement with SNG-WOFI by source group, and the ordering of the two shares in unitary countries.
C. Spending share, financing share and their wedge on identical general government observations.
D. Decision authority: Regional Authority Index self-rule components against the share (descriptive).

    python -I paperC_ext_r5w.py [--main PATH_TO_env_federalism.py] [--data DATA_EXT_LAB] [--out DIR]

Reads the panel functions of env_federalism.py, the SNG-WOFI COFOG file (data_ext/lab/sngwofi/
oecd_sng_wofi_cofog.csv) and the Regional Authority Index country file (data_ext/lab/RAI_country-april-2021.xlsx).
Writes r5w_*.csv and r5w_results.json to --out (default output).
"""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from linearmodels.iv import IV2SLS
from scipy import stats

HERE = Path(__file__).resolve().parent
_ap = argparse.ArgumentParser()
_ap.add_argument("--main", default=str(HERE / "env_federalism.py"))
_ap.add_argument("--data", default=None)
_ap.add_argument("--out", default=str(HERE / "output"))
ARGS = _ap.parse_args()
ANALYSIS = Path(ARGS.main).resolve().parent
LAB = Path(ARGS.data) if ARGS.data else ANALYSIS / "data_ext" / "lab"
spec = importlib.util.spec_from_file_location("pc", ANALYSIS / "env_federalism.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

WOFI_FILE = LAB / "sngwofi" / "oecd_sng_wofi_cofog.csv"
RAI_FILE = LAB / "RAI_country-april-2021.xlsx"
GE_REF = -0.355
REF_YEAR = 2019

OECD_2019 = ["AUS", "AUT", "BEL", "CAN", "CHL", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "ISL",
             "IRL", "ISR", "ITA", "JPN", "KOR", "LVA", "LTU", "LUX", "MEX", "NLD", "NZL", "NOR", "POL", "PRT",
             "SVK", "SVN", "ESP", "SWE", "CHE", "TUR", "GBR", "USA"]
EU28 = ["AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "IRL", "ITA",
        "LVA", "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE", "GBR"]
OECD_EU = sorted(set(OECD_2019) | set(EU28))


def me25(params, cov, s, g=GE_REF):
    """Percent change in PM2.5 for a share 25 points higher at GE = g, with its normal p-value."""
    i = f"{s}:GE" if f"{s}:GE" in params.index else f"{s}_GE"
    m = params[s] + params[i] * g
    se = np.sqrt(cov.loc[s, s] + g ** 2 * cov.loc[i, i] + 2 * g * cov.loc[s, i])
    return round(100 * (np.exp(0.25 * m) - 1), 1), round(float(2 * stats.norm.sf(abs(m / se))), 3)


def row(label, r, d, s, extra=None):
    i = f"{s}:GE" if f"{s}:GE" in r.params.index else f"{s}_GE"
    bse = r.bse if hasattr(r, "bse") else r.std_errors
    pv = r.pvalues
    cov = r.cov_params() if callable(getattr(r, "cov_params", None)) else r.cov
    me, pme = me25(r.params, cov, s)
    out = {"Model": label, "N": int(r.nobs), "Countries": int(d["ISO"].nunique()),
           "S": round(float(r.params[s]), 3), "se_S": round(float(bse[s]), 3), "p_S": round(float(pv[s]), 3),
           "SxGE": round(float(r.params[i]), 3), "se_SxGE": round(float(bse[i]), 3),
           "p_SxGE": round(float(pv[i]), 3), "ME25": me, "p_ME25": pme}
    out.update(extra or {})
    return out


# ------------------------------------------------------------------------------------------------ data

def wofi():
    w = pd.read_csv(WOFI_FILE, dtype=str)
    w["v"] = pd.to_numeric(w["OBS_VALUE"], errors="coerce")
    w = w[(w["COFOG"] == "GF05") & (w["TIME_PERIOD"] == str(REF_YEAR))]
    share = w[(w["UNIT_MEASURE"] == "PT_OTE_S13_FNC") & (w["SECTOR"] == "S13M")].set_index("REF_AREA")["v"] / 100
    gdp = w[w["UNIT_MEASURE"] == "PT_B1GQ"].pivot_table(index="REF_AREA", columns="SECTOR", values="v",
                                                         aggfunc="first")
    form = w.drop_duplicates("REF_AREA").set_index("REF_AREA")["FORM"]
    out = pd.DataFrame({"WOFI": share}).join(gdp.rename(columns=lambda c: f"W_{c}"), how="left")
    out["FORM"] = form
    out.index.name = "ISO"
    return out.reset_index()


def harmonised_05():
    h = pd.read_csv(pc.HARMONISED, dtype={"DIV": str})
    e = h[h["DIV"] == "05"].copy()
    e["SUBSHARE"] = pc.subnational_share(e)
    sub = e[[pc.SG, pc.LG]].fillna(0).sum(axis=1)
    central = e[pc.CGSS].fillna(e[[pc.CGXSS, pc.SSF]].sum(axis=1, min_count=1).where(e[pc.CGXSS].notna()))
    central = central.fillna(e[[pc.BCG, pc.EBCG, pc.SSF]].sum(axis=1, min_count=1))
    e["SUBLEV"], e["CENTRAL"] = sub, central
    e["NOSUB"] = (~(e["EVER_SG"].astype(bool) | e["EVER_LG"].astype(bool))).astype(int)
    return e


def covariates(year):
    c = pc.load_covariates()
    c = c[c["YEAR"] == year].copy()
    c["lnPM"] = np.log(c["PM25"])
    c["lnY"] = np.log(c["GDPPC"])
    c["lnY2"] = c["lnY"] ** 2
    c["lnDENS"] = np.log(c["DENS"])
    lk = pd.read_excel(pc.LOOKUP)[["alpha-3", "region", "sub-region"]].rename(
        columns={"alpha-3": "ISO", "region": "REGION", "sub-region": "SUBREGION"})
    return c.merge(lk, on="ISO", how="left")


# ------------------------------------------------------------------------------------------------ A

def part_a(sample_iso, sample_ge):
    w = wofi()
    e = harmonised_05()
    y = e[e["YEAR"] == REF_YEAR][["ISO", "SUBSHARE", "VALUE", "COMPLETE", "TIER", "NOSUB"]]
    y = y.rename(columns={"SUBSHARE": "SUBP", "VALUE": "ENVP"})
    rows, sens = [], []
    for outcome_year in (REF_YEAR, REF_YEAR + 1):
        c = covariates(outcome_year)
        if outcome_year != REF_YEAR:  # GE and controls of the outcome year, shares of 2019
            pass
        d = w.merge(c, on="ISO", how="inner").merge(y, on="ISO", how="left")
        d["lnENVW"] = np.log(d["W_S13"].where(d["W_S13"] > 0))
        d["lnENVP"] = np.log(d["ENVP"].where(d["ENVP"] > 0))
        need = ["lnPM", "lnY", "IND", "URB", "TRADE", "lnDENS", "GE", "REGION"]
        a1 = d.dropna(subset=need + ["WOFI", "lnENVW"]).copy()
        ov = a1[a1["ISO"].isin(sample_iso) & a1["SUBP"].notna() & (a1["COMPLETE"] == True)
                & a1["lnENVP"].notna()].copy()
        for fe, tag in (("C(REGION)", "region"), ("C(SUBREGION)", "subregion")):
            fw = f"lnPM ~ lnENVW + WOFI + WOFI:GE + GE + {pc.CONTROLS} + {fe}"
            fp = f"lnPM ~ lnENVP + SUBP + SUBP:GE + GE + {pc.CONTROLS} + {fe}"
            r1 = smf.ols(fw, data=a1).fit(cov_type="HC1")
            r2 = smf.ols(fw, data=ov).fit(cov_type="HC1")
            r3 = smf.ols(fp, data=ov).fit(cov_type="HC1")
            # A4: the paper's share instrumented by the WOFI share
            X = pd.get_dummies(ov[fe[2:-1]], prefix="FE", drop_first=True, dtype=float)
            ex = pd.concat([pd.Series(1.0, index=ov.index, name="const"),
                            ov[["lnENVP", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]], X], axis=1)
            en = pd.DataFrame({"SUBP": ov["SUBP"], "SUBP_GE": ov["SUBP"] * ov["GE"]})
            ins = pd.DataFrame({"WOFI": ov["WOFI"], "WOFI_GE": ov["WOFI"] * ov["GE"]})
            r4 = IV2SLS(ov["lnPM"], ex, en, ins).fit(cov_type="robust")
            fs = r4.first_stage.diagnostics
            lab = f"outcome {outcome_year}, {tag} effects"
            out = [row(f"A1 WOFI share, all WOFI countries ({lab})", r1, a1, "WOFI"),
                   row(f"A2 WOFI share, overlap ({lab})", r2, ov, "WOFI"),
                   row(f"A3 Paper's share, overlap ({lab})", r3, ov, "SUBP"),
                   row(f"A4 Paper's share instrumented by WOFI share, overlap ({lab})", r4, ov, "SUBP",
                       {"FS_F_SUB": round(float(fs.loc["SUBP", "f.stat"]), 1),
                        "FS_F_SUBxGE": round(float(fs.loc["SUBP_GE", "f.stat"]), 1),
                        "FS_partialR2_SUB": round(float(fs.loc["SUBP", "partial.rsquared"]), 3)})]
            for o in out:
                o["Outcome_year"], o["Effects"] = outcome_year, tag
            (rows if (outcome_year == REF_YEAR and tag == "region") else sens).extend(out)
        if outcome_year == REF_YEAR:
            info = {"A1_countries": int(len(a1)), "A1_in_sample": int(a1["ISO"].isin(sample_iso).sum()),
                    "A1_negative_GE_2019": int((a1["GE"] < 0).sum()),
                    "overlap_countries": int(len(ov)), "overlap_negative_GE_2019": int((ov["GE"] < 0).sum()),
                    "corr_WOFI_SUBP_overlap": round(float(ov["WOFI"].corr(ov["SUBP"])), 3),
                    "A1_mean_WOFI": round(float(a1["WOFI"].mean()), 3),
                    "A1_WOFI_lowGE_mean": round(float(a1.loc[a1["GE"] < 0, "WOFI"].mean()), 3),
                    "A1_not_in_paper_sample": sorted(a1.loc[~a1["ISO"].isin(sample_iso), "ISO"].tolist()),
                    "WOFI_countries_with_share": int(w["WOFI"].notna().sum())}
            a1.to_csv(OUT / "r5w_A_crosssection_data.csv", index=False)
    return pd.DataFrame(rows), pd.DataFrame(sens), info


# ------------------------------------------------------------------------------------------------ B

def part_b(sample_iso, sample_ge):
    w = wofi()
    e = harmonised_05()
    y = e[(e["YEAR"] == REF_YEAR)].set_index("ISO")
    d = w.set_index("ISO").join(y[["SUBSHARE", "SUBLEV", "CENTRAL", pc.GG, "TIER", "COMPLETE"]], how="inner")
    d = d[d.index.isin(sample_iso) & d["SUBSHARE"].notna() & d["WOFI"].notna()].copy()
    d["diff"] = d["SUBSHARE"] - d["WOFI"]
    d["absdiff"] = d["diff"].abs()
    d["GE_mean"] = d.index.map(sample_ge)
    d["OECD_EU"] = d.index.isin(OECD_EU)

    def st(x, name):
        return {"Group": name, "Countries": int(len(x)),
                "Correlation": round(float(x["SUBSHARE"].corr(x["WOFI"])), 3) if len(x) > 2 else np.nan,
                "Mean_abs_diff": round(float(x["absdiff"].mean()), 3),
                "Median_abs_diff": round(float(x["absdiff"].median()), 3),
                "Share_within_0.10": round(float((x["absdiff"] <= 0.10).mean()), 3),
                "Near_exact_matches": int((x["absdiff"] < 0.001).sum()),
                "Mean_diff": round(float(x["diff"].mean()), 3)}
    groups = [st(d, "All 56"), st(d[d["OECD_EU"]], "OECD or EU members"),
              st(d[~d["OECD_EU"]], "Other countries"),
              st(d[d["GE_mean"] < 0], "Negative mean GE"), st(d[d["GE_mean"] >= 0], "Non-negative mean GE"),
              st(d[(~d["OECD_EU"]) & (d["GE_mean"] < 0)], "Other countries, negative mean GE"),
              st(d[d["FORM"] == "UNI"], "Unitary"), st(d[d["FORM"] == "FED"], "Federal")]
    # Decomposition of the gap into the subnational level and the total, % of GDP
    d["IMF_sub_pctGDP"] = d["SUBLEV"]
    d["WOFI_sub_pctGDP"] = d["W_S13M"]
    d["IMF_total_pctGDP"] = d["SUBLEV"] + d["CENTRAL"]
    d["IMF_GG_pctGDP"] = d[pc.GG]
    d["WOFI_GG_pctGDP"] = d["W_S13"]
    cols = ["FORM", "TIER", "GE_mean", "SUBSHARE", "WOFI", "diff", "IMF_sub_pctGDP", "WOFI_sub_pctGDP",
            "IMF_total_pctGDP", "IMF_GG_pctGDP", "WOFI_GG_pctGDP", "OECD_EU"]
    viol = d[(d["FORM"] == "UNI") & (d["diff"] > 0.05)].sort_values("diff", ascending=False)[cols]
    neg = d.sort_values("diff").head(4)[cols]
    order = pd.concat([viol.assign(Case="Unitary, SUB above WOFI by more than 0.05"),
                       neg.assign(Case="Four largest negative gaps")]).round(3)
    # where does the gap come from: compare level ratios
    order["Ratio_sub_IMF_to_WOFI"] = (order["IMF_sub_pctGDP"] / order["WOFI_sub_pctGDP"]).round(2)
    order["Ratio_total_IMF_to_WOFI"] = (order["IMF_total_pctGDP"] / order["WOFI_GG_pctGDP"]).round(2)
    d.round(4).to_csv(OUT / "r5w_B_comparison_data.csv")
    return pd.DataFrame(groups), order.reset_index()


# ------------------------------------------------------------------------------------------------ C

def part_c(p):
    e = harmonised_05()
    e["SPEND"] = (e["SUBLEV"] / e[pc.GG]).where(e[pc.GG] > 0).clip(0, 1)
    e["FIN"] = (1 - e["CENTRAL"] / e[pc.GG]).where(e[pc.GG] > 0).clip(0, 1)
    e["RATIO"] = ((e["SUBLEV"] + e["CENTRAL"]) / e[pc.GG]).where(e[pc.GG] > 0)
    e["SPEND_RAW"] = (e["SUBLEV"] / e[pc.GG]).where(e[pc.GG] > 0)
    lag = e[["ISO", "YEAR", "SPEND", "FIN", "RATIO", "SPEND_RAW", "TIER"]].copy()
    lag["YEAR"] += 1
    lag = lag.rename(columns={"TIER": "TIER_SPEND_YEAR"})
    s = pc._sample(p).merge(lag, on=["ISO", "YEAR"], how="left")
    t = s[(s["TIER_L1"] == "T1") & s["SPEND"].notna() & s["FIN"].notna()].copy()
    t["WEDGE"] = t["SPEND"] - t["FIN"]
    f = "lnPM ~ lnENV + {v} + {v}:GE + GE + " + pc.CONTROLS + " + C(YEAR) + C(SUBREGION)"
    rows = []
    for v, lab in (("SUB", "SUB, the paper's share"), ("SPEND", "Spending share (state + local)/GG"),
                   ("FIN", "Financing share 1 - central/GG")):
        r, d = pc._fit(f.format(v=v), t, pc.BASE_NEEDED + [v])
        rows.append(row(lab, r, d, v, {"Mean_share": round(float(d[v].mean()), 3)}))
    fd = ("lnPM ~ lnENV + FIN + FIN:GE + WEDGE + WEDGE:GE + GE + " + pc.CONTROLS
          + " + C(YEAR) + C(SUBREGION)")
    r, d = pc._fit(fd, t, pc.BASE_NEEDED + ["FIN", "WEDGE"])
    names = list(r.params.index)

    def contrast(a, b):
        R = np.zeros((1, len(names)))
        R[0, names.index(a)], R[0, names.index(b)] = 1, -1
        return r.wald_test(R, scalar=True)
    eq = contrast("FIN:GE", "WEDGE:GE")
    eq0 = contrast("FIN", "WEDGE")
    dec = [row("Decomposition: financing share", r, d, "FIN"),
           row("Decomposition: wedge (spending minus financing share)", r, d, "WEDGE",
               {"p_equal_interactions": round(float(eq.pvalue), 3),
                "p_equal_main_effects": round(float(eq0.pvalue), 3)})]
    # whole-sample (not only T1) comparison is the paper's Table S7 variant F; here only identical samples
    t["GE_tercile"] = pd.qcut(t["GE"], 3, labels=["low", "middle", "high"])
    desc = {"N": int(len(t)), "Countries": int(t["ISO"].nunique()),
            "T1_obs_in_main_sample": int((pc._sample(p)["TIER_L1"] == "T1").sum()),
            "corr_SUB_SPEND": round(float(t["SUB"].corr(t["SPEND"])), 3),
            "corr_SUB_FIN": round(float(t["SUB"].corr(t["FIN"])), 3),
            "corr_SPEND_FIN": round(float(t["SPEND"].corr(t["FIN"])), 3),
            "mean_SUB": round(float(t["SUB"].mean()), 3), "mean_SPEND": round(float(t["SPEND"].mean()), 3),
            "mean_FIN": round(float(t["FIN"].mean()), 3),
            "mean_WEDGE": round(float(t["WEDGE"].mean()), 3), "sd_WEDGE": round(float(t["WEDGE"].std()), 3),
            "p90_WEDGE": round(float(t["WEDGE"].quantile(0.9)), 3),
            "share_obs_SPEND_capped": round(float((t["SPEND_RAW"] > 1).mean()), 3),
            "share_obs_identity": round(float(((t["RATIO"] - 1).abs() < 0.001).mean()), 3),
            "corr_WEDGE_GE": round(float(t["WEDGE"].corr(t["GE"])), 3),
            "ratio_by_GE_tercile": t.groupby("GE_tercile", observed=True)["RATIO"]
                                    .describe()[["count", "50%", "mean"]].round(3).to_dict(orient="index"),
            "wedge_by_GE_tercile": t.groupby("GE_tercile", observed=True)["WEDGE"].mean().round(3).to_dict(),
            "identity_share_by_GE_tercile": t.assign(I=((t["RATIO"] - 1).abs() < 0.001))
                                             .groupby("GE_tercile", observed=True)["I"].mean().round(3).to_dict()}
    return pd.DataFrame(rows + dec), desc


# ------------------------------------------------------------------------------------------------ D

def part_d(p):
    s = pc._sample(p)
    m = s.groupby("ISO").agg(SUB=("SUB", "mean"), GE=("GE", "mean"))
    rai = pd.read_excel(RAI_FILE).rename(columns={"abbr_country": "ISO"})
    rai = rai[rai["year"].between(1996, 2018)]
    r = rai.groupby("ISO")[["n_policyautonomy", "n_fiscalautonomy", "n_selfrule"]].mean()
    d = m.join(r, how="inner").dropna()
    out = []
    for name, x in (("All covered", d), ("Negative mean GE", d[d["GE"] < 0]), ("Non-negative mean GE", d[d["GE"] >= 0])):
        o = {"Group": name, "Countries": int(len(x))}
        for c in ["n_policyautonomy", "n_fiscalautonomy", "n_selfrule"]:
            o[f"corr_SUB_{c}"] = round(float(x["SUB"].corr(x[c])), 3)
            o[f"spearman_SUB_{c}"] = round(float(x["SUB"].corr(x[c], method="spearman")), 3)
        out.append(o)
    return pd.DataFrame(out)


if __name__ == "__main__":
    OUT = Path(ARGS.out)
    OUT.mkdir(parents=True, exist_ok=True)
    p0 = pc.build_panel()
    s0 = pc._sample(p0)
    print("main sample", len(s0), s0["ISO"].nunique())
    iso = set(s0["ISO"])
    ge_mean = s0.groupby("ISO")["GE"].mean().to_dict()
    a, a_sens, a_info = part_a(iso, ge_mean)
    b_groups, b_order = part_b(iso, ge_mean)
    c, c_desc = part_c(p0)
    dd = part_d(p0)
    a.to_csv(OUT / "r5w_A_wofi_crosssection.csv", index=False)
    a_sens.to_csv(OUT / "r5w_A_wofi_crosssection_sensitivity.csv", index=False)
    b_groups.to_csv(OUT / "r5w_B_validation_groups.csv", index=False)
    b_order.to_csv(OUT / "r5w_B_ordering.csv", index=False)
    c.to_csv(OUT / "r5w_C_shares_T1.csv", index=False)
    dd.to_csv(OUT / "r5w_D_rai.csv", index=False)
    (OUT / "r5w_results.json").write_text(json.dumps({"A": a_info, "C": c_desc}, indent=1, default=str),
                                          encoding="utf8")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for name, t in (("A", a), ("A sensitivity", a_sens), ("B groups", b_groups), ("B ordering", b_order),
                    ("C", c), ("D", dd)):
        print(f"\n=== {name} ===")
        print(t.to_string(index=False))
    print(json.dumps({"A": a_info, "C": c_desc}, indent=1, default=str))
