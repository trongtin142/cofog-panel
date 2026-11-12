"""
Environmental-spending study, further estimate: anthropogenic PM2.5 as outcome.

Uses the 2017 source contributions of GBD-MAPS (McDuffie et al. 2021, Nat Commun 12:3594, Supplementary Data 1)
to remove windblown dust and the remaining natural sources (sea salt, biogenic, volcanic, lightning, soil NOx)
from population-weighted PM2.5.

    python ext_anthro.py --main <path to env_federalism.py> --gbdmaps <MOESM4 xlsx> --out <dir>
"""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

GBDMAPS_SHA256 = "81a563fe2662bb81931efa0bcab204c7818410a80cd3c41f3e65c3b5ab7aed13"
GE_REF = None  # set from the main script (median GE of low- and middle-income countries)

SECTORS = ["Agriculture", "Energy Coal", "Energy NonCoal", "Industry Coal", "Industry NonCoal", "NonRoad Transport",
           "Road Transport", "Residential Coal Combustion", "Residential Biofuel Combustion",
           "Residential Other Combustion", "Commercial Combustion", "Other Combustion", "Solvent", "Waste",
           "International Shipping", "Agricultural Waste Burning", "Other Open Fire", "AFCID Dust",
           "Windblown Dust", "Remaining Sources"]
LOCAL = ["Residential Coal Combustion", "Residential Biofuel Combustion", "Residential Other Combustion",
         "Commercial Combustion", "Waste", "AFCID Dust"]
NATIONAL = ["Energy Coal", "Energy NonCoal", "Industry Coal", "Industry NonCoal"]
# GBD-MAPS country names that differ from the World Bank names (checked by hand against the sample)
MANUAL = {"Czech Republic": "CZE", "Macedonia": "MKD", "Moldova": "MDA", "Russia": "RUS", "Russian Federation": "RUS",
          "Iran": "IRN", "South Korea": "KOR", "Korea": "KOR", "Kyrgyzstan": "KGZ", "Slovakia": "SVK",
          "Egypt": "EGY", "Bahamas": "BHS", "The Bahamas": "BHS", "Congo": "COG", "Cote d'Ivoire": "CIV",
          "Cote dIvoire": "CIV", "Turkey": "TUR", "Federated States of Micronesia": "FSM", "Micronesia": "FSM",
          "Tanzania": "TZA", "Bolivia": "BOL", "Palestine": "PSE", "Sao Tome and Principe": "STP",
          "Cape Verde": "CPV", "Cabo Verde": "CPV", "Gambia": "GMB", "Laos": "LAO", "Vietnam": "VNM",
          "Syria": "SYR", "Yemen": "YEM", "Venezuela": "VEN", "Swaziland": "SWZ", "Eswatini": "SWZ",
          "Brunei": "BRN", "Timor-Leste": "TLS", "East Timor": "TLS", "United States": "USA",
          "United Kingdom": "GBR", "Saint Lucia": "LCA", "Kosovo": "XKX", "Taiwan": "TWN",
          "Democratic Republic of the Congo": "COD", "Marshall Islands": "MHL", "Solomon Islands": "SLB"}


def load_main(path: Path):
    spec = importlib.util.spec_from_file_location("pc", path)
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)
    return pc


def read_gbdmaps(path: Path) -> pd.DataFrame:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != GBDMAPS_SHA256:
        print(f"WARNING: {path.name} differs from the file used (SHA-256 {digest[:12]}...)")
    d = pd.read_excel(path, header=None)
    d = d.iloc[7:, :22].copy()
    d.columns = ["name", "PM"] + SECTORS
    d["name"] = d["name"].astype(str).str.replace("_", " ").str.strip()
    for c in ["PM"] + SECTORS:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.dropna(subset=["PM"]).reset_index(drop=True)


def match_iso(g: pd.DataFrame, pc, sample_iso: set) -> pd.DataFrame:
    """Map GBD-MAPS names to ISO3. The first occurrence of a name is the country row (regions and
    sub-national areas follow their country), and only names that map to an ISO3 are kept."""
    rows = json.loads((pc.EXT / "wb_countries.json").read_text(encoding="utf8"))[1]
    wb = {r["name"]: r["id"] for r in rows}
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower())
    wbn = {norm(k): v for k, v in wb.items()}
    out = []
    for _, r in g.iterrows():
        iso = MANUAL.get(r["name"]) or wb.get(r["name"]) or wbn.get(norm(r["name"]))
        out.append(iso)
    g = g.assign(ISO=out).dropna(subset=["ISO"])
    g = g.drop_duplicates(subset=["ISO"], keep="first")
    return g


def me25(r, ge: float, b_sub: str, b_int: str) -> dict:
    b, V = r.params, r.cov_params()
    m = b[b_sub] + b[b_int] * ge
    se = float(np.sqrt(V.loc[b_sub, b_sub] + ge ** 2 * V.loc[b_int, b_int] + 2 * ge * V.loc[b_sub, b_int]))
    return {"me": float(m), "se": se, "pct25": round(100 * (np.exp(0.25 * m) - 1), 1),
            "p": float(2 * stats.norm.sf(abs(m / se)))}


def row(name, r, d, sub, inter, ge):
    e = me25(r, ge, sub, inter)
    return {"Model": name, "N": int(r.nobs), "Countries": int(d["ISO"].nunique()), "R2": round(r.rsquared, 3),
            "SUB": round(r.params[sub], 3), "se_SUB": round(r.bse[sub], 3), "p_SUB": round(r.pvalues[sub], 4),
            "SUB:GE": round(r.params[inter], 3), "se_SUB:GE": round(r.bse[inter], 3),
            "p_SUB:GE": round(r.pvalues[inter], 4), "ME25_LMIC": e["pct25"], "p_ME25_LMIC": round(e["p"], 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    ap.add_argument("--gbdmaps", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pc = load_main(Path(a.main))
    p = pc.build_panel()
    ge = pc.ge_reference(p)["LMIC"]
    s = pc._sample(p).copy()

    g = match_iso(read_gbdmaps(Path(a.gbdmaps)), pc, set(s["ISO"]))
    g["ANTHRO"] = g["PM"] * (100 - g["Windblown Dust"] - g["Remaining Sources"]) / 100
    # anthropogenic sectors: all sectors except open fires, windblown dust and remaining sources
    g["CONTROL"] = g["PM"] * g[[c for c in SECTORS if c not in ("Other Open Fire", "Windblown Dust",
                                                                 "Remaining Sources")]].sum(axis=1) / 100
    g["LOCAL"] = g["PM"] * g[LOCAL].sum(axis=1) / 100
    g["NATIONAL"] = g["PM"] * g[NATIONAL].sum(axis=1) / 100
    g["f_anthro"] = g["ANTHRO"] / g["PM"]
    g["f_control"] = g["CONTROL"] / g["PM"]
    keep = g[g["ISO"].isin(set(s["ISO"]))]
    unmatched = sorted(set(s["ISO"]) - set(keep["ISO"]))
    keep[["name", "ISO", "PM", "Windblown Dust", "Remaining Sources", "Other Open Fire", "ANTHRO", "CONTROL",
          "LOCAL", "NATIONAL", "f_anthro", "f_control"]].to_csv(out / "r2b_gbdmaps_matched.csv", index=False)

    rows, info = [], {"ge_ref_LMIC": ge, "unmatched_sample_iso": unmatched, "matched_countries": int(len(keep))}

    # ---------- P1: panel, Table 2 column 3 with ln(PM x f) ----------
    m = s.merge(keep[["ISO", "f_anthro", "f_control"]], on="ISO", how="inner")
    m["lnPM_A"] = m["lnPM"] + np.log(m["f_anthro"])
    m["lnPM_C"] = m["lnPM"] + np.log(m["f_control"])
    need = pc.BASE_NEEDED + ["SUB"]
    for name, y in [("P1 paper outcome, matched sample", "lnPM"), ("P1 anthropogenic PM2.5 (ANTHRO)", "lnPM_A"),
                    ("P3 controllable PM2.5 (CONTROL)", "lnPM_C")]:
        r, d = pc._fit(pc.BASE.replace("lnPM ~", f"{y} ~", 1), m, need)
        rows.append(row(name, r, d, "SUB", "SUB:GE", ge))

    # ---------- P2: cross-section 2017 on country means ----------
    v = ["lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS", "lnPM"]
    cm = s.groupby("ISO")[v].mean().add_suffix("_m").reset_index()
    cm = cm.merge(s.groupby("ISO")["SUBREGION"].first().reset_index(), on="ISO")
    cm = cm.merge(keep[["ISO", "PM", "ANTHRO", "CONTROL", "LOCAL", "NATIONAL"]], on="ISO", how="inner")
    cm["SUBGE"] = cm["SUB_m"] * cm["GE_m"]
    for c in ["PM", "ANTHRO", "CONTROL", "LOCAL", "NATIONAL"]:
        cm[f"ln{c}"] = np.log(cm[c])
    rhs = ("SUB_m + SUBGE + GE_m + lnENV_m + lnY_m + lnY2_m + IND_m + URB_m + TRADE_m + lnDENS_m"
           " + C(SUBREGION)")
    for name, y in [("P2 cross-section: mean ln WDI PM2.5", "lnPM_m"), ("P2 cross-section: ln total PM2.5 2017",
                                                                       "lnPM"),
                    ("P2 cross-section: ln ANTHRO 2017", "lnANTHRO"), ("P3 cross-section: ln CONTROL 2017",
                                                                        "lnCONTROL"),
                    ("P4 exploratory: ln LOCAL 2017", "lnLOCAL"), ("P4 exploratory: ln NATIONAL 2017",
                                                                  "lnNATIONAL")]:
        dd = cm.replace([np.inf, -np.inf], np.nan).dropna(subset=[y])
        r = smf.ols(f"{y} ~ {rhs}", data=dd).fit(cov_type="HC3")
        rows.append(row(name, r, dd, "SUB_m", "SUBGE", ge))

    # ---------- P4: stacked difference LOCAL minus NATIONAL ----------
    st = []
    for k, y in [("A_LOCAL", "lnLOCAL"), ("B_NATIONAL", "lnNATIONAL")]:
        t = cm.copy()
        t["Y"], t["K"] = t[y], k
        st.append(t)
    st = pd.concat(st).replace([np.inf, -np.inf], np.nan).dropna(subset=["Y"])
    r = smf.ols(f"Y ~ C(K) * ({rhs})", data=st).fit(cov_type="cluster",
                                                    cov_kwds={"groups": pd.factorize(st["ISO"])[0]})
    d_sub, d_int = "C(K)[T.B_NATIONAL]:SUB_m", "C(K)[T.B_NATIONAL]:SUBGE"
    e = me25(r, ge, d_sub, d_int)  # NATIONAL minus LOCAL
    info["P4_stacked_national_minus_local"] = {"me_diff": round(e["me"], 3), "se": round(e["se"], 3),
                                               "p": round(e["p"], 4)}

    # descriptives of the natural share
    k2 = keep.merge(s.groupby("ISO")["SUBREGION"].first().reset_index(), on="ISO")
    info["natural_share_pct"] = {"mean": round(float((1 - k2["f_anthro"]).mean() * 100), 1),
                                 "max": round(float((1 - k2["f_anthro"]).max() * 100), 1),
                                 "by_subregion_top5": (100 * (1 - k2.groupby("SUBREGION")["f_anthro"].mean()))
                                 .sort_values(ascending=False).head(5).round(1).to_dict()}
    info["corr_ln_wdi_mean_vs_ln_gbdmaps_total"] = round(float(np.corrcoef(cm["lnPM_m"], cm["lnPM"])[0, 1]), 3)
    tab = pd.DataFrame(rows)
    tab.to_csv(out / "tab_anthro.csv", index=False)
    (out / "anthro_results.json").write_text(json.dumps(info, indent=2), encoding="utf8")
    print(tab.to_string())
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
