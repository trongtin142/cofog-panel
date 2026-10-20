"""
Paper C: environmental protection spending, its decentralisation and air pollution.

Uses the harmonised COFOG 05 panel produced by COFOG-Panel (via paperB_analysis.py, which
calls cofog_panel.resolve_value / is_complete) and World Bank WDI / WGI indicators.

Replication script for the EEPS article. Run from the repository root, after the SJIAOS replication
(which writes replication/sjiaos/output/harmonised_all_divisions.csv):
    python replication/sjiaos/evaluate_harmonisation.py
    python replication/eeps/env_federalism.py
Outputs: analysis/output/paperC/*.csv, *.png
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore", category=RuntimeWarning)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXT = HERE / "data_ext"
OUT = HERE / "output"
OUT.mkdir(parents=True, exist_ok=True)
HARMONISED = REPO / "replication" / "sjiaos" / "output" / "harmonised_all_divisions.csv"
LOOKUP = REPO / "data" / "country_codes.xlsx"

GG, CGSS = "general government", "central government including social security"
CGXSS = "central government excluding social security"
BCG, EBCG, SSF = "budgetary central government", "extrabudgetary central government", "social security funds"
SG, LG = "state government", "local government"

WDI = {
    "EN.ATM.PM25.MC.M3": "PM25", "EN.GHG.CO2.PC.CE.AR5": "CO2PC", "NY.GDP.PCAP.PP.KD": "GDPPC",
    "NV.IND.TOTL.ZS": "IND", "SP.URB.TOTL.IN.ZS": "URB", "NE.TRD.GNFS.ZS": "TRADE",
    "EN.POP.DNST": "DENS", "NY.GDP.TOTL.RT.ZS": "RENTS",
}
WGI = {"GOV_WGI_GE.EST": "GE", "GOV_WGI_CC.EST": "CC"}
CONTROLS = "lnY + lnY2 + IND + URB + TRADE + lnDENS"
TIER_COLORS = {"T1": "#2a78d6", "T2": "#eb6834", "T3": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


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

    # Subnational share of environmental spending, from complete values only:
    # (SG + LG) / (central + SG + LG); central = CGSS, else CGXSS + SSF, else BCG + EBCG + SSF
    sub = e[[SG, LG]].fillna(0).sum(axis=1)
    central = e[CGSS].fillna(e[[CGXSS, SSF]].sum(axis=1, min_count=1).where(e[CGXSS].notna()))
    central = central.fillna(e[[BCG, EBCG, SSF]].sum(axis=1, min_count=1))
    share = sub / (sub + central)
    share[(central.isna()) | ((sub + central) <= 0) | (e["COMPLETE"] != True)] = np.nan
    e["SUBSHARE"] = share.clip(0, 1)
    e = e.rename(columns={"VALUE": "ENV"})[["ISO", "YEAR", "ENV", "TIER", "COMPLETE", "SUBSHARE"]]

    # Spending enters with a one-year lag
    e = e.sort_values(["ISO", "YEAR"])
    lag = e.copy()
    lag["YEAR"] = lag["YEAR"] + 1
    lag = lag.rename(columns={"ENV": "ENV_L1", "TIER": "TIER_L1", "COMPLETE": "COMPLETE_L1",
                              "SUBSHARE": "SUBSHARE_L1"})

    cov = load_covariates()
    p = cov.merge(lag, on=["ISO", "YEAR"], how="inner").merge(e, on=["ISO", "YEAR"], how="left")
    lk = pd.read_excel(LOOKUP)[["alpha-3", "region", "sub-region"]].rename(
        columns={"alpha-3": "ISO", "region": "REGION", "sub-region": "SUBREGION"})
    p = p.merge(lk, on="ISO", how="left")

    p = p[(p["ENV_L1"] > 0) & p["YEAR"].between(1996, 2023)].copy()
    p["lnENV"] = np.log(p["ENV_L1"])
    p["SUB"] = p["SUBSHARE_L1"]
    p["lnPM"] = np.log(p["PM25"])
    p["lnCO2"] = np.log(p["CO2PC"])
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


def table_samples(p: pd.DataFrame) -> pd.DataFrame:
    """The headline coefficient on lnENV under alternative harmonisation choices."""
    f = f"lnPM ~ lnENV + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)"
    rows = []
    for name, s, form in [
        ("GG values only (T1)", p[p["TIER_L1"] == "T1"], f),
        ("Complete values (T1 + complete T2/T3)", p[p["COMPLETE_L1"]], f),
        ("All values (T1-T3)", p, f),
        ("All values + tier dummies", p, f.replace("lnENV + ", "lnENV + T2 + T3 + ")),
        ("Complete values, excl. Europe", p[p["COMPLETE_L1"] & (p["REGION"] != "Europe")], f),
    ]:
        r, d = _fit(form, s, BASE_NEEDED)
        rows.append(_row(name, r, d, ["lnENV", "GE", "T2", "T3"]))
    return pd.DataFrame(rows)


def table_main(p: pd.DataFrame) -> tuple:
    """Spending level, decentralisation and their interaction with governance."""
    s = p[p["COMPLETE_L1"]]
    need = BASE_NEEDED + ["SUB"]
    specs = [
        ("(1) Level", f"lnPM ~ lnENV + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)", BASE_NEEDED),
        ("(2) + decentralisation", f"lnPM ~ lnENV + SUB + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)", need),
        ("(3) + SUB x GE", f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)", need),
        ("(4) + lnENV x GE", f"lnPM ~ lnENV + lnENV:GE + SUB + SUB:GE + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)", need),
        ("(5) CO2 per capita", f"lnCO2 ~ lnENV + SUB + SUB:GE + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)",
         [n for n in need if n != "lnPM"] + ["lnCO2"]),
    ]
    rows, fits = [], {}
    for name, f, nd in specs:
        r, d = _fit(f, s, nd)
        rows.append(_row(name, r, d, ["lnENV", "SUB", "SUB:GE", "lnENV:GE", "GE"]))
        fits[name] = (r, d)
    return pd.DataFrame(rows), fits


def table_mundlak(p: pd.DataFrame) -> pd.DataFrame:
    """Correlated random effects: within- and between-country components."""
    s = p[p["COMPLETE_L1"]].dropna(subset=BASE_NEEDED + ["SUB"]).copy()
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
    # Two-way fixed effects for reference
    r2, d2 = _fit(f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CONTROLS} + C(YEAR) + C(ISO)", p[p["COMPLETE_L1"]],
                  BASE_NEEDED + ["SUB"])
    t.attrs["TWFE"] = _row("Two-way FE", r2, d2, ["lnENV", "SUB", "SUB:GE", "GE"])
    return t


def table_robustness(p: pd.DataFrame) -> pd.DataFrame:
    base = f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CONTROLS} + C(YEAR) + C(SUBREGION)"
    need = BASE_NEEDED + ["SUB"]
    s = p[p["COMPLETE_L1"]]
    dust = ["Northern Africa", "Western Asia"]
    rows = []
    for name, data, f in [
        ("Baseline", s, base),
        ("Excl. Northern Africa & Western Asia (dust)", s[~s["SUBREGION"].isin(dust)], base),
        ("Excl. Europe", s[s["REGION"] != "Europe"], base),
        ("Control of corruption instead of GE", s.assign(GE=s["CC"]), base),
        ("Adds natural resource rents", s, base.replace(CONTROLS, CONTROLS + " + RENTS")),
        ("Region instead of sub-region FE", s, base.replace("C(SUBREGION)", "C(REGION)")),
    ]:
        nd = need + (["RENTS"] if "RENTS" in f else [])
        try:
            r, d = _fit(f, data, nd)
            rows.append(_row(name, r, d, ["lnENV", "SUB", "SUB:GE"]))
        except Exception as ex:  # noqa: BLE001
            rows.append({"Model": name, "error": str(ex)})
    # Five-year averages (reduces short-run noise and serial correlation)
    s5 = s.dropna(subset=need).copy()
    s5["PERIOD"] = (s5["YEAR"] // 5) * 5
    num = ["lnPM", "lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]
    a = s5.groupby(["ISO", "PERIOD", "SUBREGION"], as_index=False)[num].mean()
    r = smf.ols(f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CONTROLS} + C(PERIOD) + C(SUBREGION)", data=a).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(a["ISO"])[0]})
    rows.append(_row("Five-year averages", r, a, ["lnENV", "SUB", "SUB:GE"]))
    return pd.DataFrame(rows)


def table_descriptives(p: pd.DataFrame) -> pd.DataFrame:
    s = p[p["COMPLETE_L1"]].dropna(subset=BASE_NEEDED + ["SUB"])
    cols = {"PM25": "PM2.5 exposure (µg/m³)", "CO2PC": "CO2 per capita (t)", "ENV_L1": "Env. spending (% GDP, t-1)",
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
# Figures
# ----------------------------------------------------------------------------

def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8.5)
    ax.set_axisbelow(True)


def fig_samples(t: pd.DataFrame, path: Path):
    import matplotlib.pyplot as plt
    t = t.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(7, 3.0), dpi=200)
    for i, row in t.iterrows():
        lo, hi = row["lnENV"] - 1.96 * row["se_lnENV"], row["lnENV"] + 1.96 * row["se_lnENV"]
        col = TIER_COLORS["T1"] if row["Model"].startswith("GG") else INK
        ax.plot([lo, hi], [i, i], color=col, linewidth=2, solid_capstyle="round")
        ax.scatter([row["lnENV"]], [i], s=40, color=col, edgecolor="white", linewidth=1.5, zorder=3)
        ax.text(hi + 0.01, i, f"{row['lnENV']:.3f}  (N={row['N']:,}, {row['Countries']} countries)",
                va="center", fontsize=7.5, color=INK2)
    ax.axvline(0, color=INK2, linewidth=0.8)
    ax.set_yticks(range(len(t)), t["Model"], fontsize=8)
    ax.set_xlabel("Coefficient on ln env. spending (t-1), 95% CI", fontsize=8.5, color=INK2)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_xlim(-0.2, 0.42)
    _style(ax)
    ax.set_title("ln PM2.5 exposure: estimate by harmonisation choice", fontsize=9.5, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_marginal(fits: dict, path: Path):
    import matplotlib.pyplot as plt
    r, d = fits["(3) + SUB x GE"]
    ge = np.linspace(d["GE"].quantile(0.02), d["GE"].quantile(0.98), 60)
    b, V = r.params, r.cov_params()
    me = b["SUB"] + b["SUB:GE"] * ge
    se = np.sqrt(V.loc["SUB", "SUB"] + ge ** 2 * V.loc["SUB:GE", "SUB:GE"] + 2 * ge * V.loc["SUB", "SUB:GE"])
    fig, ax = plt.subplots(figsize=(6, 3.4), dpi=200)
    ax.fill_between(ge, me - 1.96 * se, me + 1.96 * se, color=TIER_COLORS["T1"], alpha=0.18, linewidth=0)
    ax.plot(ge, me, color=TIER_COLORS["T1"], linewidth=2)
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    _style(ax)
    ax.set_xlabel("Government effectiveness (WGI)", fontsize=8.5, color=INK2)
    ax.set_ylabel("Effect of subnational share on ln PM2.5", fontsize=8.5, color=INK2)
    ax.set_title("Marginal effect of decentralised environmental spending, 95% CI", fontsize=9.5,
                 color=INK, loc="left")
    # rug of observed GE values
    ax.plot(d["GE"], np.full(len(d), ax.get_ylim()[0]), "|", color=INK2, alpha=0.15, markersize=6)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_between(p: pd.DataFrame, path: Path):
    import matplotlib.pyplot as plt
    s = p[p["COMPLETE_L1"]].dropna(subset=BASE_NEEDED)
    g = s.groupby("ISO").agg(lnENV=("lnENV", "mean"), lnPM=("lnPM", "mean"),
                             share_t1=("TIER_L1", lambda x: (x == "T1").mean())).reset_index()
    fig, ax = plt.subplots(figsize=(5.6, 4.2), dpi=200)
    for lab, mask, col in [("Mostly GG-reported (≥ 50% T1)", g["share_t1"] >= 0.5, TIER_COLORS["T1"]),
                           ("Mostly fallback (< 50% T1)", g["share_t1"] < 0.5, TIER_COLORS["T3"])]:
        x = g[mask]
        ax.scatter(np.exp(x["lnENV"]), np.exp(x["lnPM"]), s=22, color=col, alpha=0.85, edgecolor="white",
                   linewidth=0.6, label=f"{lab}, n={len(x)}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    _style(ax)
    ax.set_xlabel("Env. protection spending, % of GDP (country mean, log scale)", fontsize=8.5, color=INK2)
    ax.set_ylabel("PM2.5 exposure, µg/m³ (country mean, log scale)", fontsize=8.5, color=INK2)
    ax.set_title("Countries by source of their harmonised spending data", fontsize=9.5, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=7.5, loc="lower left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ----------------------------------------------------------------------------

def main():
    p = build_panel()
    p.to_csv(OUT / "paperC_panel.csv", index=False)

    t_desc = table_descriptives(p)
    t_samp = table_samples(p)
    t_main, fits = table_main(p)
    t_mund = table_mundlak(p)
    t_rob = table_robustness(p)

    print(f"Descriptives: N={t_desc.attrs['N']}, countries={t_desc.attrs['Countries']}, "
          f"years={t_desc.attrs['years']}, tiers={t_desc.attrs['tiers']}")
    for name, t in [("tabC1_descriptives", t_desc), ("tabC2_samples", t_samp), ("tabC3_main", t_main),
                    ("tabC4_mundlak", t_mund), ("tabC5_robustness", t_rob)]:
        t.to_csv(OUT / f"{name}.csv", index=False)
        print(f"\n=== {name} ===")
        print(t.to_string(index=False))
    print(f"\nMundlak N={t_mund.attrs['N']}, countries={t_mund.attrs['Countries']}")
    print("TWFE:", t_mund.attrs["TWFE"])
    pd.DataFrame([t_mund.attrs["TWFE"]]).to_csv(OUT / "tabC4b_twfe.csv", index=False)

    fig_samples(t_samp, OUT / "figC1_samples.png")
    fig_marginal(fits, OUT / "figC2_marginal_subshare.png")
    fig_between(p, OUT / "figC3_between.png")


if __name__ == "__main__":
    main()
