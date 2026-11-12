"""
Controls for the main sources of PM2.5, a binning estimator of the interaction and equal country weights for
the environmental-spending study.

    python ext_r3c.py --main PATH_TO_env_federalism.py --anthro PATH_TO_ext_anthro.py
                             --dl DATA_DIR --gbdmaps GBDMAPS_XLSX --out OUTPUT_DIR [--coverage]

DATA_DIR holds the files downloaded on 1 November 2026 (URLs in data_ext/SOURCES.md, SHA-256 in fetch_data.py):
    wb_EG.CFT.ACCS.ZS.json, wb_EG.ELC.COAL.ZS.json        World Bank WDI API (CC BY 4.0)
    cckp_tas_cru408.json, cckp_pr_cru408.json             World Bank CCKP, CRU TS 4.08 country means
    owid_burnt.csv                                        Our World in Data, area burnt by wildfires (GWIS)
    ceds/{SO2,NOx,NH3}_CEDS_estimates_by_country_sector_v_2025_03_18.csv   CEDS (Zenodo 15059443, CC BY 4.0)
BC and OC by sector are read from the CEDS files used by ext_mech.py (--ceds-bcoc).
With --coverage the script reports the coverage of the new controls and estimates nothing.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

CEDS_VERSION = "v_2025_03_18"
RESIDENTIAL = ["1A4b_Residential"]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------------------------------------
# New controls
# ----------------------------------------------------------------------------------------------------------

def wdi(path: Path, name: str) -> pd.DataFrame:
    rows = json.loads(path.read_text(encoding="utf8"))[1]
    return pd.DataFrame([{"ISO": r["countryiso3code"], "YEAR": int(r["date"]), name: r["value"]}
                         for r in rows if r["value"] is not None and r["countryiso3code"]])


def cckp(path: Path, name: str) -> pd.DataFrame:
    data = json.loads(path.read_text(encoding="utf8"))["data"]
    return pd.DataFrame([{"ISO": iso, "YEAR": int(k[:4]), name: v}
                         for iso, series in data.items() for k, v in series.items() if v is not None])


def gbdmaps_levels(anthro, gbdmaps: Path, pc, sample_iso: set) -> pd.DataFrame:
    """Population-weighted PM2.5 from windblown dust and from open fires (other than agricultural waste
    burning) in 2017, GBD-MAPS (McDuffie et al. 2021). Time-invariant country values."""
    g = anthro.match_iso(anthro.read_gbdmaps(gbdmaps), pc, sample_iso)
    g["DUST17"] = g["PM"] * g["Windblown Dust"] / 100
    g["FIRE17"] = g["PM"] * g["Other Open Fire"] / 100
    return g[["ISO", "DUST17", "FIRE17"]]


def burnt(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d = d[d["Code"].astype(str).str.len() == 3]
    return d.rename(columns={"Code": "ISO", "Year": "YEAR", "Annual area burnt by wildfires": "BURNT_HA"})[
        ["ISO", "YEAR", "BURNT_HA"]]


def add_controls(p: pd.DataFrame, a, pc, anthro) -> pd.DataFrame:
    dl = Path(a.dl)
    x = p.merge(wdi(dl / "wb_EG.CFT.ACCS.ZS.json", "CLEANCOOK"), on=["ISO", "YEAR"], how="left")
    x = x.merge(wdi(dl / "wb_EG.ELC.COAL.ZS.json", "COALELEC"), on=["ISO", "YEAR"], how="left")
    x = x.merge(cckp(dl / "cckp_tas_cru408.json", "TAS"), on=["ISO", "YEAR"], how="left")
    x = x.merge(cckp(dl / "cckp_pr_cru408.json", "PR"), on=["ISO", "YEAR"], how="left")
    x["lnPR"] = np.log(x["PR"])
    g = gbdmaps_levels(anthro, Path(a.gbdmaps), pc, set(x["ISO"]))
    x = x.merge(g, on="ISO", how="left")
    x["lnDUST17"] = np.log1p(x["DUST17"])
    x["lnFIRE17"] = np.log1p(x["FIRE17"])
    return x


GROUPS = {
    "household": ["CLEANCOOK"],
    "power": ["COALELEC"],
    "fires": ["lnFIRE17"],
    "climate": ["TAS", "lnPR"],
    "dust": ["lnDUST17"],
}
GROUPS["all"] = sum((v for v in GROUPS.values()), [])
LABELS = {"household": "Adds access to clean cooking fuels", "power": "Adds coal share of electricity",
          "fires": "Adds PM2.5 from open fires (2017)", "climate": "Adds temperature and ln precipitation",
          "dust": "Adds PM2.5 from windblown dust (2017)", "all": "Adds all PM2.5 source controls"}


# ----------------------------------------------------------------------------------------------------------
# Estimation helpers
# ----------------------------------------------------------------------------------------------------------

def me25(r, ge: float, sub="SUB", inter="SUB:GE") -> dict:
    b, V = r.params, r.cov_params()
    m = b[sub] + b[inter] * ge
    se = float(np.sqrt(V.loc[sub, sub] + ge ** 2 * V.loc[inter, inter] + 2 * ge * V.loc[sub, inter]))
    return {"me": float(m), "se": se, "pct25": round(100 * (np.exp(0.25 * m) - 1), 1),
            "p": float(2 * stats.norm.sf(abs(m / se)))}


def fit(formula, data, needed, weights=None):
    d = data.dropna(subset=needed).copy()
    groups = pd.factorize(d["ISO"])[0]
    if weights is None:
        r = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": groups})
    else:
        w = d["ISO"].map(1 / d.groupby("ISO").size())
        r = smf.wls(formula, data=d, weights=w).fit(cov_type="cluster", cov_kwds={"groups": groups})
    return r, d


def row(sample, name, r, d, ge, extra=None):
    e = me25(r, ge)
    out = {"Sample": sample, "Model": name, "N": int(r.nobs), "Countries": int(d["ISO"].nunique()),
           "R2": round(r.rsquared, 3),
           "SUB": round(r.params["SUB"], 3), "se_SUB": round(r.bse["SUB"], 3), "p_SUB": round(r.pvalues["SUB"], 4),
           "SUB:GE": round(r.params["SUB:GE"], 3), "se_SUB:GE": round(r.bse["SUB:GE"], 3),
           "p_SUB:GE": round(r.pvalues["SUB:GE"], 4), "ME25_LMIC": e["pct25"], "p_ME25_LMIC": round(e["p"], 4)}
    for v in (extra or []):
        out[v] = round(r.params[v], 4)
        out[f"p_{v}"] = round(r.pvalues[v], 4)
    return out


def samples(p, pc):
    s = p[p["COMPLETE_L1"]]
    return {"110": s, "74": s[s["NOSUB"] == 0], "GG": s[s["TIER_L1"] == "T1"]}


# ----------------------------------------------------------------------------------------------------------
# Analyses
# ----------------------------------------------------------------------------------------------------------

def table_controls(x, pc, ge):
    need = pc.BASE_NEEDED + ["SUB"]
    rows = []
    for sname, s in samples(x, pc).items():
        r, d = fit(pc.BASE, s, need)
        rows.append(row(sname, "Baseline", r, d, ge))
        sall = s.dropna(subset=need + GROUPS["all"])
        r, d = fit(pc.BASE, sall, need)
        rows.append(row(sname, "Baseline, sample with all source controls", r, d, ge))
        for gname, vars_ in GROUPS.items():
            f = pc.BASE.replace(pc.CONTROLS, pc.CONTROLS + " + " + " + ".join(vars_))
            r, d = fit(f, s, need + vars_)
            rows.append(row(sname, LABELS[gname], r, d, ge, extra=vars_))
    return pd.DataFrame(rows)


def burnt_sensitivity(x, pc, ge, a):
    """Exploratory: time-varying burnt area (GWIS via OWID), 2012-2023 only."""
    b = burnt(Path(a.dl) / "owid_burnt.csv")
    area = pc._wb(pc.EXT / "wb_AG.LND.TOTL.K2.json", "AREA").groupby("ISO")["AREA"].mean()
    y = x.merge(b, on=["ISO", "YEAR"], how="left")
    y["BURNT_SH"] = 100 * (y["BURNT_HA"] / 100) / y["ISO"].map(area)  # ha -> km2, share of land area in %
    y["lnBURNT"] = np.log1p(y["BURNT_SH"])
    need = pc.BASE_NEEDED + ["SUB"]
    s = y[y["COMPLETE_L1"] & (y["YEAR"] >= 2012)]
    rows = []
    r, d = fit(pc.BASE, s.dropna(subset=["lnBURNT"]), need)
    rows.append(row("110, 2012-2023", "Baseline, sample with burnt area", r, d, ge))
    f = pc.BASE.replace(pc.CONTROLS, pc.CONTROLS + " + lnBURNT")
    r, d = fit(f, s, need + ["lnBURNT"])
    rows.append(row("110, 2012-2023", "Adds ln(1 + burnt area, % of land)", r, d, ge, extra=["lnBURNT"]))
    return pd.DataFrame(rows)


def ceds_outcomes(x, pc, a):
    """Exploratory outcomes: total SO2, NOx and NH3, and residential BC+OC, per person (CEDS)."""
    dl = Path(a.dl)
    out = []
    for sp in ("SO2", "NOx", "NH3"):
        d = pd.read_csv(dl / "ceds" / f"{sp}_CEDS_estimates_by_country_sector_{CEDS_VERSION}.csv")
        yrs = [c for c in d.columns if c.startswith("X") and 1995 <= int(c[1:]) <= 2023]
        d = d[["country"] + yrs].groupby("country").sum().reset_index().melt("country", var_name="YEAR",
                                                                              value_name=sp)
        d["YEAR"] = d["YEAR"].str[1:].astype(int)
        d["ISO"] = d["country"].str.upper()
        out.append(d[["ISO", "YEAR", sp]])
    res = []
    for sp in ("BC", "OC"):
        d = pd.read_csv(Path(a.ceds_bcoc) / f"{sp}_CEDS_estimates_by_country_sector_{CEDS_VERSION}.csv")
        yrs = [c for c in d.columns if c.startswith("X") and 1995 <= int(c[1:]) <= 2023]
        d = d[d["sector"].isin(RESIDENTIAL)][["country"] + yrs].groupby("country").sum().reset_index()
        d = d.melt("country", var_name="YEAR", value_name=sp)
        d["YEAR"] = d["YEAR"].str[1:].astype(int)
        d["ISO"] = d["country"].str.upper()
        res.append(d[["ISO", "YEAR", sp]])
    r = res[0].merge(res[1], on=["ISO", "YEAR"])
    r["RES_BCOC"] = r["BC"] + r["OC"]
    e = out[0]
    for o in out[1:]:
        e = e.merge(o, on=["ISO", "YEAR"], how="outer")
    e = e.merge(r[["ISO", "YEAR", "RES_BCOC"]], on=["ISO", "YEAR"], how="outer")
    pop = pc._wb(pc.EXT / "wb_SP.POP.TOTL.json", "POP")
    y = x.merge(e, on=["ISO", "YEAR"], how="left").merge(pop, on=["ISO", "YEAR"], how="left")
    rows = []
    need = [c for c in pc.BASE_NEEDED if c != "lnPM"] + ["SUB"]
    s = y[y["COMPLETE_L1"]]
    ge = a.ge
    for v, lab in (("SO2", "ln SO2 per person, all sectors"), ("NOx", "ln NOx per person, all sectors"),
                   ("NH3", "ln NH3 per person, all sectors"), ("RES_BCOC", "ln residential BC+OC per person")):
        s = s.assign(Y=np.log(s[v] / s["POP"]).replace([np.inf, -np.inf], np.nan))
        f = pc.BASE.replace("lnPM ~", "Y ~")
        r, d = fit(f, s, need + ["Y"])
        rows.append(row("110", lab, r, d, ge))
    return pd.DataFrame(rows)


def binning(x, pc, ge, nbins=3):
    """Binning estimator of Hainmueller, Mummolo and Xu (2019): GE terciles, marginal association of SUB at the
    bin medians, with the linear interaction model evaluated at the same points for comparison."""
    need = pc.BASE_NEEDED + ["SUB"]
    s = pc._sample(x).copy()
    cuts = s["GE"].quantile([1 / 3, 2 / 3]).values
    s["BIN"] = np.digitize(s["GE"], cuts)  # 0, 1, 2
    med = s.groupby("BIN")["GE"].median().to_dict()
    terms = []
    for j in range(nbins):
        g = (s["BIN"] == j).astype(float)
        s[f"G{j}"] = g
        s[f"SG{j}"] = s["SUB"] * g
        s[f"XG{j}"] = (s["GE"] - med[j]) * g
        s[f"SXG{j}"] = s["SUB"] * (s["GE"] - med[j]) * g
        terms += [f"G{j}", f"SG{j}", f"XG{j}", f"SXG{j}"]
    f = (f"lnPM ~ 0 + lnENV + {' + '.join(terms)} + {pc.CONTROLS} + C(YEAR) + C(SUBREGION)")
    r, d = fit(f, s, need)
    rl, _ = fit(pc.BASE, s, need)
    rows = []
    for j in range(nbins):
        b, se = r.params[f"SG{j}"], r.bse[f"SG{j}"]
        lin = me25(rl, med[j])
        # difference between the bin estimate and the linear model at the bin median (independent fits,
        # so the test is approximate)
        diff = b - lin["me"]
        rows.append({"bin": j + 1, "GE_from": round(float(s.loc[s["BIN"] == j, "GE"].min()), 2),
                     "GE_to": round(float(s.loc[s["BIN"] == j, "GE"].max()), 2), "GE_median": round(med[j], 3),
                     "N": int((s["BIN"] == j).sum()), "Countries": int(s.loc[s["BIN"] == j, "ISO"].nunique()),
                     "bin_me": round(float(b), 3), "bin_se": round(float(se), 3),
                     "bin_p": round(float(r.pvalues[f"SG{j}"]), 4),
                     "bin_pct25": round(100 * (np.exp(0.25 * b) - 1), 1),
                     "linear_me": round(lin["me"], 3), "linear_se": round(lin["se"], 3),
                     "diff_bin_minus_linear": round(float(diff), 3)})
    # joint Wald test that the three bin estimates equal the linear predictions at the bin medians
    R = np.zeros((nbins, len(r.params)))
    q = np.zeros(nbins)
    names = list(r.params.index)
    for j in range(nbins):
        R[j, names.index(f"SG{j}")] = 1
        q[j] = me25(rl, med[j])["me"]
    w = r.wald_test((R, q), scalar=True)
    return pd.DataFrame(rows), {"wald_bins_equal_linear_chi2": round(float(w.statistic), 3),
                                "wald_df": nbins, "wald_p": round(float(w.pvalue), 4)}, (r, rl, s, med)


def fig_binning(fitobj, path: Path, pc):
    r, rl, s, med = fitobj
    plt = pc._plt()
    ge = np.linspace(s["GE"].quantile(0.02), s["GE"].quantile(0.98), 60)
    b, V = rl.params, rl.cov_params()
    me = b["SUB"] + b["SUB:GE"] * ge
    se = np.sqrt(V.loc["SUB", "SUB"] + ge ** 2 * V.loc["SUB:GE", "SUB:GE"] + 2 * ge * V.loc["SUB", "SUB:GE"])
    fig, ax = plt.subplots(figsize=(pc.WIDTH_IN, 2.9))
    ax.fill_between(ge, me - 1.96 * se, me + 1.96 * se, color=pc.TIER_COLORS["T1"], alpha=0.18, linewidth=0)
    ax.plot(ge, me, color=pc.TIER_COLORS["T1"], linewidth=1.8, label="Linear interaction")
    xs = [med[j] for j in range(3)]
    ys = [r.params[f"SG{j}"] for j in range(3)]
    es = [1.96 * r.bse[f"SG{j}"] for j in range(3)]
    ax.errorbar(xs, ys, yerr=es, fmt="o", color=pc.INK, markersize=4, capsize=3, linewidth=1.0,
                label="Binning estimator, GE terciles")
    ax.axhline(0, color=pc.INK2, linewidth=0.8)
    ax.yaxis.grid(True, color=pc.GRID, linewidth=0.8)
    pc._style(ax)
    ax.set_xlabel("Government effectiveness (WGI)", fontsize=8.5, color=pc.INK2)
    ax.set_ylabel("Marginal association of the\nsubnational share with ln PM2.5", fontsize=8.5, color=pc.INK2)
    ax.plot(s["GE"], np.full(len(s), ax.get_ylim()[0]), "|", color=pc.INK2, alpha=0.15, markersize=5)
    ax.legend(fontsize=7.5, frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=600)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def equal_weights(x, pc, ge):
    need = pc.BASE_NEEDED + ["SUB"]
    rows = []
    for sname, s in samples(x, pc).items():
        r, d = fit(pc.BASE, s, need, weights="country")
        rows.append(row(sname, "Equal weight for each country", r, d, ge))
    return pd.DataFrame(rows)


def coverage(x, pc):
    s = pc._sample(x)
    out = {"main_sample": {"N": len(s), "countries": int(s["ISO"].nunique())}}
    for v in GROUPS["all"]:
        ok = s[v].notna()
        out[v] = {"N": int(ok.sum()), "countries": int(s.loc[ok, "ISO"].nunique()),
                  "years": [int(s.loc[ok, "YEAR"].min()), int(s.loc[ok, "YEAR"].max())] if ok.any() else None}
    ok = s[GROUPS["all"]].notna().all(axis=1)
    out["all"] = {"N": int(ok.sum()), "countries": int(s.loc[ok, "ISO"].nunique())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    ap.add_argument("--anthro", required=True)
    ap.add_argument("--dl", required=True)
    ap.add_argument("--gbdmaps", required=True)
    ap.add_argument("--ceds-bcoc", dest="ceds_bcoc", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--coverage", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pc = load_module(Path(a.main), "pc")
    anthro = load_module(Path(a.anthro), "anthro")
    p = pc.build_panel()
    ge = pc.ge_reference(p)["LMIC"]
    a.ge = ge
    x = add_controls(p, a, pc, anthro)
    if a.coverage:
        print(json.dumps(coverage(x, pc), indent=1))
        return
    t1 = table_controls(x, pc, ge)
    t1.to_csv(out / "r3c_source_controls.csv", index=False)
    t2 = burnt_sensitivity(x, pc, ge, a)
    t2.to_csv(out / "r3c_burnt_area.csv", index=False)
    t3 = ceds_outcomes(x, pc, a)
    t3.to_csv(out / "r3c_ceds_exploratory.csv", index=False)
    tb, wald, fitobj = binning(x, pc, ge)
    tb.to_csv(out / "r3c_binning.csv", index=False)
    fig_binning(fitobj, out / "r3c_fig1_binning.png", pc)
    t4 = equal_weights(x, pc, ge)
    t4.to_csv(out / "r3c_equal_weights.csv", index=False)
    res = {"ge_reference_LMIC": ge, "coverage": coverage(x, pc), "binning_wald": wald}
    (out / "r3c_results.json").write_text(json.dumps(res, indent=1), encoding="utf8")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    for name, t in (("SOURCE CONTROLS", t1), ("BURNT AREA", t2), ("CEDS EXPLORATORY", t3), ("BINNING", tb),
                    ("EQUAL WEIGHTS", t4)):
        print("\n" + name)
        print(t.to_string(index=False))
    print("\n", json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
