"""
Replication of the environmental-spending study (manuscript under review; the reference will be added on
publication).

Uses the harmonised COFOG 05 panel produced by COFOG-Panel (via the replication in replication/harmonisation, which
calls cofog_panel.resolve_value / is_complete) and World Bank WDI / WGI indicators.
The main sample codes the subnational share as missing for coverage gaps, the countries whose COFOG data cover
central government alone for all ten functions in every year (see build_panel and env_samples.py);
gaps_as_zero() gives the construction with these zeros (108 countries).
The specificity tests also read total outlays by subsector from the IMF extract and harmonise
them with the same functions.

Replication script for the environmental-spending study. Run from the repository root, after the
harmonisation replication (which writes replication/harmonisation/output/harmonised_all_divisions.csv):
    python replication/harmonisation/evaluate_harmonisation.py
    python replication/environment/env_federalism.py
Outputs: replication/environment/output/*.csv, *.json, *.png, *.pdf
Every number quoted in the text of the article is written to the tables or to sample_composition.json.
"""
import hashlib
import json
import sys
import warnings
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_samples import NO_SUBNATIONAL_GOVERNMENT  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXT = HERE / "data_ext"
OUT = HERE / "output"
OUT.mkdir(parents=True, exist_ok=True)
HARMONISED = REPO / "replication" / "harmonisation" / "output" / "harmonised_all_divisions.csv"
LOOKUP = REPO / "data" / "country_codes.xlsx"
RAW = REPO / "data" / "gfs_raw_data.xlsx"
# SHA-256 of the extract used in the article (IMF.STA:GFS_COFOG 11.0.0, published 3 February 2026)
RAW_SHA256 = "91e3db1bdb838f322dcbe648b133f511f3efe1921e50c8bc0d7621f512668cfe"

GG, CGSS = "general government", "central government including social security"
CGXSS = "central government excluding social security"
BCG, EBCG, SSF = "budgetary central government", "extrabudgetary central government", "social security funds"
SG, LG = "state government", "local government"
SECTORS = [GG, CGSS, CGXSS, BCG, EBCG, SSF, SG, LG]

WDI = {
    "EN.ATM.PM25.MC.M3": "PM25", "NY.GDP.PCAP.PP.KD": "GDPPC",
    "NV.IND.TOTL.ZS": "IND", "SP.URB.TOTL.IN.ZS": "URB", "NE.TRD.GNFS.ZS": "TRADE",
    "EN.POP.DNST": "DENS", "NY.GDP.TOTL.RT.ZS": "RENTS",
}
WGI = {"GOV_WGI_GE.EST": "GE", "GOV_WGI_CC.EST": "CC"}
CONTROLS = "lnY + lnY2 + IND + URB + TRADE + lnDENS"
TIER_COLORS = {"T1": "#2a78d6", "T2": "#eb6834", "T3": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
WIDTH_IN = 119 / 25.4  # artwork: 119 mm wide, sans-serif lettering


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------

def _wb(path: Path, name: str) -> pd.DataFrame:
    rows = json.loads(path.read_text(encoding="utf8"))[1]
    return pd.DataFrame([{"ISO": r["countryiso3code"], "YEAR": int(r["date"]), name: r["value"]}
                         for r in rows if r["value"] is not None and r["countryiso3code"]])


def load_covariates() -> pd.DataFrame:
    d = None
    for code, name in WDI.items():
        x = _wb(EXT / f"wb_{code}.json", name)
        d = x if d is None else d.merge(x, on=["ISO", "YEAR"], how="outer")
    for code, name in WGI.items():
        d = d.merge(_wb(EXT / f"wgi_{code}.json", name), on=["ISO", "YEAR"], how="left")
    # WGI is biennial before 2002: interpolate inside each country's observed range
    d = d.sort_values(["ISO", "YEAR"])
    for c in WGI.values():
        d[c] = d.groupby("ISO")[c].transform(lambda s: s.interpolate(limit_area="inside"))
    return d


def build_panel() -> pd.DataFrame:
    h = pd.read_csv(HARMONISED, dtype={"DIV": str})
    e = h[h["DIV"] == "05"].copy()

    # Subnational share of environmental spending, from complete values only (see subnational_share)
    e["SUBSHARE"] = subnational_share(e)
    # Countries that report neither state nor local government for COFOG 05 in any year: their share is
    # zero by construction (only central government reports), not a measured zero
    e["NOSUB"] = (~(e["EVER_SG"].astype(bool) | e["EVER_LG"].astype(bool))).astype(int)
    # Coverage gaps: countries whose COFOG data cover central government alone for all ten functions in every
    # year, except countries without subnational government (env_samples.NO_SUBNATIONAL_GOVERNMENT). Their
    # zero reflects what the data cover, so the main construction codes their share as missing. SUBSHARE0 keeps
    # the construction with these zeros (coverage gaps coded as zero), used for one robustness row.
    other = h[h["DIV"] != "05"].groupby("ISO")[["EVER_SG", "EVER_LG"]].any().any(axis=1)
    ever_other = e["ISO"].map(other).fillna(False).astype(bool)
    e["COVGAP"] = ((e["NOSUB"] == 1) & ~ever_other & ~e["ISO"].isin(list(NO_SUBNATIONAL_GOVERNMENT))).astype(int)
    e["SUBSHARE0"] = e["SUBSHARE"]
    e.loc[e["COVGAP"] == 1, "SUBSHARE"] = np.nan
    # Whether the country reports a general government value for COFOG 05 in any year of its series
    e["EVER_GG"] = e.groupby("ISO")[GG].transform(lambda x: x.notna().any()).astype(int)
    e = e.rename(columns={"VALUE": "ENV"})[["ISO", "YEAR", "ENV", "TIER", "COMPLETE", "SUBSHARE", "SUBSHARE0",
                                            "NOSUB", "COVGAP", "EVER_GG"]]

    # Spending enters with a one-year lag
    e = e.sort_values(["ISO", "YEAR"])
    lag = e.copy()
    lag["YEAR"] = lag["YEAR"] + 1
    lag = lag.rename(columns={"ENV": "ENV_L1", "TIER": "TIER_L1", "COMPLETE": "COMPLETE_L1",
                              "SUBSHARE": "SUBSHARE_L1", "SUBSHARE0": "SUBSHARE0_L1"})
    e = e.drop(columns=["NOSUB", "COVGAP", "EVER_GG", "SUBSHARE0"])

    cov = load_covariates()
    p = cov.merge(lag, on=["ISO", "YEAR"], how="inner").merge(e, on=["ISO", "YEAR"], how="left")
    ge_lag = cov[["ISO", "YEAR", "GE"]].assign(YEAR=cov["YEAR"] + 1).rename(columns={"GE": "GE_L1"})
    p = p.merge(ge_lag, on=["ISO", "YEAR"], how="left")
    lk = pd.read_excel(LOOKUP)[["alpha-3", "region", "sub-region"]].rename(
        columns={"alpha-3": "ISO", "region": "REGION", "sub-region": "SUBREGION"})
    p = p.merge(lk, on="ISO", how="left")

    p = p[(p["ENV_L1"] > 0) & p["YEAR"].between(1996, 2023)].copy()
    p["lnENV"] = np.log(p["ENV_L1"])
    p["SUB"] = p["SUBSHARE_L1"]
    p["SUB0"] = p["SUBSHARE0_L1"]
    p["lnPM"] = np.log(p["PM25"])
    p["lnY"] = np.log(p["GDPPC"])
    p["lnY2"] = p["lnY"] ** 2
    p["lnDENS"] = np.log(p["DENS"])
    p["T2"] = (p["TIER_L1"] == "T2").astype(int)
    p["T3"] = (p["TIER_L1"] == "T3").astype(int)
    p["COMPLETE_L1"] = p["COMPLETE_L1"] == True
    return p


# ----------------------------------------------------------------------------
# Estimation helpers
# ----------------------------------------------------------------------------

def _fit(formula: str, data: pd.DataFrame, needed: list):
    d = data.dropna(subset=needed).copy()
    r = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d["ISO"])[0]})
    return r, d


def _row(name, r, d, keys):
    out = {"Model": name, "N": int(r.nobs), "Countries": d["ISO"].nunique(), "R2": round(r.rsquared, 3)}
    for k in keys:
        if k in r.params:
            out[k] = round(r.params[k], 3)
            out[f"se_{k}"] = round(r.bse[k], 3)
            out[f"p_{k}"] = round(r.pvalues[k], 3)
    return out


BASE_NEEDED = ["lnPM", "lnENV", "lnY", "IND", "URB", "TRADE", "lnDENS", "GE", "SUBREGION"]
BASE = f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)"


def _sample(p: pd.DataFrame) -> pd.DataFrame:
    """Main estimation sample (Table 2, column 3): coverage gaps are missing."""
    return p[p["COMPLETE_L1"]].dropna(subset=BASE_NEEDED + ["SUB"])


def gaps_as_zero(p: pd.DataFrame) -> pd.DataFrame:
    """The panel with coverage gaps coded as zero (the construction with 108 countries): SUB takes the value of
    SUB0, the share before coverage gaps are set to missing."""
    return p.assign(SUB=p["SUB0"])


def income_groups() -> dict:
    """Current World Bank income classification, from the country metadata file."""
    rows = json.loads((EXT / "wb_countries.json").read_text(encoding="utf8"))[1]
    return {r["id"]: r["incomeLevel"]["value"] for r in rows if r.get("incomeLevel")}


def ge_reference(p: pd.DataFrame) -> dict:
    """Median GE by income group (country-year observations) in the panel with coverage gaps coded as zero, so
    that the reference point is the same for the main sample and for the construction with 108 countries."""
    s = _sample(gaps_as_zero(p)).copy()
    s["INC"] = s["ISO"].map(income_groups())
    lmic = ["Low income", "Lower middle income", "Upper middle income"]
    return {"LMIC": round(float(s.loc[s["INC"].isin(lmic), "GE"].median()), 3),
            "UMIC": round(float(s.loc[s["INC"] == "Upper middle income", "GE"].median()), 3),
            "HIC": round(float(s.loc[s["INC"] == "High income", "GE"].median()), 3)}


def effect_25pp(r, ge: float, p_digits: int | None = 3) -> tuple:
    """Percent change in PM2.5 for a subnational share 25 points higher at a given GE, with its p-value
    (rounded to p_digits, or unrounded with p_digits=None)."""
    from scipy import stats
    b, V = r.params, r.cov_params()
    m = b["SUB"] + b["SUB:GE"] * ge
    se = np.sqrt(V.loc["SUB", "SUB"] + ge ** 2 * V.loc["SUB:GE", "SUB:GE"] + 2 * ge * V.loc["SUB", "SUB:GE"])
    p = float(2 * stats.norm.sf(abs(m / se)))
    return round(100 * (np.exp(0.25 * m) - 1), 1), (p if p_digits is None else round(p, p_digits))


def sample_composition(p: pd.DataFrame, fits: dict) -> dict:
    """Which countries the harmonised panel adds, and where they lie relative to the GE threshold."""
    s = _sample(p)
    gg = s[s["TIER_L1"] == "T1"]
    r, _ = fits["(3) + SUB x GE"]
    threshold = -r.params["SUB"] / r.params["SUB:GE"]
    ge_all = s.groupby("ISO")["GE"].mean()
    ge_gg = gg.groupby("ISO")["GE"].mean()
    added = sorted(set(s["ISO"]) - set(gg["ISO"]))
    return {"countries": int(s["ISO"].nunique()), "countries_gg_only_sample": int(gg["ISO"].nunique()),
            "countries_added": len(added), "added_iso": added,
            "countries_mean_ge_below_0_harmonised": int((ge_all < 0).sum()),
            "countries_mean_ge_below_0_gg_only": int((ge_gg < 0).sum()),
            "countries_added_mean_ge_below_0": int((ge_all[added] < 0).sum()),
            "ge_threshold": round(float(threshold), 3),
            "share_obs_below_threshold": round(float((s["GE"] < threshold).mean()), 3),
            "countries_mean_ge_below_threshold": int((ge_all < threshold).sum())}


def table_main(p: pd.DataFrame) -> tuple:
    """Decentralisation of environmental spending and its interaction with government effectiveness."""
    s = p[p["COMPLETE_L1"]]
    need = BASE_NEEDED + ["SUB"]
    specs = [
        ("(1) Controls only", f"lnPM ~ lnENV + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)", BASE_NEEDED),
        ("(2) + decentralisation", f"lnPM ~ lnENV + SUB + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)", need),
        ("(3) + SUB x GE", f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)", need),
    ]
    rows, fits = [], {}
    for name, f, nd in specs:
        r, d = _fit(f, s, nd)
        rows.append(_row(name, r, d, ["lnENV", "SUB", "SUB:GE", "GE"]))
        fits[name] = (r, d)
    return pd.DataFrame(rows), fits


def table_mundlak(p: pd.DataFrame) -> pd.DataFrame:
    """Correlated random effects: within- and between-country components."""
    s = _sample(p).copy()
    for v in ["lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]:
        s[f"{v}_m"] = s.groupby("ISO")[v].transform("mean")
        s[f"{v}_w"] = s[v] - s[f"{v}_m"]
    s["SUBGE_w"] = s["SUB_w"] * s["GE_m"]
    s["SUBGE_m"] = s["SUB_m"] * s["GE_m"]
    f = ("lnPM ~ lnENV_w + lnENV_m + SUB_w + SUB_m + SUBGE_w + SUBGE_m + GE_w + GE_m"
         " + lnY_w + lnY_m + lnY2_w + lnY2_m + IND_w + IND_m + URB_w + URB_m + TRADE_w + TRADE_m"
         " + lnDENS_w + lnDENS_m + C(YEAR) + C(SUBREGION)")
    r, d = _fit(f, s, ["lnPM"])
    rows = []
    for v, lab in [("lnENV", "ln env. spending"), ("SUB", "Subnational share"),
                   ("SUBGE", "Subnational share x GE"), ("GE", "Government effectiveness")]:
        rows.append({"Variable": lab,
                     "Within": round(r.params[f"{v}_w"], 3), "se_within": round(r.bse[f"{v}_w"], 3),
                     "p_within": round(r.pvalues[f"{v}_w"], 3),
                     "Between": round(r.params[f"{v}_m"], 3), "se_between": round(r.bse[f"{v}_m"], 3),
                     "p_between": round(r.pvalues[f"{v}_m"], 3)})
    t = pd.DataFrame(rows)
    t.attrs["N"], t.attrs["Countries"] = int(r.nobs), d["ISO"].nunique()
    t.attrs["tests"] = mundlak_tests(r, d, ge_reference(p)["LMIC"])
    # Two-way fixed effects for reference
    r2, d2 = _fit(f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CONTROLS} + C(YEAR) + C(ISO)", p[p["COMPLETE_L1"]],
                  BASE_NEEDED + ["SUB"])
    t.attrs["TWFE"] = _row("Two-way FE", r2, d2, ["lnENV", "SUB", "SUB:GE", "GE"])
    return t


def mundlak_tests(r, d: pd.DataFrame, ge_ref: float) -> dict:
    """
    Wald tests of equal within- and between-country coefficients of the share in Table 3, with the clustered
    covariance of the table (written to tabC3_mundlak_tests.json). Both interactions multiply a component of the share
    by the country mean of GE (SUBGE_w = SUB_w x GE_m, SUBGE_m = SUB_m x GE_m), so each pair is comparable: the within
    and between slopes of the share at country-mean GE are SUB_w + SUBGE_w x GE_m and SUB_m + SUBGE_m x GE_m. p uses
    the normal and chi-squared distributions, like the p-values of the table, and p_G-1 the t and F distributions with
    G - 1 denominator degrees of freedom (G countries). The *_ci95 entries give [estimate, lower, upper] of the within
    and between slopes at GE = 0 (the share coefficients of the table) and at the reference GE.
    """
    from scipy import stats
    names, G = list(r.params.index), d["ISO"].nunique()

    def wald(*rows):
        R = np.zeros((len(rows), len(names)))
        for i, w in enumerate(rows):
            for k, v in w.items():
                R[i, names.index(k)] = v
        res = r.wald_test(R, scalar=True)
        chi2, q = float(res.statistic), len(rows)
        return {"chi2": round(chi2, 2), "df": q, "p": round(float(res.pvalue), 3),
                "p_G-1": round(float(stats.f.sf(chi2 / q, q, G - 1)), 3)}

    share, inter = {"SUB_w": 1, "SUB_m": -1}, {"SUBGE_w": 1, "SUBGE_m": -1}
    at_ref = {"SUB_w": 1, "SUBGE_w": ge_ref, "SUB_m": -1, "SUBGE_m": -ge_ref}
    out = {"share_within_equals_between": {**_contrast(r, share), **wald(share)},
           "interaction_within_equals_between": {**_contrast(r, inter), **wald(inter)},
           "joint_share_and_interaction": wald(share, inter),
           "ge_ref": ge_ref,
           "slope_at_ge_ref_within_equals_between": {**_contrast(r, at_ref), **wald(at_ref)}}
    z, b, V = stats.norm.ppf(0.975), r.params, r.cov_params()
    for lab, g in [("share_coefficient_ci95", 0.0), ("slope_at_ge_ref_ci95", ge_ref)]:
        est = {}
        for c in ("w", "m"):
            x, xg = f"SUB_{c}", f"SUBGE_{c}"
            m = b[x] + g * b[xg]
            se = np.sqrt(V.loc[x, x] + g ** 2 * V.loc[xg, xg] + 2 * g * V.loc[x, xg])
            est[c] = [m, m - z * se, m + z * se]
        out[lab] = {"within": [round(float(v), 3) for v in est["w"]],
                    "between": [round(float(v), 3) for v in est["m"]],
                    "within_upper_over_between": round(float(est["w"][2] / est["m"][0]), 2),
                    "effect_25pp_pct_within": [round(float(100 * (np.exp(0.25 * v) - 1)), 1) for v in est["w"]],
                    "effect_25pp_pct_between": [round(float(100 * (np.exp(0.25 * v) - 1)), 1) for v in est["m"]]}
    return out


def table_robustness(p: pd.DataFrame, ge_ref: float) -> pd.DataFrame:
    """Variations of Table 2, column 3, with the marginal association at the reference GE in every row."""
    base = BASE
    need = BASE_NEEDED + ["SUB"]
    s = p[p["COMPLETE_L1"]]
    dust = ["Northern Africa", "Western Asia"]
    rows = []
    # GE averaged over each country's first three sample years
    s0 = s.dropna(subset=need).sort_values(["ISO", "YEAR"])
    s0 = s0.assign(GE=s0.groupby("ISO")["GE"].transform(lambda x: x.iloc[:3].mean()), GE_NOW=s0["GE"])
    start = base.replace(" + GE + ", " + GE_NOW + ")
    for name, data, f in [
        ("Baseline", s, base),
        ("GG values only (T1)", s[s["TIER_L1"] == "T1"], base),
        ("GE lagged one year", s.assign(GE=s["GE_L1"]), base),
        ("GE at start of period in the interaction", s0, start),
        ("Excl. Northern Africa & Western Asia (dust)", s[~s["SUBREGION"].isin(dust)], base),
        ("Excl. Europe", s[s["REGION"] != "Europe"], base),
        ("Control of corruption instead of GE", s.assign(GE=s["CC"]), base),
        ("Adds natural resource rents", s, base.replace(CONTROLS, CONTROLS + " + RENTS")),
        ("Region instead of sub-region FE", s, base.replace("C(SUBREGION)", "C(REGION)")),
        ("Region FE and region-specific GE slopes", s,
         f"lnPM ~ lnENV + SUB + SUB:GE + GE*C(REGION) + {CONTROLS} + C(YEAR) + C(REGION)"),
        ("No subnational data: own intercept and GE slope", s,
         base.replace(" + GE + ", " + GE + NOSUB + NOSUB:GE + ")),
        ("Excl. countries without subnational data", s[s["NOSUB"] == 0], base),
    ]:
        nd = need + (["RENTS"] if "RENTS" in f else [])
        try:
            r, d = _fit(f, data, nd)
            row = _row(name, r, d, ["SUB", "SUB:GE"])
            row["ME25_LMIC"], row["p_ME25_LMIC"] = effect_25pp(r, ge_ref)
            rows.append(row)
        except Exception as ex:  # noqa: BLE001
            rows.append({"Model": name, "error": str(ex)})
    # Five-year averages (reduces short-run noise and serial correlation)
    s5 = s.dropna(subset=need).copy()
    s5["PERIOD"] = (s5["YEAR"] // 5) * 5
    num = ["lnPM", "lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]
    a = s5.groupby(["ISO", "PERIOD", "SUBREGION"], as_index=False)[num].mean()
    r = smf.ols(f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CONTROLS} + C(PERIOD) + C(SUBREGION)", data=a).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(a["ISO"])[0]})
    row = _row("Five-year averages", r, a, ["SUB", "SUB:GE"])
    row["ME25_LMIC"], row["p_ME25_LMIC"] = effect_25pp(r, ge_ref)
    rows.append(row)
    return pd.DataFrame(rows)


def table_leave_one_out(p: pd.DataFrame, ge_ref: float) -> pd.DataFrame:
    """Baseline re-estimated with one UN sub-region left out at a time (sub-regions in the sample only)."""
    s = p[p["COMPLETE_L1"]]
    rows = []
    for sr in sorted(_sample(p)["SUBREGION"].unique()):
        r, d = _fit(BASE, s[s["SUBREGION"] != sr], BASE_NEEDED + ["SUB"])
        row = _row(f"Excl. {sr}", r, d, ["SUB", "SUB:GE"])
        row["ME25_LMIC"], row["p_ME25_LMIC"] = effect_25pp(r, ge_ref)
        rows.append(row)
    return pd.DataFrame(rows)


def income_interaction(p: pd.DataFrame) -> dict:
    """Baseline plus the interaction of the share with ln GDP per capita."""
    r, d = _fit(BASE.replace(" + GE + ", " + GE + SUB:lnY + "), p[p["COMPLETE_L1"]], BASE_NEEDED + ["SUB"])
    return {k: [round(r.params[k], 3), round(r.bse[k], 3), round(r.pvalues[k], 3)] for k in ("SUB:GE", "SUB:lnY")}


def wild_bootstrap_subregion(p: pd.DataFrame, B: int = 1999, seed: int = 20261101) -> dict:
    """Wild cluster bootstrap-t (Webb weights, null imposed) for SUB x GE, clusters = UN sub-regions."""
    s = _sample(p).reset_index(drop=True)
    cl = pd.factorize(s["SUBREGION"])[0]
    ru = smf.ols(BASE, data=s).fit(cov_type="cluster", cov_kwds={"groups": cl})
    rr = smf.ols(BASE.replace(" + SUB:GE", ""), data=s).fit()
    X, j = ru.model.exog, ru.model.exog_names.index("SUB:GE")
    n, k = X.shape
    G = cl.max() + 1
    XtXi = np.linalg.pinv(X.T @ X)
    c = G / (G - 1) * (n - 1) / (n - k)
    webb = np.array([-np.sqrt(1.5), -1, -np.sqrt(0.5), np.sqrt(0.5), 1, np.sqrt(1.5)])
    rng = np.random.default_rng(seed)
    t0 = ru.params["SUB:GE"] / ru.bse["SUB:GE"]
    yhat, uhat = rr.fittedvalues.values, rr.resid.values
    ts = np.empty(B)
    for b in range(B):
        yb = yhat + uhat * rng.choice(webb, G)[cl]
        beta = XtXi @ (X.T @ yb)
        e = yb - X @ beta
        score = np.zeros((G, k))
        np.add.at(score, cl, X * e[:, None])
        V = c * XtXi @ (score.T @ score) @ XtXi
        ts[b] = beta[j] / np.sqrt(V[j, j])
    return {"clusters": int(G), "replications": B, "t": round(float(t0), 2),
            "p_wild": round(float(np.mean(np.abs(ts) >= abs(t0))), 3)}


def subnational_share(e: pd.DataFrame) -> pd.Series:
    """(SG + LG) / (central + SG + LG) for complete values; central = CGSS, else CGXSS + SSF, else
    BCG + EBCG + SSF.

    A subnational level (SG or LG) that the country reports for the function in some year but not in this
    year makes the share missing for this year: the level exists, so counting it as zero would understate
    the share. A level the country never reports adds zero."""
    sub = e[[SG, LG]].fillna(0).sum(axis=1)
    central = e[CGSS].fillna(e[[CGXSS, SSF]].sum(axis=1, min_count=1).where(e[CGXSS].notna()))
    central = central.fillna(e[[BCG, EBCG, SSF]].sum(axis=1, min_count=1))
    share = sub / (sub + central)
    gap = (e["EVER_SG"].astype(bool) & e[SG].isna()) | (e["EVER_LG"].astype(bool) & e[LG].isna())
    share[(central.isna()) | ((sub + central) <= 0) | (e["COMPLETE"] != True) | gap] = np.nan
    return share.clip(0, 1)


@lru_cache(maxsize=1)
def _read_extract() -> pd.DataFrame:
    """Percent-of-GDP rows of the IMF extract, with ISO code, series code and sector name (read once per run)."""
    digest = hashlib.sha256(RAW.read_bytes()).hexdigest()
    if digest != RAW_SHA256:
        print(f"WARNING: {RAW.name} differs from the extract used in the article (SHA-256 {digest[:12]}..., "
              f"expected {RAW_SHA256[:12]}...).")
    sys.path.insert(0, str(REPO))
    from cofog_panel.aggregate import IMF_TO_ISO
    raw = pd.read_excel(RAW)
    raw = raw[raw["TYPE_OF_TRANSFORMATION"] == "Percent of GDP"].copy()
    parts = raw["SERIES_CODE"].str.split(".", expand=True)
    raw["ISO"] = parts[0].str.upper().replace(IMF_TO_ISO)
    raw["CODE"] = parts[3]
    raw["SECTOR_NORM"] = raw["SECTOR"].str.lower().str.strip()
    return raw


def _wide(raw: pd.DataFrame, code: str) -> pd.DataFrame:
    """One row per (ISO, YEAR), one column per sector, for one series code."""
    ycols = [c for c in raw.columns if str(c).isdigit() and 1990 <= int(c) <= 2024]
    x = raw[raw["CODE"] == code]
    long = x.melt(id_vars=["ISO", "SECTOR_NORM"], value_vars=ycols, var_name="YEAR",
                  value_name="VALUE").dropna(subset=["VALUE"])
    long["YEAR"] = long["YEAR"].astype(int)
    w = long.pivot_table(index=["ISO", "YEAR"], columns="SECTOR_NORM", values="VALUE", aggfunc="first")
    for s in SECTORS:
        if s not in w.columns:
            w[s] = np.nan
    return w[SECTORS]


def _harmonise(w: pd.DataFrame) -> pd.DataFrame:
    """Selected value, tier and completeness flag from cofog_panel.resolve_value / is_complete."""
    sys.path.insert(0, str(REPO))
    from decimal import Decimal
    from cofog_panel.aggregate import resolve_value, is_complete, COVERAGE_LEVELS
    ever = {s: w[s].groupby(level="ISO").transform(lambda x: x.notna().any()) for s in COVERAGE_LEVELS}
    recs = []
    for i, row in enumerate(w.itertuples(index=False)):
        vals = {s: (None if pd.isna(v) else Decimal(repr(float(v)))) for s, v in zip(SECTORS, row)}
        levels = [s for s in COVERAGE_LEVELS if ever[s].iat[i]]
        v, tier, used = resolve_value(vals)
        recs.append((None if v is None else float(v), tier, is_complete(tier, used, levels, vals)))
    h = pd.DataFrame(recs, columns=["VALUE", "TIER", "COMPLETE"], index=w.index).join(w)
    h["EVER_SG"], h["EVER_LG"] = ever[SG], ever[LG]
    return h


def harmonised_total() -> pd.DataFrame:
    """
    Total outlays by subsector (IMF code TOTOUT_T, percent of GDP) with the COFOG-Panel selection rule and
    completeness flag, plus the transfers of a general character between levels of government (GF0180_T)
    reported by each subsector. Cached next to the outputs; the cache is rebuilt when the extract is newer.
    """
    cache = OUT / "_harmonised_total.csv"
    if cache.exists() and cache.stat().st_mtime > RAW.stat().st_mtime:
        return pd.read_csv(cache)
    raw = _read_extract()
    h = _harmonise(_wide(raw, "TOTOUT_T"))
    gt = _wide(raw, "GF0180_T").add_prefix("GT ")
    h = h.join(gt, how="left").reset_index()
    h.to_csv(cache, index=False)
    return h


# COFOG groups of environmental protection: 05.1 waste management ... 05.6 environmental protection n.e.c.
GROUP_CODES = {"0510": "Waste management", "0520": "Waste water management", "0530": "Pollution abatement",
               "0540": "Protection of biodiversity and landscape", "0550": "R&D environmental protection",
               "0560": "Environmental protection n.e.c."}


def harmonised_groups() -> pd.DataFrame:
    """The six COFOG groups of environmental protection by subsector, harmonised like total outlays (cached)."""
    cache = OUT / "_harmonised_groups.csv"
    if cache.exists() and cache.stat().st_mtime > RAW.stat().st_mtime:
        return pd.read_csv(cache, dtype={"GROUP": str})
    raw = _read_extract()
    h = pd.concat([_harmonise(_wide(raw, f"GF{g}_T")).reset_index().assign(GROUP=g) for g in GROUP_CODES],
                  ignore_index=True)
    h.to_csv(cache, index=False)
    return h


def add_other_shares(p: pd.DataFrame) -> pd.DataFrame:
    """
    Lagged subnational shares of total outlays (as reported, and net of transfers of a general character
    between levels of government) and of two other functions (08 recreation, culture and religion, 09 education).
    """
    t = harmonised_total()
    out = t[["ISO", "YEAR"]].copy()
    out["SUBTOT"] = subnational_share(t)
    net = t.copy()
    for s in SECTORS:
        net[s] = t[s] - t[f"GT {s}"].fillna(0)
    out["SUBTOTN"] = subnational_share(net)
    h = pd.read_csv(HARMONISED, dtype={"DIV": str})
    for div in ("08", "09"):
        e = h[h["DIV"] == div]
        out = out.merge(e[["ISO", "YEAR"]].assign(**{f"SUB{div}": subnational_share(e).values}),
                        on=["ISO", "YEAR"], how="outer")
    out["YEAR"] = out["YEAR"] + 1
    q = p.merge(out, on=["ISO", "YEAR"], how="left")
    # Coverage gaps cover central government alone for every function, so their function shares are missing too
    q.loc[q["COVGAP"] == 1, ["SUB08", "SUB09"]] = np.nan
    return q


def effect_25pp_of(r, ge: float, v: str) -> tuple:
    """As effect_25pp, for the share v and its interaction v:GE."""
    from scipy import stats
    b, V = r.params, r.cov_params()
    m = b[v] + b[f"{v}:GE"] * ge
    se = np.sqrt(V.loc[v, v] + ge ** 2 * V.loc[f"{v}:GE", f"{v}:GE"] + 2 * ge * V.loc[v, f"{v}:GE"])
    return round(100 * (np.exp(0.25 * m) - 1), 1), round(float(2 * stats.norm.sf(abs(m / se))), 3)


def table_specificity(px: pd.DataFrame, ge_ref: float) -> pd.DataFrame:
    """Environmental decentralisation against decentralisation of total outlays and of other functions."""
    s = px[px["COMPLETE_L1"]]
    need = BASE_NEEDED + ["SUB"]
    fx = f"{CONTROLS} + C(YEAR) + C(SUBREGION)"
    rows = []
    for name, nd, f in [
        ("Baseline, sample with share of total outlays", need + ["SUBTOT"], BASE),
        ("Adds share of total outlays", need + ["SUBTOT"],
         f"lnPM ~ lnENV + SUB + SUB:GE + GE + SUBTOT + {fx}"),
        ("Adds share of total outlays and its interaction with GE", need + ["SUBTOT"],
         f"lnPM ~ lnENV + SUB + SUB:GE + GE + SUBTOT + SUBTOT:GE + {fx}"),
        ("Share of total outlays in place of SUB", need + ["SUBTOT"],
         f"lnPM ~ lnENV + SUBTOT + SUBTOT:GE + GE + {fx}"),
        ("Adds share of total outlays net of general transfers, with interaction", need + ["SUBTOTN"],
         f"lnPM ~ lnENV + SUB + SUB:GE + GE + SUBTOTN + SUBTOTN:GE + {fx}"),
        ("Share of recreation, culture and religion (08) in place of SUB", BASE_NEEDED + ["SUB08"],
         f"lnPM ~ lnENV + SUB08 + SUB08:GE + GE + {fx}"),
        ("Share of education (09) in place of SUB", BASE_NEEDED + ["SUB09"],
         f"lnPM ~ lnENV + SUB09 + SUB09:GE + GE + {fx}"),
        ("Adds share of education (09) and its interaction with GE", need + ["SUB09"],
         f"lnPM ~ lnENV + SUB + SUB:GE + GE + SUB09 + SUB09:GE + {fx}"),
        ("Adds share of recreation, culture and religion (08) and its interaction with GE", need + ["SUB08"],
         f"lnPM ~ lnENV + SUB + SUB:GE + GE + SUB08 + SUB08:GE + {fx}"),
    ]:
        r, d = _fit(f, s, nd)
        keys = ["SUB", "SUB:GE", "SUBTOT", "SUBTOT:GE", "SUBTOTN", "SUBTOTN:GE", "SUB08", "SUB08:GE",
                "SUB09", "SUB09:GE"]
        row = _row(name, r, d, keys)
        for v in ("SUB", "SUBTOT", "SUBTOTN", "SUB08", "SUB09"):
            if f"{v}:GE" in r.params:
                row[f"ME25_{v}"], row[f"p_ME25_{v}"] = effect_25pp_of(r, ge_ref, v)
        rows.append(row)
    return pd.DataFrame(rows)


def table_predetermined(p: pd.DataFrame, ge_ref: float) -> pd.DataFrame:
    """The share averaged over each country's first three sample years, in place of the current share."""
    need = BASE_NEEDED + ["SUB"]
    s0 = p[p["COMPLETE_L1"]].dropna(subset=need).sort_values(["ISO", "YEAR"])
    s0 = s0.assign(SUB=s0.groupby("ISO")["SUB"].transform(lambda x: x.iloc[:3].mean()),
                   K=s0.groupby("ISO").cumcount())
    rows = []
    for name, data in [("Share at start of period", s0),
                       ("Share at start of period, later years only", s0[s0["K"] >= 3])]:
        r, d = _fit(BASE, data, need)
        row = _row(name, r, d, ["SUB", "SUB:GE"])
        row["ME25_LMIC"], row["p_ME25_LMIC"] = effect_25pp(r, ge_ref)
        rows.append(row)
    return pd.DataFrame(rows)


def _oster(y: np.ndarray, x: np.ndarray, W: np.ndarray, M: np.ndarray, rmax_mult: float = 1.3) -> dict:
    """
    Oster (2019) coefficient stability for the coefficient on x. M holds the regressors included in both the
    short and the long regression (partialled out first), W the observed controls added in the long one.
    Returns the short and long coefficients and R-squared, delta for beta = 0 and beta at delta = 1.
    """
    def res(a, B):
        return a - B @ np.linalg.lstsq(B, a, rcond=None)[0]
    yr, xr = res(y, M), res(x, M)
    Wr = np.column_stack([res(W[:, j], M) for j in range(W.shape[1])])
    sst = yr @ yr
    b_o = (xr @ yr) / (xr @ xr)
    r_o = 1 - ((yr - b_o * xr) @ (yr - b_o * xr)) / sst
    XL = np.column_stack([xr, Wr])
    coef = np.linalg.lstsq(XL, yr, rcond=None)[0]
    b_t = coef[0]
    r_t = 1 - ((yr - XL @ coef) @ (yr - XL @ coef)) / sst
    rmax = min(1.0, rmax_mult * r_t)
    n = len(y)
    s_yy, s_xx = sst / n, (xr @ xr) / n
    ex = res(xr, Wr)
    t_x = (ex @ ex) / n
    A, B, D = (r_t - r_o) * s_yy, (rmax - r_t) * s_yy, b_o - b_t

    def delta(beta):
        b = b_t - beta
        num = b * A * t_x + b * s_xx * t_x * D ** 2 + 2 * b ** 2 * t_x * D * s_xx + b ** 3 * (t_x * s_xx - t_x ** 2)
        den = B * D * s_xx + b * B * (s_xx - t_x) + b ** 2 * t_x * D * s_xx + b ** 3 * (t_x * s_xx - t_x ** 2)
        return num / den
    # delta = 1: the cubic terms cancel and b = beta_tilde - beta solves a quadratic
    roots = np.roots([t_x * D * s_xx, A * t_x + s_xx * t_x * D ** 2 - B * (s_xx - t_x), -B * D * s_xx])
    roots = roots[np.isreal(roots)].real
    b_star = b_t - roots[np.argmin(np.abs(roots))] if len(roots) else np.nan
    return {"beta_short": round(float(b_o), 3), "R2_short": round(float(r_o), 3),
            "beta_long": round(float(b_t), 3), "R2_long": round(float(r_t), 3), "R2_max": round(float(rmax), 3),
            "delta_for_beta_0": round(float(delta(0.0)), 2),
            "delta_approx": round(float(b_t * (r_t - r_o) / (D * (rmax - r_t))), 2) if D * (rmax - r_t) else None,
            "beta_at_delta_1": round(float(b_star), 3)}


def table_oster(p: pd.DataFrame, ge_ref: float) -> pd.DataFrame:
    """
    Coefficient stability (Oster 2019) for the marginal association at the reference GE and for the interaction.
    The short regression holds the terms of the interaction model and year effects. The long regression adds
    ln environmental spending, the controls and, in the first variant, sub-region effects. In the second variant
    sub-region effects are in both regressions, so the comparison is within sub-regions.
    """
    import patsy
    s = _sample(p).copy()
    s["SUBGE"] = s["SUB"] * s["GE"]
    s["SUBGEc"] = s["SUB"] * (s["GE"] - ge_ref)
    y = s["lnPM"].to_numpy()
    rows = []
    for target, x_col, other in [(f"Marginal association at GE = {ge_ref}", "SUB", "SUBGEc"),
                                 ("Interaction SUB x GE", "SUBGE", "SUB")]:
        for variant, sr_in_both in [("Sub-region effects among added controls", False),
                                    ("Sub-region effects in both regressions", True)]:
            m_terms = f"{other} + GE + C(YEAR)" + (" + C(SUBREGION)" if sr_in_both else "")
            w_terms = f"lnENV + {CONTROLS}" + ("" if sr_in_both else " + C(SUBREGION)") + " - 1"
            M = np.asarray(patsy.dmatrix(m_terms, s))
            W = np.asarray(patsy.dmatrix(w_terms, s))
            out = {"Target": target, "Variant": variant, "N": len(s)}
            out.update(_oster(y, s[x_col].to_numpy(), W, M))
            rows.append(out)
    return pd.DataFrame(rows)


def other_numbers(px: pd.DataFrame, comp: dict) -> dict:
    """Correlation of the environmental share with the share of total outlays, and reporting of the
    countries without subnational data for environmental protection."""
    s = _sample(px)
    c = s.dropna(subset=["SUBTOT"])
    m = c.groupby("ISO")[["SUB", "SUBTOT"]].mean()
    nosub = comp["coverage_panel"]["central_only_iso"]  # the central-only countries of the panel with gaps
    t = harmonised_total()
    tot_ever = t.groupby("ISO")[["EVER_SG", "EVER_LG"]].any().any(axis=1)
    h = pd.read_csv(HARMONISED, dtype={"DIV": str}, usecols=["ISO", "DIV", "EVER_SG", "EVER_LG"])
    div_ever = h[h["DIV"] != "05"].groupby("ISO")[["EVER_SG", "EVER_LG"]].any().any(axis=1)
    with_tot = sorted(i for i in nosub if bool(tot_ever.get(i, False)))
    with_div = sorted(i for i in nosub if bool(div_ever.get(i, False)))
    return {"corr_sub_subtot_obs": round(float(c["SUB"].corr(c["SUBTOT"])), 3),
            "corr_sub_subtot_country_means": round(float(m["SUB"].corr(m["SUBTOT"])), 3),
            "obs_with_subtot": len(c), "countries_with_subtot": int(c["ISO"].nunique()),
            "nosub_countries": len(nosub),
            "nosub_with_subnational_total_outlays": len(with_tot), "nosub_with_subnational_total_iso": with_tot,
            "nosub_with_subnational_other_function": len(with_div), "nosub_with_subnational_other_iso": with_div}


# Federal countries: the country chapters (chapters 2-27) of Griffiths et al. (2020), The Forum of Federations
# Handbook of Federal Countries 2020, https://doi.org/10.1007/978-3-030-42088-8, without the European Union and
# without Cyprus, a unitary state whose chapter ("Seeking a federal solution") covers proposals for a federation.
FEDERAL = ["ARG", "AUS", "AUT", "BEL", "BIH", "BRA", "CAN", "COM", "ETH", "DEU", "IND", "MYS", "MEX",
           "FSM", "NPL", "NGA", "PAK", "RUS", "KNA", "ZAF", "ESP", "CHE", "ARE", "USA"]


def add_area_federal(p: pd.DataFrame) -> pd.DataFrame:
    """ln land area (country mean of WDI AG.LND.TOTL.K2) and an indicator for federal countries."""
    a = _wb(EXT / "wb_AG.LND.TOTL.K2.json", "AREA").groupby("ISO")["AREA"].mean()
    return p.assign(lnAREA=np.log(p["ISO"].map(a)), FED=p["ISO"].isin(FEDERAL).astype(int))


def table_size_federal(p: pd.DataFrame, ge_ref: float) -> pd.DataFrame:
    """Country size and federal structure, which the subnational share might proxy for."""
    pa = add_area_federal(p)
    s = pa[pa["COMPLETE_L1"]]
    need = BASE_NEEDED + ["SUB"]
    rows = []
    for name, data, f, nd in [
        ("Adds ln land area", s, BASE.replace(CONTROLS, CONTROLS + " + lnAREA"), need + ["lnAREA"]),
        ("Adds federal country indicator", s, BASE.replace(CONTROLS, CONTROLS + " + FED"), need),
        ("Adds ln land area, federal indicator and its interaction with GE", s,
         BASE.replace(CONTROLS, CONTROLS + " + lnAREA + FED + FED:GE"), need + ["lnAREA"]),
        ("Excl. federal countries", s[s["FED"] == 0], BASE, need),
    ]:
        r, d = _fit(f, data, nd)
        row = _row(name, r, d, ["SUB", "SUB:GE"])
        row["ME25_LMIC"], row["p_ME25_LMIC"] = effect_25pp(r, ge_ref)
        rows.append(row)
    return pd.DataFrame(rows)


def federal_numbers(p: pd.DataFrame) -> dict:
    s = add_area_federal(_sample(p))
    fed = sorted(s.loc[s["FED"] == 1, "ISO"].unique())
    return {"federal_countries_in_sample": len(fed), "federal_iso_in_sample": fed,
            "federal_obs_in_sample": int(s["FED"].sum()),
            "corr_sub_lnarea_country_means": round(float(s.groupby("ISO")[["SUB", "lnAREA"]].mean().corr().iloc[0, 1]), 3)}


# Post-socialist countries (note to Table 5 of the paper): the successor states of the Soviet Union and of Yugoslavia,
# Albania, Bulgaria, Czechia, Hungary, Poland, Romania, Slovakia and Mongolia, as in ext_r5z.py
POST_SOCIALIST = ["ARM", "AZE", "BLR", "EST", "GEO", "KAZ", "KGZ", "LVA", "LTU", "MDA", "RUS", "TJK", "TKM",
                  "UKR", "UZB", "ALB", "BGR", "CZE", "HUN", "POL", "ROU", "SVK", "SVN", "HRV", "BIH", "SRB",
                  "MNE", "MKD", "XKX", "MNG"]


def fig_binned_by_ge(p: pd.DataFrame, path: Path) -> dict:
    """
    Fig. 2 of the paper: country means of ln PM2.5 net of the controls, ln environmental spending, GE, year and
    sub-region effects, against the country mean of the subnational share, by tercile of country-mean GE.
    Triangles: post-socialist countries. Open circles: countries without subnational data. Solid line: OLS fit
    across the countries of the tercile. Dashed line: the same fit without the post-socialist countries.
    """
    from matplotlib.lines import Line2D
    plt = _plt()
    s = _sample(p).copy()
    r = smf.ols(f"lnPM ~ lnENV + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)", data=s).fit()
    s["RES"] = r.resid
    c = s.groupby("ISO").agg(SUB=("SUB", "mean"), RES=("RES", "mean"), GE=("GE", "mean"), NOSUB=("NOSUB", "max"))
    c["T"] = pd.qcut(c["GE"], 3, labels=False)
    c["PS"] = c.index.isin(POST_SOCIALIST)
    fig, axes = plt.subplots(1, 3, figsize=(WIDTH_IN, 3.35), sharey=True)
    out = {}

    def minus(v):
        return f"{v:.2f}".replace("-", "−")

    xs = np.array([0, 1])
    for t, ax in enumerate(axes):
        g = c[c["T"] == t]
        other = g[~g["PS"] & (g["NOSUB"] == 0)]
        ax.scatter(other["SUB"], other["RES"], s=13, color=TIER_COLORS["T1"], alpha=0.55, linewidth=0)
        ax.scatter(g.loc[g["PS"], "SUB"], g.loc[g["PS"], "RES"], s=17, marker="^", color=INK, linewidth=0)
        ax.scatter(g.loc[g["NOSUB"] == 1, "SUB"], g.loc[g["NOSUB"] == 1, "RES"], s=13, facecolor="none",
                   edgecolor=INK2, linewidth=0.7)
        fit = np.polyfit(g["SUB"], g["RES"], 1)
        h = g[g["NOSUB"] == 0]
        fit_h = np.polyfit(h["SUB"], h["RES"], 1)
        q = g[~g["PS"]]
        fit_q = np.polyfit(q["SUB"], q["RES"], 1)
        ax.plot(xs, fit[1] + fit[0] * xs, color=INK2, linewidth=1.2)
        ax.plot(xs, fit_q[1] + fit_q[0] * xs, color=INK, linewidth=0.9, linestyle=(0, (3, 2)))
        ax.axhline(0, color=GRID, linewidth=0.8, zorder=0)
        lo, hi = g["GE"].min(), g["GE"].max()
        ax.set_title(f"{['Lowest', 'Middle', 'Highest'][t]} third of GE\n({minus(lo)} to {minus(hi)})",
                     fontsize=8, color=INK2)
        ax.text(0.03, 0.98, f"Slope {minus(fit[0])}\n{minus(fit_q[0])} without ▲\n{minus(fit_h[0])} without ○",
                transform=ax.transAxes, fontsize=8, color=INK2, va="top", ha="left", linespacing=1.15)
        ax.set_xlim(-0.06, 1.06)
        ax.set_xticks([0, 0.5, 1], ["0", "0.5", "1"])
        _style(ax)
        out[f"tercile_{t + 1}"] = {"ge_range": [round(float(lo), 2), round(float(hi), 2)], "countries": len(g),
                                   "countries_without_subnational_data": int(g["NOSUB"].sum()),
                                   "slope": round(float(fit[0]), 3),
                                   "slope_without_those_countries": round(float(fit_h[0]), 3),
                                   "post_socialist_countries": int(g["PS"].sum()),
                                   "slope_without_post_socialist": round(float(fit_q[0]), 3)}
    axes[0].set_ylim(-0.52, 0.98)
    axes[0].set_ylabel("ln PM2.5, net of controls\nand sub-region effects", fontsize=8, color=INK2)
    fig.subplots_adjust(left=0.135, right=0.985, top=0.855, bottom=0.315, wspace=0.12)
    fig.text(0.56, 0.215, "Subnational share of environmental spending, country mean", fontsize=8, color=INK2,
             ha="center", va="center")
    handles = [Line2D([], [], marker="^", linestyle="", markersize=4.5, color=INK),
               Line2D([], [], marker="o", linestyle="", markersize=4, color=TIER_COLORS["T1"], alpha=0.55,
                      markeredgewidth=0),
               Line2D([], [], marker="o", linestyle="", markersize=4, markerfacecolor="none", markeredgecolor=INK2),
               Line2D([], [], color=INK2, linewidth=1.2),
               Line2D([], [], color=INK, linewidth=0.9, linestyle=(0, (3, 2)))]
    fig.legend(handles, ["Post-socialist country", "Other country", "Central-only country", "Fit, all countries",
                         "Fit without post-socialist countries"], loc="lower center", bbox_to_anchor=(0.56, 0),
               ncol=2, frameon=False, fontsize=8, handlelength=2.2, columnspacing=2.0, handletextpad=0.5,
               labelspacing=0.3)
    _save(fig, path)
    plt.close(fig)
    return out


# Economies in transition: Table B of the country classification in United Nations (2024), World Economic Situation
# and Prospects 2024, statistical annex, p. 135 (South-Eastern Europe; Commonwealth of Independent States and Georgia)
# https://www.un.org/development/desa/dpad/wp-content/uploads/sites/45/WESP_2024_Web.pdf
TRANSITION = ["ALB", "BIH", "MNE", "MKD", "SRB", "ARM", "AZE", "BLR", "GEO", "KAZ", "KGZ", "MDA", "RUS", "TJK",
              "TKM", "UKR", "UZB"]


def table_transition(p: pd.DataFrame, ge_ref: float) -> tuple:
    """Economies in transition left out, or given their own intercept and slope of the subnational share."""
    s = p[p["COMPLETE_L1"]].assign(TRANS=lambda d: d["ISO"].isin(TRANSITION).astype(int))
    need = BASE_NEEDED + ["SUB"]
    rows, extra = [], {}
    for name, data, f in [
        ("Excl. economies in transition", s[s["TRANS"] == 0], BASE),
        ("Economies in transition: own intercept and SUB slope", s,
         BASE.replace(" + GE + ", " + GE + TRANS + SUB:TRANS + ")),
    ]:
        r, d = _fit(f, data, need)
        row = _row(name, r, d, ["SUB", "SUB:GE"])
        row["ME25_LMIC"], row["p_ME25_LMIC"] = effect_25pp(r, ge_ref)
        rows.append(row)
        if "SUB:TRANS" in r.params:
            extra["sub_x_transition"] = [round(r.params["SUB:TRANS"], 3), round(r.bse["SUB:TRANS"], 3),
                                         round(r.pvalues["SUB:TRANS"], 3)]
    m = _sample(p)
    tr = m[m["ISO"].isin(TRANSITION)]
    extra.update({"transition_countries_in_sample": int(tr["ISO"].nunique()),
                  "transition_iso_in_sample": sorted(tr["ISO"].unique()), "transition_obs_in_sample": len(tr),
                  "transition_mean_ge": round(float(tr.groupby("ISO")["GE"].mean().mean()), 2)})
    return pd.DataFrame(rows), extra


def _contrast(r, weights: dict) -> dict:
    """Linear combination of coefficients (name: weight) with its clustered standard error and p-value."""
    R = np.zeros(len(r.params))
    names = list(r.params.index)
    for k, w in weights.items():
        R[names.index(k)] = w
    t = r.t_test(R)
    return {"difference": round(float(t.effect[0]), 3), "se": round(float(t.sd[0][0]), 3),
            "p": round(float(t.pvalue), 3)}


def further_tests(p: pd.DataFrame, px: pd.DataFrame, ge_ref: dict) -> dict:
    """Wald tests of equal interactions, the control-of-corruption row at its own reference value and magnitudes."""
    from scipy import stats
    out = {}
    s = px[px["COMPLETE_L1"]]
    fx = f"{CONTROLS} + C(YEAR) + C(SUBREGION)"
    for v, lab in [("SUB08", "recreation_culture_religion"), ("SUB09", "education"), ("SUBTOT", "total_outlays")]:
        r, _ = _fit(f"lnPM ~ lnENV + SUB + SUB:GE + GE + {v} + {v}:GE + {fx}", s, BASE_NEEDED + ["SUB", v])
        g = ge_ref["LMIC"]
        out[f"wald_SUBxGE_equals_{lab}xGE"] = _contrast(r, {"SUB:GE": 1, f"{v}:GE": -1})
        out[f"wald_SUB_equals_{lab}"] = _contrast(r, {"SUB": 1, v: -1})
        out[f"wald_marginal_at_ge_ref_SUB_equals_{lab}"] = _contrast(r, {"SUB": 1, "SUB:GE": g, v: -1, f"{v}:GE": -g})
    # Control of corruption in place of GE, evaluated at the median CC of low- and middle-income countries in the
    # panel with coverage gaps coded as zero, the same population as the GE reference point (ge_reference)
    m = _sample(p).copy()
    m["INC"] = m["ISO"].map(income_groups())
    lmic = ["Low income", "Lower middle income", "Upper middle income"]
    m0 = _sample(gaps_as_zero(p))
    cc_ref = round(float(m0.loc[m0["ISO"].map(income_groups()).isin(lmic), "CC"].median()), 3)
    q = p[p["COMPLETE_L1"]]
    r, _ = _fit(BASE, q.assign(GE=q["CC"]), BASE_NEEDED + ["SUB"])
    out["cc_median_lmic"] = cc_ref
    out["cc_row_effect_25pp_at_cc_median_lmic"] = effect_25pp(r, cc_ref)
    # Magnitudes in micrograms per cubic metre at the baseline estimate
    r3, _ = _fit(BASE, q, BASE_NEEDED + ["SUB"])
    b, V = r3.params, r3.cov_params()
    g = ge_ref["LMIC"]
    me = b["SUB"] + b["SUB:GE"] * g
    se = np.sqrt(V.loc["SUB", "SUB"] + g ** 2 * V.loc["SUB:GE", "SUB:GE"] + 2 * g * V.loc["SUB", "SUB:GE"])
    lo, hi = me - stats.norm.ppf(0.975) * se, me + stats.norm.ppf(0.975) * se
    pct = {k: float(np.exp(0.25 * x) - 1) for k, x in [("point", me), ("lo", lo), ("hi", hi)]}
    pm_all = float(m["PM25"].mean())
    pm_lmic = float(m.loc[m["INC"].isin(lmic), "PM25"].mean())
    out["effect_25pp_pct_ci95"] = [round(100 * pct["point"], 1), round(100 * pct["lo"], 1), round(100 * pct["hi"], 1)]
    out["pm25_mean_sample"] = round(pm_all, 2)
    out["pm25_mean_lmic_obs"] = round(pm_lmic, 2)
    out["lmic_obs"] = int(m["INC"].isin(lmic).sum())
    out["lmic_countries"] = int(m.loc[m["INC"].isin(lmic), "ISO"].nunique())
    out["effect_25pp_ugm3_at_sample_mean"] = [round(pct[k] * pm_all, 3) for k in ("point", "lo", "hi")]
    out["effect_25pp_ugm3_at_lmic_mean"] = [round(pct[k] * pm_lmic, 3) for k in ("point", "lo", "hi")]
    return out


def table_cofog_groups(p: pd.DataFrame, ge_ref: float) -> tuple:
    """
    Subnational shares of single COFOG groups of environmental protection (05.1 waste management, 05.3 pollution
    abatement), computed like the share of the division, in place of SUB in the specification of Table 2, column 3.
    """
    h = harmonised_groups()
    cover = {}
    rows = []
    m = _sample(p)
    for g in ("0510", "0530"):
        e = h[h["GROUP"] == g]
        sh = e[["ISO", "YEAR"]].assign(SUBG=subnational_share(e).values)
        sh["YEAR"] = sh["YEAR"] + 1
        q = p.merge(sh, on=["ISO", "YEAR"], how="left")
        # Coverage gaps cover central government alone for every function, so their group shares are missing too.
        # Both rows of a group use the observations with both the division share and the group share.
        q.loc[q["COVGAP"] == 1, "SUBG"] = np.nan
        q = q[q["COMPLETE_L1"] & q["SUBG"].notna() & q["SUB"].notna()]
        r, d = _fit(BASE, q, BASE_NEEDED + ["SUB"])
        row = _row(f"Baseline, sample with share of 05.{g[2]}", r, d, ["SUB", "SUB:GE"])
        row["ME25_LMIC"], row["p_ME25_LMIC"] = effect_25pp(r, ge_ref)
        rows.append(row)
        q = q.assign(SUB=lambda d: d["SUBG"])
        r, d = _fit(BASE, q, BASE_NEEDED + ["SUB"])
        row = _row(f"Share of {GROUP_CODES[g].lower()} (05.{g[2]}) in place of SUB", r, d, ["SUB", "SUB:GE"])
        row["ME25_LMIC"], row["p_ME25_LMIC"] = effect_25pp(r, ge_ref)
        rows.append(row)
        mm = m.merge(sh, on=["ISO", "YEAR"], how="left")
        mm.loc[mm["COVGAP"] == 1, "SUBG"] = np.nan
        cover[f"group_05{g[2]}"] = {"obs_in_main_sample_with_share": int(mm["SUBG"].notna().sum()),
                                   "countries_in_main_sample_with_share": int(mm.loc[mm["SUBG"].notna(), "ISO"].nunique()),
                                   "corr_with_division_share": round(float(mm["SUB"].corr(mm["SUBG"])), 3)}
    # Reporting of the six groups in the extract: countries with any value, by group
    cover["countries_reporting_group"] = {g: int(h.loc[(h["GROUP"] == g) & h["VALUE"].notna(), "ISO"].nunique())
                                          for g in GROUP_CODES}
    return pd.DataFrame(rows), cover


def text_numbers(p: pd.DataFrame, comp: dict) -> dict:
    """Numbers quoted in the text that are not in a table."""
    s = _sample(p)
    added = comp["added_iso"]
    ge = s.groupby("ISO")["GE"].mean()
    rng = s.groupby("ISO")["SUB"].agg(lambda x: x.max() - x.min())
    nosub = sorted(s.loc[s["NOSUB"] == 1, "ISO"].unique())
    cty = s.drop_duplicates("ISO").set_index("ISO")
    added_no_gg = [c for c in added if cty.loc[c, "EVER_GG"] == 0]
    h = pd.read_csv(HARMONISED, dtype={"DIV": str}, usecols=["ISO", "DIV", GG])
    h = h[h["DIV"] == "05"]
    # Sustained versus transitory changes in the share within countries
    s = s.sort_values(["ISO", "YEAR"]).copy()
    g = s.groupby("ISO")["SUB"]
    sustained = (g.apply(lambda x: x.iloc[-3:].mean()) - g.apply(lambda x: x.iloc[:3].mean())).abs()
    s["d"] = g.diff()
    s["d1"], s["d2"] = s.groupby("ISO")["d"].shift(-1), s.groupby("ISO")["d"].shift(-2)
    j = s[s["d"].abs() > 0.2]
    rev = [((np.sign(j[c]) == -np.sign(j["d"])) & (j[c].abs() > 0.1)) for c in ("d1", "d2")]
    return {"countries_with_gg_value_05": int(h.loc[h[GG].notna(), "ISO"].nunique()),
            "subregions_in_sample": int(s["SUBREGION"].nunique()),
            "mean_sub_by_region": s.groupby("REGION")["SUB"].mean().round(2).to_dict(),
            "countries_sub_range_above_0.2": int((rng > 0.2).sum()),
            "countries_sub_first3_last3_change_above_0.2": int((sustained > 0.2).sum()),
            "yearly_changes_above_0.2": len(j), "countries_with_such_changes": int(j["ISO"].nunique()),
            "such_changes_reversed_within_2_years": int((rev[0] | rev[1]).sum()),
            "added_by_region": s[s["ISO"].isin(added)].groupby("REGION")["ISO"].nunique().to_dict(),
            "added_without_any_gg_value": len(added_no_gg),
            "added_without_any_gg_by_region": cty.loc[added_no_gg].groupby("REGION").size().to_dict(),
            "added_with_gg_outside_sample": sorted(set(added) - set(added_no_gg)),
            "added_mean_ge_below_threshold": int((ge[added] < comp["ge_threshold"]).sum()),
            "countries_without_subnational_data": len(nosub),
            "obs_without_subnational_data": int(s["NOSUB"].sum()),
            "without_subnational_data_by_region": cty.loc[nosub].groupby("REGION").size().to_dict(),
            "added_without_subnational_data": len(set(nosub) & set(added)),
            "iso_without_subnational_data": nosub}


def coverage_numbers(p: pd.DataFrame) -> dict:
    """The harmonised panel with coverage gaps coded as zero (108 countries) and the countries that the main
    sample codes as missing."""
    s0 = _sample(gaps_as_zero(p))
    s = _sample(p)
    gg0 = s0[s0["TIER_L1"] == "T1"]
    ge0 = s0.groupby("ISO")["GE"].mean()
    ge_gg0 = gg0.groupby("ISO")["GE"].mean()
    added0 = sorted(set(s0["ISO"]) - set(gg0["ISO"]))
    cty = s0.groupby("ISO").agg(NOSUB=("NOSUB", "max"), COVGAP=("COVGAP", "max"))
    gaps = sorted(cty.index[cty["COVGAP"] == 1])
    nosub = sorted(cty.index[cty["NOSUB"] == 1])
    neg = set(ge0.index[ge0 < 0])
    return {"countries": int(s0["ISO"].nunique()), "obs": len(s0),
            "countries_gg_values": int(gg0["ISO"].nunique()), "countries_added": len(added0),
            "countries_mean_ge_below_0": len(neg), "countries_mean_ge_below_0_gg_only": int((ge_gg0 < 0).sum()),
            "countries_added_mean_ge_below_0": len(neg & set(added0)),
            "central_only": len(nosub), "central_only_iso": nosub,
            "central_only_among_added": len(set(nosub) & set(added0)),
            "coverage_gaps": len(gaps), "coverage_gaps_iso": gaps, "coverage_gap_obs": int(s0["COVGAP"].sum()),
            "coverage_gaps_among_added": len(set(gaps) & set(added0)),
            "coverage_gaps_with_gg_value": sorted(set(gaps) - set(added0)),
            "coverage_gaps_mean_ge_below_0": len(set(gaps) & neg),
            "added_mean_ge_below_0_coverage_gaps": len(set(gaps) & neg & set(added0)),
            "central_only_kept_iso": sorted(set(nosub) - set(gaps)),
            "main_sample_countries": int(s["ISO"].nunique()), "main_sample_obs": len(s),
            "main_sample_countries_mean_ge_below_0": int((s.groupby("ISO")["GE"].mean() < 0).sum())}


def table_descriptives(p: pd.DataFrame) -> pd.DataFrame:
    s = _sample(p)
    cols = {"PM25": "PM2.5 exposure (µg/m³)", "ENV_L1": "Env. spending (% GDP, t-1)",
            "SUB": "Subnational share of env. spending", "GE": "Government effectiveness",
            "GDPPC": "GDP per capita (PPP, 2021 $)", "IND": "Industry (% GDP)", "URB": "Urban population (%)",
            "TRADE": "Trade (% GDP)", "DENS": "Population density"}
    rows = [{"Variable": lab, "Mean": round(s[c].mean(), 3), "SD": round(s[c].std(), 3),
             "Min": round(s[c].min(), 3), "Max": round(s[c].max(), 3)} for c, lab in cols.items()]
    t = pd.DataFrame(rows)
    t.attrs["N"], t.attrs["Countries"] = len(s), s["ISO"].nunique()
    t.attrs["tiers"] = s["TIER_L1"].value_counts().to_dict()
    t.attrs["years"] = (int(s["YEAR"].min()), int(s["YEAR"].max()))
    return t


# ----------------------------------------------------------------------------
# Figures (artwork: no title inside the figure, 119 mm wide, Arial 8-8.5 pt)
# ----------------------------------------------------------------------------

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": ["Arial", "DejaVu Sans"], "pdf.fonttype": 42,
                         "ps.fonttype": 42, "axes.unicode_minus": True})
    return plt


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.set_axisbelow(True)


def _save(fig, path: Path):
    # vector graphics, or bitmaps of at least 600 dpi
    fig.savefig(path, dpi=600)
    fig.savefig(path.with_suffix(".pdf"))


def fig_marginal(fits: dict, path: Path, ge_ref: float):
    """Percent change in PM2.5 for a share 25 pp higher, with its 95% band, over the observed range of GE."""
    plt = _plt()
    r, d = fits["(3) + SUB x GE"]
    ge = np.linspace(d["GE"].quantile(0.02), d["GE"].quantile(0.98), 60)
    b, V = r.params, r.cov_params()

    def pct25(g):  # ln points of a move of the share from 0 to 1, converted to % for 25 pp
        me = b["SUB"] + b["SUB:GE"] * g
        se = np.sqrt(V.loc["SUB", "SUB"] + g ** 2 * V.loc["SUB:GE", "SUB:GE"] + 2 * g * V.loc["SUB", "SUB:GE"])
        return [100 * (np.exp(0.25 * x) - 1) for x in (me, me - 1.96 * se, me + 1.96 * se)]

    est, lo, hi = pct25(ge)
    e0, lo0, hi0 = (float(x) for x in pct25(ge_ref))
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.9))
    ax.fill_between(ge, lo, hi, color=TIER_COLORS["T1"], alpha=0.18, linewidth=0)
    ax.plot(ge, est, color=TIER_COLORS["T1"], linewidth=1.8)
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.axvline(ge_ref, color=INK2, linewidth=0.8, linestyle=":")
    ax.plot([ge_ref, ge_ref], [lo0, hi0], color=INK, linewidth=1.0)
    ax.plot(ge_ref, e0, "o", color=INK, markersize=3.5)
    ax.text(ge_ref + 0.07, 18.2, f"{e0:.1f}% (95% CI {lo0:.1f}% to {hi0:.1f}%) at GE = "
            f"{ge_ref:.3f}".replace("-", "−") + ",\nmedian of low- and middle-income countries",
            fontsize=8, color=INK2, va="center", ha="left")
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    _style(ax)
    ax.set_xlabel("Government effectiveness (WGI)", fontsize=8.5, color=INK2)
    ax.set_ylabel("% change in PM2.5 exposure for a\nsubnational share 25 pp higher", fontsize=8.5, color=INK2)
    # rug of observed GE values
    ax.plot(d["GE"], np.full(len(d), ax.get_ylim()[0]), "|", color=INK2, alpha=0.15, markersize=5)
    fig.tight_layout()
    _save(fig, path)
    plt.close(fig)


def fig_ge_by_source(p: pd.DataFrame, comp: dict, path: Path):
    """Country-mean government effectiveness, for countries with and without a GG value in the estimation sample."""
    plt = _plt()
    s = _sample(gaps_as_zero(p))  # the harmonised panel, coverage gaps included
    ge = s.groupby("ISO")["GE"].mean()
    gap = s.groupby("ISO")["COVGAP"].max() == 1
    added = set(ge.index) - set(s.loc[s["TIER_L1"] == "T1", "ISO"])
    groups = [("No GG value in sample", ge[ge.index.isin(added)], TIER_COLORS["T3"]),
              ("GG value in sample", ge[~ge.index.isin(added)], TIER_COLORS["T1"])]
    rng = np.random.default_rng(0)
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.4))
    for i, (_, x, col) in enumerate(groups):
        y = i + rng.uniform(-0.18, 0.18, len(x))
        g = gap[x.index].to_numpy()
        ax.scatter(x[~g], y[~g], s=12, color=col, alpha=0.85, edgecolor="white", linewidth=0.4)
        ax.scatter(x[g], y[g], s=12, facecolor="none", edgecolor=col, linewidth=0.8)
    ax.axvline(comp["ge_threshold"], color=INK2, linewidth=0.8, linestyle="--")
    ax.text(comp["ge_threshold"] - 0.05, 1.5, "Marginal association of the\nsubnational share changes sign",
            fontsize=8, color=INK2, va="center", ha="right")
    ax.set_yticks([0, 1], [f"{lab}\n(n={len(x)})" for lab, x, _ in groups], fontsize=8)
    ax.set_ylim(-0.5, 1.75)
    ax.set_xlabel("Government effectiveness (WGI), country mean", fontsize=8.5, color=INK2)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    _style(ax)
    fig.tight_layout()
    _save(fig, path)
    plt.close(fig)


# ----------------------------------------------------------------------------

def main():
    p = build_panel()
    p.to_csv(OUT / "paperC_panel.csv", index=False)

    t_desc = table_descriptives(p)
    t_main, fits = table_main(p)
    comp = sample_composition(p, fits)
    t_mund = table_mundlak(p)
    ge_ref = ge_reference(p)
    r3, _ = fits["(3) + SUB x GE"]
    comp["ge_median_by_income"] = ge_ref
    comp["effect_25pp_baseline"] = {f"GE={g}": effect_25pp(r3, g) for g in
                                    [0.0, ge_ref["UMIC"], ge_ref["LMIC"], ge_ref["HIC"], 1.5]}
    # Range of GE over which the 95% band of the marginal association excludes zero
    grid = np.round(np.arange(-1.6, 2.31, 0.01), 2)
    sig = [g for g in grid if effect_25pp(r3, g, p_digits=None)[1] < 0.05]
    comp["me_significant_ge_range"] = [float(min(sig)), float(max(sig))] if sig else None
    comp["share_obs_in_significant_range"] = (round(float((_sample(p)["GE"] <= max(sig)).mean()), 3)
                                              if sig else None)
    t_rob = table_robustness(p, ge_ref["LMIC"])
    t_loo = table_leave_one_out(p, ge_ref["LMIC"])
    comp["income_interaction"] = income_interaction(p)
    comp["wild_bootstrap_subregion"] = wild_bootstrap_subregion(p)
    comp["text_numbers"] = text_numbers(p, comp)
    comp["coverage_panel"] = coverage_numbers(p)
    # Predetermined share (appended to Table 4), specificity tests and coefficient stability
    t_rob = pd.concat([t_rob, table_predetermined(p, ge_ref["LMIC"]), table_size_federal(p, ge_ref["LMIC"])],
                      ignore_index=True)
    px = add_other_shares(p)
    t_spec = table_specificity(px, ge_ref["LMIC"])
    t_oster = table_oster(p, ge_ref["LMIC"])
    extra = other_numbers(px, comp)
    extra.update(federal_numbers(p))
    # Economies in transition (appended to Table 4), COFOG groups, equality tests and magnitudes
    t_tr, further = table_transition(p, ge_ref["LMIC"])
    t_rob = pd.concat([t_rob, t_tr], ignore_index=True)
    t_grp, cover = table_cofog_groups(p, ge_ref["LMIC"])
    further.update(cover)
    further.update(further_tests(p, px, ge_ref))

    print(f"Descriptives: N={t_desc.attrs['N']}, countries={t_desc.attrs['Countries']}, "
          f"years={t_desc.attrs['years']}, tiers={t_desc.attrs['tiers']}")
    for name, t in [("tabC1_descriptives", t_desc), ("tabC2_main", t_main), ("tabC3_mundlak", t_mund),
                    ("tabC4_robustness", t_rob), ("tabC4b_leave_one_out", t_loo),
                    ("tabC5_specificity", t_spec), ("tabC6_oster", t_oster), ("tabC7_cofog_groups", t_grp)]:
        t.to_csv(OUT / f"{name}.csv", index=False)
        print(f"\n=== {name} ===")
        print(t.to_string(index=False))
    print(f"\nLeave one sub-region out: SUB x GE in [{t_loo['SUB:GE'].min()}, {t_loo['SUB:GE'].max()}], "
          f"max p = {t_loo['p_SUB:GE'].max()}; 25 pp at reference GE in [{t_loo['ME25_LMIC'].min()}, "
          f"{t_loo['ME25_LMIC'].max()}], max p = {t_loo['p_ME25_LMIC'].max()}")
    print(f"\nMundlak N={t_mund.attrs['N']}, countries={t_mund.attrs['Countries']}")
    print("TWFE:", t_mund.attrs["TWFE"])
    pd.DataFrame([t_mund.attrs["TWFE"]]).to_csv(OUT / "tabC3b_twfe.csv", index=False)
    (OUT / "tabC3_mundlak_tests.json").write_text(json.dumps(t_mund.attrs["tests"], indent=1), encoding="utf8")
    (OUT / "sample_composition.json").write_text(json.dumps(comp, indent=1), encoding="utf8")
    (OUT / "extensions.json").write_text(json.dumps(extra, indent=1), encoding="utf8")
    (OUT / "further_tests.json").write_text(json.dumps(further, indent=1), encoding="utf8")
    print("\nFurther tests:", further)
    print("\nExtensions:", extra)
    print("\nSample composition:", {k: v for k, v in comp.items() if k != "added_iso"})

    fig_marginal(fits, OUT / "figC1_marginal_subshare.png", ge_ref["LMIC"])
    fig_ge_by_source(p, comp, OUT / "figC2_ge_by_source.png")
    # Fig. 2 of the paper (figC2_ge_by_source.png is Fig. S2 of the supplementary material)
    binned = fig_binned_by_ge(p, OUT / "figC3_binned_by_ge.png")
    (OUT / "figC3_binned_by_ge.json").write_text(json.dumps(binned, indent=1), encoding="utf8")


if __name__ == "__main__":
    main()
