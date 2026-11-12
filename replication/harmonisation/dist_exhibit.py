"""
Distributional translation of the filling choice: the redistributive effect of government health and
education spending (COFOG 07 + 09) when the spending total comes from general government (GG), from
central government alone (CGSS), from a complete subsector sum (T2, T3), from the tiered value without
GG or from the spliced value, on the fixed samples of evaluate_extensions.py.

Run from the repository root, after or instead of evaluate_extensions.py:
    python replication/harmonisation/dist_exhibit.py [--source FILE] [--inputs FILE] [--out DIR] [--cache DIR]

Inputs : data/gfs_raw_data.xlsx and data/country_codes.xlsx, read through evaluate_extensions.py
         (same tiers, sums, splicing and fixed samples; that script is imported, not modified)
         replication/harmonisation/data_ext/dist_inputs_wid_wdi.csv, built by fetch_inputs.py from
         WID (pre-tax national income per equal-split adult aged 20 or over, gptinc992j and
         sptinc992j, retrieved through Our World in Data) and WDI (net national income / GDP)
Outputs: ext_d1_*.csv and ext_fig_d1_redistribution_he.png in --out

Allocation rule (lump sum). Spending per adult is the same for everyone. Adding a lump sum c to incomes
with mean mu, Gini G and bottom-50% share s50 gives, exactly and without reranking,
    G_ext   = G / (1 + t),                 t = c / mu = spending / national income
    RE      = G - G_ext = G t / (1 + t)    (Reynolds-Smolensky redistributive effect)
    s50_ext = (s50 + 0.5 t) / (1 + t).
t = (spending, % of GDP) / (100 x NNI/GDP). For any rule that distributes the transfer with a fixed
concentration coefficient C (no reranking), RE = (G - C) t / (1 + t), so the error of a construction
relative to GG in per cent of the GG effect does not depend on G or C, and the error in Gini points
scales with G - C: zero under allocation proportional to income (C = G), largest among these rules
under the lump sum (C = 0) unless benefits are concentrated on the poor (C < 0).

Fixed samples (identical to evaluate_extensions.py, measure HE):
  "Common, subnational > 0, no identity"  (ext_a4_*): GG and CGSS, T2, T3 and the spliced value
      available, SG + LG > 0, neither complete sum equal to GG.
  "Common, all country-years"             (ext_a1_*, Sample "Common", Country-years "All").
The script is deterministic: no randomness enters.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

CONSTRUCTIONS = [("GG_OK", "General government (GG)"), ("CG", "CGSS alone"), ("T2", "T2 sum, complete"),
                 ("T3", "T3 sum, complete"), ("RULE", "Tiered rule without GG, complete"),
                 ("SPL5", "Tiered rule, spliced (d >= 5)")]
MAIN = ["GG_OK", "CG", "T2", "T3", "SPL5"]          # constructions of the main table (COMMON + GG)
SAMPLES = [("NOID", "Common, subnational > 0, no identity"), ("COMMON", "Common, all country-years")]
DIVS = ["07", "09"]
NNI_FILL_YEARS = 2          # NNI/GDP missing: nearest year of the same country within this distance
B50_ALT = 45.0              # bottom-50% share of benefits, lower end for education (Gethin 2023, p. 17)
CUTS = (0.5, 1.0)           # Gini points


# ----------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------

def load_ext(folder: Path):
    sys.path.insert(0, str(folder))
    import evaluate_extensions as ext  # noqa: E402
    return ext


def fixed_samples(ext, source: Path, cache: Path) -> pd.DataFrame:
    """Health + education by country-year on the common sample, with a flag for the no-identity sample."""
    div, _, digest = ext.load_extract(source, cache)
    h = ext.eh.harmonise(ext.eh.to_wide(div))
    reg = ext.regions()
    c = ext.cell_table(h)
    m = ext.measure_table(c, DIVS)
    m["REGION"] = m["ISO"].map(reg["region"]).fillna("Unassigned")
    base = m[m["GG_OK"].notna()]
    common = base[base[ext.COMMON].notna().all(axis=1)].copy()
    ident = pd.concat([(common[a] - common["GG_OK"]).abs() <= ext.TOL * common["GG_OK"] for a in ("T2", "T3")],
                      axis=1).any(axis=1)
    common["NOID"] = (common["SUBNAT"] > 0) & ~ident
    common["COMMON"] = True
    common.attrs["digest"] = digest
    return common.reset_index(drop=True)


def load_inputs(path: Path) -> pd.DataFrame:
    """WID and WDI inputs; NNI/GDP gaps filled from the nearest year of the same country (flagged)."""
    d = pd.read_csv(path)
    d["NNI_GDP_FILLED"] = False
    out = []
    for iso, g in d.groupby("ISO"):
        g = g.sort_values("YEAR").copy()
        have = g.dropna(subset=["NNI_GDP"])
        for i in g.index[g["NNI_GDP"].isna()]:
            if have.empty:
                break
            dist = (have["YEAR"] - g.at[i, "YEAR"]).abs()
            j = dist.idxmin()           # first of equally distant years = earlier year
            if dist[j] <= NNI_FILL_YEARS:
                g.at[i, "NNI_GDP"], g.at[i, "NNI_GDP_FILLED"] = have.at[j, "NNI_GDP"], True
        out.append(g)
    return pd.concat(out, ignore_index=True)


# ----------------------------------------------------------------------------
# Country-year table
# ----------------------------------------------------------------------------

def country_years(s: pd.DataFrame, inp: pd.DataFrame) -> pd.DataFrame:
    """Long table: one row per country-year and construction, with t, extended Gini, RE and s50."""
    x = s.merge(inp, on=["ISO", "YEAR"], how="left")
    x = x[x["GINI_PRE"].notna() & x["S50_PRE"].notna() & x["NNI_GDP"].notna()]
    rows = []
    for col, lab in CONSTRUCTIONS:
        r = x[["ISO", "YEAR", "REGION", "NOID", "COMMON", "GINI_PRE", "S50_PRE", "GINI_PRE_OBS", "NNI_GDP",
               "NNI_GDP_FILLED"]].copy()
        r.insert(2, "Construction", lab)
        r.insert(3, "Code", col)
        r["HE (% GDP)"] = x[col]
        r["t"] = x[col] / (100 * x["NNI_GDP"])
        rows.append(r)
    d = pd.concat(rows, ignore_index=True)
    k = d["t"] / (1 + d["t"])
    d["Extended Gini (x100)"] = 100 * d["GINI_PRE"] / (1 + d["t"])
    d["RE (Gini points)"] = 100 * d["GINI_PRE"] * k
    d["Bottom 50% share, extended (%)"] = (d["S50_PRE"] + 50 * d["t"]) / (1 + d["t"])
    d["Change in bottom 50% share (pp)"] = d["Bottom 50% share, extended (%)"] - d["S50_PRE"]
    d["Change in bottom 50% share, 45% rule (pp)"] = (B50_ALT - d["S50_PRE"]) * k
    d["RE, WID estimates only (Gini points)"] = 100 * d["GINI_PRE_OBS"] * k
    d["RE, t on GDP (Gini points)"] = 100 * d["GINI_PRE"] * (d["t"] * d["NNI_GDP"]) / (1 + d["t"] * d["NNI_GDP"])
    gg = d[d["Code"] == "GG_OK"].set_index(["ISO", "YEAR"])
    key = pd.MultiIndex.from_frame(d[["ISO", "YEAR"]])
    for c in ("RE (Gini points)", "Change in bottom 50% share (pp)", "RE, WID estimates only (Gini points)",
              "RE, t on GDP (Gini points)", "Change in bottom 50% share, 45% rule (pp)"):
        ref = gg[c].reindex(key).to_numpy()
        d[f"{c}, GG"] = ref
        d[f"{c}, error"] = d[c] - ref
    d["RE error (% of GG effect)"] = 100 * d["RE (Gini points), error"] / d["RE (Gini points), GG"]
    return d


# ----------------------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------------------

def _cmed(v: pd.Series, iso: pd.Series) -> float:
    """Median over countries of the country medians."""
    return v.groupby(iso).median().median()


def summary(d: pd.DataFrame, flag: str, sample: str) -> pd.DataFrame:
    """Statistics by construction on one fixed sample."""
    s = d[d[flag]]
    cm = s.groupby(["Code", "ISO"])[["Extended Gini (x100)", "RE (Gini points)", "GINI_PRE"]].mean()
    gg_cm = cm.loc["GG_OK"]
    rows = []
    for col, lab in CONSTRUCTIONS:
        x = s[s["Code"] == col]
        err, pct = x["RE (Gini points), error"], x["RE error (% of GG effect)"]
        c = cm.loc[col].reindex(gg_cm.index)
        r_gg = gg_cm["Extended Gini (x100)"].rank(method="first")
        r_alt = c["Extended Gini (x100)"].rank(method="first")
        q = lambda r: pd.qcut(r, 5, labels=False)  # noqa: E731
        row = {"Sample": sample, "Construction": lab, "N": len(x), "Countries": x["ISO"].nunique(),
               "Countries outside Europe": x.loc[x["REGION"] != "Europe", "ISO"].nunique(),
               "Years": f"{x['YEAR'].min()}-{x['YEAR'].max()}",
               "Median HE (% GDP)": x["HE (% GDP)"].median(),
               "Median t (% of national income)": 100 * x["t"].median(),
               "Median pre-transfer Gini (x100)": 100 * x["GINI_PRE"].median(),
               "Median extended Gini (x100)": x["Extended Gini (x100)"].median(),
               "Median RE (Gini points)": x["RE (Gini points)"].median(),
               "Median RE, median country (Gini points)": _cmed(x["RE (Gini points)"], x["ISO"]),
               "Median RE / RE GG": (x["RE (Gini points)"] / x["RE (Gini points), GG"]).median(),
               "Median error (Gini points)": err.median(),
               "Median error, median country (Gini points)": _cmed(err, x["ISO"]),
               "P25 error (Gini points)": err.quantile(0.25), "P75 error (Gini points)": err.quantile(0.75),
               "Median error (% of GG effect)": pct.median(),
               "Median error, median country (% of GG effect)": _cmed(pct, x["ISO"]),
               "Mean abs. error (Gini points)": err.abs().mean()}
        for cut in CUTS:
            row[f"Understated by > {cut:g} Gini point (%)"] = 100 * (err < -cut).mean()
        for cut in CUTS:
            row[f"Overstated by > {cut:g} Gini point (%)"] = 100 * (err > cut).mean()
        row.update({
            "Spearman, country means, extended Gini vs GG": c["Extended Gini (x100)"].corr(
                gg_cm["Extended Gini (x100)"], method="spearman"),
            "Spearman, country means, RE vs GG": c["RE (Gini points)"].corr(gg_cm["RE (Gini points)"],
                                                                            method="spearman"),
            "Mean abs. rank shift, extended Gini (positions)": (r_alt - r_gg).abs().mean(),
            "Countries changing quintile, extended Gini": int((q(r_alt) != q(r_gg)).sum()) if len(c) >= 10 else np.nan,
            "Median change in bottom 50% share (pp)": x["Change in bottom 50% share (pp)"].median(),
            "Median error, bottom 50% share (pp)": x["Change in bottom 50% share (pp), error"].median(),
            "Median error, bottom 50% share, median country (pp)": _cmed(x["Change in bottom 50% share (pp), error"],
                                                                         x["ISO"])})
        if col == "GG_OK":
            row["Spearman, country means, extended Gini vs pre-transfer Gini (GG)"] = \
                gg_cm["Extended Gini (x100)"].corr(gg_cm["GINI_PRE"], method="spearman")
        rows.append(row)
    return pd.DataFrame(rows)


def sensitivity(d: pd.DataFrame, flag: str, sample: str) -> pd.DataFrame:
    """Main statistics under other allocation rules, inequality data and denominators."""
    s = d[d[flag]]
    rows = []
    for col, lab in CONSTRUCTIONS:
        x = s[s["Code"] == col]
        # (1) allocation proportional to pre-tax income: the Gini does not change under any construction
        rows.append({"Sample": sample, "Variant": "Allocation proportional to pre-tax income (C = G)",
                     "Construction": lab, "N": len(x), "Median RE (Gini points)": 0.0,
                     "Median error (Gini points)": 0.0, "Understated by > 0.5 Gini point (%)": 0.0})
        # (2) WID estimates that WID neither interpolates nor extrapolates
        o = x[x["GINI_PRE_OBS"].notna()]
        e = o["RE, WID estimates only (Gini points), error"]
        rows.append({"Sample": sample, "Variant": "Lump sum, WID estimates only (no interpolation or extrapolation)",
                     "Construction": lab, "N": len(o), "Countries": o["ISO"].nunique(),
                     "Median RE (Gini points)": o["RE, WID estimates only (Gini points)"].median(),
                     "Median error (Gini points)": e.median(),
                     "Median error (% of GG effect)": (100 * e / o["RE, WID estimates only (Gini points), GG"]).median(),
                     "Understated by > 0.5 Gini point (%)": 100 * (e < -0.5).mean(),
                     "Understated by > 1 Gini point (%)": 100 * (e < -1).mean()})
        # (3) t measured on GDP instead of national income
        e = x["RE, t on GDP (Gini points), error"]
        rows.append({"Sample": sample, "Variant": "Lump sum, t = spending / GDP",
                     "Construction": lab, "N": len(x), "Countries": x["ISO"].nunique(),
                     "Median RE (Gini points)": x["RE, t on GDP (Gini points)"].median(),
                     "Median error (Gini points)": e.median(),
                     "Median error (% of GG effect)": (100 * e / x["RE, t on GDP (Gini points), GG"]).median(),
                     "Understated by > 0.5 Gini point (%)": 100 * (e < -0.5).mean(),
                     "Understated by > 1 Gini point (%)": 100 * (e < -1).mean()})
        # (4) bottom 50% receives 45% of the benefits (bottom-50% share only)
        e = x["Change in bottom 50% share, 45% rule (pp), error"]
        rows.append({"Sample": sample, "Variant": "Bottom 50% receives 45% of benefits (bottom 50% share only)",
                     "Construction": lab, "N": len(x), "Countries": x["ISO"].nunique(),
                     "Median change in bottom 50% share (pp)": x["Change in bottom 50% share, 45% rule (pp)"].median(),
                     "Median error, bottom 50% share (pp)": e.median(),
                     "Median error, bottom 50% share (% of GG effect)":
                         (100 * e / x["Change in bottom 50% share, 45% rule (pp), GG"]).median()})
    return pd.DataFrame(rows)


def coverage(s: pd.DataFrame, inp: pd.DataFrame) -> pd.DataFrame:
    """Country-years of each fixed sample with and without the WID and WDI inputs, by region."""
    x = s.merge(inp, on=["ISO", "YEAR"], how="left")
    ok = x["GINI_PRE"].notna() & x["S50_PRE"].notna() & x["NNI_GDP"].notna()
    rows = []
    for flag, name in SAMPLES:
        f = x[x[flag]]
        for reg, g in [("All", f)] + list(f.groupby("REGION")):
            k = ok[g.index]
            rows.append({"Sample": name, "Region": reg, "Country-years (fixed sample)": len(g),
                         "Countries (fixed sample)": g["ISO"].nunique(), "Country-years with inputs": int(k.sum()),
                         "Countries with inputs": g.loc[k, "ISO"].nunique(),
                         "Country-years with a WID estimate (no interpolation or extrapolation)":
                             int(g["GINI_PRE_OBS"].notna().sum()),
                         "Country-years with NNI/GDP from the nearest year": int(g["NNI_GDP_FILLED"].eq(True).sum()),
                         "Years": f"{g['YEAR'].min()}-{g['YEAR'].max()}",
                         "Countries": " ".join(sorted(g["ISO"].unique()))})
    return pd.DataFrame(rows)


def main_table(summ: pd.DataFrame) -> pd.DataFrame:
    cols = ["Sample", "Construction", "N", "Countries", "Median t (% of national income)",
            "Median extended Gini (x100)", "Median RE (Gini points)", "Median RE, median country (Gini points)",
            "Median error (Gini points)", "Median error (% of GG effect)",
            "Median error, median country (% of GG effect)",
            "Understated by > 0.5 Gini point (%)", "Understated by > 1 Gini point (%)",
            "Overstated by > 0.5 Gini point (%)",
            "Spearman, country means, extended Gini vs GG", "Spearman, country means, RE vs GG",
            "Median change in bottom 50% share (pp)", "Median error, bottom 50% share (pp)"]
    keep = summ["Construction"].isin(dict(CONSTRUCTIONS)[c] for c in MAIN)
    return summ.loc[keep, cols]


# ----------------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------------

def gini(y: np.ndarray) -> float:
    y = np.sort(y)
    n = len(y)
    return float((2 * np.arange(1, n + 1) - n - 1) @ y / (n * y.sum()))


def checks(s: pd.DataFrame, d: pd.DataFrame, ext_out: Path) -> pd.DataFrame:
    rows = []
    # Fixed samples reproduce the published extension tables (N, countries, median ratio to GG)
    for flag, name, file, smp in (("NOID", SAMPLES[0][1], "ext_a4_main_table.csv", None),
                                  ("COMMON", SAMPLES[1][1], "ext_a1_main_table.csv", None)):
        f = s[s[flag]]
        p = ext_out / file
        t = pd.read_csv(p) if p.exists() else None
        for col in ("CG", "T2", "T3", "SPL5"):
            lab = dict(CONSTRUCTIONS)[col]
            mr = (f[col] / f["GG_OK"]).median()
            row = {"Check": f"{name}: {lab}", "N here": len(f), "Countries here": f["ISO"].nunique(),
                   "Median ratio here": round(mr, 6)}
            if t is not None:
                r = t[(t["Measure"] == "HE") & (t["Alternative"] == lab)].iloc[0]
                row.update({"N published": r["N"], "Countries published": r["Countries"],
                            "Median ratio published": r["Median ratio"],
                            "Match": bool(r["N"] == len(f) and r["Countries"] == f["ISO"].nunique()
                                          and abs(r["Median ratio"] - round(mr, 6)) < 1e-9)})
            rows.append(row)
    # Every country-year of both samples has the inequality and national income inputs
    n_cy = d[d["Code"] == "GG_OK"]
    rows.append({"Check": "Country-years with inputs / fixed sample, no identity",
                 "N here": int(n_cy["NOID"].sum()), "N published": int(s["NOID"].sum()),
                 "Match": int(n_cy["NOID"].sum()) == int(s["NOID"].sum())})
    rows.append({"Check": "Country-years with inputs / common sample",
                 "N here": len(n_cy), "N published": len(s), "Match": len(n_cy) == len(s)})
    # The closed forms equal direct computation on a skewed test distribution
    y = np.exp(np.linspace(-3, 3, 2001)) + np.linspace(0, 1, 2001) ** 4
    g, mu, t = gini(y), y.mean(), 0.12
    yc = y + t * mu
    s50 = np.sort(y)[: len(y) // 2].sum() / y.sum()
    s50c = np.sort(yc)[: len(y) // 2].sum() / yc.sum()
    rows.append({"Check": "Gini of y + c equals G / (1 + t) (test distribution, t = 0.12)",
                 "Match": abs(gini(yc) - g / (1 + t)) < 1e-12})
    rows.append({"Check": "Bottom-group share of y + c equals (s + p t) / (1 + t), p = population share (test distribution)",
                 "Match": abs(s50c - (s50 + (len(y) // 2) / len(y) * t) / (1 + t)) < 1e-12})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Figure
# ----------------------------------------------------------------------------

def fig_redistribution(d: pd.DataFrame, eh, path: Path) -> pd.DataFrame:
    """RE of health and education (Gini points) by country, country means over the fixed sample, ranked by GG."""
    import matplotlib.pyplot as plt
    x = d[d["NOID"]]
    cm = x.pivot_table(index="ISO", columns="Code", values="RE (Gini points)", aggfunc="mean")
    cm = cm[["GG_OK", "CG", "RULE", "SPL5"]].sort_values("GG_OK")
    cm["Years"] = x[x["Code"] == "GG_OK"].groupby("ISO").size()
    vals = cm[["GG_OK", "CG", "RULE", "SPL5"]]
    fig, ax = plt.subplots(figsize=(7, 0.24 * len(cm) + 1.4), dpi=200)
    y = np.arange(len(cm))
    ax.hlines(y, vals.min(axis=1), vals.max(axis=1), color=eh.GRID, linewidth=1.2, zorder=1)
    for col, lab, colour, marker, size in [("CG", "CGSS alone", eh.INK2, "o", 26),
                                           ("RULE", "Tiered value (unconsolidated sum)", eh.TIER_COLORS["T2"], "s", 24),
                                           ("SPL5", "Spliced value", eh.TIER_COLORS["T1"], "D", 22),
                                           ("GG_OK", "General government (GG)", eh.INK, "|", 90)]:
        ax.scatter(cm[col], y, s=size, marker=marker, color=colour, zorder=3, label=lab,
                   linewidth=1.6 if marker == "|" else 0.5, edgecolor="white" if marker != "|" else None)
    eh._style(ax)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=eh.GRID, linewidth=0.8)
    ax.set_yticks(y, cm.index, fontsize=8)
    ax.set_xlabel("Redistributive effect of health and education, Gini points (country mean)",
                  color=eh.INK2, fontsize=9)
    ax.set_xlim(left=0)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)
    lab = dict(CONSTRUCTIONS)
    return cm.rename(columns={k: lab[k] for k in ("GG_OK", "CG", "RULE", "SPL5")}).reset_index()


# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0].strip())
    ap.add_argument("--scripts", type=Path, default=HERE, help="folder holding evaluate_extensions.py (default: %(default)s)")
    ap.add_argument("--source", type=Path, help="IMF GFS COFOG extract (default: that of evaluate_extensions.py)")
    ap.add_argument("--inputs", type=Path, help="WID and WDI inputs (default: <scripts>/data_ext/dist_inputs_wid_wdi.csv)")
    ap.add_argument("--out", type=Path, help="output folder (default: <scripts>/output_ext)")
    ap.add_argument("--cache", type=Path, help="folder of the extract cache _ext_long_*.pkl (default: --out)")
    ap.add_argument("--ext-out", type=Path, help="folder with ext_a1/ext_a4 tables for the checks (default: --out)")
    a = ap.parse_args()
    sj = a.scripts.resolve()
    out = (a.out or sj / "output_ext").resolve()
    out.mkdir(parents=True, exist_ok=True)
    ext = load_ext(sj)
    source = (a.source or ext.RAW).resolve()
    s = fixed_samples(ext, source, (a.cache or out).resolve())
    inp = load_inputs((a.inputs or sj / "data_ext" / "dist_inputs_wid_wdi.csv").resolve())
    d = country_years(s, inp)

    summ = pd.concat([summary(d, f, n) for f, n in SAMPLES], ignore_index=True)
    sens = pd.concat([sensitivity(d, f, n) for f, n in SAMPLES], ignore_index=True)
    tables = {"ext_d1_summary": summ, "ext_d1_main_table": main_table(summ), "ext_d1_sensitivity": sens,
              "ext_d1_coverage": coverage(s, inp), "ext_d1_checks": checks(s, d, (a.ext_out or out).resolve()),
              "ext_d1_country_years": d.drop(columns=["COMMON"]).rename(columns={"NOID": "No-identity sample"}),
              "ext_fig_d1_redistribution_he_data": fig_redistribution(d, ext.eh, out / "ext_fig_d1_redistribution_he.png")}
    for name, t in tables.items():
        t.round(6).to_csv(out / f"{name}.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(f"Extract SHA-256 {s.attrs['digest'][:12]}...")
    for name in ("ext_d1_main_table", "ext_d1_coverage", "ext_d1_checks"):
        print(f"\n=== {name} ===")
        print(tables[name].round(3).drop(columns=["Countries"], errors="ignore").to_string(index=False))
    print(f"\nOutputs in {out}")


if __name__ == "__main__":
    main()
