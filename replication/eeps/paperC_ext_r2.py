"""
Environmental-spending study: further estimates (central-only countries, other functions, diversity of local conditions, influence of single countries).

    python paperC_ext_r2.py [--main PATH_TO_env_federalism.py] [--ext DIR_WITH_PROXIES] [--out DIR]

(1) Table 2, column (4): without the 36 countries that report central data alone.
(2) Placebo shares (education, recreation/culture/religion) without those countries, with Wald tests.
(3) Proposition 2(iii): heterogeneity of local conditions (terrain ruggedness, ethnic fractionalisation).
(4) Influence of single countries: leave-one-country-out and country DFBETA.
(5) Fit of the share with SNG-WOFI among countries with negative mean GE.
(6) Asia and Oceania among the countries with negative mean GE.

Proxy data (not redistributed):
    Nunn and Puga (2012) ruggedness: https://diegopuga.org/data/rugged/rugged_data.zip
        (SHA-256 of the zip 3696fc1bd592cad7e75393b5988f797b234ce1797b92a1db037da7e9c657ed1f)
    Drazanova (2019) HIEF: https://dataverse.harvard.edu/api/access/datafile/3476857?format=original
        (doi:10.7910/DVN/4JQRCL, SHA-256 273f31955e24154f63b8e831008558d8531dfc3775e72067f0782fcc949e77fe)
"""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--main", default=str(HERE / "env_federalism.py"))
ap.add_argument("--ext", default=str(HERE / "data_ext" / "lab"))
ap.add_argument("--esm", default=str(HERE / "output" / "ESM1_TableS3_sngwofi_comparison.csv"))
ap.add_argument("--out", default=str(HERE / "output"))
args = ap.parse_args()

spec = importlib.util.spec_from_file_location("pc", args.main)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)
EXT, OUT = Path(args.ext), Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)

G_REF = None           # median GE of low- and middle-income countries, set below from the panel
G_THR = 1.0             # baseline threshold (Table 2, column 3)
NEED = pc.BASE_NEEDED + ["SUB"]
FX = f"{pc.CONTROLS} + C(YEAR) + C(SUBREGION)"


def lincom(r, w: dict) -> dict:
    R = np.zeros(len(r.params))
    names = list(r.params.index)
    for k, v in w.items():
        R[names.index(k)] = v
    t = r.t_test(R)
    est, se = float(t.effect[0]), float(t.sd[0][0])
    return {"est": est, "se": se, "p": float(2 * stats.norm.sf(abs(est / se)))}


def pct25(m: dict) -> dict:
    return {"pct": round(100 * (np.exp(0.25 * m["est"]) - 1), 1), "p": round(m["p"], 4)}


def coefs(r, keys):
    return {k: {"b": round(r.params[k], 3), "se": round(r.bse[k], 3), "p": round(r.pvalues[k], 4)}
            for k in keys if k in r.params}


p = pc.build_panel()
s = p[p["COMPLETE_L1"]]
main = pc._sample(p)
G_REF = pc.ge_reference(p)["LMIC"]
res = {}

# (1) Table 2, column (4) ------------------------------------------------------------------------------
r3, d3 = pc._fit(pc.BASE, s, NEED)
r4, d4 = pc._fit(pc.BASE, s[s["NOSUB"] == 0], NEED)
r4b, d4b = pc._fit(pc.BASE, s.assign(SUB=s["SUB"].where(s["NOSUB"] == 0)), NEED)
col4 = {"N": int(r4.nobs), "countries": int(d4["ISO"].nunique()), "R2": round(r4.rsquared, 3),
        **coefs(r4, ["lnENV", "SUB", "SUB:GE", "GE"]),
        "ME25_at_LMIC_median": pct25(lincom(r4, {"SUB": 1, "SUB:GE": G_REF}))}
col4["variant_SUB_missing_same_estimates"] = bool(
    int(r4b.nobs) == int(r4.nobs) and np.allclose(r4b.params.values, r4.params.values))
col4["col3_reference"] = {"N": int(r3.nobs), **coefs(r3, ["SUB", "SUB:GE"])}
res["1_table2_col4"] = col4

# (2) Placebo shares without central-only countries ------------------------------------------------------
px = pc.add_other_shares(p)
h = pd.read_csv(pc.HARMONISED, dtype={"DIV": str})
for div in ("08", "09"):
    e = h[h["DIV"] == div]
    struct0 = e.groupby("ISO").apply(lambda g: not (g["EVER_SG"].astype(bool).any() or g["EVER_LG"].astype(bool).any()),
                                     include_groups=False)
    px[f"NOSUB{div}"] = px["ISO"].map(struct0).fillna(True).astype(int)
sx = px[px["COMPLETE_L1"] & (px["NOSUB"] == 0)]


def placebo_rows(data, tag):
    rows = {}
    specs = [
        ("a_baseline_sample_SUB08", NEED + ["SUB08"], pc.BASE),
        ("b_SUB08_in_place", pc.BASE_NEEDED + ["SUB08"], f"lnPM ~ lnENV + SUB08 + SUB08:GE + GE + {FX}"),
        ("c_SUB09_in_place", pc.BASE_NEEDED + ["SUB09"], f"lnPM ~ lnENV + SUB09 + SUB09:GE + GE + {FX}"),
        ("d_SUB_and_SUB08", NEED + ["SUB08"], f"lnPM ~ lnENV + SUB + SUB:GE + GE + SUB08 + SUB08:GE + {FX}"),
        ("e_SUB_and_SUB09", NEED + ["SUB09"], f"lnPM ~ lnENV + SUB + SUB:GE + GE + SUB09 + SUB09:GE + {FX}"),
    ]
    for name, nd, f in specs:
        r, d = pc._fit(f, data, nd)
        row = {"N": int(r.nobs), "countries": int(d["ISO"].nunique()),
               **coefs(r, ["SUB", "SUB:GE", "SUB08", "SUB08:GE", "SUB09", "SUB09:GE"])}
        for v in ("SUB", "SUB08", "SUB09"):
            if f"{v}:GE" in r.params:
                row[f"ME25_{v}"] = pct25(lincom(r, {v: 1, f"{v}:GE": G_REF}))
        for v in ("SUB08", "SUB09"):
            if "SUB:GE" in r.params and f"{v}:GE" in r.params:
                row[f"wald_SUBxGE_minus_{v}xGE"] = {k: round(x, 4) for k, x in
                                                     lincom(r, {"SUB:GE": 1, f"{v}:GE": -1}).items()}
                row[f"wald_ME_SUB_minus_{v}_at_LMIC_median"] = {k: round(x, 4) for k, x in lincom(
                    r, {"SUB": 1, "SUB:GE": G_REF, v: -1, f"{v}:GE": -G_REF}).items()}
        rows[name] = row
    return rows


res["2_placebo_excl_central_only"] = placebo_rows(sx, "primary")
sx8 = sx[sx["NOSUB08"] == 0]
sx9 = sx[sx["NOSUB09"] == 0]
sec = {}
for nm, data in (("excl_struct_zero_08", sx8), ("excl_struct_zero_09", sx9)):
    rr = placebo_rows(data, nm)
    keep = ["b_SUB08_in_place", "d_SUB_and_SUB08"] if nm.endswith("08") else ["c_SUB09_in_place", "e_SUB_and_SUB09"]
    sec[nm] = {k: rr[k] for k in keep}
res["2b_placebo_secondary"] = sec

# (3) Proposition 2(iii) ---------------------------------------------------------------------------------
rug = pd.read_csv(EXT / "rugged" / "rugged_data.csv", encoding="latin-1")[["isocode", "rugged"]].rename(columns={"isocode": "ISO"})
hief = pd.read_csv(EXT / "HIEF_data.csv")
NAME2ISO = {
    "Albania": "ALB", "Algeria": "DZA", "Angola": "AGO", "Argentina": "ARG", "Armenia": "ARM", "Australia": "AUS",
    "Austria": "AUT", "Azerbaijan": "AZE", "Bangladesh": "BGD", "Belarus": "BLR", "Belgium": "BEL", "Bhutan": "BTN",
    "Bolivia": "BOL", "Botswana": "BWA", "Brazil": "BRA", "Bulgaria": "BGR", "Burkina Faso": "BFA",
    "Cape Verde": "CPV", "Chile": "CHL", "China": "CHN", "Congo": "COG", "Costa Rica": "CRI",
    "Cote d'Ivoire": "CIV", "Croatia": "HRV", "Cyprus": "CYP", "Czech Republic": "CZE", "Denmark": "DNK",
    "Dominican Republic": "DOM", "East Timor": "TLS", "Ecuador": "ECU", "Egypt": "EGY", "El Salvador": "SLV",
    "Estonia": "EST", "Fiji": "FJI", "Finland": "FIN", "Georgia": "GEO", "German Federal Republic": "DEU",
    "Greece": "GRC", "Guatemala": "GTM", "Honduras": "HND", "Hungary": "HUN", "Indonesia": "IDN", "Iran": "IRN",
    "Ireland": "IRL", "Israel": "ISR", "Italy": "ITA", "Japan": "JPN", "Kazakhstan": "KAZ", "Kenya": "KEN",
    "Kuwait": "KWT", "Kyrgyz Republic": "KGZ", "Latvia": "LVA", "Lebanon": "LBN", "Lithuania": "LTU",
    "Madagascar": "MDG", "Mauritius": "MUS", "Moldova": "MDA", "Mongolia": "MNG", "Mozambique": "MOZ",
    "Namibia": "NAM", "Nepal": "NPL", "Netherlands": "NLD", "New Zealand": "NZL", "Nicaragua": "NIC",
    "Norway": "NOR", "Oman": "OMN", "Pakistan": "PAK", "Panama": "PAN", "Philippines": "PHL", "Poland": "POL",
    "Portugal": "PRT", "Qatar": "QAT", "Republic of Korea": "KOR", "Romania": "ROU", "Russia": "RUS",
    "Serbia": "SRB", "Singapore": "SGP", "Slovakia": "SVK", "Slovenia": "SVN", "Solomon Islands": "SLB",
    "South Africa": "ZAF", "Spain": "ESP", "Sweden": "SWE", "Switzerland": "CHE", "Tajikistan": "TJK",
    "Tanzania": "TZA", "Thailand": "THA", "Tunisia": "TUN", "Turkey": "TUR", "Uganda": "UGA", "Ukraine": "UKR",
    "United Kingdom": "GBR", "Uzbekistan": "UZB", "Zambia": "ZMB",
}
hief["ISO"] = hief["Country"].map(NAME2ISO)
ef = hief[hief["Year"].between(1990, 2013)].dropna(subset=["ISO"]).groupby("ISO")["EFindex"].mean().rename("EF")
countries = sorted(main["ISO"].unique())
proxies = pd.DataFrame({"ISO": countries}).merge(rug, on="ISO", how="left").merge(ef, on="ISO", how="left")


def het_test(var, label):
    z = proxies.set_index("ISO")[var]
    z = (z - z.mean()) / z.std()
    d = s.assign(H=s["ISO"].map(z))
    f = pc.BASE.replace(" + GE + ", " + GE + H + SUB:H + GE:H + SUB:GE:H + ")
    r, dd = pc._fit(f, d, NEED + ["H"])
    out = {"proxy": label, "countries_with_proxy": int(z.notna().sum()), "N": int(r.nobs),
           "countries": int(dd["ISO"].nunique()), **coefs(r, ["SUB", "SUB:GE", "SUB:H", "SUB:GE:H", "H", "GE:H"])}
    out["dME_dH_at_GE_1.0"] = {k: round(x, 4) for k, x in lincom(r, {"SUB:H": 1, "SUB:GE:H": G_THR}).items()}
    out["dME_dH_at_LMIC_median"] = {k: round(x, 4) for k, x in lincom(r, {"SUB:H": 1, "SUB:GE:H": G_REF}).items()}
    # thresholds g*(H) = -(b_SUB + b_SUB:H H) / (b_SUB:GE + b_SUB:GE:H H), delta method
    b, V = r.params, r.cov_params()
    ks = ["SUB", "SUB:H", "SUB:GE", "SUB:GE:H"]
    for hv in (-1.0, 0.0, 1.0):
        num, den = b["SUB"] + b["SUB:H"] * hv, b["SUB:GE"] + b["SUB:GE:H"] * hv
        g = -num / den
        grad = np.array([-1 / den, -hv / den, num / den ** 2, num * hv / den ** 2])
        se = float(np.sqrt(grad @ V.loc[ks, ks].values @ grad))
        out[f"threshold_at_H_{hv:+.0f}SD"] = {"g": round(float(g), 3), "se": round(se, 3)}
    return out


res["3_prop2iii"] = {"primary_ruggedness": het_test("rugged", "Terrain ruggedness (Nunn and Puga 2012)"),
                     "secondary_ethnic_fractionalisation": het_test("EF", "HIEF ethnic fractionalisation, mean 1990-2013")}
res["3_prop2iii"]["proxy_missing_ruggedness"] = sorted(proxies.loc[proxies["rugged"].isna(), "ISO"])
res["3_prop2iii"]["proxy_missing_EF"] = sorted(proxies.loc[proxies["EF"].isna(), "ISO"])

# (4) Influence ------------------------------------------------------------------------------------------
me3 = lincom(r3, {"SUB": 1, "SUB:GE": G_REF})
rows = []
for c in countries:
    r, d = pc._fit(pc.BASE, s[s["ISO"] != c], NEED)
    me = lincom(r, {"SUB": 1, "SUB:GE": G_REF})
    rows.append({"ISO": c, "SUB": r.params["SUB"], "SUBxGE": r.params["SUB:GE"], "p_SUBxGE": r.pvalues["SUB:GE"],
                 "ME": me["est"], "ME25_pct": 100 * (np.exp(0.25 * me["est"]) - 1), "p_ME": me["p"],
                 "DFB_SUB": (r3.params["SUB"] - r.params["SUB"]) / r3.bse["SUB"],
                 "DFB_SUBxGE": (r3.params["SUB:GE"] - r.params["SUB:GE"]) / r3.bse["SUB:GE"],
                 "DFB_ME": (me3["est"] - me["est"]) / me3["se"]})
loco = pd.DataFrame(rows)
loco.round(4).to_csv(OUT / "r2_leave_one_country_out.csv", index=False)
thr = 2 / np.sqrt(len(countries))
infl = {"threshold": round(thr, 3),
        "SUBxGE_range": [round(loco["SUBxGE"].min(), 3), round(loco["SUBxGE"].max(), 3)],
        "p_SUBxGE_max": round(loco["p_SUBxGE"].max(), 4),
        "ME25_range": [round(loco["ME25_pct"].min(), 1), round(loco["ME25_pct"].max(), 1)],
        "p_ME_max": round(loco["p_ME"].max(), 4)}
for key, col in (("primary_SUBxGE", "DFB_SUBxGE"), ("secondary_ME", "DFB_ME")):
    drop = sorted(loco.loc[loco[col].abs() > thr, "ISO"])
    r, d = pc._fit(pc.BASE, s[~s["ISO"].isin(drop)], NEED)
    infl[f"drop_{key}"] = {"countries_dropped": drop, "N": int(r.nobs), "countries": int(d["ISO"].nunique()),
                           **coefs(r, ["SUB", "SUB:GE"]),
                           "ME25_at_LMIC_median": pct25(lincom(r, {"SUB": 1, "SUB:GE": G_REF}))}
for c in ("BOL", "NPL"):
    row = loco[loco["ISO"] == c].iloc[0]
    infl[c] = {"SUBxGE_without": round(row["SUBxGE"], 3), "p": round(row["p_SUBxGE"], 4),
               "ME25_without": round(row["ME25_pct"], 1), "p_ME": round(row["p_ME"], 4),
               "DFB_SUBxGE": round(row["DFB_SUBxGE"], 3), "DFB_ME": round(row["DFB_ME"], 3)}
res["4_influence"] = infl

# (5) Fit with SNG-WOFI among countries with negative mean GE --------------------------------------------
cmp_ = pd.read_csv(args.esm)
cmp_ = cmp_[(cmp_["In_sample"] == 1) & cmp_["SUB_2019"].notna() & cmp_["WOFI_share"].notna()].copy()
ge_m = main.groupby("ISO")["GE"].mean()
cmp_["GE_mean"] = cmp_["ISO3"].map(ge_m)
a_col, b_col = "SUB_2019", "WOFI_share"
neg = cmp_[cmp_["GE_mean"] < 0]
res["5_sngwofi_negative_ge"] = {"columns_used": [a_col, b_col], "countries": int(len(neg)),
                                "r": round(float(neg[a_col].corr(neg[b_col])), 3),
                                "mean_abs_diff": round(float((neg[a_col] - neg[b_col]).abs().mean()), 3),
                                "median_abs_diff": round(float((neg[a_col] - neg[b_col]).abs().median()), 3),
                                "all_countries": int(len(cmp_)),
                                "r_all": round(float(cmp_[a_col].corr(cmp_[b_col])), 3)}

# (6) Asia and Oceania among countries with negative mean GE ---------------------------------------------
reg = main.groupby("ISO")["REGION"].first()
negc = ge_m[ge_m < 0].index
res["6_asia_pacific_negative_ge"] = {"countries_negative_ge": int(len(negc)),
                                     "by_region": reg[negc].value_counts().to_dict(),
                                     "asia_plus_oceania": int(reg[negc].isin(["Asia", "Oceania"]).sum())}

(OUT / "r2_results.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf8")
print(json.dumps(res, indent=1, default=float))
