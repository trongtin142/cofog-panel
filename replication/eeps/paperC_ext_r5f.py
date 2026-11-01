"""Environmental-spending study: is the association specific to environmental spending?

    python paperC_ext_r5f.py [--main PATH_TO_env_federalism.py] [--out DIR]

(1) Subnational share of each COFOG division 01-10 in place of the environmental share (Table 2, column 3).
(2) The baseline on the same observations.
(3) Environmental share and the share of one other division together, with Wald tests of the differences.
(4) "Excess" environmental decentralisation: SUB - SUBTOT, the residual of SUB on SUBTOT, and the residual of SUB
    on the mean (and first principal component) of the nine other division shares.
All with lnENV, GE, the controls, year and sub-region effects, and standard errors clustered by country, for all
countries and without the countries in which only central government reports environmental spending.
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
ap.add_argument("--out", default=str(HERE / "output"))
ap.add_argument("--figure-only", action="store_true")
args = ap.parse_args()

spec = importlib.util.spec_from_file_location("pc", args.main)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)
OUT = Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)

DIVS = {"01": "General public services", "02": "Defence", "03": "Public order and safety",
        "04": "Economic affairs", "05": "Environmental protection", "06": "Housing and community amenities",
        "07": "Health", "08": "Recreation, culture and religion", "09": "Education", "10": "Social protection"}
OTHER = [d for d in DIVS if d != "05"]
FX = f"{pc.CONTROLS} + C(YEAR) + C(SUBREGION)"


def lincom(r, w: dict) -> dict:
    names = list(r.params.index)
    R = np.zeros(len(names))
    for k, v in w.items():
        R[names.index(k)] = v
    est = float(R @ r.params.values)
    se = float(np.sqrt(R @ r.cov_params().values @ R))
    return {"est": est, "se": se, "p": float(2 * stats.norm.sf(abs(est / se)))}


def wald2(r, rows: list) -> dict:
    names = list(r.params.index)
    R = np.zeros((len(rows), len(names)))
    for i, w in enumerate(rows):
        for k, v in w.items():
            R[i, names.index(k)] = v
    b = R @ r.params.values
    V = R @ r.cov_params().values @ R.T
    chi2 = float(b @ np.linalg.solve(V, b))
    return {"chi2": round(chi2, 3), "df": len(rows), "p": round(float(stats.chi2.sf(chi2, len(rows))), 4)}


def me25(r, v: str, g: float) -> dict:
    m = lincom(r, {v: 1, f"{v}:GE": g})
    pct = lambda x: 100 * (np.exp(0.25 * x) - 1)
    return {"ME25": round(pct(m["est"]), 1), "ME25_lo": round(pct(m["est"] - 1.96 * m["se"]), 1),
            "ME25_hi": round(pct(m["est"] + 1.96 * m["se"]), 1), "p_ME25": round(m["p"], 4)}


def holm(ps: list) -> list:
    order = np.argsort(ps)
    adj = np.empty(len(ps))
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        adj[i] = run
    return [round(float(a), 4) for a in adj]


# figure -----------------------------------------------------------------------------------------------------
def figure(tab: pd.DataFrame, out: Path):
    """Ten divisions: association at the median GE of LMICs (left) and interaction with GE (right), two samples."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"], "font.size": 7})
    fig, axes = plt.subplots(1, 2, figsize=(119 / 25.4, 3.4), sharey=True)
    order = list(DIVS)[::-1]
    y0 = {d: i for i, d in enumerate(order)}
    panels = [("ME25", "ME25_lo", "ME25_hi", (-30, 40),
               "Association at the median GE of LMICs\n(% change for a share 25 pp higher)"),
              ("bGE", None, None, (-1.2, 0.8), "Interaction with GE\n(coefficient)")]
    for ax, (c, lo, hi, lim, xl) in zip(axes, panels):
        for sname, off, mk in (("all", 0.17, "o"), ("excl_central_only", -0.17, "^")):
            t = tab[tab["Sample"] == sname].set_index("Division")
            for d in order:
                est = t.loc[d, c]
                a = t.loc[d, lo] if lo else est - 1.96 * t.loc[d, "se_bGE"]
                b = t.loc[d, hi] if hi else est + 1.96 * t.loc[d, "se_bGE"]
                col = "#2a78d6" if d == "05" else "#4a4a4a"  # environmental protection in the blue of Figs 1-2
                y = y0[d] + off
                ax.plot([max(a, lim[0]), min(b, lim[1])], [y, y], color=col, lw=0.9)
                if a < lim[0]:
                    ax.annotate("", xy=(lim[0], y), xytext=(lim[0] + 0.06 * (lim[1] - lim[0]), y),
                                arrowprops=dict(arrowstyle="->", color=col, lw=0.8))
                if b > lim[1]:
                    ax.annotate("", xy=(lim[1], y), xytext=(lim[1] - 0.06 * (lim[1] - lim[0]), y),
                                arrowprops=dict(arrowstyle="->", color=col, lw=0.8))
                if lim[0] <= est <= lim[1]:
                    ax.plot(est, y, mk, color=col, ms=3.2, mfc=col if sname == "all" else "white", mew=0.8)
        ax.axvline(0, color="#999999", lw=0.6)
        ax.set_xlim(*lim)
        ax.set_xlabel(xl)
        for sp_ in ("top", "right"):
            ax.spines[sp_].set_visible(False)
    axes[0].set_yticks(range(len(order)))
    axes[0].set_yticklabels([f"{d} {DIVS[d]}" for d in order])
    h1, = axes[1].plot([], [], "o", color="#4a4a4a", ms=3.2, label="All countries")
    h2, = axes[1].plot([], [], "^", color="#4a4a4a", ms=3.2, mfc="white", mew=0.8,
                       label="Without central-only countries")
    fig.legend(handles=[h1, h2], loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.6, -0.01))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(out / "r5f_fig_divisions.png", dpi=300)
    fig.savefig(out / "r5f_fig_divisions.pdf")


if args.figure_only:
    figure(pd.read_csv(OUT / "r5f_divisions.csv", dtype={"Division": str}), OUT)
    raise SystemExit(0)

# ---------------------------------------------------------------------------------------------------------
p = pc.build_panel()
G = pc.ge_reference(p)["LMIC"]
px = pc.add_other_shares(p)
h = pd.read_csv(pc.HARMONISED, dtype={"DIV": str})
for d in DIVS:
    e = h[h["DIV"] == d].copy()
    sh = e[["ISO", "YEAR"]].assign(**{f"SH{d}": pc.subnational_share(e).values})
    sh["YEAR"] = sh["YEAR"] + 1
    px = px.merge(sh, on=["ISO", "YEAR"], how="left")
    never = e.groupby("ISO").apply(lambda g: not (g["EVER_SG"].astype(bool).any() or g["EVER_LG"].astype(bool).any()),
                                   include_groups=False)
    px[f"NOSUB{d}"] = px["ISO"].map(never).fillna(True).astype(int)
# Coverage gaps cover central government alone for every function: their shares are missing for every division
for d in DIVS:
    px.loc[px["COVGAP"] == 1, f"SH{d}"] = np.nan
check05 = px.dropna(subset=["SUB", "SH05"])
assert np.allclose(check05["SUB"], check05["SH05"]), "division 05 share differs from SUB"

S = {"all": px[px["COMPLETE_L1"]], "excl_central_only": px[px["COMPLETE_L1"] & (px["NOSUB"] == 0)]}
NEED = pc.BASE_NEEDED

rows, both = [], []
for sname, s in S.items():
    for d in DIVS:
        v = "SUB" if d == "05" else f"SH{d}"
        r, dd = pc._fit(f"lnPM ~ lnENV + {v} + {v}:GE + GE + {FX}", s, NEED + [v])
        row = {"Sample": sname, "Division": d, "Function": DIVS[d], "N": int(r.nobs),
               "Countries": int(dd["ISO"].nunique()),
               "Countries_never_subnational": int(dd.loc[dd[f"NOSUB{d}"] == 1, "ISO"].nunique()),
               "mean_share": round(float(dd[v].mean()), 3), "sd_share": round(float(dd[v].std()), 3),
               "b": round(r.params[v], 3), "se_b": round(r.bse[v], 3),
               "bGE": round(r.params[f"{v}:GE"], 3), "se_bGE": round(r.bse[f"{v}:GE"], 3),
               "p_bGE": round(r.pvalues[f"{v}:GE"], 4), **me25(r, v, G)}
        if d != "05":
            r0, d0 = pc._fit(pc.BASE, s, NEED + ["SUB", v])
            row.update({"N_same": int(r0.nobs), "ME25_SUB_same": me25(r0, "SUB", G)["ME25"],
                        "p_ME25_SUB_same": me25(r0, "SUB", G)["p_ME25"],
                        "bGE_SUB_same": round(r0.params["SUB:GE"], 3)})
            rb, db = pc._fit(f"lnPM ~ lnENV + SUB + SUB:GE + GE + {v} + {v}:GE + {FX}", s, NEED + ["SUB", v])
            dme = lincom(rb, {"SUB": 1, "SUB:GE": G, v: -1, f"{v}:GE": -G})
            dge = lincom(rb, {"SUB:GE": 1, f"{v}:GE": -1})
            both.append({"Sample": sname, "Division": d, "Function": DIVS[d], "N": int(rb.nobs),
                         "Countries": int(db["ISO"].nunique()),
                         "ME25_SUB": me25(rb, "SUB", G)["ME25"], "p_ME25_SUB": me25(rb, "SUB", G)["p_ME25"],
                         "ME25_other": me25(rb, v, G)["ME25"], "p_ME25_other": me25(rb, v, G)["p_ME25"],
                         "bGE_SUB": round(rb.params["SUB:GE"], 3), "p_bGE_SUB": round(rb.pvalues["SUB:GE"], 4),
                         "bGE_other": round(rb.params[f"{v}:GE"], 3),
                         "p_bGE_other": round(rb.pvalues[f"{v}:GE"], 4),
                         "diff_ME": round(dme["est"], 3), "p_diff_ME": round(dme["p"], 4),
                         "diff_GE": round(dge["est"], 3), "p_diff_GE": round(dge["p"], 4),
                         **{f"joint_{k}": x for k, x in wald2(rb, [{"SUB": 1, "SUB:GE": G, v: -1, f"{v}:GE": -G},
                                                                   {"SUB:GE": 1, f"{v}:GE": -1}]).items()}})
        rows.append(row)

tab = pd.DataFrame(rows)
tb = pd.DataFrame(both)
for sname in S:
    m = tab["Sample"] == sname
    o = m & (tab["Division"] != "05")
    tab.loc[o, "p_ME25_holm9"] = holm(tab.loc[o, "p_ME25"].tolist())
    tab.loc[o, "p_bGE_holm9"] = holm(tab.loc[o, "p_bGE"].tolist())
    mb = tb["Sample"] == sname
    tb.loc[mb, "p_diff_ME_holm9"] = holm(tb.loc[mb, "p_diff_ME"].tolist())
    tb.loc[mb, "p_diff_GE_holm9"] = holm(tb.loc[mb, "p_diff_GE"].tolist())
    tab.loc[m, "rank_ME25"] = tab.loc[m, "ME25"].rank(ascending=False).astype(int)
    tab.loc[m, "rank_bGE_most_negative"] = tab.loc[m, "bGE"].rank(ascending=True).astype(int)
tab.to_csv(OUT / "r5f_divisions.csv", index=False)
tb.to_csv(OUT / "r5f_both.csv", index=False)

# (4) Excess environmental decentralisation ------------------------------------------------------------------
ex = []
for sname, s in S.items():
    s = s.copy()
    # Table 4 row for reference: adds SUBTOT and its GE interaction
    rt, dt = pc._fit(f"lnPM ~ lnENV + SUB + SUB:GE + GE + SUBTOT + SUBTOT:GE + {FX}", s, NEED + ["SUB", "SUBTOT"])
    ex.append({"Sample": sname, "Measure": "Reference: SUB with SUBTOT and SUBTOT x GE added", "N": int(rt.nobs),
               "Countries": int(dt["ISO"].nunique()), "b": round(rt.params["SUB"], 3), "se_b": round(rt.bse["SUB"], 3), "p_b": round(rt.pvalues["SUB"], 4),
               "bGE": round(rt.params["SUB:GE"], 3), "se_bGE": round(rt.bse["SUB:GE"], 3),
               "p_bGE": round(rt.pvalues["SUB:GE"], 4), **me25(rt, "SUB", G)})
    r0, d0 = pc._fit(pc.BASE, s, NEED + ["SUB", "SUBTOT"])
    ex.append({"Sample": sname, "Measure": "Reference: SUB, same sample", "N": int(r0.nobs),
               "Countries": int(d0["ISO"].nunique()), "b": round(r0.params["SUB"], 3), "se_b": round(r0.bse["SUB"], 3), "p_b": round(r0.pvalues["SUB"], 4),
               "bGE": round(r0.params["SUB:GE"], 3), "se_bGE": round(r0.bse["SUB:GE"], 3),
               "p_bGE": round(r0.pvalues["SUB:GE"], 4), **me25(r0, "SUB", G)})
    base = s.dropna(subset=NEED + ["SUB", "SUBTOT"]).copy()
    base["DSUB"] = base["SUB"] - base["SUBTOT"]
    X = np.column_stack([np.ones(len(base)), base["SUBTOT"]])
    coef = np.linalg.lstsq(X, base["SUB"].values, rcond=None)[0]
    base["RSUB"] = base["SUB"] - X @ coef
    corr_tot = float(base["SUB"].corr(base["SUBTOT"]))
    for v, lab in (("DSUB", "E1: SUB minus SUBTOT"), ("RSUB", "E2: residual of SUB on SUBTOT")):
        r, dd = pc._fit(f"lnPM ~ lnENV + {v} + {v}:GE + GE + {FX}", base, NEED + [v])
        ex.append({"Sample": sname, "Measure": lab, "N": int(r.nobs), "Countries": int(dd["ISO"].nunique()),
                   "b": round(r.params[v], 3), "se_b": round(r.bse[v], 3), "p_b": round(r.pvalues[v], 4), "bGE": round(r.params[f"{v}:GE"], 3),
                   "se_bGE": round(r.bse[f"{v}:GE"], 3), "p_bGE": round(r.pvalues[f"{v}:GE"], 4),
                   **me25(r, v, G), "aux_slope": round(float(coef[1]), 3) if v == "RSUB" else None,
                   "corr_SUB_SUBTOT": round(corr_tot, 3)})
    oth = [f"SH{d}" for d in OTHER]
    b9 = s.dropna(subset=NEED + ["SUB"] + oth).copy()
    b9["M9"] = b9[oth].mean(axis=1)
    Z = (b9[oth] - b9[oth].mean()) / b9[oth].std().replace(0, np.nan)
    Z = Z.dropna(axis=1)
    w, V = np.linalg.eigh(np.cov(Z.values.T))
    pc1 = Z.values @ V[:, -1]
    b9["PC1"] = pc1 if np.corrcoef(pc1, b9["M9"])[0, 1] > 0 else -pc1
    share_pc1 = float(w[-1] / w.sum())
    r0, d0 = pc._fit(pc.BASE, b9, NEED + ["SUB"])
    ex.append({"Sample": sname, "Measure": "Reference: SUB, sample with all nine other shares", "N": int(r0.nobs),
               "Countries": int(d0["ISO"].nunique()), "b": round(r0.params["SUB"], 3), "se_b": round(r0.bse["SUB"], 3), "p_b": round(r0.pvalues["SUB"], 4),
               "bGE": round(r0.params["SUB:GE"], 3), "se_bGE": round(r0.bse["SUB:GE"], 3),
               "p_bGE": round(r0.pvalues["SUB:GE"], 4), **me25(r0, "SUB", G)})
    for z, lab in (("M9", "E3: residual of SUB on the mean of the nine other shares"),
                   ("PC1", "E3b: residual of SUB on the first principal component of the nine other shares")):
        X = np.column_stack([np.ones(len(b9)), b9[z]])
        c = np.linalg.lstsq(X, b9["SUB"].values, rcond=None)[0]
        b9["R"] = b9["SUB"] - X @ c
        r, dd = pc._fit(f"lnPM ~ lnENV + R + R:GE + GE + {FX}", b9, NEED + ["R"])
        ex.append({"Sample": sname, "Measure": lab, "N": int(r.nobs), "Countries": int(dd["ISO"].nunique()),
                   "b": round(r.params["R"], 3), "se_b": round(r.bse["R"], 3), "p_b": round(r.pvalues["R"], 4), "bGE": round(r.params["R:GE"], 3),
                   "se_bGE": round(r.bse["R:GE"], 3), "p_bGE": round(r.pvalues["R:GE"], 4),
                   **me25(r, "R", G), "aux_slope": round(float(c[1]), 3),
                   "corr_SUB_breadth": round(float(b9["SUB"].corr(b9[z])), 3),
                   "pc1_variance_share": round(share_pc1, 3) if z == "PC1" else None})
exdf = pd.DataFrame(ex)
exdf.to_csv(OUT / "r5f_excess.csv", index=False)

# summary -----------------------------------------------------------------------------------------------------
summ = {"GE_reference": G}
for sname in S:
    t = tab[tab["Sample"] == sname].set_index("Division")
    b = tb[tb["Sample"] == sname]
    summ[sname] = {
        "rank_ME25_env_of_10": int(t.loc["05", "rank_ME25"]),
        "rank_bGE_env_most_negative_of_10": int(t.loc["05", "rank_bGE_most_negative"]),
        "n_other_bGE_negative_p_lt_010": int(((t.drop("05")["bGE"] < 0) & (t.drop("05")["p_bGE"] < 0.10)).sum()),
        "n_other_bGE_negative_p_lt_005": int(((t.drop("05")["bGE"] < 0) & (t.drop("05")["p_bGE"] < 0.05)).sum()),
        "n_other_ME25_positive_p_lt_005": int(((t.drop("05")["ME25"] > 0) & (t.drop("05")["p_ME25"] < 0.05)).sum()),
        "n_other_ME25_positive_p_lt_005_holm": int(((t.drop("05")["ME25"] > 0) &
                                                   (t.drop("05")["p_ME25_holm9"] < 0.05)).sum()),
        "n_diff_ME_p_lt_005": int((b["p_diff_ME"] < 0.05).sum()),
        "n_diff_ME_p_lt_005_holm": int((b["p_diff_ME_holm9"] < 0.05).sum()),
        "n_diff_ME_positive": int((b["diff_ME"] > 0).sum()),
        "n_diff_GE_p_lt_005": int((b["p_diff_GE"] < 0.05).sum()),
        "IUT_env_exceeds_every_other_ME": bool(((b["diff_ME"] > 0) & (b["p_diff_ME"] < 0.05)).all()),
        "median_ME25_other": float(t.drop("05")["ME25"].median()),
        "median_bGE_other": float(t.drop("05")["bGE"].median()),
    }
(OUT / "r5f_summary.json").write_text(json.dumps(summ, indent=1), encoding="utf8")
print(tab[["Sample", "Division", "N", "Countries", "Countries_never_subnational", "mean_share", "ME25", "p_ME25",
           "bGE", "p_bGE", "rank_ME25"]].to_string(index=False))
print(tb[["Sample", "Division", "N", "ME25_SUB", "ME25_other", "diff_ME", "p_diff_ME", "diff_GE", "p_diff_GE",
          "joint_p"]].to_string(index=False))
print(exdf[["Sample", "Measure", "N", "Countries", "ME25", "p_ME25", "bGE", "p_bGE"]].to_string(index=False))
print(json.dumps(summ, indent=1))


figure(tab, OUT)
print("wrote", OUT)
