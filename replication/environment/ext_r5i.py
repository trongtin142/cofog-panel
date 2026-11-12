"""Environmental-spending study, further estimates on the moderator, functional form, omitted variables, the
sources of exposure, structural controls and inference.

    python ext_r5i.py [--main PATH_TO_env_federalism.py] [--data DATA_EXT] [--out DIR]

Reads the panel of env_federalism.py and the GBD-MAPS reader of ext_anthro.py (same folder as --main).
Additional World Bank series (WDI and WGI, World Bank API, 3 November 2026) are in data_ext/ (--data), with
SHA-256 in data_ext/CHECKSUMS_r5i.sha256. Writes r5i_* files to --out (default output).
"""
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

HERE = Path(__file__).resolve().parent
_ap = argparse.ArgumentParser()
_ap.add_argument("--main", default=str(HERE / "env_federalism.py"))
_ap.add_argument("--data", default=None)
_ap.add_argument("--out", default=str(HERE / "output"))
ARGS, _ = _ap.parse_known_args()
ANALYSIS = Path(ARGS.main).resolve().parent
DATA = Path(ARGS.data) if ARGS.data else ANALYSIS / "data_ext"
OUT = Path(ARGS.out)
OUT.mkdir(parents=True, exist_ok=True)
GBD = ANALYSIS / "data_ext" / "lab" / "gbdmaps" / "41467_2021_23853_MOESM4_ESM.xlsx"
COAL = ANALYSIS / "data_ext" / "lab" / "r3c" / "wb_EG.ELC.COAL.ZS.json"
EU_CEE = ["BGR", "HRV", "CZE", "EST", "HUN", "LVA", "LTU", "POL", "ROU", "SVK", "SVN"]
LMIC = ["Low income", "Lower middle income", "Upper middle income"]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pc = load(ANALYSIS / "env_federalism.py", "pc")
an = load(ANALYSIS / "ext_anthro.py", "an")
CTRL = pc.CONTROLS


def pct(b):
    return round(100 * (np.exp(0.25 * b) - 1), 1)


def panel() -> pd.DataFrame:
    p = pc.build_panel()
    extra = [("wb_NV.IND.MANF.ZS.json", "MANF"), ("wb_EG.EGY.PRIM.PP.KD.json", "EI"),
             ("wb_TX.VAL.FUEL.ZS.UN.json", "FUEL"), ("wgi_GOV_WGI_VA.EST.json", "VA"),
             ("wgi_GOV_WGI_RQ.EST.json", "RQ"), ("wgi_GOV_WGI_RL.EST.json", "RL")]
    for f, name in extra:
        x = pc._wb(DATA / f, name)
        if name in ("VA", "RQ", "RL"):  # biennial before 2002: interpolate inside each country's range, like GE
            x = x.sort_values(["ISO", "YEAR"])
            full = x.set_index(["ISO", "YEAR"]).reindex(
                pd.MultiIndex.from_product([x["ISO"].unique(), range(int(x["YEAR"].min()), int(x["YEAR"].max()) + 1)],
                                           names=["ISO", "YEAR"])).reset_index()
            full[name] = full.groupby("ISO")[name].transform(lambda s: s.interpolate(limit_area="inside"))
            x = full
        p = p.merge(x, on=["ISO", "YEAR"], how="left")
    p = p.merge(pc._wb(COAL, "COAL"), on=["ISO", "YEAR"], how="left")
    p["lnEI"] = np.log(p["EI"].where(p["EI"] > 0))
    p["POSTSOC"] = p["ISO"].isin(pc.TRANSITION + EU_CEE + ["MNG"]).astype(int)
    return p


def lmic_medians(s: pd.DataFrame, cols) -> dict:
    inc = s["ISO"].map(pc.income_groups())
    m = s[inc.isin(LMIC)]
    return {c: float(m[c].median()) for c in cols}


def centre(s: pd.DataFrame, med: dict) -> pd.DataFrame:
    s = s.copy()
    for c, v in med.items():
        s[f"{c}c"] = s[c] - v
    return s


def fit(formula, d, needed, cov="cluster"):
    d = d.dropna(subset=needed).copy()
    if cov == "cluster":
        r = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d["ISO"])[0]})
    else:
        r = smf.ols(formula, data=d).fit()
    return r, d


def rec(name, r, d, terms=()):
    out = {"Model": name, "N": int(r.nobs), "Countries": int(d["ISO"].nunique()),
           "ME_SUB": round(float(r.params["SUB"]), 3), "se_ME": round(float(r.bse["SUB"]), 3),
           "p_ME": round(float(r.pvalues["SUB"]), 4), "ME25": pct(r.params["SUB"])}
    for t in terms:
        if t in r.params:
            out[t] = round(float(r.params[t]), 3)
            out[f"se_{t}"] = round(float(r.bse[t]), 3)
            out[f"p_{t}"] = round(float(r.pvalues[t]), 4)
    return out


NEED = pc.BASE_NEEDED + ["SUB"]
BASEC = f"lnPM ~ lnENV + SUB + SUB:GEc + GEc + {CTRL} + C(YEAR) + C(SUBREGION)"


# ---------------------------------------------------------------- A. moderators
def moderators(s, med):
    rows = []
    r, d = fit(BASEC, s, NEED)
    rows.append(rec("A1 Baseline", r, d, ["SUB:GEc"]))
    for name, add in [("A2 + SUB x ln GDP per capita", " + SUB:lnYc"), ("A3 + SUB x industry share", " + SUB:INDc"),
                      ("A4 + SUB x urban share", " + SUB:URBc"),
                      ("A5 + SUB x ln GDP per capita, industry and urban shares", " + SUB:lnYc + SUB:INDc + SUB:URBc")]:
        r, d = fit(BASEC + add, s, NEED)
        rows.append(rec(name, r, d, ["SUB:GEc", "SUB:lnYc", "SUB:INDc", "SUB:URBc"]))
    gex = " + ".join(f"GEc:{v}" for v in ["lnENV", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"])
    r, d = fit(BASEC + " + " + gex, s, NEED)
    rows.append(rec("A6 + GE x every control and ln ENV", r, d, ["SUB:GEc"]))
    for k, lab in [("VA", "voice and accountability"), ("RQ", "regulatory quality"), ("RL", "rule of law"),
                   ("CC", "control of corruption")]:
        f = BASEC.replace("SUB:GEc + GEc", f"SUB:{k}c + {k}c")
        r, d = fit(f, s, [n for n in NEED if n != "GE"] + [k])
        rows.append(rec(f"A {k}: {lab} in place of GE", r, d, [f"SUB:{k}c"]))
    r, d = fit(BASEC + " + SUB:VAc + VAc", s, NEED + ["VA"])
    rows.append(rec("A11 SUB x GE and SUB x voice and accountability", r, d, ["SUB:GEc", "SUB:VAc"]))
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "r5i_moderators.csv", index=False)
    return t


# ---------------------------------------------------------------- B. common support
def support(s):
    q1, q2 = np.quantile(s["GE"], [1 / 3, 2 / 3])
    s = s.assign(TER=np.where(s["GE"] <= q1, 1, np.where(s["GE"] <= q2, 2, 3)))
    rows = []
    for k, g in s.groupby("TER"):
        pos = g[g["SUB"] > 0]
        rows.append({"Tercile": int(k), "GE from": round(g["GE"].min(), 2), "GE to": round(g["GE"].max(), 2),
                     "N": len(g), "Countries": g["ISO"].nunique(),
                     "N SUB = 0": int((g["SUB"] == 0).sum()), "N SUB > 0": len(pos),
                     "Countries with SUB > 0": pos["ISO"].nunique(),
                     "Countries with central data alone": g.loc[g["NOSUB"] == 1, "ISO"].nunique(),
                     "SUB > 0: p25": round(pos["SUB"].quantile(.25), 2), "p50": round(pos["SUB"].median(), 2),
                     "p75": round(pos["SUB"].quantile(.75), 2)})
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "r5i_support.csv", index=False)
    plt = pc._plt()
    fig, ax = plt.subplots(figsize=(pc.WIDTH_IN, 3.0))
    a, b = s[s["NOSUB"] == 0], s[s["NOSUB"] == 1]
    ax.scatter(a["GE"], a["SUB"], s=6, color="#2a78d6", alpha=.45, lw=0, label="Subnational data")
    ax.scatter(b["GE"], b["SUB"], s=10, facecolors="none", edgecolors="#eb6834", lw=.6, label="Central data alone")
    for v in (q1, q2):
        ax.axvline(v, color=pc.INK2, lw=.6, ls=":")
    ax.axvline(-0.355, color=pc.INK, lw=.7, ls="--")
    ax.set_xlabel("Government effectiveness (WGI)", fontsize=8.5, color=pc.INK2)
    ax.set_ylabel("Subnational share (t−1)", fontsize=8.5, color=pc.INK2)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    pc._style(ax)
    fig.tight_layout()
    pc._save(fig, OUT / "r5i_fig_support.png")
    return t, {"q1": round(float(q1), 3), "q2": round(float(q2), 3)}


# ---------------------------------------------------------------- C. kernel
def kernel(s, ge_ref):
    sd, n = s["GE"].std(), len(s)
    h0 = 1.06 * sd * n ** (-1 / 5)
    grid = list(np.linspace(np.quantile(s["GE"], .05), np.quantile(s["GE"], .95), 15)) + [ge_ref]
    rows = []
    for mult in (1, 2):
        h = h0 * mult
        for g in grid:
            d = s.copy()
            d["GEg"] = d["GE"] - g
            w = np.exp(-0.5 * ((d["GE"] - g) / h) ** 2)
            r = smf.wls(f"lnPM ~ lnENV + SUB + SUB:GEg + GEg + {CTRL} + C(YEAR) + C(SUBREGION)", data=d,
                        weights=w).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d["ISO"])[0]})
            rows.append({"bandwidth": round(h, 3), "bw_mult": mult, "GE": round(float(g), 3),
                         "ME": round(float(r.params["SUB"]), 3), "se": round(float(r.bse["SUB"]), 3),
                         "p": round(float(r.pvalues["SUB"]), 4), "ME25": pct(r.params["SUB"]),
                         "eff_n": round(float(w.sum() ** 2 / (w ** 2).sum()), 0)})
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "r5i_kernel.csv", index=False)
    r, _ = pc._fit(pc.BASE, s, NEED)
    plt = pc._plt()
    fig, ax = plt.subplots(figsize=(pc.WIDTH_IN, 3.0))
    xs = np.linspace(np.quantile(s["GE"], .02), np.quantile(s["GE"], .98), 100)
    b, V = r.params, r.cov_params()
    lin = b["SUB"] + b["SUB:GE"] * xs
    se = np.sqrt(V.loc["SUB", "SUB"] + xs ** 2 * V.loc["SUB:GE", "SUB:GE"] + 2 * xs * V.loc["SUB", "SUB:GE"])
    ax.plot(xs, lin, color=pc.INK2, lw=1, ls="--", label="Linear interaction (Table 2, column 3)")
    k = t[(t["bw_mult"] == 1) & (t["GE"] != round(ge_ref, 3))].sort_values("GE")
    ax.plot(k["GE"], k["ME"], color="#2a78d6", lw=1.4, label=f"Kernel estimator, bandwidth {h0:.2f}")
    ax.fill_between(k["GE"], k["ME"] - 1.96 * k["se"], k["ME"] + 1.96 * k["se"], color="#2a78d6", alpha=.15, lw=0)
    ax.axhline(0, color=pc.INK, lw=.6)
    ax.set_xlabel("Government effectiveness (WGI)", fontsize=8.5, color=pc.INK2)
    ax.set_ylabel("Marginal association of SUB", fontsize=8.5, color=pc.INK2)
    ax.legend(fontsize=7, frameon=False)
    pc._style(ax)
    fig.tight_layout()
    pc._save(fig, OUT / "r5i_fig_kernel.png")
    return t, round(h0, 3)


# ---------------------------------------------------------------- D. Cinelli and Hazlett (2020)
def rv(t, df, q=1.0, alpha=None):
    f = q * abs(t) / np.sqrt(df)
    if alpha is not None:
        fstar = stats.t.ppf(1 - alpha / 2, df - 1) / np.sqrt(df - 1)
        f = f - fstar
        if f <= 0:
            return 0.0
    return float(0.5 * (np.sqrt(f ** 4 + 4 * f ** 2) - f ** 2))


def rss(formula, d):
    return float(smf.ols(formula, data=d).fit().ssr)


def sensitivity(s):
    rows, d = [], s.dropna(subset=NEED).copy()
    d["SUBGEc"] = d["SUB"] * d["GEc"]
    for target, treat, other in [("Marginal association at GE = -0.355", "SUB", "SUBGEc"),
                                 ("Interaction SUB x GE", "SUBGEc", "SUB")]:
        covs = ["lnENV", other, "GEc"] + CTRL.split(" + ") + ["C(YEAR)", "C(SUBREGION)"]
        rhs_x = " + ".join(covs)
        full = f"lnPM ~ {treat} + {rhs_x}"
        r = smf.ols(full, data=d).fit()
        est, se, t, df = float(r.params[treat]), float(r.bse[treat]), float(r.tvalues[treat]), float(r.df_resid)
        rc = smf.ols(full, data=d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d["ISO"])[0]})
        t_cl, G = float(rc.tvalues[treat]), d["ISO"].nunique()
        base = {"Target": target, "Estimate": round(est, 3), "se_classical": round(se, 4), "t_classical": round(t, 2),
                "df": int(df), "partial_R2_Y_D": round(t ** 2 / (t ** 2 + df), 4),
                "RV_q1": round(rv(t, df), 4), "RV_q1_a05": round(rv(t, df, alpha=0.05), 4),
                "t_cluster": round(t_cl, 2), "RV_q1_cluster": round(rv(t_cl, G - 1), 4),
                "RV_q1_a05_cluster": round(rv(t_cl, G - 1, alpha=0.05), 4),
                # deviation: cluster-robust t with the residual df (df = G - 1 is not conservative)
                "RV_q1_cluster_dfres": round(rv(t_cl, df), 4),
                "RV_q1_a05_cluster_dfres": round(rv(t_cl, df, alpha=0.05), 4)}
        se_cl = float(rc.bse[treat])
        for grp, terms in [("industry share", ["IND"]), ("ln GDP per capita and its square", ["lnY", "lnY2"]),
                           ("urban share", ["URB"])]:
            rhs_wo = " + ".join(c for c in covs if c not in terms)
            # partial R2 of the group with D given the other covariates, and with Y given D and the others
            r2dxj = 1 - rss(f"{treat} ~ {rhs_x}", d) / rss(f"{treat} ~ {rhs_wo}", d)
            r2yxj = 1 - rss(f"lnPM ~ {treat} + {rhs_x}", d) / rss(f"lnPM ~ {treat} + {rhs_wo}", d)
            for k in (1, 2, 3):
                r2dz = k * r2dxj / (1 - r2dxj)
                r2zxj = k * r2dxj ** 2 / ((1 - k * r2dxj) * (1 - r2dxj))
                r2yz = min(1.0, ((np.sqrt(k) + np.sqrt(r2zxj)) / np.sqrt(1 - r2zxj)) ** 2 * (r2yxj / (1 - r2yxj)))
                if r2dz >= 1:
                    continue
                bias = se * np.sqrt(df) * np.sqrt(r2yz * r2dz / (1 - r2dz))
                adj = est - np.sign(est) * bias
                adj_se = se * np.sqrt((1 - r2yz) / (1 - r2dz)) * np.sqrt(df / (df - 1))
                row = dict(base)
                row.update({"Benchmark": grp, "k": k, "partial_R2_D_Xj": round(r2dxj, 4),
                            "partial_R2_Y_Xj": round(r2yxj, 4), "R2_DZ": round(r2dz, 4), "R2_YZ": round(r2yz, 4),
                            "Adjusted estimate": round(float(adj), 3), "Adjusted t": round(float(adj / adj_se), 2),
                            "Adjusted t, cluster": round(float(adj / (se_cl * adj_se / se)), 2),
                            "Adjusted ME25": pct(adj) if treat == "SUB" else None})
                rows.append(row)
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "r5i_sensitivity.csv", index=False)
    return t


# ---------------------------------------------------------------- E. sources of exposure, 2017
GROUPS = {"Waste": ["Waste"],
          "Residential and commercial combustion": ["Residential Coal Combustion", "Residential Biofuel Combustion",
                                                    "Residential Other Combustion", "Commercial Combustion"],
          "Fugitive combustion and industrial dust": ["AFCID Dust"],
          "Energy": ["Energy Coal", "Energy NonCoal"], "Industry": ["Industry Coal", "Industry NonCoal"],
          "Energy and industry": ["Energy Coal", "Energy NonCoal", "Industry Coal", "Industry NonCoal"],
          "Transport": ["Road Transport", "NonRoad Transport"], "Agriculture": ["Agriculture"]}


def channel(s, ge):
    g = an.match_iso(an.read_gbdmaps(GBD), pc, set(s["ISO"]))
    keep = g[g["ISO"].isin(set(s["ISO"]))].copy()
    v = ["lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS", "lnPM"]
    cm = s.groupby("ISO")[v].mean().add_suffix("_m").reset_index()
    cm = cm.merge(s.groupby("ISO")["SUBREGION"].first().reset_index(), on="ISO")
    for k, cols in GROUPS.items():
        keep[f"S_{k}"] = keep[cols].sum(axis=1)            # % of exposure
        keep[f"X_{k}"] = keep["PM"] * keep[f"S_{k}"] / 100  # ug/m3
    cm = cm.merge(keep[["ISO", "PM"] + [c for c in keep.columns if c[:2] in ("S_", "X_")]], on="ISO", how="inner")
    cm["SUBGE"] = cm["SUB_m"] * cm["GE_m"]
    rhs = "SUB_m + SUBGE + GE_m + lnENV_m + lnY_m + lnY2_m + IND_m + URB_m + TRADE_m + lnDENS_m + C(SUBREGION)"
    rows = []
    for k in GROUPS:
        dd = cm.assign(Y=np.log(cm[f"X_{k}"].where(cm[f"X_{k}"] > 0))).dropna(subset=["Y"])
        r = smf.ols(f"Y ~ {rhs}", data=dd).fit(cov_type="HC3")
        e = an.me25(r, ge, "SUB_m", "SUBGE")
        rows.append({"Outcome": f"ln exposure from {k.lower()}", "N": int(r.nobs), "SUB": round(r.params["SUB_m"], 3),
                     "se_SUB": round(r.bse["SUB_m"], 3), "SUB:GE": round(r.params["SUBGE"], 3),
                     "se_SUB:GE": round(r.bse["SUBGE"], 3), "p_SUB:GE": round(r.pvalues["SUBGE"], 4),
                     "ME25": e["pct25"], "p_ME25": round(e["p"], 4)})
    for k in ("Waste", "Energy and industry"):
        r = smf.ols(f"Q('S_{k}') ~ {rhs}", data=cm).fit(cov_type="HC3")
        e = an.me25(r, ge, "SUB_m", "SUBGE")
        rows.append({"Outcome": f"share of exposure from {k.lower()} (percentage points)", "N": int(r.nobs),
                     "SUB": round(r.params["SUB_m"], 3), "se_SUB": round(r.bse["SUB_m"], 3),
                     "SUB:GE": round(r.params["SUBGE"], 3), "se_SUB:GE": round(r.bse["SUBGE"], 3),
                     "p_SUB:GE": round(r.pvalues["SUBGE"], 4),
                     "ME25": round(0.25 * e["me"], 2), "p_ME25": round(e["p"], 4)})
    t = pd.DataFrame(rows)
    st = []
    for k, y in [("A_waste", "X_Waste"), ("B_energy_industry", "X_Energy and industry")]:
        x = cm.copy()
        x["Y"], x["K"] = np.log(x[y].where(x[y] > 0)), k
        st.append(x)
    st = pd.concat(st).dropna(subset=["Y"])
    r = smf.ols(f"Y ~ C(K) * ({rhs})", data=st).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(st["ISO"])[0]})
    e = an.me25(r, ge, "C(K)[T.B_energy_industry]:SUB_m", "C(K)[T.B_energy_industry]:SUBGE")
    neg = cm[cm["GE_m"] < 0]
    info = {"stacked_energy_industry_minus_waste": {"me_diff": round(e["me"], 3), "se": round(e["se"], 3),
                                                     "p": round(e["p"], 4)},
            "countries_matched": int(len(cm)), "countries_negative_mean_GE": int(len(neg)),
            "mean_share_pct_negative_GE": {k: round(float(neg[f"S_{k}"].mean()), 1) for k in GROUPS},
            "mean_share_pct_all": {k: round(float(cm[f"S_{k}"].mean()), 1) for k in GROUPS},
            "local_sources_share_negative_GE_pct": round(float((neg["S_Waste"] + neg["S_Residential and commercial combustion"]
                                                               + neg["S_Fugitive combustion and industrial dust"]).mean()), 1)}
    t.to_csv(OUT / "r5i_channel.csv", index=False)
    return t, info


# ---------------------------------------------------------------- F. structural controls
def structural(s):
    rows = []
    specs = [("F1 + manufacturing value added", ["MANF"]), ("F2 + ln energy intensity", ["lnEI"]),
             ("F3 + fuel exports", ["FUEL"]), ("F4 + coal share of electricity and resource rents", ["COAL", "RENTS"]),
             ("F5 + voice and accountability", ["VA"]), ("F6 + post-socialist indicator", ["POSTSOC"]),
             ("F7 F1 to F6 jointly", ["MANF", "lnEI", "FUEL", "COAL", "RENTS", "VA", "POSTSOC"])]
    for name, add in specs:
        need = NEED + add
        r0, d0 = fit(BASEC, s.dropna(subset=add), NEED)
        rows.append(rec(f"{name}: baseline on the same sample", r0, d0, ["SUB:GEc"]))
        r, d = fit(BASEC.replace(f" + {CTRL}", f" + {CTRL} + " + " + ".join(add)), s, need)
        rows.append(rec(name, r, d, ["SUB:GEc"] + add))
    r, d = fit(BASEC, s[s["POSTSOC"] == 0], NEED)
    rows.append(rec("F8 without the post-socialist countries", r, d, ["SUB:GEc"]))
    r, d = fit(BASEC, s[s["ISO"] != "CHN"], NEED)
    rows.append(rec("F9 without China", r, d, ["SUB:GEc"]))
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "r5i_structural.csv", index=False)
    post = sorted(s.loc[s["POSTSOC"] == 1, "ISO"].unique())
    return t, {"postsocialist_in_sample": post, "n_postsocialist": len(post)}


# ---------------------------------------------------------------- G. inference and outcome checks
def wild(s, cluster_col, B=1999, seed=20261103):
    d = s.dropna(subset=NEED).reset_index(drop=True)
    cl = pd.factorize(d[cluster_col])[0]
    ru = smf.ols(BASEC, data=d).fit(cov_type="cluster", cov_kwds={"groups": cl})
    rr = smf.ols(BASEC.replace("lnENV + SUB + ", "lnENV + "), data=d).fit()
    X, j = ru.model.exog, ru.model.exog_names.index("SUB")
    n, k = X.shape
    G = cl.max() + 1
    XtXi = np.linalg.pinv(X.T @ X)
    c = G / (G - 1) * (n - 1) / (n - k)
    webb = np.array([-np.sqrt(1.5), -1, -np.sqrt(0.5), np.sqrt(0.5), 1, np.sqrt(1.5)])
    rng = np.random.default_rng(seed)
    t0 = ru.params["SUB"] / ru.bse["SUB"]
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
            "p_wild": round(float(np.mean(np.abs(ts) >= abs(t0))), 4)}


def inference(s):
    rows, info = [], {}
    d = s.dropna(subset=NEED).sort_values(["YEAR", "ISO"]).copy()
    r = smf.ols(BASEC, data=d).fit(cov_type="hac-groupsum",
                                   cov_kwds={"time": (d["YEAR"] - d["YEAR"].min()).to_numpy(), "maxlags": 2})
    rows.append(rec("G1 Driscoll-Kraay standard errors, 2 lags", r, d, ["SUB:GEc"]))
    info["G2_wild_country"] = wild(s, "ISO")
    info["G2_wild_subregion"] = wild(s, "SUBREGION")
    r, dd = fit(f"lnPM ~ SUB + SUB:GEc + GEc + lnY + lnY2 + TRADE + lnDENS + C(YEAR) + C(SUBREGION)", s,
                ["lnPM", "SUB", "GE", "lnY", "TRADE", "lnDENS", "SUBREGION"])
    rows.append(rec("G3 short specification without ln ENV, industry and urban shares", r, dd, ["SUB:GEc"]))
    g = an.match_iso(an.read_gbdmaps(GBD), pc, set(s["ISO"]))
    g["f_anthro"] = (100 - g["Windblown Dust"] - g["Remaining Sources"]) / 100
    m = s.merge(g[["ISO", "f_anthro"]], on="ISO", how="inner")
    m["lnFA"] = np.log(m["f_anthro"])
    r, dd = fit(BASEC + " + lnFA", m, NEED + ["lnFA"])
    rows.append(rec("G4 ln anthropogenic share 2017 as a control, free coefficient", r, dd, ["SUB:GEc", "lnFA"]))
    for v in ("lnPM", "SUB"):
        within = s[v] - s.groupby("ISO")[v].transform("mean")
        info[f"G5_{v}"] = {"sd_total": round(float(s[v].std()), 3), "sd_within": round(float(within.std()), 3),
                           "sd_between_country_means": round(float(s.groupby("ISO")[v].mean().std()), 3)}
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "r5i_inference.csv", index=False)
    return t, info


def main():
    p = panel()
    s = pc._sample(p).copy()
    ge = pc.ge_reference(p)["LMIC"]
    # Every moderator is centred at its median in low- and middle-income countries of the panel with coverage gaps
    # coded as zero, the population of the GE reference point (pc.ge_reference)
    med = lmic_medians(pc._sample(pc.gaps_as_zero(p)), ["GE", "lnY", "IND", "URB", "VA", "RQ", "RL", "CC"])
    assert abs(med["GE"] - ge) < 5e-4
    med["GE"] = ge
    s = centre(s, med)
    info = {"ge_ref": ge, "lmic_medians": {k: round(v, 3) for k, v in med.items()}, "N": len(s)}
    a = moderators(s, med)
    b, cut = support(s)
    info["terciles"] = cut
    k, h0 = kernel(s, ge)
    info["kernel_bandwidth"] = h0
    dd = sensitivity(s)
    e, info["channel"] = channel(s, ge)
    f, info["structural"] = structural(s)
    g, info["inference"] = inference(s)
    (OUT / "r5i_results.json").write_text(json.dumps(info, indent=1), encoding="utf8")
    for name, t in [("A moderators", a), ("B support", b), ("C kernel", k), ("D sensitivity", dd), ("E channel", e),
                    ("F structural", f), ("G inference", g)]:
        print(f"\n=== {name} ===")
        print(t.to_string(index=False))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
