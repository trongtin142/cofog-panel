"""
Environmental-spending study: further estimates on the sources of variation of the association between the
subnational share and PM2.5 exposure.

    python ext_between_within.py [--main PATH_TO_env_federalism.py] [--out DIR] [--inputs DIR]

Run after replication/harmonisation/evaluate_harmonisation.py (the panel of env_federalism.py reads its output),
after esm_tables.py (country names from ESM1_TableS1_countries.csv in --inputs, default output) and after ext_specification.py
(source_power refits the cross-section of specification_channel.csv and checks the refit against specification_channel.csv and
specification_results.json in --inputs).
Sections, each written to bw_results.json under its key:
    income_moderator     the share interacted with GE and with ln GDP per capita, pooled and between countries
    moderator_tests      correlation and variance inflation factors of the two interactions, joint Wald tests
    influence            leaving out one country, one sub-region, groups of countries or the k most influential
                         countries (k = 1 to 5)
    post_socialist       the share inside and outside the post-socialist group, wild cluster bootstrap p-values
    long_run_within      five-year averages with country effects and ten-year long differences
    reporting_changes    years with a change in the reporting of COFOG 05, and country-by-reporting-spell effects
    recording            within estimates without the years of a change in reporting and without reversed jumps
    ge_percentiles       the association at percentiles of GE and at the high-income median
    first_year_share     the share of each country's first sample year in place of the current share
    between_estimators   regressions on country means and the between slope of the correlated random effects model
    overlap              covariate overlap between weak and strong effectiveness, estimate on common support
    source_power         minimum detectable effects of the contrast between sources of exposure (Table S11) and of
                         the association inside the post-socialist group
Outputs in --out (default output): bw_results.csv (one row per estimate, with key, estimate, standard error,
p-value, 95% interval, N and countries), bw_results.json (the same, nested by section and model), bw_trace.csv
(the printed form of every number with its locator in bw_results.json), bw_leave_one_country_out.csv and
bw_leave_one_subregion_out.csv.
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
_ap.add_argument("--out", default=str(HERE / "output"))
_ap.add_argument("--inputs", default=str(HERE / "output"),
                 help="folder with ESM1_TableS1_countries.csv, specification_channel.csv and specification_results.json")
ARGS, _ = _ap.parse_known_args()
OUT = Path(ARGS.out)
OUT.mkdir(parents=True, exist_ok=True)

_spec = importlib.util.spec_from_file_location("pc", ARGS.main)
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

CTRL = pc.CONTROLS
BASE = pc.BASE
TWFE = f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CTRL} + C(YEAR) + C(ISO)"
LMIC = ["Low income", "Lower middle income", "Upper middle income"]
# Post-socialist countries: economies in transition, the EU member states of Central and Eastern Europe and Mongolia,
# as in ext_specification.py
EU_CEE = ["BGR", "HRV", "CZE", "EST", "HUN", "LVA", "LTU", "POL", "ROU", "SVK", "SVN"]
POSTSOC = sorted(set(pc.TRANSITION + EU_CEE + ["MNG"]))
MVARS = ["lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]
OTHER_M = ("lnENV_w + lnENV_m + GE_w + GE_m + lnY_w + lnY_m + lnY2_w + lnY2_m + IND_w + IND_m + URB_w + URB_m"
           " + TRADE_w + TRADE_m + lnDENS_w + lnDENS_m + C(YEAR) + C(SUBREGION)")
MUNDLAK = f"lnPM ~ SUB_w + SUB_m + SUBGE_w + SUBGE_m + {OTHER_M}"  # the model of Table 3 (pc.table_mundlak)
SEED, B_WILD, B_RADEMACHER = 20261124, 1999, 9999
NUM = ["lnPM", "lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]
OVERLAP_VARS = ["SUB", "lnY", "IND", "URB", "TRADE", "lnDENS"]  # ln environmental spending is left out
SHARE_BINS = [("0", None, 0.0), ("(0, 0.1]", 0.0, 0.1), ("(0.1, 0.3]", 0.1, 0.3), ("(0.3, 0.5]", 0.3, 0.5),
              ("(0.5, 1]", 0.5, 1.0)]
Z80, Z975 = float(stats.norm.ppf(0.80)), float(stats.norm.ppf(0.975))

ROWS = []
RES = {}


# ----------------------------------------------------------------------------------------------- helpers
def pct(b):
    return float(100 * (np.exp(0.25 * b) - 1))


def fit(formula, d, cov="cluster", weights=None):
    d = d.reset_index(drop=True)
    if cov == "cluster":
        m = smf.ols(formula, data=d) if weights is None else smf.wls(formula, data=d, weights=d[weights])
        r = m.fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d["ISO"])[0]})
    else:
        m = smf.ols(formula, data=d) if weights is None else smf.wls(formula, data=d, weights=d[weights])
        r = m.fit(cov_type=cov)
    assert int(r.nobs) == len(d), (formula, r.nobs, len(d))
    return r, d


def lincom(r, w: dict) -> tuple:
    names = list(r.params.index)
    R = np.zeros(len(names))
    for k, v in w.items():
        R[names.index(k)] = v
    est = float(R @ r.params.values)
    se = float(np.sqrt(R @ r.cov_params().values @ R))
    return est, se, float(2 * stats.norm.sf(abs(est / se)))


def put(sec, model, term, r, d, w, share_slope=False, note=""):
    """Record one estimate (a coefficient or a linear combination w of coefficients)."""
    est, se, p = lincom(r, w if isinstance(w, dict) else {w: 1.0})
    z = stats.norm.ppf(0.975)
    row = {"key": f"{sec}/{model}/{term}", "section": sec, "model": model, "term": term,
           "estimate": round(est, 6), "se": round(se, 6), "p": round(p, 6),
           "ci_lo": round(est - z * se, 6), "ci_hi": round(est + z * se, 6),
           "N": int(r.nobs), "countries": int(d["ISO"].nunique()), "note": note}
    if share_slope:
        row.update({"effect25_pct": round(pct(est), 6), "effect25_lo": round(pct(est - z * se), 6),
                    "effect25_hi": round(pct(est + z * se), 6)})
    ROWS.append(row)
    m = RES.setdefault(sec, {}).setdefault(model, {"N": int(r.nobs), "countries": int(d["ISO"].nunique()),
                                                    "terms": {}})
    m["terms"][term] = {k: v for k, v in row.items() if k not in ("key", "section", "model", "term", "N",
                                                                    "countries")}
    return row


def info(sec, key, value):
    RES.setdefault(sec, {}).setdefault("info", {})[key] = value


def mundlak_frame(s: pd.DataFrame) -> pd.DataFrame:
    s = s.copy()
    for v in MVARS:
        s[f"{v}_m"] = s.groupby("ISO")[v].transform("mean")
        s[f"{v}_w"] = s[v] - s[f"{v}_m"]
    s["SUBGE_w"] = s["SUB_w"] * s["GE_m"]
    s["SUBGE_m"] = s["SUB_m"] * s["GE_m"]
    return s


def wild_t(formula, term, d, B=B_WILD, seed=SEED, weights="webb") -> dict:
    """Wild cluster bootstrap-t for one coefficient: Webb (six-point) or Rademacher weights, null imposed,
    clusters = countries."""
    d = d.reset_index(drop=True)
    cl = pd.factorize(d["ISO"])[0]
    G = int(cl.max() + 1)
    ru = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": cl})
    y, X = ru.model.endog, ru.model.exog
    j = ru.model.exog_names.index(term)
    Xr = np.delete(X, j, axis=1)
    yhat = Xr @ np.linalg.lstsq(Xr, y, rcond=None)[0]
    u = y - yhat
    n, k = X.shape
    XtXi = np.linalg.pinv(X.T @ X)
    c = G / (G - 1) * (n - 1) / (n - k)
    webb = np.array([-np.sqrt(1.5), -1, -np.sqrt(0.5), np.sqrt(0.5), 1, np.sqrt(1.5)])
    w_set = webb if weights == "webb" else np.array([-1.0, 1.0])
    rng = np.random.default_rng(seed)
    t0 = float(ru.params[term] / ru.bse[term])
    ts = np.empty(B)
    for b in range(B):
        yb = yhat + u * rng.choice(w_set, G)[cl]
        beta = XtXi @ (X.T @ yb)
        e = yb - X @ beta
        score = np.zeros((G, k))
        np.add.at(score, cl, X * e[:, None])
        V = c * XtXi @ (score.T @ score) @ XtXi
        ts[b] = beta[j] / np.sqrt(V[j, j])
    out = {"clusters": G, "replications": B, "seed": seed, "t": round(t0, 4),
           "p_wild": round(float(np.mean(np.abs(ts) >= abs(t0))), 4)}
    if weights != "webb":
        out["weights"] = weights
    return out


def dist(x: pd.Series) -> dict:
    return {"min": round(float(x.min()), 6), "p5": round(float(x.quantile(0.05)), 6),
            "median": round(float(x.median()), 6), "p95": round(float(x.quantile(0.95)), 6),
            "max": round(float(x.max()), 6)}


def dist_full(x: pd.Series) -> dict:
    """Minimum, 5th, 25th, 50th, 75th and 95th percentiles and maximum."""
    out = {"min": round(float(x.min()), 6)}
    out.update({f"p{q}": round(float(x.quantile(q / 100)), 6) for q in (5, 25, 50, 75, 95)})
    out["max"] = round(float(x.max()), 6)
    return out


def wald_joint(r, terms) -> dict:
    """Joint Wald test that the listed coefficients are zero, with the covariance of the fit (chi-squared)."""
    b = r.params[terms].values
    V = r.cov_params().loc[terms, terms].values
    w = float(b @ np.linalg.solve(V, b))
    return {"chi2": round(w, 6), "df": len(terms), "p": round(float(stats.chi2.sf(w, len(terms))), 6)}


def vif(r, term) -> float:
    """Variance inflation factor of one column of the design matrix of a fit (all other columns as regressors)."""
    X = r.model.exog
    j = r.model.exog_names.index(term)
    y, Z = X[:, j], np.delete(X, j, axis=1)
    e = y - Z @ np.linalg.lstsq(Z, y, rcond=None)[0]
    r2 = 1 - float(e @ e) / float(((y - y.mean()) ** 2).sum())
    return round(1 / (1 - r2), 6)


def country_names(inputs: Path) -> dict:
    """Country names of Table S6, in the short form before a comma ("Moldova" for "Moldova, Republic of")."""
    t = pd.read_csv(inputs / "ESM1_TableS1_countries.csv")
    return dict(zip(t["ISO3"], t["Country"].str.split(",").str[0]))


def five_year_cells(s: pd.DataFrame, flags=()) -> pd.DataFrame:
    """Country-period means of five-year periods (as the five-year row of Table S8), with the country mean of GE
    in the main sample (GE_m) and, for each flag column, whether the cell contains a flagged year."""
    s5 = s.assign(PERIOD=(s["YEAR"] // 5) * 5, GE_m=s.groupby("ISO")["GE"].transform("mean"))
    agg = {v: (v, "mean") for v in NUM + ["GE_m"]}
    agg.update({f: (f, "max") for f in flags})
    a = s5.groupby(["ISO", "PERIOD", "SUBREGION"], as_index=False).agg(**agg)
    return a.assign(SUBGEm=a["SUB"] * a["GE_m"])


def ten_year_pairs(s: pd.DataFrame, flags=()) -> pd.DataFrame:
    """Ten-year differences of every pair of main-sample observations of a country ten years apart (YEAR is the end
    year), with the change of the share times the country mean of GE (dSUBGEm) and, for each flag column, whether a
    flagged year of the country lies in the window (end year - 10, end year]."""
    q = s.assign(GE_m=s.groupby("ISO")["GE"].transform("mean"))
    base = q.set_index(["ISO", "YEAR"])[NUM]
    lag = base.copy()
    lag.index = pd.MultiIndex.from_arrays([lag.index.get_level_values(0), lag.index.get_level_values(1) + 10],
                                          names=["ISO", "YEAR"])
    dd = (base - lag).dropna().add_prefix("d").reset_index()
    dd = dd.merge(q.groupby("ISO")["GE_m"].first().reset_index(), on="ISO")
    dd["dSUBGEm"] = dd["dSUB"] * dd["GE_m"]
    for f in flags:
        yrs = q.loc[q[f].astype(bool), ["ISO", "YEAR"]]
        hit = dd[["ISO", "YEAR"]].merge(yrs, on="ISO", suffixes=("", "_f"))
        hit = hit[(hit["YEAR_f"] > hit["YEAR"] - 10) & (hit["YEAR_f"] <= hit["YEAR"])]
        key = set(zip(hit["ISO"], hit["YEAR"]))
        dd[f] = [(i, y) in key for i, y in zip(dd["ISO"], dd["YEAR"])]
    return dd


FD_GEM = "dlnPM ~ dlnENV + dSUB + dSUBGEm + dGE + dlnY + dlnY2 + dIND + dURB + dTRADE + dlnDENS + C(YEAR)"
FIVE_GEM = f"lnPM ~ lnENV + SUB + SUBGEm + GE + {CTRL} + C(PERIOD) + C(ISO)"


# ----------------------------------------------------------------------------------------------- sections
def income_moderator(s, ref, med_lny):
    sec = "income_moderator"
    s = s.assign(GEc=s["GE"] - ref, lnYc=s["lnY"] - med_lny)
    fx = f"{CTRL} + C(YEAR) + C(SUBREGION)"
    specs = [("baseline_centred", f"lnPM ~ lnENV + SUB + SUB:GEc + GEc + {fx}", ["SUB:GEc"]),
             ("income_in_place_of_ge", f"lnPM ~ lnENV + SUB + SUB:lnYc + GEc + {fx}", ["SUB:lnYc"]),
             ("both_interactions", f"lnPM ~ lnENV + SUB + SUB:GEc + SUB:lnYc + GEc + {fx}", ["SUB:GEc", "SUB:lnYc"])]
    fits = {}
    for model, f, terms in specs:
        r, d = fit(f, s)
        fits[model] = r
        put(sec, model, "SUB", r, d, "SUB", share_slope=True,
            note="share coefficient = association at GE -0.355 and at the median ln GDP per capita of LMIC")
        for t in terms:
            put(sec, model, t, r, d, t)
        info(sec, f"{model}_R2", round(float(r.rsquared), 6))
    m = mundlak_frame(s)
    m["GE_mc"], m["lnY_mc"] = m["GE_m"] - ref, m["lnY_m"] - med_lny
    for model, inter, terms in [
        ("mundlak_ge_only", "SUB_w:GE_mc + SUB_m:GE_mc", ["SUB_w:GE_mc", "SUB_m:GE_mc"]),
        ("mundlak_income_only", "SUB_w:lnY_mc + SUB_m:lnY_mc", ["SUB_w:lnY_mc", "SUB_m:lnY_mc"]),
        ("mundlak_both", "SUB_w:GE_mc + SUB_m:GE_mc + SUB_w:lnY_mc + SUB_m:lnY_mc",
         ["SUB_w:GE_mc", "SUB_m:GE_mc", "SUB_w:lnY_mc", "SUB_m:lnY_mc"])]:
        r, d = fit(f"lnPM ~ SUB_w + SUB_m + {inter} + {OTHER_M}", m)
        fits[model] = r
        put(sec, model, "SUB_w", r, d, "SUB_w", share_slope=True, note="within slope at the centring values")
        put(sec, model, "SUB_m", r, d, "SUB_m", share_slope=True, note="between slope at the centring values")
        for t in terms:
            put(sec, model, t, r, d, t)
    cm = s.groupby("ISO")[["GE", "lnY"]].mean()
    sd = {"GE": float(cm["GE"].std()), "lnY": float(cm["lnY"].std())}
    info(sec, "sd_country_mean_GE", round(sd["GE"], 6))
    info(sec, "sd_country_mean_lnY", round(sd["lnY"], 6))
    info(sec, "corr_country_means_GE_lnY", round(float(cm["GE"].corr(cm["lnY"])), 6))
    info(sec, "median_lnY_lmic_panel108", round(med_lny, 6))
    info(sec, "ge_ref", ref)
    # interactions per standard deviation of the country means of the moderator
    for model, pairs in [("both_interactions", [("SUB:GEc", "GE"), ("SUB:lnYc", "lnY")]),
                         ("mundlak_both", [("SUB_m:GE_mc", "GE"), ("SUB_m:lnY_mc", "lnY")])]:
        r = fits[model]
        d = m if model.startswith("mundlak") else s
        for t, v in pairs:
            put(sec, f"{model}_per_sd", t, r, d, {t: sd[v]}, note=f"coefficient x SD of country-mean {v}")
    # correlation and variance inflation factors of the two interactions, joint Wald tests (clustered covariance)
    for model, (tg, ty) in [("both_interactions", ("SUB:GEc", "SUB:lnYc")),
                            ("mundlak_both", ("SUB_m:GE_mc", "SUB_m:lnY_mc"))]:
        r = fits[model]
        X = pd.DataFrame(r.model.exog, columns=r.model.exog_names)
        RES.setdefault("moderator_tests", {})[model] = {
            "corr_interactions": round(float(X[tg].corr(X[ty])), 6),
            "vif": {tg: vif(r, tg), ty: vif(r, ty)}, "wald_both_interactions": wald_joint(r, [tg, ty])}


def influence(s, ref):
    sec = "influence"
    m_full = mundlak_frame(s)
    r0, d0 = fit(BASE, s)
    rm0, dm0 = fit(MUNDLAK, m_full)
    me0 = lincom(r0, {"SUB": 1, "SUB:GE": ref})
    bs0 = lincom(rm0, {"SUB_m": 1, "SUBGE_m": ref})
    put(sec, "full_pooled", "SUB:GE", r0, d0, "SUB:GE")
    put(sec, "full_pooled", "slope_at_ref", r0, d0, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
    put(sec, "full_mundlak", "SUB_m", rm0, dm0, "SUB_m", share_slope=True)
    put(sec, "full_mundlak", "SUBGE_m", rm0, dm0, "SUBGE_m")
    put(sec, "full_mundlak", "between_slope_at_ref", rm0, dm0, {"SUB_m": 1, "SUBGE_m": ref}, share_slope=True)
    rows = []
    for c in sorted(s["ISO"].unique()):
        q = s[s["ISO"] != c]
        r, d = fit(BASE, q)
        rm, dm = fit(MUNDLAK, mundlak_frame(q))
        me = lincom(r, {"SUB": 1, "SUB:GE": ref})
        bs = lincom(rm, {"SUB_m": 1, "SUBGE_m": ref})
        rows.append({"ISO_left_out": c, "N": int(r.nobs), "countries": int(d["ISO"].nunique()),
                     "pooled_SUBxGE": r.params["SUB:GE"], "pooled_se_SUBxGE": r.bse["SUB:GE"],
                     "pooled_p_SUBxGE": r.pvalues["SUB:GE"],
                     "pooled_slope_at_ref": me[0], "pooled_se_slope_at_ref": me[1], "pooled_p_slope_at_ref": me[2],
                     "pooled_effect25_at_ref": pct(me[0]),
                     "between_SUB_m": rm.params["SUB_m"], "between_se_SUB_m": rm.bse["SUB_m"],
                     "between_p_SUB_m": rm.pvalues["SUB_m"],
                     "between_SUBGE_m": rm.params["SUBGE_m"], "between_se_SUBGE_m": rm.bse["SUBGE_m"],
                     "between_p_SUBGE_m": rm.pvalues["SUBGE_m"],
                     "between_slope_at_ref": bs[0], "between_se_slope_at_ref": bs[1], "between_p_slope_at_ref": bs[2],
                     "between_effect25_at_ref": pct(bs[0]),
                     "shift_between_slope_in_full_se": (bs[0] - bs0[0]) / bs0[1],
                     "shift_pooled_slope_in_full_se": (me[0] - me0[0]) / me0[1],
                     "pooled_SUB": r.params["SUB"], "pooled_se_SUB": r.bse["SUB"], "pooled_p_SUB": r.pvalues["SUB"]})
    lo = pd.DataFrame(rows)
    lo.round(6).to_csv(OUT / "bw_leave_one_country_out.csv", index=False)
    summ = {}
    for col in ["pooled_SUBxGE", "pooled_p_SUBxGE", "pooled_effect25_at_ref", "pooled_p_slope_at_ref",
                "between_SUB_m", "between_p_SUB_m", "between_SUBGE_m", "between_p_SUBGE_m", "between_slope_at_ref",
                "between_effect25_at_ref", "between_p_slope_at_ref"]:
        summ[col] = dist(lo[col])
    summ["runs"] = len(lo)
    summ["between_slope_at_ref_positive"] = int((lo["between_slope_at_ref"] > 0).sum())
    summ["between_slope_at_ref_p_ge_005"] = int((lo["between_p_slope_at_ref"] >= 0.05).sum())
    summ["between_SUBGE_m_p_ge_005"] = int((lo["between_p_SUBGE_m"] >= 0.05).sum())
    summ["pooled_SUBxGE_p_ge_005"] = int((lo["pooled_p_SUBxGE"] >= 0.05).sum())
    summ["pooled_slope_at_ref_p_ge_005"] = int((lo["pooled_p_slope_at_ref"] >= 0.05).sum())
    big = lo[lo["shift_between_slope_in_full_se"].abs() > 1]
    summ["influential_between_slope_more_than_1se"] = big[["ISO_left_out", "shift_between_slope_in_full_se",
                                                          "between_effect25_at_ref", "between_p_slope_at_ref"]] \
        .round(4).to_dict("records")
    bigp = lo[lo["shift_pooled_slope_in_full_se"].abs() > 1]
    summ["influential_pooled_slope_more_than_1se"] = bigp["ISO_left_out"].tolist()
    i = lo["shift_between_slope_in_full_se"].abs().idxmax()
    summ["largest_shift_between"] = {"ISO": lo.loc[i, "ISO_left_out"],
                                     "shift_in_full_se": round(float(lo.loc[i, "shift_between_slope_in_full_se"]), 4),
                                     "effect25": round(float(lo.loc[i, "between_effect25_at_ref"]), 4),
                                     "p": round(float(lo.loc[i, "between_p_slope_at_ref"]), 4)}
    info(sec, "leave_one_country_out", summ)
    # leave one sub-region out, correlated random effects model (and the pooled baseline, last columns)
    rows = []
    for g in sorted(s["SUBREGION"].unique()):
        q = s[s["SUBREGION"] != g]
        rm, dm = fit(MUNDLAK, mundlak_frame(q))
        bs = lincom(rm, {"SUB_m": 1, "SUBGE_m": ref})
        r, d = fit(BASE, q)
        me = lincom(r, {"SUB": 1, "SUB:GE": ref})
        rows.append({"subregion_left_out": g, "N": int(rm.nobs), "countries": int(dm["ISO"].nunique()),
                     "between_SUB_m": rm.params["SUB_m"], "between_se_SUB_m": rm.bse["SUB_m"],
                     "between_p_SUB_m": rm.pvalues["SUB_m"],
                     "between_SUBGE_m": rm.params["SUBGE_m"], "between_se_SUBGE_m": rm.bse["SUBGE_m"],
                     "between_p_SUBGE_m": rm.pvalues["SUBGE_m"],
                     "between_slope_at_ref": bs[0], "between_se_slope_at_ref": bs[1], "between_p_slope_at_ref": bs[2],
                     "between_effect25_at_ref": pct(bs[0]),
                     "pooled_SUB": r.params["SUB"], "pooled_p_SUB": r.pvalues["SUB"],
                     "pooled_SUBxGE": r.params["SUB:GE"], "pooled_p_SUBxGE": r.pvalues["SUB:GE"],
                     "pooled_slope_at_ref": me[0], "pooled_p_slope_at_ref": me[2], "pooled_effect25_at_ref": pct(me[0])})
    ls = pd.DataFrame(rows)
    ls.round(6).to_csv(OUT / "bw_leave_one_subregion_out.csv", index=False)
    summ = {col: dist(ls[col]) for col in ["between_SUB_m", "between_p_SUB_m", "between_SUBGE_m", "between_p_SUBGE_m",
                                           "between_slope_at_ref", "between_effect25_at_ref",
                                           "between_p_slope_at_ref"]}
    summ["runs"] = len(ls)
    summ["between_slope_at_ref_p_ge_005"] = int((ls["between_p_slope_at_ref"] >= 0.05).sum())
    summ["between_SUBGE_m_p_ge_005"] = int((ls["between_p_SUBGE_m"] >= 0.05).sum())
    imin = ls["between_effect25_at_ref"].idxmin()
    summ["smallest_effect"] = {"subregion": ls.loc[imin, "subregion_left_out"],
                               "effect25": round(float(ls.loc[imin, "between_effect25_at_ref"]), 4),
                               "p": round(float(ls.loc[imin, "between_p_slope_at_ref"]), 4)}
    info(sec, "leave_one_subregion_out", summ)
    influence_more(s, ref, lo, ls)
    # groups left out jointly
    gm = s.groupby("ISO")["GE"].mean()
    below = sorted(gm[gm < ref].index)
    groups = {"without_RUS_UKR": ["RUS", "UKR"],
              "without_postsocialist_below_ref": sorted(set(below) & set(POSTSOC)),
              "without_all_below_ref": below}
    info(sec, "countries_mean_ge_below_ref", below)
    info(sec, "postsocialist_below_ref", groups["without_postsocialist_below_ref"])
    for model, drop in groups.items():
        q = s[~s["ISO"].isin(drop)]
        r, d = fit(BASE, q)
        put(sec, model, "pooled_SUB:GE", r, d, "SUB:GE")
        put(sec, model, "pooled_slope_at_ref", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
        rm, dm = fit(MUNDLAK, mundlak_frame(q))
        put(sec, model, "between_SUB_m", rm, dm, "SUB_m", share_slope=True)
        put(sec, model, "between_SUBGE_m", rm, dm, "SUBGE_m")
        put(sec, model, "between_slope_at_ref", rm, dm, {"SUB_m": 1, "SUBGE_m": ref}, share_slope=True,
            note="extrapolated outside the remaining support" if model == "without_all_below_ref" else "")
        info(sec, f"{model}_min_country_mean_ge", round(float(q.groupby("ISO")["GE"].mean().min()), 6))
    # support of the country-mean share below and above the reference value
    cs = s.groupby("ISO")[["SUB", "GE"]].mean()
    for lab, g in [("below_ref", cs[cs["GE"] < ref]), ("above_ref", cs[cs["GE"] >= ref])]:
        info(sec, f"support_{lab}", {"countries": int(len(g)), "mean_share": round(float(g["SUB"].mean()), 6),
                                     "sd_share": round(float(g["SUB"].std()), 6),
                                     "min_share": round(float(g["SUB"].min()), 6),
                                     "max_share": round(float(g["SUB"].max()), 6),
                                     "positive_share": int((g["SUB"] > 0).sum()),
                                     "share_above_0.5": int((g["SUB"] > 0.5).sum())})


def influence_more(s, ref, lo, ls):
    """Over the single deletions of influence(): minimum, percentiles and maximum of each statistic, the number of
    deletions with p < 0.05 and p < 0.10, and the five deletions that move it most (change from the full-sample
    estimate, also in standard errors of the full-sample estimate). Then the baseline and the model of Table 3
    without the k countries whose single deletion moves the association at the reference value most, k = 1 to 5,
    ranked once by the pooled association and once by the between-country association."""
    sec = "influence_top_k"
    r0, _ = fit(BASE, s)
    rm0, _ = fit(MUNDLAK, mundlak_frame(s))
    me0, bs0 = lincom(r0, {"SUB": 1, "SUB:GE": ref}), lincom(rm0, {"SUB_m": 1, "SUBGE_m": ref})
    full = {"pooled_SUB": (r0.params["SUB"], r0.bse["SUB"]), "pooled_SUBxGE": (r0.params["SUB:GE"], r0.bse["SUB:GE"]),
            "pooled_slope_at_ref": me0[:2], "between_SUB_m": (rm0.params["SUB_m"], rm0.bse["SUB_m"]),
            "between_SUBGE_m": (rm0.params["SUBGE_m"], rm0.bse["SUBGE_m"]), "between_slope_at_ref": bs0[:2]}
    pcol = {"pooled_SUB": "pooled_p_SUB", "pooled_SUBxGE": "pooled_p_SUBxGE",
            "pooled_slope_at_ref": "pooled_p_slope_at_ref", "between_SUB_m": "between_p_SUB_m",
            "between_SUBGE_m": "between_p_SUBGE_m", "between_slope_at_ref": "between_p_slope_at_ref"}
    for lab, df, key in [("single_countries", lo, "ISO_left_out"), ("single_subregions", ls, "subregion_left_out")]:
        out = {"runs": int(len(df))}
        for col, p_col in pcol.items():
            est, se = full[col]
            shift = df[col] - est
            top = shift.abs().sort_values(ascending=False, kind="stable").index[:5]
            out[col] = {"distribution": dist_full(df[col]), "p_lt_005": int((df[p_col] < 0.05).sum()),
                        "p_lt_010": int((df[p_col] < 0.10).sum()),
                        "largest_moves": [{"left_out": NAMES.get(df.loc[i, key], df.loc[i, key]),
                                           "change": round(float(shift[i]), 6),
                                           "change_in_se": round(float(shift[i] / se), 6)} for i in top]}
            if col.endswith("slope_at_ref"):
                out[col]["effect25_distribution"] = dist_full(df[col.replace("slope_at_ref", "effect25_at_ref")])
        info(sec, lab, out)
    for tag, shift_col in [("pooled_ranking", "shift_pooled_slope_in_full_se"),
                           ("between_ranking", "shift_between_slope_in_full_se")]:
        rank = lo.loc[lo[shift_col].abs().sort_values(ascending=False, kind="stable").index, "ISO_left_out"].tolist()
        info(sec, f"top5_{tag}", [NAMES.get(c, c) for c in rank[:5]])
        for k in range(1, 6):
            q = s[~s["ISO"].isin(rank[:k])]
            model = f"without_top{k}_{tag}"
            r, d = fit(BASE, q)
            put(sec, model, "pooled_SUB:GE", r, d, "SUB:GE")
            put(sec, model, "pooled_slope_at_ref", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
            rm, dm = fit(MUNDLAK, mundlak_frame(q))
            put(sec, model, "between_SUB_m", rm, dm, "SUB_m", share_slope=True)
            put(sec, model, "between_SUBGE_m", rm, dm, "SUBGE_m")
            put(sec, model, "between_slope_at_ref", rm, dm, {"SUB_m": 1, "SUBGE_m": ref}, share_slope=True)


def post_socialist(s, ref):
    sec = "post_socialist"
    s = s.assign(PS=s["ISO"].isin(POSTSOC).astype(int))
    ps, other = s[s["PS"] == 1], s[s["PS"] == 0]
    info(sec, "countries_in_group", sorted(ps["ISO"].unique()))
    info(sec, "obs_in_group", int(len(ps)))
    r, d = fit(BASE.replace(" + GE + ", " + GE + PS + SUB:PS + "), s)
    for t in ["SUB", "SUB:GE", "PS", "SUB:PS"]:
        put(sec, "interaction_with_group", t, r, d, t)
    put(sec, "interaction_with_group", "slope_at_ref_other", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
    put(sec, "interaction_with_group", "slope_at_ref_group", r, d, {"SUB": 1, "SUB:PS": 1, "SUB:GE": ref},
        share_slope=True)
    no_int = f"lnPM ~ lnENV + SUB + GE + {CTRL} + C(YEAR) + C(SUBREGION)"
    mund_noint = f"lnPM ~ SUB_w + SUB_m + {OTHER_M}"
    for tag, g in [("group_only", ps), ("other_only", other)]:
        r, d = fit(no_int, g)
        row = put(sec, f"{tag}_no_interaction", "SUB", r, d, "SUB", share_slope=True)
        if tag == "group_only":
            w = wild_t(no_int, "SUB", d)
            row["note"] = f"wild cluster bootstrap p = {w['p_wild']}"
            RES[sec][f"{tag}_no_interaction"]["wild_SUB"] = w
        if tag == "group_only":
            r, d = fit(BASE, g)
            put(sec, f"{tag}_with_interaction", "SUB", r, d, "SUB", share_slope=True)
            put(sec, f"{tag}_with_interaction", "SUB:GE", r, d, "SUB:GE")
            put(sec, f"{tag}_with_interaction", "slope_at_ref", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
            info(sec, "group_ge_range_obs", [round(float(g["GE"].min()), 6), round(float(g["GE"].max()), 6)])
        m = mundlak_frame(g)
        r, d = fit(mund_noint, m)
        put(sec, f"{tag}_mundlak", "SUB_w", r, d, "SUB_w", share_slope=True)
        row = put(sec, f"{tag}_mundlak", "SUB_m", r, d, "SUB_m", share_slope=True)
        if tag == "group_only":
            w = wild_t(mund_noint, "SUB_m", d)
            row["note"] = f"wild cluster bootstrap p = {w['p_wild']}"
            RES[sec][f"{tag}_mundlak"]["wild_SUB_m"] = w
        info(sec, f"{tag}_sd_country_mean_share", round(float(g.groupby("ISO")["SUB"].mean().std()), 6))
    # the group interaction model with GE x post-socialist added
    r, d = fit(BASE.replace(" + GE + ", " + GE + PS + SUB:PS + GE:PS + "), s)
    for t in ["SUB:GE", "SUB:PS", "GE:PS"]:
        put(sec, "interaction_with_group_and_ge", t, r, d, t)
    put(sec, "interaction_with_group_and_ge", "slope_at_ref_other", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
    put(sec, "interaction_with_group_and_ge", "slope_at_ref_group", r, d, {"SUB": 1, "SUB:PS": 1, "SUB:GE": ref},
        share_slope=True)
    # wild cluster bootstrap with Rademacher weights (9,999 draws) inside the group: the share without SUB x GE, the
    # share at the reference value with SUB x GE (GE centred at the reference value) and the between component
    gc = ps.assign(GEc=ps["GE"] - ref)
    with_int_c = f"lnPM ~ lnENV + SUB + SUB:GEc + GEc + {CTRL} + C(YEAR) + C(SUBREGION)"
    for model, f, data, t in [("group_only_no_interaction", no_int, ps, "SUB"),
                              ("group_only_with_interaction", with_int_c, gc, "SUB"),
                              ("group_only_mundlak", mund_noint, mundlak_frame(ps), "SUB_m")]:
        RES[sec][model][f"wild_rademacher_{t}"] = wild_t(f, t, data, B=B_RADEMACHER, weights="rademacher")


def long_run_within(s, ref):
    sec = "long_run_within"
    # annual two-way fixed effects, for reference
    for model, f in [("annual_twfe", TWFE), ("annual_twfe_no_interaction", TWFE.replace(" + SUB:GE", ""))]:
        r, d = fit(f, s)
        put(sec, model, "SUB", r, d, "SUB", share_slope=True)
        if "SUB:GE" in r.params:
            put(sec, model, "SUB:GE", r, d, "SUB:GE")
            put(sec, model, "slope_at_ref", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
    rm, dm = fit(MUNDLAK, mundlak_frame(s))
    put(sec, "mundlak_reference", "between_slope_at_ref", rm, dm, {"SUB_m": 1, "SUBGE_m": ref}, share_slope=True)
    put(sec, "mundlak_reference", "within_slope_at_ref", rm, dm, {"SUB_w": 1, "SUBGE_w": ref}, share_slope=True)
    # five-year averages, as table_robustness, with country and period effects
    s5 = s.copy()
    s5["PERIOD"] = (s5["YEAR"] // 5) * 5
    num = ["lnPM", "lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]
    a = s5.groupby(["ISO", "PERIOD", "SUBREGION"], as_index=False)[num].mean()
    info(sec, "five_year_cells", int(len(a)))
    info(sec, "five_year_countries_with_2plus_periods", int((a.groupby("ISO")["PERIOD"].nunique() >= 2).sum()))
    r, d = fit(f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CTRL} + C(PERIOD) + C(SUBREGION)", a)
    put(sec, "five_year_pooled", "SUB", r, d, "SUB", note="as the five-year row of Table S8")
    put(sec, "five_year_pooled", "SUB:GE", r, d, "SUB:GE")
    fe = f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CTRL} + C(PERIOD) + C(ISO)"
    r, d = fit(fe, a)
    put(sec, "five_year_country_effects", "SUB", r, d, "SUB", share_slope=True)
    put(sec, "five_year_country_effects", "SUB:GE", r, d, "SUB:GE")
    put(sec, "five_year_country_effects", "slope_at_ref", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
    r, d = fit(fe.replace(" + SUB:GE", ""), a)
    put(sec, "five_year_country_effects_no_interaction", "SUB", r, d, "SUB", share_slope=True)
    # ten-year long differences
    q = s.copy()
    q["SG"] = q["SUB"] * q["GE"]
    cols = num + ["SG"]
    base = q.set_index(["ISO", "YEAR"])[cols]
    lag = base.copy()
    lag.index = pd.MultiIndex.from_arrays([lag.index.get_level_values(0), lag.index.get_level_values(1) + 10],
                                          names=["ISO", "YEAR"])
    dd = (base - lag).dropna().add_prefix("d").reset_index()
    info(sec, "ten_year_pairs", int(len(dd)))
    fd = ("dlnPM ~ dlnENV + dSUB + dSG + dGE + dlnY + dlnY2 + dIND + dURB + dTRADE + dlnDENS + C(YEAR)")
    r, d = fit(fd, dd)
    put(sec, "ten_year_differences", "dSUB", r, d, "dSUB", share_slope=True)
    put(sec, "ten_year_differences", "dSUBxGE", r, d, "dSG")
    put(sec, "ten_year_differences", "slope_at_ref", r, d, {"dSUB": 1, "dSG": ref}, share_slope=True)
    r, d = fit(fd.replace(" + dSG", ""), dd)
    put(sec, "ten_year_differences_no_interaction", "dSUB", r, d, "dSUB", share_slope=True)
    info(sec, "sd_ten_year_change_share", round(float(dd["dSUB"].std()), 6))
    info(sec, "sd_annual_within_share", round(float((s["SUB"] - s.groupby("ISO")["SUB"].transform("mean")).std()), 6))
    # the same with the share interacted with the country mean of GE (GE_m), as in the within part of Table 3
    a = five_year_cells(s)
    r, d = fit(FIVE_GEM, a)
    put(sec, "five_year_country_effects_mean_ge", "SUBGEm", r, d, "SUBGEm")
    put(sec, "five_year_country_effects_mean_ge", "slope_at_ref", r, d, {"SUB": 1, "SUBGEm": ref}, share_slope=True)
    dd = ten_year_pairs(s)
    for model, data, f in [("ten_year_differences_mean_ge", dd, FD_GEM),
                           ("ten_year_nonoverlapping_mean_ge", dd[dd["YEAR"].isin([2013, 2023])], FD_GEM),
                           ("ten_year_country_effects_mean_ge", dd, FD_GEM + " + C(ISO)")]:
        r, d = fit(f, data)
        put(sec, model, "dSUBGEm", r, d, "dSUBGEm")
        put(sec, model, "slope_at_ref", r, d, {"dSUB": 1, "dSUBGEm": ref}, share_slope=True)
    info(sec, "nonoverlapping_pairs_by_end_year",
         {str(k): int(v) for k, v in dd[dd["YEAR"].isin([2013, 2023])]["YEAR"].value_counts().sort_index().items()})


def reporting_changes(s, ref):
    sec = "reporting_changes"
    h = pd.read_csv(pc.HARMONISED, dtype={"DIV": str})
    e = h[h["DIV"] == "05"].copy()
    e["PATTERN"] = e[pc.SECTORS].notna().astype(int).astype(str).agg("".join, axis=1)
    e = e[["ISO", "YEAR", "TIER", "PATTERN"]].assign(YEAR=e["YEAR"] + 1)  # lagged, like the share
    q = s.merge(e.rename(columns={"TIER": "TIER_LAG", "PATTERN": "PATTERN_LAG"}), on=["ISO", "YEAR"], how="left")
    q = q.sort_values(["ISO", "YEAR"]).reset_index(drop=True)
    assert q["PATTERN_LAG"].notna().all()
    state = q["TIER_LAG"].astype(str) + "|" + q["PATTERN_LAG"]
    prev_state = state.groupby(q["ISO"]).shift(1)
    prev_year = q.groupby("ISO")["YEAR"].shift(1)
    q["CHANGE"] = ((q["YEAR"] - prev_year) == 1) & (state != prev_state)
    q["NEWSPELL"] = prev_state.isna() | (state != prev_state)
    q["SPELL"] = q["ISO"] + "_" + q.groupby("ISO")["NEWSPELL"].cumsum().astype(str)
    info(sec, "change_years", int(q["CHANGE"].sum()))
    info(sec, "countries_with_change_year", int(q.loc[q["CHANGE"], "ISO"].nunique()))
    info(sec, "spells", int(q["SPELL"].nunique()))
    info(sec, "countries_with_2plus_spells", int((q.groupby("ISO")["SPELL"].nunique() >= 2).sum()))
    k = q[~q["CHANGE"]]
    r, d = fit(BASE, k)
    put(sec, "without_change_years_baseline", "SUB:GE", r, d, "SUB:GE")
    put(sec, "without_change_years_baseline", "slope_at_ref", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
    for model, data, f in [("without_change_years_twfe", k, TWFE),
                           ("spell_effects", q, TWFE.replace("C(ISO)", "C(SPELL)"))]:
        r, d = fit(f, data)
        put(sec, model, "SUB", r, d, "SUB", share_slope=True)
        put(sec, model, "SUB:GE", r, d, "SUB:GE")
        put(sec, model, "slope_at_ref", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
        r, d = fit(f.replace(" + SUB:GE", ""), data)
        put(sec, f"{model}_no_interaction", "SUB", r, d, "SUB", share_slope=True)
    recording(s, ref, q[["ISO", "YEAR", "CHANGE"]])


def recording(s, ref, change):
    """Within estimates at the reference value without the years of a change in reporting (CHANGE), and also
    without reversed jumps of the share (REV): the changes larger than 0.2 between successive sample years of a
    country that a change of more than 0.1 in the opposite direction follows within two sample years (the count of
    env_federalism.text_numbers), from the year of the jump to the year before the opposite change. Five-year cells
    and ten-year windows that contain such a year are left out. Each estimate is compared with its value on all
    observations, in standard errors of that value."""
    sec = "recording"
    q = s.sort_values(["ISO", "YEAR"]).reset_index(drop=True).merge(change, on=["ISO", "YEAR"], how="left")
    q["CHANGE"] = q["CHANGE"].fillna(False).astype(bool)
    q["d"] = q.groupby("ISO")["SUB"].diff()
    q["d1"], q["d2"] = q.groupby("ISO")["d"].shift(-1), q.groupby("ISO")["d"].shift(-2)
    big = q["d"].abs() > 0.2
    r1 = (np.sign(q["d1"]) == -np.sign(q["d"])) & (q["d1"].abs() > 0.1)
    r2 = (np.sign(q["d2"]) == -np.sign(q["d"])) & (q["d2"].abs() > 0.1)
    rev = big & (r1 | r2)
    q["REV"] = False
    for i in q.index[rev]:
        q.loc[i, "REV"] = True
        if not r1[i]:
            q.loc[i + 1, "REV"] = True
    q["FLAG"] = q["CHANGE"] | q["REV"]
    info(sec, "share_changes_above_0.2", int(big.sum()))
    info(sec, "share_changes_above_0.2_reversed_within_2_years", int(rev.sum()))
    info(sec, "share_changes_above_0.2_in_change_years", int((big & q["CHANGE"]).sum()))
    info(sec, "share_changes_above_0.2_consecutive_years", int((big & (q.groupby("ISO")["YEAR"].diff() == 1)).sum()))
    info(sec, "reversed_jump_years", int(q["REV"].sum()))
    info(sec, "countries_with_reversed_jump", int(q.loc[q["REV"], "ISO"].nunique()))
    a = five_year_cells(q, flags=("CHANGE", "FLAG"))
    dd = ten_year_pairs(q, flags=("CHANGE", "FLAG"))
    ref_vals = {"mundlak": lincom(fit(MUNDLAK, mundlak_frame(s))[0], {"SUB_w": 1, "SUBGE_w": ref}),
                "twfe": lincom(fit(TWFE, s)[0], {"SUB": 1, "SUB:GE": ref}),
                "five_year": lincom(fit(FIVE_GEM, a)[0], {"SUB": 1, "SUBGEm": ref}),
                "ten_year": lincom(fit(FD_GEM, dd)[0], {"dSUB": 1, "dSUBGEm": ref})}
    rise = {}
    for tag, col in [("without_change_years", "CHANGE"), ("without_change_years_and_reversed_jumps", "FLAG")]:
        k = q[~q[col]]
        for est, data, f, w in [("mundlak", mundlak_frame(k), MUNDLAK, {"SUB_w": 1, "SUBGE_w": ref}),
                                ("twfe", k, TWFE, {"SUB": 1, "SUB:GE": ref}),
                                ("five_year", a[~a[col].astype(bool)], FIVE_GEM, {"SUB": 1, "SUBGEm": ref}),
                                ("ten_year", dd[~dd[col].astype(bool)], FD_GEM, {"dSUB": 1, "dSUBGEm": ref})]:
            r, d = fit(f, data)
            row = put(sec, f"{est}_{tag}", "within_slope_at_ref", r, d, w, share_slope=True)
            rise[f"{est}_{tag}"] = round((row["estimate"] - ref_vals[est][0]) / ref_vals[est][1], 6)
    info(sec, "change_in_full_sample_se", rise)
    info(sec, "full_sample_within_slope_at_ref", {k: round(v[0], 6) for k, v in ref_vals.items()})


def ge_percentiles(s, ref, hic=None):
    sec = "ge_percentiles"
    r, d = fit(BASE, s)
    m = mundlak_frame(s)
    rm, dm = fit(MUNDLAK, m)
    obs = {f"obs_P{k}": float(s["GE"].quantile(k / 100)) for k in (10, 25, 50)}
    cm = s.groupby("ISO")["GE"].mean()
    cty = {f"country_P{k}": float(cm.quantile(k / 100)) for k in (10, 25, 50)}
    info(sec, "ge_values", {k: round(v, 6) for k, v in {**obs, **cty, "ref": ref}.items()})
    info(sec, "share_obs_below_ref", round(float((s["GE"] < ref).mean()), 6))
    for lab, g in {**obs, "ref": ref, **cty}.items():
        put(sec, "baseline", f"slope_at_{lab}", r, d, {"SUB": 1, "SUB:GE": g}, share_slope=True,
            note=f"GE = {round(g, 3)}")
    for lab, g in {**cty, "ref": ref}.items():
        put(sec, "mundlak_between", f"slope_at_{lab}", rm, dm, {"SUB_m": 1, "SUBGE_m": g}, share_slope=True,
            note=f"GE = {round(g, 3)}")
        put(sec, "mundlak_within", f"slope_at_{lab}", rm, dm, {"SUB_w": 1, "SUBGE_w": g}, share_slope=True,
            note=f"GE = {round(g, 3)}")
    if hic is not None:  # the median GE of high-income countries (pc.ge_reference)
        info(sec, "ge_hic_median", hic)
        put(sec, "baseline", "slope_at_hic_median", r, d, {"SUB": 1, "SUB:GE": hic}, share_slope=True,
            note=f"GE = {hic}")
        for model, a, b in [("mundlak_between", "SUB_m", "SUBGE_m"), ("mundlak_within", "SUB_w", "SUBGE_w")]:
            put(sec, model, "slope_at_hic_median", rm, dm, {a: 1, b: hic}, share_slope=True, note=f"GE = {hic}")


def first_year_share(s, ref):
    sec = "first_year_share"
    q = s.sort_values(["ISO", "YEAR"]).copy()
    q["SUB_FIRST"] = q.groupby("ISO")["SUB"].transform("first")
    q["K"] = q.groupby("ISO").cumcount()
    q["Y0"] = q.groupby("ISO")["YEAR"].transform("min")
    q = q.assign(SUB=q["SUB_FIRST"])
    for model, data in [("all_years", q), ("from_fourth_sample_year", q[q["K"] >= 3]),
                        ("ten_or_more_years_after_first", q[q["YEAR"] >= q["Y0"] + 10])]:
        r, d = fit(BASE, data)
        put(sec, model, "SUB", r, d, "SUB")
        put(sec, model, "SUB:GE", r, d, "SUB:GE")
        put(sec, model, "slope_at_ref", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
    # share and effectiveness both fixed at the first sample year (SUB0, GE0), current GE kept as a control, from
    # the fourth sample year on; then with ln PM2.5 of the first sample year added; then a cross-section of the
    # country means of ln PM2.5 over the same years on first-year values, sub-region effects and HC3 errors
    first = q.groupby("ISO")[NUM].transform("first")
    q = q.assign(SUB0=first["SUB"], GE0=first["GE"], lnPM0=first["lnPM"])
    later = q[q["K"] >= 3]
    fx = f"lnENV + SUB0 + SUB0:GE0 + GE0 + GE + {CTRL} + C(YEAR) + C(SUBREGION)"
    for model, f in [("first_year_share_and_ge", f"lnPM ~ {fx}"),
                     ("first_year_share_and_ge_first_year_pm", f"lnPM ~ {fx} + lnPM0")]:
        r, d = fit(f, later)
        put(sec, model, "SUB0:GE0", r, d, "SUB0:GE0")
        put(sec, model, "slope_at_ref", r, d, {"SUB0": 1, "SUB0:GE0": ref}, share_slope=True)
        if "lnPM0" in r.params:
            put(sec, model, "lnPM0", r, d, "lnPM0")
    x0 = q[q["K"] == 0].set_index("ISO")[["lnENV", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS", "SUBREGION"]]
    c = later.groupby("ISO").agg(lnPM=("lnPM", "mean"), SUB0=("SUB0", "first"), GE0=("GE0", "first")).join(
        x0.add_suffix("0").rename(columns={"SUBREGION0": "SUBREGION"})).reset_index()
    f = ("lnPM ~ SUB0 + SUB0:GE0 + GE0 + lnENV0 + lnY0 + lnY20 + IND0 + URB0 + TRADE0 + lnDENS0 + C(SUBREGION)")
    r, d = fit(f, c, cov="HC3")
    put(sec, "cross_section_later_means", "SUB0:GE0", r, d, "SUB0:GE0")
    put(sec, "cross_section_later_means", "slope_at_ref", r, d, {"SUB0": 1, "SUB0:GE0": ref}, share_slope=True)


def between_estimators(s, ref):
    sec = "between_estimators"
    num = ["lnPM", "lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]
    c = s.groupby("ISO").agg(**{v: (v, "mean") for v in num}, SUBREGION=("SUBREGION", "first"),
                             NOBS=("YEAR", "size")).reset_index()
    f = f"lnPM ~ lnENV + SUB + SUB:GE + GE + {CTRL} + C(SUBREGION)"
    for model, w in [("country_means", None), ("country_means_weighted", "NOBS")]:
        r, d = fit(f, c, cov="HC1", weights=w)
        put(sec, model, "SUB", r, d, "SUB", share_slope=True)
        put(sec, model, "SUB:GE", r, d, "SUB:GE")
        put(sec, model, "slope_at_ref", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)
        info(sec, f"{model}_R2", round(float(r.rsquared), 6))
    rm, dm = fit(MUNDLAK, mundlak_frame(s))
    put(sec, "mundlak", "SUB_m", rm, dm, "SUB_m", share_slope=True)
    put(sec, "mundlak", "SUBGE_m", rm, dm, "SUBGE_m")
    put(sec, "mundlak", "between_slope_at_ref", rm, dm, {"SUB_m": 1, "SUBGE_m": ref}, share_slope=True)
    put(sec, "mundlak", "within_slope_at_ref", rm, dm, {"SUB_w": 1, "SUBGE_w": ref}, share_slope=True)


def overlap(s, ref):
    """Covariate overlap between weak and strong effectiveness: (i) observations with GE below and at or above the
    reference value, (ii) the countries of the lowest and the highest third of country-mean GE (the thirds of
    Fig. 2). For each variable: means and standard deviations, the normalised difference (difference of means over
    the square root of the mean of the two variances), the log ratio of the standard deviations and the share of
    each group's observations inside the 2.5th to 97.5th percentile range of the other group. For the share, the
    distribution over five bins. Then a logit of membership of group (i) on the same variables, and the baseline on
    the observations with a fitted probability between 0.1 and 0.9 (Crump et al., 2009)."""
    sec = "overlap"
    third = pd.qcut(s.groupby("ISO")["GE"].mean(), 3, labels=False)
    groups = {"obs_below_ref": (s["GE"] < ref, s["GE"] >= ref),
              "country_thirds": (s["ISO"].map(third) == 0, s["ISO"].map(third) == 2)}
    for gname, (weak, strong) in groups.items():
        a, b = s[weak], s[strong]
        out = {"weak": {"obs": int(len(a)), "countries": int(a["ISO"].nunique())},
               "strong": {"obs": int(len(b)), "countries": int(b["ISO"].nunique())}, "variables": {}}
        for v in OVERLAP_VARS:
            ma, mb, sa, sb = a[v].mean(), b[v].mean(), a[v].std(), b[v].std()
            la, ha = a[v].quantile(0.025), a[v].quantile(0.975)
            lb, hb = b[v].quantile(0.025), b[v].quantile(0.975)
            out["variables"][v] = {
                "mean_weak": round(float(ma), 6), "mean_strong": round(float(mb), 6),
                "sd_weak": round(float(sa), 6), "sd_strong": round(float(sb), 6),
                "normalised_difference": round(float((ma - mb) / np.sqrt((sa ** 2 + sb ** 2) / 2)), 6),
                "log_sd_ratio": round(float(np.log(sa / sb)), 6),
                "weak_inside_strong_range": round(float(a[v].between(lb, hb).mean()), 6),
                "strong_inside_weak_range": round(float(b[v].between(la, ha).mean()), 6)}
        bins = {}
        for lab, lo_, hi_ in SHARE_BINS:
            sel = (lambda x: x == 0) if lo_ is None else (lambda x, lo_=lo_, hi_=hi_: (x > lo_) & (x <= hi_))
            bins[lab] = {"weak": round(float(sel(a["SUB"]).mean()), 6), "strong": round(float(sel(b["SUB"]).mean()), 6)}
        out["share_bins"] = bins
        out["weak_countries_mean_share_above_0.25"] = int((a.groupby("ISO")["SUB"].mean() > 0.25).sum())
        out["n_normalised_difference_above_0.25"] = int(sum(abs(x["normalised_difference"]) > 0.25
                                                            for x in out["variables"].values()))
        info(sec, gname, out)
    w = s.assign(W=(s["GE"] < ref).astype(int)).reset_index(drop=True)
    lg = smf.logit("W ~ " + " + ".join(OVERLAP_VARS), data=w).fit(disp=0)
    w["PSCORE"] = lg.predict(w)
    cs = w[w["PSCORE"].between(0.1, 0.9)]
    info(sec, "common_support", {"obs": int(len(cs)), "countries": int(cs["ISO"].nunique()),
                                 "weak_obs": int(cs["W"].sum()), "weak_countries": int(cs.loc[cs["W"] == 1, "ISO"].nunique()),
                                 "pseudo_r2": round(float(lg.prsquared), 6)})
    r, d = fit(BASE, cs)
    put(sec, "common_support", "SUB", r, d, "SUB")
    put(sec, "common_support", "SUB:GE", r, d, "SUB:GE")
    put(sec, "common_support", "slope_at_ref", r, d, {"SUB": 1, "SUB:GE": ref}, share_slope=True)


def channel_refit(s, ref, inputs: Path) -> dict:
    """The country-mean cross-section of Table S11 (ext_specification.channel), refitted here so that the standard errors are
    unrounded: ln exposure from a source on the country means of the regressors of Table 2, column 3, sub-region
    effects, HC3 errors, and the stacked difference between energy and industry and waste (errors clustered by
    country). The refit must reproduce specification_channel.csv and specification_results.json in --inputs to their printed digits."""
    spec_loc = importlib.util.spec_from_file_location("spec_loc", Path(ARGS.main).resolve().parent / "ext_specification.py")
    mod = importlib.util.module_from_spec(spec_loc)
    spec_loc.loader.exec_module(mod)
    g = mod.an.match_iso(mod.an.read_gbdmaps(mod.GBD), pc, set(s["ISO"]))
    keep = g[g["ISO"].isin(set(s["ISO"]))].copy()
    cm = s.groupby("ISO")[["lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS", "lnPM"]].mean()
    cm = cm.add_suffix("_m").reset_index().merge(s.groupby("ISO")["SUBREGION"].first().reset_index(), on="ISO")
    groups = {k: mod.GROUPS[k] for k in ("Waste", "Energy and industry", "Agriculture")}
    for k, cols in groups.items():
        keep[f"X_{k}"] = keep["PM"] * keep[cols].sum(axis=1) / 100
    cm = cm.merge(keep[["ISO"] + [f"X_{k}" for k in groups]], on="ISO", how="inner")
    cm["SUBGE"] = cm["SUB_m"] * cm["GE_m"]
    rhs = "SUB_m + SUBGE + GE_m + lnENV_m + lnY_m + lnY2_m + IND_m + URB_m + TRADE_m + lnDENS_m + C(SUBREGION)"
    ch = pd.read_csv(inputs / "specification_channel.csv")
    out = {}
    for k in groups:
        dd = cm.assign(Y=np.log(cm[f"X_{k}"].where(cm[f"X_{k}"] > 0))).dropna(subset=["Y"])
        r = smf.ols(f"Y ~ {rhs}", data=dd).fit(cov_type="HC3")
        est, se, p = lincom(r, {"SUB_m": 1, "SUBGE": ref})
        row = ch[ch["Outcome"] == f"ln exposure from {k.lower()}"].iloc[0]
        assert int(r.nobs) == int(row["N"]) and round(pct(est), 1) == row["ME25"] and round(p, 4) == row["p_ME25"], k
        out[k] = {"N": int(r.nobs), "coefficient": est, "se": se, "p": p}
    st = []
    for k, y in [("A_waste", "X_Waste"), ("B_energy_industry", "X_Energy and industry")]:
        x = cm.copy()
        x["Y"], x["K"] = np.log(x[y].where(x[y] > 0)), k
        st.append(x)
    st = pd.concat(st).dropna(subset=["Y"])
    r = smf.ols(f"Y ~ C(K) * ({rhs})", data=st).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(st["ISO"])[0]})
    est, se, p = lincom(r, {"C(K)[T.B_energy_industry]:SUB_m": 1, "C(K)[T.B_energy_industry]:SUBGE": ref})
    rec = json.loads((inputs / "specification_results.json").read_text(encoding="utf8"))["channel"][
        "stacked_energy_industry_minus_waste"]
    assert (round(est, 3), round(se, 3), round(p, 4)) == (rec["me_diff"], rec["se"], rec["p"]), (est, se, p, rec)
    out["stacked"] = {"coefficient": est, "se": se, "p": p}
    return out


def source_power(s, ref, inputs: Path):
    """
    Minimum detectable effects at the 5% level (two-sided): (z_0.975 + z_0.80) x SE for 80% power and z_0.975 x SE
    for 50% power, on the coefficient scale and as the percentage change for a share 25 pp higher. For the
    associations at -0.355 of the cross-section of Table S11 (refitted by channel_refit, so the standard errors are
    unrounded), for the stacked difference between energy and industry and waste, and for the association of the
    share inside the post-socialist group (post_socialist, group_only_no_interaction). Also the power of each test
    at its own estimate.
    """
    sec = "source_power"
    k80, k50 = Z975 + Z80, Z975

    def power(b, se):
        z = abs(b) / se
        return round(float(stats.norm.cdf(z - Z975) + stats.norm.cdf(-z - Z975)), 6)

    def entry(n, b, se, p, effect=True):
        e = {"N": n, "coefficient": round(float(b), 6), "se": round(float(se), 6), "p": round(float(p), 6),
             "mde_coefficient": round(k80 * se, 6), "mde50_coefficient": round(k50 * se, 6),
             "power_at_estimate": power(b, se)}
        if effect:
            e.update({"effect25_pct": round(pct(b), 6), "mde_effect25_pct": round(pct(k80 * se), 6),
                      "mde50_effect25_pct": round(pct(k50 * se), 6)})
        return e

    fits = channel_refit(s, ref, inputs)
    out = {"multiplier": round(k80, 6), "multiplier_50": round(k50, 6)}
    for lab, k in [("waste", "Waste"), ("energy_and_industry", "Energy and industry"), ("agriculture", "Agriculture")]:
        f = fits[k]
        out[lab] = entry(f["N"], f["coefficient"], f["se"], f["p"])
    f = fits["stacked"]
    out["stacked_difference"] = entry(None, f["coefficient"], f["se"], f["p"], effect=False)
    del out["stacked_difference"]["N"]
    g = RES["post_socialist"]["group_only_no_interaction"]
    t = g["terms"]["SUB"]
    out["postsocialist_group"] = entry(g["N"], t["estimate"], t["se"], t["p"])
    out["postsocialist_group"]["countries"] = g["countries"]
    RES[sec] = out


# ----------------------------------------------------------------------------------------------- output
def trace_json(x, path=""):
    """Numbers of the info blocks and of source_power, with their locators in bw_results.json."""
    if isinstance(x, dict):
        for k, v in x.items():
            yield from trace_json(v, f"{path}/{k}" if path else str(k))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from trace_json(v, f"{path}/{i}")
    elif isinstance(x, (int, float)) and not isinstance(x, bool):
        yield path, x


def trace_rows():
    """Printed form of each number (3 decimals for coefficients and p-values, 1 for percentages)."""
    out = []
    for r in ROWS:
        loc = f"{r['section']}/{r['model']}/terms/{r['term']}"
        for q, dec in [("estimate", 3), ("se", 3), ("p", 3), ("ci_lo", 3), ("ci_hi", 3), ("effect25_pct", 1),
                       ("effect25_lo", 1), ("effect25_hi", 1)]:
            if q in r and r[q] is not None and not (isinstance(r[q], float) and np.isnan(r[q])):
                v = r[q]
                out.append({"key": f"{r['key']}/{q}", "printed": f"{v:.{dec}f}".replace("-", "−"),
                            "file": "bw_results.json", "locator": f"{loc}/{q}", "value": v})
        for q in ("N", "countries"):
            out.append({"key": f"{r['key']}/{q}", "printed": f"{r[q]:,}", "file": "bw_results.json",
                        "locator": f"{r['section']}/{r['model']}/{q}", "value": r[q]})
    extra = {"sample": RES["sample"], "source_power": RES.get("source_power", {}),
             "moderator_tests": RES.get("moderator_tests", {})}
    extra.update({f"{sec}/info": v["info"] for sec, v in RES.items() if isinstance(v, dict) and "info" in v})
    for model in ("group_only_no_interaction", "group_only_with_interaction", "group_only_mundlak"):
        for w in ("wild_SUB", "wild_SUB_m", "wild_rademacher_SUB", "wild_rademacher_SUB_m"):
            if w in RES["post_socialist"].get(model, {}):
                extra[f"post_socialist/{model}/{w}"] = RES["post_socialist"][model][w]
    for loc, v in trace_json(extra):
        dec = 0 if isinstance(v, int) else 3
        out.append({"key": loc, "printed": (f"{v:,}" if dec == 0 else f"{v:.3f}").replace("-", "−"),
                    "file": "bw_results.json", "locator": loc, "value": v})
    return pd.DataFrame(out).drop_duplicates(subset=["locator"])


NAMES = {}


def main():
    NAMES.update(country_names(Path(ARGS.inputs)))
    p = pc.build_panel()
    s = pc._sample(p).copy()
    gref = pc.ge_reference(p)
    ref = gref["LMIC"]
    z = pc._sample(pc.gaps_as_zero(p))
    med_lny = float(z.loc[z["ISO"].map(pc.income_groups()).isin(LMIC), "lnY"].median())
    RES["sample"] = {"N": int(len(s)), "countries": int(s["ISO"].nunique()), "ge_ref": ref,
                     "years": [int(s["YEAR"].min()), int(s["YEAR"].max())]}
    # the published baseline and Table 3, reproduced
    r, _ = fit(BASE, s)
    rm, _ = fit(MUNDLAK, mundlak_frame(s))
    RES["sample"]["reproduced"] = {"baseline_SUB": round(float(r.params["SUB"]), 3),
                                   "baseline_SUB:GE": round(float(r.params["SUB:GE"]), 3),
                                   "mundlak_SUB_m": round(float(rm.params["SUB_m"]), 3),
                                   "mundlak_SUBGE_m": round(float(rm.params["SUBGE_m"]), 3),
                                   "mundlak_SUB_w": round(float(rm.params["SUB_w"]), 3),
                                   "mundlak_SUBGE_w": round(float(rm.params["SUBGE_w"]), 3)}
    income_moderator(s, ref, med_lny)
    influence(s, ref)
    post_socialist(s, ref)
    long_run_within(s, ref)
    reporting_changes(s, ref)
    ge_percentiles(s, ref, hic=gref["HIC"])
    first_year_share(s, ref)
    between_estimators(s, ref)
    overlap(s, ref)
    source_power(s, ref, Path(ARGS.inputs))
    t = pd.DataFrame(ROWS)
    t.to_csv(OUT / "bw_results.csv", index=False)
    (OUT / "bw_results.json").write_text(json.dumps(RES, indent=1, default=str), encoding="utf8")
    trace_rows().to_csv(OUT / "bw_trace.csv", index=False, encoding="utf8")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    cols = ["key", "estimate", "se", "p", "effect25_pct", "N", "countries"]
    print(t[[c for c in cols if c in t.columns]].to_string(index=False))
    print(json.dumps(RES["sample"], indent=1))


if __name__ == "__main__":
    main()
