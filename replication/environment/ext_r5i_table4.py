"""Companion to ext_r5i.py: rows in the format of Table 4 (uncentred SUB, SUB x GE, 25 pp at GE = -0.355),
the plausibility arithmetic for the sources of exposure, and a two-panel Fig. S1 (linear, binning and kernel
estimates, and common support).

    python ext_r5i_table4.py [--main ...] [--data ...] [--out DIR]   (after ext_r5i.py, same options)
"""
import json

import numpy as np
import pandas as pd

import ext_r5i as r5

OUT, pc = r5.OUT, r5.pc


def table4_rows(s, ge):
    rows = []
    add = ["MANF", "lnEI", "FUEL", "COAL", "RENTS", "VA", "POSTSOC"]
    specs = [("Adds structural controls", pc.BASE.replace(f" + {r5.CTRL}", f" + {r5.CTRL} + " + " + ".join(add)), s,
              add),
             ("Excl. post-socialist countries", pc.BASE, s[s["POSTSOC"] == 0], []),
             ("GE interacted with every control", pc.BASE + " + " + " + ".join(
                 f"GE:{v}" for v in ["lnENV", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]), s, [])]
    # rows for Table S7: single structural controls, without China, short specification, free ln anthropogenic share
    for lab, a in [("Adds manufacturing value added", ["MANF"]), ("Adds ln energy intensity", ["lnEI"]),
                   ("Adds fuel exports", ["FUEL"]), ("Adds coal share of electricity and resource rents", ["COAL", "RENTS"]),
                   ("Adds voice and accountability", ["VA"]), ("Adds post-socialist indicator", ["POSTSOC"])]:
        specs.append((lab, pc.BASE.replace(f" + {r5.CTRL}", f" + {r5.CTRL} + " + " + ".join(a)), s, a))
    specs.append(("Without China", pc.BASE, s[s["ISO"] != "CHN"], []))
    specs.append(("Without ln ENV, industry and urban shares",
                  "lnPM ~ SUB + SUB:GE + GE + lnY + lnY2 + TRADE + lnDENS + C(YEAR) + C(SUBREGION)", s, []))
    g = r5.an.match_iso(r5.an.read_gbdmaps(r5.GBD), pc, set(s["ISO"]))
    g["lnFA"] = np.log((100 - g["Windblown Dust"] - g["Remaining Sources"]) / 100)
    sf = s.merge(g[["ISO", "lnFA"]], on="ISO", how="inner")
    specs.append(("Adds ln 2017 anthropogenic share, free coefficient", pc.BASE + " + lnFA", sf, ["lnFA"]))
    for name, f, d, extra in specs:
        r, dd = pc._fit(f, d, r5.NEED + extra)
        me, p = pc.effect_25pp(r, ge)
        rows.append({"Specification": name, "N": int(r.nobs), "Countries": int(dd["ISO"].nunique()),
                     "SUB": round(float(r.params["SUB"]), 3), "se_SUB": round(float(r.bse["SUB"]), 3),
                     "p_SUB": round(float(r.pvalues["SUB"]), 4), "SUB:GE": round(float(r.params["SUB:GE"]), 3),
                     "se_SUB:GE": round(float(r.bse["SUB:GE"]), 3), "p_SUB:GE": round(float(r.pvalues["SUB:GE"]), 4),
                     "ME25_LMIC": me, "p_ME25_LMIC": p})
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "r5i_table4_rows.csv", index=False)
    return t


def plausibility():
    ch = pd.read_csv(OUT / "r5i_channel.csv").set_index("Outcome")
    info = json.loads((OUT / "r5i_results.json").read_text(encoding="utf8"))["channel"]
    sh = info["mean_share_pct_negative_GE"]
    out = {}
    for k, lab in [("Waste", "ln exposure from waste"), ("Energy and industry", "ln exposure from energy and industry")]:
        me = float(ch.loc[lab, "ME25"])
        # contribution to total exposure, in % of total, if the sector's exposure rises by ME25 percent
        out[k] = {"sector_share_pct_negative_GE": sh[k], "ME25_sector_pct": me,
                  "implied_change_in_total_exposure_pct": round(sh[k] * me / 100, 2)}
    out["waste_increase_needed_for_10pct_total"] = round(10.0 / sh["Waste"] * 100, 0)
    (OUT / "r5i_plausibility.json").write_text(json.dumps(out, indent=1), encoding="utf8")
    return out


def fig_s1(s, q):
    plt = pc._plt()
    k = pd.read_csv(OUT / "r5i_kernel.csv")
    k = k[(k["bw_mult"] == 1) & (k["GE"] != -0.355)].sort_values("GE")
    bn = pd.read_csv(pc.OUT / "r3c_binning.csv")
    r, _ = pc._fit(pc.BASE, s, r5.NEED)
    fig, (a, b) = plt.subplots(2, 1, figsize=(pc.WIDTH_IN, 5.6), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    xs = np.linspace(np.quantile(s["GE"], .02), np.quantile(s["GE"], .98), 100)
    B, V = r.params, r.cov_params()
    lin = B["SUB"] + B["SUB:GE"] * xs
    se = np.sqrt(V.loc["SUB", "SUB"] + xs ** 2 * V.loc["SUB:GE", "SUB:GE"] + 2 * xs * V.loc["SUB", "SUB:GE"])
    a.plot(xs, lin, color=pc.INK2, lw=1, ls="--", label="Linear interaction")
    a.fill_between(xs, lin - 1.96 * se, lin + 1.96 * se, color=pc.INK2, alpha=.08, lw=0)
    a.plot(k["GE"], k["ME"], color="#2a78d6", lw=1.4, label="Kernel estimator")
    a.fill_between(k["GE"], k["ME"] - 1.96 * k["se"], k["ME"] + 1.96 * k["se"], color="#2a78d6", alpha=.15, lw=0)
    a.errorbar(bn["GE_median"], bn["bin_me"], yerr=1.96 * bn["bin_se"], fmt="o", color="#eb6834", ms=4, lw=1,
               capsize=2, label="Binning estimator (terciles)")
    a.axhline(0, color=pc.INK, lw=.6)
    a.set_ylabel("Marginal association of SUB", fontsize=8.5, color=pc.INK2)
    a.legend(fontsize=7, frameon=False)
    a.set_title("(a) Marginal association", fontsize=8.5, color=pc.INK, loc="left")
    pc._style(a)
    x0, x1 = s[s["NOSUB"] == 0], s[s["NOSUB"] == 1]
    b.scatter(x0["GE"], x0["SUB"], s=5, color="#2a78d6", alpha=.45, lw=0, label="Subnational data")
    b.scatter(x1["GE"], x1["SUB"], s=8, facecolors="none", edgecolors="#eb6834", lw=.6, label="Central data alone")
    for v in (q["q1"], q["q2"]):
        b.axvline(v, color=pc.INK2, lw=.6, ls=":")
    b.set_xlabel("Government effectiveness (WGI)", fontsize=8.5, color=pc.INK2)
    b.set_ylabel("Subnational share (t−1)", fontsize=8.5, color=pc.INK2)
    b.legend(fontsize=7, frameon=False, loc="upper left")
    b.set_title("(b) Observations", fontsize=8.5, color=pc.INK, loc="left")
    pc._style(b)
    fig.tight_layout()
    pc._save(fig, OUT / "r5i_figS1_combined.png")


def main():
    p = r5.panel()
    s = pc._sample(p).copy()
    ge = pc.ge_reference(p)["LMIC"]
    t = table4_rows(s, ge)
    pl = plausibility()
    q = json.loads((OUT / "r5i_results.json").read_text(encoding="utf8"))["terciles"]
    fig_s1(s, q)
    print(t.to_string(index=False))
    print(json.dumps(pl, indent=1))


if __name__ == "__main__":
    main()
