"""
Environmental-spending study, instrumental-variable estimates of the association between the subnational share of environmental
spending (SUB) and ln PM2.5 exposure.

    python paperC_ext_iv.py [OUT_DIR]

Reads the panel of env_federalism.py (build_panel, _sample, FEDERAL, CONTROLS) and the Regional
Authority Index (Hooghe et al. 2016), country file of April 2021:
https://garymarks.web.unc.edu/wp-content/uploads/sites/13018/2021/04/RAI_country-april-2021.xlsx
(SHA-256 4ae1860a62b23ee0f0adaf5f33beb648d878642a7c5829a1d0a04203ed60c610).

Writes tabIV_results.csv and iv_details.json.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
from scipy import stats
from linearmodels.iv import IV2SLS, IVLIML, IVGMM

ROOT = Path(__file__).resolve().parent
HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "output"
OUT.mkdir(parents=True, exist_ok=True)
RAI_FILE = ROOT / "data_ext" / "lab" / "RAI_country-april-2021.xlsx"
RAI_SHA256 = "4ae1860a62b23ee0f0adaf5f33beb648d878642a7c5829a1d0a04203ed60c610"

spec = importlib.util.spec_from_file_location("pc", ROOT / "env_federalism.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

EXOG = f"lnENV + GE + {pc.CONTROLS} + C(YEAR) + C(SUBREGION)"
EXOG_MEANS = f"lnENV + GE + {pc.CONTROLS} + C(SUBREGION)"
GRID = np.round(np.arange(-5, 5.0001, 0.005), 3)


def pct(b):
    return round(100 * (np.exp(0.25 * b) - 1), 1)


def load() -> pd.DataFrame:
    s = pc._sample(pc.build_panel()).copy()
    s["FED"] = s["ISO"].isin(pc.FEDERAL).astype(int)
    assert hashlib.sha256(RAI_FILE.read_bytes()).hexdigest() == RAI_SHA256, "RAI file differs"
    rai = pd.read_excel(RAI_FILE).rename(columns={"abbr_country": "ISO"})
    r = rai[rai["year"].between(1990, 1995)].sort_values(["ISO", "year"]).groupby("ISO").first()
    s["RAI90"] = s["ISO"].map(r["n_RAI"])
    return s


def means(s: pd.DataFrame) -> pd.DataFrame:
    num = ["lnPM", "SUB", "lnENV", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS", "FED", "RAI90"]
    m = s.groupby("ISO")[num].mean()
    m["SUBREGION"] = s.groupby("ISO")["SUBREGION"].first()
    return m.reset_index()


def matrices(d: pd.DataFrame, exog: str, z: list):
    W = patsy.dmatrix(exog, d, return_type="dataframe")
    y, x, Z =d["lnPM"].values, d["SUB"].values, d[z].values
    return y, x, Z, W


def partial(v, W):
    b, *_ = np.linalg.lstsq(W, v, rcond=None)
    return v - W @ b


def cluster_scores(Zt, u, g):
    """Sum of z_i u_i within clusters, one row per cluster."""
    S = pd.DataFrame(Zt * u[:, None]).groupby(g).sum().values
    return S


def ar_set(y, x, Z, W, g, k_full):
    """Anderson-Rubin 95% confidence set for beta by inversion, cluster-robust, chi2(q)."""
    Wv = W.values
    yt, xt = partial(y, Wv), partial(x, Wv)
    Zt = np.column_stack([partial(Z[:, j], Wv) for j in range(Z.shape[1])])
    ZZi = np.linalg.inv(Zt.T @ Zt)
    py, px = ZZi @ Zt.T @ yt, ZZi @ Zt.T @ xt
    uy, ux = yt - Zt @ py, xt - Zt @ px
    Sy, Sx = cluster_scores(Zt, uy, g), cluster_scores(Zt, ux, g)
    G, N, q = len(Sy), len(y), Z.shape[1]
    c = G / (G - 1) * (N - 1) / (N - k_full)
    keep, pvals = [], []
    for b in GRID:
        pi = py - b * px
        S = Sy - b * Sx
        V = c * ZZi @ (S.T @ S) @ ZZi
        w = float(pi @ np.linalg.solve(V, pi))
        pv = float(stats.chi2.sf(w, q))
        pvals.append(pv)
        if pv > 0.05:
            keep.append(b)
    keep = np.array(keep)
    if keep.size == 0:
        return {"set": "empty"}, None
    # intervals of accepted grid points
    breaks = np.where(np.diff(keep) > 0.0051)[0]
    pieces = np.split(keep, breaks + 1)
    ivs = [[float(pc_[0]), float(pc_[-1])] for pc_ in pieces]
    unbounded = keep[0] <= GRID[0] + 1e-9 or keep[-1] >= GRID[-1] - 1e-9
    p0 = pvals[int(np.argmin(np.abs(GRID)))]
    return {"intervals": ivs, "touches_grid_edge": bool(unbounded), "p_beta0": round(p0, 4)}, ivs


def first_stage(x, Z, W, g, k_full):
    Wv = W.values
    xt = partial(x, Wv)
    Zt = np.column_stack([partial(Z[:, j], Wv) for j in range(Z.shape[1])])
    ZZi = np.linalg.inv(Zt.T @ Zt)
    pi = ZZi @ Zt.T @ xt
    u = xt - Zt @ pi
    S = cluster_scores(Zt, u, g)
    G, N, q = len(S), len(x), Z.shape[1]
    V = G / (G - 1) * (N - 1) / (N - k_full) * ZZi @ (S.T @ S) @ ZZi
    F = float(pi @ np.linalg.solve(V, pi)) / q
    return pi, np.sqrt(np.diag(V)), F


def conley_uci(y, x, z, W, g, k_full, gmax):
    """Union of 95% CIs for beta over a direct effect gamma of the single instrument in [-gmax, gmax]."""
    Wv = W.values
    yt, xt, zt = partial(y, Wv), partial(x, Wv), partial(z, Wv)
    lo, hi, rows = np.inf, -np.inf, []
    for gam in np.linspace(-gmax, gmax, 81):
        yy = yt - gam * zt
        b = float(zt @ yy / (zt @ xt))
        u = yy - xt * b
        S = pd.Series(zt * u).groupby(g).sum().values
        G, N = len(S), len(y)
        c = G / (G - 1) * (N - 1) / (N - k_full)
        se = float(np.sqrt(c * (S @ S)) / abs(zt @ xt))
        lo, hi = min(lo, b - 1.96 * se), max(hi, b + 1.96 * se)
    return [round(lo, 3), round(hi, 3)]


def estimate(name, d, exog, z, cluster=True):
    d = d.dropna(subset=["lnPM", "SUB"] + z + ["lnENV", "GE", "lnY", "IND", "URB", "TRADE", "lnDENS", "SUBREGION"]).copy()
    y, x, Z, W = matrices(d, exog, z)
    g = pd.factorize(d["ISO"])[0] if cluster else np.arange(len(d))
    k_full = np.linalg.matrix_rank(W.values) + Z.shape[1]
    pi, pise, F = first_stage(x, Z, W, g, k_full)
    cov = dict(cov_type="clustered", clusters=g) if cluster else dict(cov_type="robust")
    m = IV2SLS(d["lnPM"], W, d[["SUB"]], d[z]).fit(**cov)
    res = {"Model": name, "N": len(d), "Countries": d["ISO"].nunique(), "Instruments": " + ".join(z),
           "FS_coef": "; ".join(f"{a:.4f} ({b:.4f})" for a, b in zip(pi, pise)), "Effective_F": round(F, 1),
           "b_2SLS": round(float(m.params["SUB"]), 3), "se_2SLS": round(float(m.std_errors["SUB"]), 3),
           "p_2SLS": round(float(m.pvalues["SUB"]), 3), "pct25_2SLS": pct(float(m.params["SUB"]))}
    if len(z) > 1:
        l = IVLIML(d["lnPM"], W, d[["SUB"]], d[z]).fit(**cov)
        gm = IVGMM(d["lnPM"], W, d[["SUB"]], d[z]).fit(**cov)
        res.update({"b_LIML": round(float(l.params["SUB"]), 3), "se_LIML": round(float(l.std_errors["SUB"]), 3),
                    "HansenJ": round(float(gm.j_stat.stat), 3), "HansenJ_p": round(float(gm.j_stat.pval), 3)})
    ar, ivs = ar_set(y, x, Z, W, g, k_full)
    res["AR_set"] = json.dumps(ar["intervals"]) if ivs else "empty"
    res["AR_touches_edge"] = ar.get("touches_grid_edge")
    res["AR_p_beta0"] = ar.get("p_beta0")
    if ivs:
        res["AR_set_pct25"] = json.dumps([[pct(a), pct(b)] for a, b in ar["intervals"]])
    ols = IV2SLS(d["lnPM"], pd.concat([W, d[["SUB"]]], axis=1), None, None).fit(**cov)
    res.update({"b_OLS_same_sample": round(float(ols.params["SUB"]), 3), "se_OLS": round(float(ols.std_errors["SUB"]), 3),
                "pct25_OLS": pct(float(ols.params["SUB"]))})
    if z == ["FED"]:  # Conley bounds for the federal instrument (P1, P2, P4)
        res["Conley_UCI_0.05"] = json.dumps(conley_uci(y, x, Z[:, 0], W, g, k_full, 0.05))
        res["Conley_UCI_0.10"] = json.dumps(conley_uci(y, x, Z[:, 0], W, g, k_full, 0.10))
        res["gamma_zeroing_beta"] = round(float(pi[0] * m.params["SUB"]), 3)
    return res, d


def main():
    s = load()
    med = float(s["GE"].median())
    low = s[s["GE"] < med]
    rows, info = [], {"GE_median_sample": round(med, 3)}
    for name, d, exog, z, cl in [
        ("P1 Low-GE half, FED", low, EXOG, ["FED"], True),
        ("P2 Full sample, FED", s, EXOG, ["FED"], True),
        ("P3a RAI sample, RAI90", s, EXOG, ["RAI90"], True),
        ("P3b RAI sample, FED + RAI90", s, EXOG, ["FED", "RAI90"], True),
        ("P4 Country means, low-GE half, FED", means(low), EXOG_MEANS, ["FED"], False),
        ("P4 Country means, full sample, FED", means(s), EXOG_MEANS, ["FED"], False),
    ]:
        r, dd = estimate(name, d, exog, z, cl)
        rows.append(r)
        info[name] = {"countries": sorted(dd["ISO"].unique().tolist()),
                      "federal_in_sample": sorted(dd.loc[dd["FED"] == 1, "ISO"].unique().tolist())}
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "tabIV_results.csv", index=False)
    (OUT / "iv_details.json").write_text(json.dumps(info, indent=1), encoding="utf8")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(t.T)


if __name__ == "__main__":
    main()
