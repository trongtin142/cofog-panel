"""
Further extensions of the harmonisation study: an external benchmark, consequences by recording
practice, pairwise main samples, classification variants and sample traces.

Run from the repository root, after evaluate_extensions.py and dist_exhibit.py:
    python -I replication/harmonisation/evaluate_extensions_r6.py [--source FILE] [--vintage FILE] [--out DIR]
        [--cache DIR] [--practice FILE] [--benchmarks FILE] [--inputs FILE] [--grants FILE]

Inputs : data/gfs_raw_data.xlsx and data/country_codes.xlsx, read through evaluate_extensions.py
         (same tiers, sums, splicing, samples and practice classification; that script and
         dist_exhibit.py are imported, not modified, so their outputs stay byte-identical)
         replication/harmonisation/data_ext/ext_benchmarks_wdi.csv, built by ext_fetch_benchmarks.py from the
         World Bank WDI bulk CSV files of SH.XPD.GHED.GD.ZS (WHO GHED) and SE.XPD.TOTL.GD.ZS (UNESCO UIS)
         replication/harmonisation/data_ext/dist_inputs_wid_wdi.csv (WID and WDI, see dist_exhibit.py)
         replication/harmonisation/data_ext/gfs_soo_grants_pcgdp.csv (IMF GFS_SOO, see evaluate_extensions.py)
         --practice: ext_b3_practice_countries.csv written by evaluate_extensions.py (checked against a
         recomputation here)
         --vintage (optional): the IMF release of 21 October 2026, for the common-sample decomposition
Outputs: ext_r6_*.csv and ext_fig_classification_r6.png in --out

Item 1  External benchmark: IMF GG, CGSS alone, complete sums, the tiered value and spliced values
        against WHO GHED (health, COFOG 07) and UNESCO UIS (education, COFOG 09), in overlap years and
        in country-years without GG.
Item 2  CGSS alone against GG by recording practice, with the accounting split
        CGSS/GG = 1 - (SG + LG)/GG + (T2 - GG)/GG and the error in the redistributive effect.
Item 3  Pairwise samples with subnational spending for every alternative, with and without exact and
        near identities, the common-sample decomposition and the redistributive effect.
Item 4  Classification on T2 sums only and with F excluding divisions 07 and 10, grant test (a) for
        each, country details, and Figure 1 with panel (b) in the unit of the classification.
Item 5  Sample-size traces.
The script is deterministic: permutations and bootstraps use the fixed seed of evaluate_extensions.py.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate_extensions as ext  # noqa: E402
import dist_exhibit as dx  # noqa: E402

eh = ext.eh
GG, CGSS, SG, LG, SSF = ext.GG, ext.CGSS, ext.SG, ext.LG, ext.SSF
TOL = ext.TOL
NEAR = 0.005                            # near identity: |estimate / GG - 1| <= 0.5%
BENCH = {"07": ("GHED_GG_HEALTH", "WHO GHED, domestic general government health expenditure (SH.XPD.GHED.GD.ZS)"),
         "09": ("UIS_GOV_EDU", "UNESCO UIS, government expenditure on education (SE.XPD.TOTL.GD.ZS)")}
REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania"]
ALT_LAB = dict(ext.ALTERNATIVES)
ALT_LAB.update({"GG_OK": "General government (GG)", "CENTRAL": "Central government value (CGSS or its components)",
                "VALUE": "Tiered value", "SPLN": "Tiered value, spliced (d >= 1)"})
PRACTICE_ORDER = ["A", "B", "C", "B and C", "D", "U", "Not classified", "All"]


def _q(s, p):
    return s.quantile(p) if len(s) else np.nan


def _cmed(v: pd.Series, iso: pd.Series) -> float:
    return v.groupby(iso).median().median() if len(v) else np.nan


def ratio_stats(r: pd.Series, iso: pd.Series) -> dict:
    """Median ratio, IQR, shares within 10% and 25%, counts and the median-country version."""
    r = r.dropna()
    iso = iso[r.index]
    lr = np.log(r.where(r > 0))
    return {"N": len(r), "Countries": iso.nunique(), "Median ratio": r.median(), "P25 ratio": _q(r, 0.25),
            "P75 ratio": _q(r, 0.75), "Within 10% (%)": 100 * ((r - 1).abs() <= 0.10).mean() if len(r) else np.nan,
            "Within 25% (%)": 100 * ((r - 1).abs() <= 0.25).mean() if len(r) else np.nan,
            "Median abs. log ratio": lr.abs().median(),
            "Median ratio, median country": _cmed(r, iso)}


# ----------------------------------------------------------------------------
# Item 1: external benchmark
# ----------------------------------------------------------------------------

def splice_nogg(c: pd.DataFrame, d: int = 1, k: int = eh.ADJ_K) -> pd.Series:
    """
    Ratio splicing applied where GG is missing: the tiered value without GG (RULE) times the median
    ratio GG/RULE in the k overlap years closest to, and at least d years after, the year, among overlap
    years with the same tier and components (as in evaluate_extensions.splice, here for years without GG).
    """
    out = pd.Series(np.nan, index=c.index)
    ok = c["RULE"] > 0
    for _, g in c[ok].groupby(["ISO", "DIV", "RULE_SECT"]):
        ov = g[g["GG_OK"].notna()]
        tgt = g[g["GG_OK"].isna() & (g[GG].isna())]
        if ov.empty or tgt.empty:
            continue
        yrs, rat = ov["YEAR"].to_numpy(), (ov["GG_OK"] / ov["RULE"]).to_numpy()
        out.loc[tgt.index] = [eh._later_ratio(yrs, rat, y, d, k) * v for y, v in zip(tgt["YEAR"], tgt["RULE"])]
    return out


def benchmark_tables(c: pd.DataFrame, bm: pd.DataFrame, reg: pd.DataFrame):
    rows_a, rows_b, rows_h = [], [], []
    c = c.copy()
    c["SPLN"] = splice_nogg(c, 1)
    c["REGION"] = c["ISO"].map(reg["region"]).fillna("Unassigned")
    for dv, (col, lab) in BENCH.items():
        x = c[c["DIV"] == dv].merge(bm[["ISO", "YEAR", col]], on=["ISO", "YEAR"], how="left")
        x = x[x[col] > 0].rename(columns={col: "B"})
        name = {"07": "Health (07)", "09": "Education (09)"}[dv]
        # (a) overlap years: GG reported, positive and not flagged
        ov = x[x["GG_OK"].notna()]
        sub = ov["SUBNAT"] > 0
        common = ov[ov[["CG", "T2", "T3", "SPL5"]].notna().all(axis=1)]
        samples = [("Pairwise", "All", ov), ("Pairwise", "Subnational > 0", ov[sub]),
                   ("Common (CGSS, T2, T3, spliced available)", "All", common),
                   ("Common (CGSS, T2, T3, spliced available)", "Subnational > 0", common[common["SUBNAT"] > 0])]
        for smp, sub_name, frame in samples:
            for alt in ("GG_OK", "CG", "T2", "T3", "RULE", "SPL5"):
                s = frame[frame[alt].notna() & (frame[alt] > 0)]
                st = ratio_stats(s[alt] / s["B"], s["ISO"])
                # head to head with GG on the same country-years
                closer = (np.log(s[alt] / s["B"]).abs() < np.log(s["GG_OK"] / s["B"]).abs())
                rows_a.append({"Function": name, "Benchmark": lab, "Sample": smp, "Country-years": sub_name,
                               "IMF value": ALT_LAB[alt], **st,
                               "Closer to benchmark than GG (%)": 100 * closer.mean() if alt != "GG_OK" and len(s) else np.nan,
                               "Years": f"{s['YEAR'].min()}-{s['YEAR'].max()}" if len(s) else ""})
        # GG / benchmark by country in overlap years: calibration for definitional differences
        cal = (ov["GG_OK"] / ov["B"]).groupby(ov["ISO"]).median()
        # (b) country-years without GG: tier T2 or T3, central value and tiered value available
        ng = x[x["TIER"].isin(["T2", "T3"]) & x["CENTRAL"].notna() & (x["VALUE"] > 0)].copy()
        ng["CAL"] = ng["ISO"].map(cal)
        for compl, g0 in (("Complete only", ng[ng["COMPLETE"] == True]), ("All", ng)):  # noqa: E712
            for sp_name, g1 in (("Subnational > 0", g0[g0["SUBNAT"] > 0]), ("Subnational = 0 or not reported", g0[~(g0["SUBNAT"] > 0)])):
                for rg, g in ([("All", g1)] + [(r, g1[g1["REGION"] == r]) for r in REGIONS]
                              + [("Outside Africa and Oceania", g1[~g1["REGION"].isin(["Africa", "Oceania"])])]):
                    if g.empty:
                        continue
                    for alt in ("CENTRAL", "VALUE", "SPLN"):
                        s = g[g[alt].notna() & (g[alt] > 0)]
                        st = ratio_stats(s[alt] / s["B"], s["ISO"])
                        sc = s[s["CAL"].notna()]
                        rc = (sc[alt] / sc["B"]) / sc["CAL"]
                        row = {"Function": name, "Benchmark": lab, "Tiered values": compl, "Subnational spending": sp_name,
                               "Region": rg, "IMF value": ALT_LAB[alt], **st,
                               "Calibrated: N (countries with overlap years)": len(sc),
                               "Calibrated: countries": sc["ISO"].nunique(),
                               "Calibrated: median ratio / country GG ratio": rc.median(),
                               "Calibrated: within 25% (%)": 100 * ((rc - 1).abs() <= 0.25).mean() if len(rc) else np.nan}
                        if alt != "CENTRAL":
                            both = s[s["CENTRAL"] > 0]
                            ca = np.log(both[alt] / both["B"]).abs()
                            cc = np.log(both["CENTRAL"] / both["B"]).abs()
                            row["Head to head: N"] = len(both)
                            row["Closer to benchmark than central value (%)"] = 100 * (ca < cc).mean() if len(both) else np.nan
                            row["Equal to central value (%)"] = 100 * ((both[alt] - both["CENTRAL"]).abs() <= TOL * both["CENTRAL"]).mean() if len(both) else np.nan
                            bc = both[both["CAL"].notna()]
                            ca2 = np.log(bc[alt] / bc["B"] / bc["CAL"]).abs()
                            cc2 = np.log(bc["CENTRAL"] / bc["B"] / bc["CAL"]).abs()
                            row["Calibrated: closer than central value (%)"] = 100 * (ca2 < cc2).mean() if len(bc) else np.nan
                        rows_b.append(row)
        # headline: country-years without GG with subnational spending, complete tiered values
        g = ng[(ng["COMPLETE"] == True) & (ng["SUBNAT"] > 0)]  # noqa: E712
        rows_h.append({"Function": name, "Benchmark": lab,
                       "Overlap: GG / benchmark, median": (ov["GG_OK"] / ov["B"]).median(),
                       "Overlap: GG / benchmark, within 25% (%)": 100 * (((ov["GG_OK"] / ov["B"]) - 1).abs() <= 0.25).mean(),
                       "Overlap: country-years": len(ov), "Overlap: countries": ov["ISO"].nunique(),
                       "Without GG, subnational > 0: country-years": len(g), "Without GG, subnational > 0: countries": g["ISO"].nunique(),
                       "Central / benchmark, median": (g["CENTRAL"] / g["B"]).median(),
                       "Tiered / benchmark, median": (g["VALUE"] / g["B"]).median(),
                       "Central / benchmark, median country": _cmed(g["CENTRAL"] / g["B"], g["ISO"]),
                       "Tiered / benchmark, median country": _cmed(g["VALUE"] / g["B"], g["ISO"])})
    return pd.DataFrame(rows_a), pd.DataFrame(rows_b), pd.DataFrame(rows_h)


# ----------------------------------------------------------------------------
# Measures, samples and the redistributive effect
# ----------------------------------------------------------------------------

def measures(c: pd.DataFrame, gdp: pd.DataFrame, reg: pd.DataFrame) -> dict:
    out = {}
    for code, name, divs in ext.MEASURES:
        m = ext.measure_table(c, divs).merge(gdp, on=["ISO", "YEAR"], how="left")
        m["REGION"] = m["ISO"].map(reg["region"]).fillna("Unassigned")
        out[code] = m
    return out


def noid_sample(m: pd.DataFrame) -> pd.DataFrame:
    """Fixed sample of evaluate_extensions.analysis_a_noident (common, SG + LG > 0, no T2 or T3 identity)."""
    base = m[m["GG_OK"].notna() & (m["SUBNAT"] > 0)]
    ident = {a: (base[a] - base["GG_OK"]).abs() <= TOL * base["GG_OK"] for a in ("T2", "T3")}
    return base[base[ext.COMMON].notna().all(axis=1) & ~(ident["T2"] | ident["T3"])]


def redistribution(s: pd.DataFrame, alt: str, inp: pd.DataFrame) -> dict:
    """Redistributive effect of GG and of the alternative on the same country-years (dist_exhibit formulas)."""
    x = s[["ISO", "YEAR", "REGION", "GG_OK", alt]].copy()
    for col, _ in dx.CONSTRUCTIONS:
        if col not in x.columns:
            x[col] = np.nan
    x["NOID"], x["COMMON"] = True, True
    d = dx.country_years(x, inp)
    gg = d[d["Code"] == "GG_OK"].set_index(["ISO", "YEAR"])
    a = d[d["Code"] == alt]
    err, pct = a["RE (Gini points), error"], a["RE error (% of GG effect)"]
    cm = a.groupby("ISO")["RE (Gini points)"].mean()
    cg = gg.groupby(level="ISO")["RE (Gini points)"].mean().reindex(cm.index)
    # error in % of the GG effect from t alone (no inequality data needed): k = t / (1 + t)
    t_in = s.merge(inp[["ISO", "YEAR", "NNI_GDP"]], on=["ISO", "YEAR"], how="left").dropna(subset=["NNI_GDP"])
    k_gg = (t_in["GG_OK"] / (100 * t_in["NNI_GDP"])) / (1 + t_in["GG_OK"] / (100 * t_in["NNI_GDP"]))
    k_alt = (t_in[alt] / (100 * t_in["NNI_GDP"])) / (1 + t_in[alt] / (100 * t_in["NNI_GDP"]))
    pct_t = 100 * (k_alt - k_gg) / k_gg
    return {"RE: country-years with WID and WDI": len(a), "RE: countries": a["ISO"].nunique(),
            "RE GG, median (Gini points)": gg["RE (Gini points)"].median(),
            "RE GG, median country (Gini points)": gg["RE (Gini points)"].groupby(level="ISO").median().median(),
            "RE alt, median (Gini points)": a["RE (Gini points)"].median(),
            "RE error, median (Gini points)": err.median(),
            "RE error, median country (Gini points)": _cmed(err, a["ISO"]),
            "RE error, median (% of GG effect)": pct.median(),
            "RE error, median country (% of GG effect)": _cmed(pct, a["ISO"]),
            "Understated by > 1 Gini point (%)": 100 * (err < -1).mean() if len(a) else np.nan,
            "Overstated by > 1 Gini point (%)": 100 * (err > 1).mean() if len(a) else np.nan,
            "Spearman, country means of RE": cm.corr(cg, method="spearman") if len(cm) > 2 else np.nan,
            "Bottom 50% change GG, median (pp)": gg["Change in bottom 50% share (pp)"].median(),
            "Bottom 50% change alt, median (pp)": a["Change in bottom 50% share (pp)"].median(),
            "Error from t only: country-years with NNI/GDP": len(t_in),
            "Error from t only, median (% of GG effect)": pct_t.median(),
            "Error from t only, median country (% of GG effect)": _cmed(pct_t, t_in["ISO"])}


# ----------------------------------------------------------------------------
# Item 2: consequences by recording practice
# ----------------------------------------------------------------------------

def by_practice(ms: dict, prac: pd.Series, inp: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for code in ("07", "09", "HE", "SOC"):
        m = ms[code].copy()
        m["P"] = m["ISO"].map(prac).fillna("Not classified")
        base = m[m["GG_OK"].notna()]
        samples = [("Pairwise, subnational > 0 (CGSS alone and GG)", base[base["CG"].notna() & (base["SUBNAT"] > 0)]),
                   ("Fixed sample without identities", noid_sample(m))]
        for smp, s in samples:
            for p in PRACTICE_ORDER:
                g = s if p == "All" else s[s["P"].isin(["B", "C"])] if p == "B and C" else s[s["P"] == p]
                if g.empty:
                    continue
                r = g["CG"] / g["GG_OK"]
                sub = g["SUBNAT"] / g["GG_OK"]
                t2 = g[g["T2"].notna()]
                exc = (t2["T2"] - t2["GG_OK"]) / t2["GG_OK"]
                row = {"Measure": code, "Sample": smp, "Practice": p, "N": len(g), "Countries": g["ISO"].nunique(),
                       "Countries outside Europe": g.loc[g["REGION"] != "Europe", "ISO"].nunique(),
                       "CGSS/GG, median": r.median(), "CGSS/GG, P25": _q(r, 0.25), "CGSS/GG, P75": _q(r, 0.75),
                       "CGSS/GG, median country": _cmed(r, g["ISO"]),
                       "(SG+LG)/GG, median": sub.median(), "(SG+LG)/GG, median country": _cmed(sub, g["ISO"]),
                       "Complete T2 available: N": len(t2),
                       "(T2-GG)/GG, median": exc.median(), "(T2-GG)/GG, median country": _cmed(exc, t2["ISO"]),
                       # exact accounting on the rows with a complete T2 sum: mean CGSS/GG = 1 - mean (SG+LG)/GG + mean excess
                       "T2 rows: mean CGSS/GG": (t2["CG"] / t2["GG_OK"]).mean(),
                       "T2 rows: mean (SG+LG)/GG": (t2["SUBNAT"] / t2["GG_OK"]).mean(),
                       "T2 rows: mean (T2-GG)/GG": exc.mean(),
                       "Shortfall GG-CGSS (pp GDP), median": (g["GG_OK"] - g["CG"]).median(),
                       "Shortfall GG-CGSS (pp GDP), median country": _cmed(g["GG_OK"] - g["CG"], g["ISO"])}
                if code in ("HE", "07", "09"):
                    row.update(redistribution(g, "CG", inp))
                rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Item 3: pairwise main samples, identities, decomposition
# ----------------------------------------------------------------------------

def pairwise_main(ms: dict, inp: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for code in ("HE", "SOC", "07", "09", "10"):
        m = ms[code]
        base = m[m["GG_OK"].notna() & (m["SUBNAT"] > 0)]
        for alt in ("CG", "T2", "T3", "RULE", "SPL5", "SPL1"):
            s0 = base[base[alt].notna()]
            dev = (s0[alt] / s0["GG_OK"] - 1).abs()
            exact = (s0[alt] - s0["GG_OK"]).abs() <= TOL * s0["GG_OK"]
            near = dev <= NEAR
            for var, s in (("All", s0), ("Excluding exact identities", s0[~exact]),
                           ("Excluding values within 0.5% of GG", s0[~near])):
                if s.empty:
                    continue
                st = ext.fixed_sample_stats_r(s.rename(columns={"GG_OK": "GG"}).assign(ALT=s[alt])[
                    ["ISO", "YEAR", "GG", "ALT", "GDPPC", "REGION"]])
                row = {"Measure": code, "Alternative": ALT_LAB[alt], "Sample": "Pairwise, subnational > 0",
                       "Identity rule": var, "Exact identities in the pairwise sample": int(exact.sum()),
                       "Near identities (within 0.5%, not exact)": int((near & ~exact).sum()),
                       "Pairwise sample N": len(s0), "Pairwise sample countries": s0["ISO"].nunique(), **st}
                if code == "HE":
                    row.update(redistribution(s, alt, inp))
                rows.append(row)
    keep = ["Measure", "Alternative", "Sample", "Identity rule", "Pairwise sample N", "Pairwise sample countries",
            "Exact identities in the pairwise sample", "Near identities (within 0.5%, not exact)", "N", "Countries",
            "Countries outside Europe", "Years", "Median ratio", "P25 ratio", "P75 ratio", "Median ratio, median country",
            "Error > 10% (%)", "Error > 25% (%)", "Shortfall GG - alt (pp GDP), pooled median",
            "Shortfall GG - alt (pp GDP), median country", "Shortfall (% of GG), pooled median",
            "Shortfall (% of GG), median country", "Spearman, country means", "Mean abs. quintile shift",
            "Mean abs. quintile shift, random reordering", "Mean abs. quintile shift, permutation p",
            "Countries moving 2+ quintiles (%)", "Countries moving 2+ quintiles, random reordering (%)",
            "b GG", "b alt", "Difference (alt - GG)", "Difference, bootstrap 2.5%", "Difference, bootstrap 97.5%"]
    out = pd.DataFrame(rows)
    return out[keep + [c for c in out.columns if c not in keep]]


def decomposition(ms_by_release: dict) -> pd.DataFrame:
    """CGSS/GG on the common sample: share with subnational spending, conditional ratios and the median."""
    rows = []
    for rel, ms in ms_by_release.items():
        for code in ("HE", "07", "09", "SOC"):
            m = ms[code]
            base = m[m["GG_OK"].notna()]
            common = base[base[ext.COMMON].notna().all(axis=1)]
            r = common["CG"] / common["GG_OK"]
            sp = common["SUBNAT"] > 0
            p = sp.mean()
            rs, rn = r[sp], r[~sp]
            srt = np.sort(r.to_numpy())
            rows.append({"Release": rel, "Measure": code, "N": len(common), "Countries": common["ISO"].nunique(),
                         "Share with SG + LG > 0": p, "N with SG + LG > 0": int(sp.sum()),
                         "Median CGSS/GG, all": r.median(), "Median CGSS/GG | SG + LG > 0": rs.median(),
                         "Median CGSS/GG | SG + LG = 0": rn.median(), "Min CGSS/GG | SG + LG = 0": rn.min(),
                         "Quantile 0.5/p of CGSS/GG | SG + LG > 0": rs.quantile(min(1.0, 0.5 / p)),
                         "Mean CGSS/GG, all": r.mean(), "Mean CGSS/GG | SG + LG > 0": rs.mean(),
                         "p x mean | SG + LG > 0 + (1 - p) x mean | SG + LG = 0": p * rs.mean() + (1 - p) * rn.mean(),
                         "Values in (0.72, 0.85)": int(((r > 0.72) & (r < 0.85)).sum()),
                         "Values <= 0.72": int((r <= 0.72).sum()), "Values >= 0.999": int((r >= 0.999).sum()),
                         "Ordered values around the median": " ".join(f"{v:.3f}" for v in srt[len(srt) // 2 - 4: len(srt) // 2 + 5])})
    return pd.DataFrame(rows)


def release_changes(ms_feb: dict, ms_oct: dict) -> pd.DataFrame:
    """Country-years of the HE common sample added in the October release and changes in the others."""
    def common(ms):
        m = ms["HE"]
        b = m[m["GG_OK"].notna()]
        b = b[b[ext.COMMON].notna().all(axis=1)].copy()
        b["R"] = b["CG"] / b["GG_OK"]
        return b.set_index(["ISO", "YEAR"])
    f, o = common(ms_feb), common(ms_oct)
    new, gone, both = o.index.difference(f.index), f.index.difference(o.index), o.index.intersection(f.index)
    dr = (o.loc[both, "R"] - f.loc[both, "R"]).abs()
    rows = [{"Item": "Common sample, February", "Value": len(f)}, {"Item": "Common sample, October", "Value": len(o)},
            {"Item": "Country-years added in October", "Value": len(new),
             "Detail": f"years {sorted(set(i[1] for i in new))}"},
            {"Item": "  of which CGSS/GG >= 0.85", "Value": int((o.loc[new, "R"] >= 0.85).sum())},
            {"Item": "  of which SG + LG = 0", "Value": int((o.loc[new, "SUBNAT"] <= 0).sum())},
            {"Item": "Country-years dropped in October", "Value": len(gone)},
            {"Item": "Country-years in both releases", "Value": len(both)},
            {"Item": "  of which CGSS/GG changes by more than 0.01", "Value": int((dr > 0.01).sum()),
             "Detail": " ".join(sorted(set(i[0] for i in dr[dr > 0.01].index)))}]
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Item 4: classification variants
# ----------------------------------------------------------------------------

def classify(h: pd.DataFrame, gv, kind: str = "RULE", fcol: str = "F", cut: float = ext.F_CUT) -> pd.DataFrame:
    """Country-year classification of evaluate_extensions.practice_tables for one kind of sum and one F."""
    o = ext.overlap_cells(h, kind)
    d = ext.division01_metrics(o, gv)
    f = o[o["DIV"] != "01"].merge(d[["ISO", "YEAR"]], on=["ISO", "YEAR"])
    f["GAP_C"] = f["GAP"].where(f["GAP"] > ext.GAP_MIN * f[GG], 0.0)
    fg = f.groupby(["ISO", "YEAR"]).agg(N_DIV=("DIV", "size"), N_IDENT=("IDENT", "sum"), FGAP=("GAP_C", "sum"))
    fx = f[~f["DIV"].isin(["07", "10"])].groupby(["ISO", "YEAR"]).agg(FGAP_X=("GAP_C", "sum"))
    for dv in ("07", "09", "10"):
        fd = f[f["DIV"] == dv].set_index(["ISO", "YEAR"])["GAP_C"].rename(f"GAP_C_{dv}")
        fg = fg.join(fd)
    d = d.merge(fg.reset_index(), on=["ISO", "YEAR"], how="left").merge(fx.reset_index(), on=["ISO", "YEAR"], how="left")
    g01 = d["GAP01"].where(d["GAP01_POS"], 0.0)
    for col, fc in (("F", "FGAP"), ("F_X", "FGAP_X")):
        tot = d[fc] + g01
        d[col] = (d[fc] / tot.where(tot > 0)).fillna(0.0).where(d["N_DIV"] >= 6)
    share = d["R018"].where(d["R018"].notna(), d["RC018"])
    d["SHARE018"] = share
    d["REC018"] = (d["C018"] > 0) & (share >= 0.5)
    d["ANY_GAP"] = d["GAP01_POS"] | (d["FGAP"] > 0)

    def one(F, rec, any_gap):
        if pd.isna(F):
            return "U"
        if not any_gap:
            return "E"
        if F <= cut:
            return "A" if rec else "D"
        return "C" if rec else "B"
    d["CLASS"] = [one(F, r, g) for F, r, g in zip(d[fcol], d["REC018"], d["ANY_GAP"])]
    d["F_USED"] = d[fcol]
    return d


def country_table(d: pd.DataFrame, cut: float = ext.F_CUT) -> pd.DataFrame:
    cl = d[d["CLASS"] != "U"]
    g = d.groupby("ISO")
    t = pd.DataFrame({"Country-years": g.size(), "Sum": g["KIND"].agg(lambda s: "/".join(sorted(set(s))))})
    t["Classified years"] = cl.groupby("ISO").size().reindex(t.index).fillna(0).astype(int)
    t["Practice"] = g["CLASS"].agg(lambda s: ext.country_practice(s)[0])
    t["Modal class"] = g["CLASS"].agg(lambda s: ext.country_practice(s)[1])
    t["Years in modal class (% of classified)"] = g["CLASS"].agg(lambda s: ext.country_practice(s)[2])
    # criteria in the unit of the classification: shares of classified years
    t["Share of classified years with F > threshold"] = (cl["F_USED"] > cut).groupby(cl["ISO"]).mean().reindex(t.index)
    t["Share of classified years with a 01.8 record"] = cl["REC018"].groupby(cl["ISO"]).mean().reindex(t.index)
    # medians over the years of the modal class
    for col, lab in (("F_USED", "Median F, years in modal class"), ("SHARE018", "Median 01.8 share of 01 gap, years in modal class")):
        t[lab] = [d.loc[(d["ISO"] == i) & (d["CLASS"] == t.at[i, "Modal class"]), col].median() for i in t.index]
    # the medians shown in the earlier Figure 1(b)
    t["Median F, all years with F"] = g["F_USED"].median()
    t["Median 01.8 gap / 01 gap"] = g["R018"].median()
    t["Median central 01.8 / 01 gap"] = g["RC018"].median()
    return t


def variant_tables(h, gv, gr, reg, prac_pub: pd.Series):
    specs = [("Baseline: complete sum (T2, otherwise T3), F over divisions 02-10", "RULE", "F"),
             ("T2 sums only", "T2", "F"),
             ("F excluding divisions 07 and 10", "RULE", "F_X"),
             ("T2 sums only, F excluding divisions 07 and 10", "T2", "F_X")]
    counts, tests, moves, ctabs = [], [], [], {}
    base_prac = None
    for name, kind, fcol in specs:
        d = classify(h, gv, kind, fcol)
        ct = country_table(d)
        ctabs[name] = (d, ct)
        prac = ct["Practice"]
        if base_prac is None:
            base_prac = prac
        vc = prac.value_counts()
        row = {"Variant": name, "Country-years": len(d), "Countries": d["ISO"].nunique(),
               "Classified country-years": int((d["CLASS"] != "U").sum())}
        for p in ("A", "B", "C", "D", "E", "U"):
            row[f"Countries {p}"] = int(vc.get(p, 0))
        row["A outside Europe"] = int(((prac == "A") & (prac.index.map(reg["region"]) != "Europe")).sum())
        row["A in EU/EFTA"] = int(((prac == "A") & prac.index.isin(ext.EU_EFTA)).sum())
        counts.append(row)
        # grant tests on this classification
        if gr is not None:
            b5, cc = ext.grant_tests(d, ct.reset_index()[["ISO", "Practice"]], gr)
            ta = b5[b5["Test"].astype(str).str.startswith("(a)") & b5["Practice"].isin(["A", "B", "C", "B and C"])]
            for _, r in ta.iterrows():
                if r["Cells"] == 0:
                    continue
                tests.append({"Variant": name, "Practice": r["Practice"], "Sum": r["Sum"], "Cells": r["Cells"],
                              "Countries": r["Countries"], "Median": r["Median"], "P25": r["P25"], "P75": r["P75"],
                              "Within 10% (%)": r["Within 10% (%)"], "Median of country medians": r["Median of country medians"]})
            for p in ("A", "B", "C"):
                x = cc[cc["Practice"] == p]
                tests.append({"Variant": name, "Practice": p, "Sum": "Country medians",
                              "Countries with grant data": len(x),
                              "Countries within 10% of 1": int(x["Passes (a): within 10%"].sum()),
                              "Countries below 0.5": int((x["Median central 01.8 / central 263"] < 0.5).sum()),
                              "Countries outside 10% (ISO: country median)": " ".join(
                                  f"{i}:{v:.3f}" for i, v, ok in zip(x["ISO"], x["Median central 01.8 / central 263"],
                                                                     x["Passes (a): within 10%"]) if not ok),
                              "Practice countries without grant data": " ".join(sorted(set(ct.index[ct["Practice"] == p]) - set(x["ISO"])))})
        ch = prac.reindex(base_prac.index.union(prac.index))
        bp = base_prac.reindex(ch.index)
        for iso in ch.index[(ch.fillna("-") != bp.fillna("-"))]:
            moves.append({"Variant": name, "ISO": iso, "Country": reg["name"].get(iso, iso),
                          "Baseline practice": bp.get(iso, "-") if pd.notna(bp.get(iso)) else "not in sample",
                          "Variant practice": ch.get(iso) if pd.notna(ch.get(iso)) else "not in sample"})
    base_d, base_ct = ctabs[specs[0][0]]
    chk = pd.DataFrame([{"Check": "Baseline classification equals ext_b3_practice_countries.csv (every country)",
                         "Match": bool(prac_pub is not None and base_ct["Practice"].sort_index().equals(prac_pub.sort_index()))}])
    return pd.DataFrame(counts), pd.DataFrame(tests), pd.DataFrame(moves), ctabs, chk


def country_details(ctabs: dict, gr: pd.DataFrame, grp: pd.DataFrame) -> pd.DataFrame:
    """Year-level evidence for three countries named in the review (variables from the classification)."""
    d, ct = ctabs["Baseline: complete sum (T2, otherwise T3), F over divisions 02-10"]
    dx_, _ = ctabs["F excluding divisions 07 and 10"]
    v = gr.set_index(["ISO", "YEAR", "SECTOR", "ITEM"])["VALUE"].to_dict()
    gtot = grp[grp["GRP"] == "TOT"].set_index(["ISO", "YEAR", "SECTOR_NORM"])["VALUE"].to_dict()
    rows = []
    for iso in ("LTU", "LVA", "SWE"):
        x = d[d["ISO"] == iso].set_index("YEAR")
        xx = dx_[dx_["ISO"] == iso].set_index("YEAR")
        for y, r in x.iterrows():
            comps = r["COMPS"].split("+")
            cen = [s for s in comps if s in ext.CENTRAL_ABBR]
            c263 = sum(v.get((iso, y, s, "263"), np.nan) for s in cen)
            ssf263 = v.get((iso, y, "SSF", "263"), np.nan)
            lg133 = v.get((iso, y, "LG", "133"), np.nan)
            ssf_tot = gtot.get((iso, y, ext.SSF), np.nan)
            row = {"ISO": iso, "YEAR": y, "Sum": r["KIND"], "Components": r["COMPS"], "N divisions 02-10 with a complete sum": r["N_DIV"],
                   "Gap 01 (% GDP)": r["GAP01"], "GG 01.8 (% GDP)": r["G018"], "Central 01.8 (% GDP)": r["C018"],
                   "01.8 share of 01 gap (criterion)": r["SHARE018"], "01.8 record": r["REC018"],
                   "Gap 07 counted (% GDP)": r.get("GAP_C_07"), "Gap 09 counted (% GDP)": r.get("GAP_C_09"),
                   "Gap 10 counted (% GDP)": r.get("GAP_C_10"), "Gaps 02-10 counted (% GDP)": r["FGAP"],
                   "Gaps 02-10 excl. 07 and 10 (% GDP)": r["FGAP_X"], "F": r["F"], "F excl. 07 and 10": r["F_X"],
                   "Class (baseline)": r["CLASS"], "Class (F excl. 07 and 10)": xx.at[y, "CLASS"] if y in xx.index else None,
                   "Central grants 263 (% GDP)": c263, "Central 01.8 / central 263": r["C018"] / c263 if c263 and c263 > 0 else np.nan,
                   "SSF grants 263 (% GDP)": ssf263, "LG grants received 133 (% GDP)": lg133,
                   "Central 01.8 / LG grants received": r["C018"] / lg133 if lg133 and lg133 > 0 else np.nan,
                   "Total outlays: sum (% GDP)": r["STOT"], "Total outlays: GG (% GDP)": r["GTOT"], "Total-outlays gap / 01 gap": r["RTOT"],
                   "SSF total outlays (% GDP)": ssf_tot,
                   "Total-outlays gap with SSF added (% GDP)": (r["STOT"] + ssf_tot - r["GTOT"]) if "SSF" not in comps and pd.notna(ssf_tot) else np.nan}
            rows.append(row)
    return pd.DataFrame(rows)


def ssf_history(h: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for iso in ("LTU", "LVA", "SWE"):
        x = h[h["ISO"] == iso]
        for dv, g in x.groupby("DIV"):
            s = g[g[SSF].notna()]
            t3c = g[g[GG].notna() & (g[GG] > 0) & (g["COMPLETE"] == True)]  # noqa: E712
            rows.append({"ISO": iso, "DIV": dv, "SSF reported: years": len(s),
                         "SSF reported: first": s["YEAR"].min() if len(s) else None,
                         "SSF reported: last": s["YEAR"].max() if len(s) else None,
                         "GG overlap years": len(t3c), "Complete T3 sum in GG overlap years": int(t3c["T3_COMPLETE"].sum()),
                         "Complete T2 sum in GG overlap years": int(t3c["T2_COMPLETE"].sum())})
    return pd.DataFrame(rows)


def fig_classification_r6(ct_base: pd.DataFrame, ctry_pub: pd.DataFrame, path) -> pd.DataFrame:
    """
    Panel (a) as in evaluate_extensions.fig_classification. Panel (b) in the unit of the classification:
    for each country, the share of its classified years in which F exceeds 0.10 and the share in which
    central government records group 01.8. A country takes a practice only when that practice holds in
    more than half of its classified years, so practices A, B and C lie in their quadrants.
    """
    import matplotlib.pyplot as plt
    ctry = ctry_pub.set_index("ISO").join(ct_base[["Share of classified years with F > threshold",
                                                     "Share of classified years with a 01.8 record"]])
    colors = ext.PRACTICE_COLORS
    groups = [(p, ctry[ctry["Practice"] == p], colors[p]) for p in ("A", "B", "C")]
    groups.append(("other", ctry[~ctry["Practice"].isin(["A", "B", "C"])], eh.INK2))
    labels = {"A": "A: 01.8, eliminated there", "B": "B: by function", "C": "C: both"}
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2), dpi=200)
    ax = axes[0]
    hi = np.nanmax(ctry[["Median 01 gap (% GDP)", "Median 01.8 gap (% GDP)"]].to_numpy()) * 1.05
    ax.plot([0, hi], [0, hi], color=eh.INK2, linewidth=0.8, zorder=1)
    none = ctry["Median 01.8 gap (% GDP)"].isna() & ctry["Median central 01.8 (% GDP)"].isna()
    for p, g, col in groups:
        filled = p != "other"
        has = g["Median 01.8 gap (% GDP)"].notna()
        cen = ~has & g["Median central 01.8 (% GDP)"].notna()
        nan = ~has & ~cen
        ax.scatter(g.loc[has, "Median 01 gap (% GDP)"], g.loc[has, "Median 01.8 gap (% GDP)"], s=26, zorder=2,
                   color=col if filled else "white", edgecolor="white" if filled else col, linewidth=0.8 if filled else 1.2,
                   label=labels.get(p, "Undetermined or other"))
        ax.scatter(g.loc[cen, "Median 01 gap (% GDP)"], g.loc[cen, "Median central 01.8 (% GDP)"], s=30, zorder=2,
                   marker="^", color=col if filled else "white", edgecolor="white" if filled else col,
                   linewidth=0.8 if filled else 1.2)
        # central government does not report group 01.8: shown at zero (crosses)
        ax.scatter(g.loc[nan, "Median 01 gap (% GDP)"], np.zeros(int(nan.sum())), s=30, zorder=3, marker="x",
                   color=col, linewidth=1.3, clip_on=False)
    ax.scatter([], [], s=30, marker="x", color=eh.INK2, linewidth=1.3, label="Group 01.8 not reported (at zero)")
    ax.set_title("(a) Gap in group 01.8 against gap in division 01", fontsize=10, color=eh.INK, loc="left")
    eh._style(ax)
    ax.set_xlim(0, hi)
    ax.set_ylim(0, hi)
    ax.set_xlabel("Gap in division 01: sum minus GG, % of GDP", fontsize=9, color=eh.INK2)
    ax.set_ylabel("Gap in group 01.8, % of GDP", fontsize=9, color=eh.INK2)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax = axes[1]
    # deterministic sunflower offsets so that countries at the same shares stay visible
    xy = ctry[["Share of classified years with F > threshold", "Share of classified years with a 01.8 record"]].copy()
    key = xy.iloc[:, 0].map("{:.4f}".format) + "|" + xy.iloc[:, 1].map("{:.4f}".format)
    rank = key.groupby(key).cumcount().to_numpy()
    size = key.map(key.value_counts()).to_numpy()
    ang = rank * np.pi * (3 - np.sqrt(5))
    rad = np.where(size > 1, 0.014 * np.sqrt(rank + 0.5), 0.0)
    xs = xy.iloc[:, 0] + rad * np.cos(ang)
    ys = xy.iloc[:, 1] + rad * np.sin(ang)
    for p, g, col in groups:
        filled = p != "other"
        gi = g.index[~none[g.index]]
        ax.scatter(xs[gi], ys[gi], s=24, zorder=2, color=col if filled else "white",
                   edgecolor="white" if filled else col, linewidth=0.8 if filled else 1.2)
        gx = g.index[none[g.index]]
        ax.scatter(xs[gx], ys[gx], s=28, zorder=3, marker="x", color=col, linewidth=1.3)
    ax.axvline(0.5, color=eh.INK2, linewidth=0.8, linestyle="--")
    ax.axhline(0.5, color=eh.INK2, linewidth=0.8, linestyle="--")
    for (x0, y0, txt) in ((0.03, 1.07, "A"), (0.97, 0.03, "B"), (0.97, 1.07, "C"), (0.03, 0.03, "D")):
        ax.text(x0, y0, txt, fontsize=9, color=eh.INK2, ha="left" if x0 < 0.5 else "right", va="center")
    ax.set_title("(b) Classification criteria, share of classified years", fontsize=10, color=eh.INK, loc="left")
    eh._style(ax)
    ax.set_xlim(-0.08, 1.08)
    ax.set_ylim(-0.08, 1.12)
    ax.set_xlabel("Share of years with F above 0.10", fontsize=9, color=eh.INK2)
    ax.set_ylabel("Share of years with a 01.8 record", fontsize=9, color=eh.INK2)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)
    out = ctry[["Practice", "Classified years", "Share of classified years with F > threshold",
                "Share of classified years with a 01.8 record", "Median share of consolidation outside 01 (F)",
                "Median 01.8 gap / 01 gap", "Median central 01.8 / 01 gap", "Median 01 gap (% GDP)",
                "Median 01.8 gap (% GDP)", "Median central 01.8 (% GDP)"]].copy()
    out["Group 01.8 not reported (cross)"] = none
    # quadrant checks: earlier panel (b) and the new one
    yb = out["Median 01.8 gap / 01 gap"].fillna(out["Median central 01.8 / 01 gap"])
    xb = out["Median share of consolidation outside 01 (F)"]
    exp_old = {"A": (xb <= ext.F_CUT) & (yb >= 0.5), "B": (xb > ext.F_CUT) & (yb < 0.5), "C": (xb > ext.F_CUT) & (yb >= 0.5)}
    xn, yn = out["Share of classified years with F > threshold"], out["Share of classified years with a 01.8 record"]
    exp_new = {"A": (xn < 0.5) & (yn > 0.5), "B": (xn > 0.5) & (yn < 0.5), "C": (xn > 0.5) & (yn > 0.5)}
    out["In quadrant, earlier panel (b)"] = [bool(exp_old[p][i]) if p in exp_old else None for i, p in out["Practice"].items()]
    out["In quadrant, new panel (b)"] = [bool(exp_new[p][i]) if p in exp_new else None for i, p in out["Practice"].items()]
    return out.reset_index()


# ----------------------------------------------------------------------------
# Item 5: traces
# ----------------------------------------------------------------------------

def traces(ms: dict, c: pd.DataFrame) -> pd.DataFrame:
    rows = []
    nid = {k: noid_sample(ms[k]).set_index(["ISO", "YEAR"]) for k in ("07", "09", "10", "HE", "SOC")}
    for k, s in nid.items():
        rows.append({"Item": f"Fixed sample without identities, {k}", "Value": len(s), "Detail": f"{s.index.get_level_values(0).nunique()} countries"})
    he, ed = nid["HE"], nid["09"]
    only_he = he.index.difference(ed.index)
    only_ed = ed.index.difference(he.index)
    cc = c.set_index(["ISO", "DIV", "YEAR"])

    def why09(i):
        iso, y = i
        r = cc.loc[(iso, "09", y)]
        ids = [a for a in ("T2", "T3") if pd.notna(r[a]) and abs(r[a] - r["GG_OK"]) <= TOL * r["GG_OK"]]
        if ids:
            return f"complete {'/'.join(ids)} sum equals GG in 09"
        if not r["SUBNAT"] > 0:
            return "no SG or LG spending in 09"
        return "an alternative missing in 09"
    reasons = pd.Series([why09(i) for i in only_he], dtype=object)
    rows.append({"Item": "In the health and education sample, not in the education sample", "Value": len(only_he),
                 "Detail": "; ".join(f"{k}: {v}" for k, v in reasons.value_counts().items()) + " | " +
                           " ".join(f"{i[0]}{i[1]}" for i in only_he)})
    rows.append({"Item": "  countries lost from the education sample", "Value": len(set(he.index.get_level_values(0)) - set(ed.index.get_level_values(0))),
                 "Detail": " ".join(sorted(set(he.index.get_level_values(0)) - set(ed.index.get_level_values(0))))})
    rows.append({"Item": "In the education sample, not in the health and education sample", "Value": len(only_ed),
                 "Detail": " ".join(f"{i[0]}{i[1]}" for i in only_ed)})
    for k, lab in (("07", "health"), ("10", "social protection")):
        x = nid[k]
        rows.append({"Item": f"In the health and education sample, not in the {lab} sample", "Value": len(he.index.difference(x.index))})
    soc = nid["SOC"]
    rows.append({"Item": "Social spending sample minus health and education sample", "Value": len(soc.index.difference(he.index)),
                 "Detail": f"{len(he.index.difference(soc.index))} in health and education only"})
    # pairwise samples of CGSS alone with subnational spending
    for k in ("07", "09", "10", "HE", "SOC"):
        m = ms[k]
        b = m[m["GG_OK"].notna() & m["CG"].notna() & (m["SUBNAT"] > 0)]
        eu = b[b["REGION"] == "Europe"]
        rows.append({"Item": f"Pairwise sample, CGSS alone, SG + LG > 0, {k}", "Value": len(b),
                     "Detail": f"{b['ISO'].nunique()} countries, Europe {len(eu)} country-years in {eu['ISO'].nunique()} countries"})
    m07, m09 = ms["07"], ms["09"]
    he_pw = ms["HE"][ms["HE"]["GG_OK"].notna() & ms["HE"]["CG"].notna() & (ms["HE"]["SUBNAT"] > 0)].set_index(["ISO", "YEAR"])
    s07 = m07[m07["SUBNAT"] > 0].set_index(["ISO", "YEAR"]).index
    s09 = m09[m09["SUBNAT"] > 0].set_index(["ISO", "YEAR"]).index
    rows.append({"Item": "  HE pairwise country-years with SG + LG = 0 in 07 (subnational spending in 09 only)",
                 "Value": len(he_pw.index.difference(s07))})
    rows.append({"Item": "  HE pairwise country-years with SG + LG = 0 in 09 (subnational spending in 07 only)",
                 "Value": len(he_pw.index.difference(s09))})
    for k in ("HE", "SOC"):
        m = ms[k]
        b = m[m["GG_OK"].notna()]
        cm = b[b[ext.COMMON].notna().all(axis=1)]
        rows.append({"Item": f"Common sample, {k}", "Value": len(cm), "Detail": f"{cm['ISO'].nunique()} countries, "
                     f"{int((cm['SUBNAT'] > 0).sum())} with SG + LG > 0"})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0].strip())
    ap.add_argument("--source", type=Path, default=ext.RAW)
    ap.add_argument("--vintage", type=Path, help="IMF release of 21 October 2026 (CSV), for the decomposition")
    ap.add_argument("--out", type=Path, default=HERE / "output_r6")
    ap.add_argument("--cache", type=Path, help="folder of the extract caches _ext_long_*.pkl (default: --out)")
    ap.add_argument("--practice", type=Path, help="ext_b3_practice_countries.csv of evaluate_extensions.py")
    ap.add_argument("--benchmarks", type=Path, default=HERE / "data_ext" / "ext_benchmarks_wdi.csv")
    ap.add_argument("--inputs", type=Path, default=HERE / "data_ext" / "dist_inputs_wid_wdi.csv")
    ap.add_argument("--grants", type=Path, default=ext.GRANTS_FILE)
    a = ap.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache = (a.cache or out).resolve()

    div, grp, digest = ext.load_extract(a.source.resolve(), cache)
    h = eh.harmonise(eh.to_wide(div))
    reg = ext.regions()
    gdp = eh.load_gdppc()
    c = ext.cell_table(h)
    ms = measures(c, gdp, reg)
    inp = dx.load_inputs(a.inputs.resolve())
    bm = pd.read_csv(a.benchmarks.resolve())
    gr = ext.load_grants(a.grants.resolve()) if a.grants.exists() else None
    gv = ext.GroupValues(grp)
    ctry_pub = pd.read_csv(a.practice) if a.practice else None
    prac_pub = ctry_pub.set_index("ISO")["Practice"] if ctry_pub is not None else None
    print(f"Extract SHA-256 {digest[:12]}..., {len(h)} cells")

    tables = {}
    # Item 1
    tables["ext_r6_1a_benchmark_overlap"], tables["ext_r6_1b_benchmark_without_gg"], tables["ext_r6_1_headline"] = \
        benchmark_tables(c, bm, reg)
    # Item 4 first: the classification gives the practices of item 2
    counts, tests, moves, ctabs, chk = variant_tables(h, gv, gr, reg, prac_pub)
    tables.update({"ext_r6_4_variant_counts": counts, "ext_r6_4_variant_grant_test_a": tests,
                   "ext_r6_4_variant_moves": moves, "ext_r6_4_country_details": country_details(ctabs, gr, grp),
                   "ext_r6_4_ssf_history": ssf_history(h)})
    base_ct = ctabs["Baseline: complete sum (T2, otherwise T3), F over divisions 02-10"][1]
    prac = prac_pub if prac_pub is not None else base_ct["Practice"]
    if ctry_pub is not None:
        tables["ext_r6_4_fig_classification_data"] = fig_classification_r6(base_ct, ctry_pub, out / "ext_fig_classification_r6.png")
    # Item 2
    tables["ext_r6_2_cgss_by_practice"] = by_practice(ms, prac, inp)
    # Item 3
    tables["ext_r6_3_pairwise_main"] = pairwise_main(ms, inp)
    rel = {"February 2026": ms}
    if a.vintage is not None and a.vintage.exists():
        div_o, _, dig_o = ext.load_extract(a.vintage.resolve(), cache)
        ms_o = measures(ext.cell_table(eh.harmonise(eh.to_wide(div_o))), gdp, reg)
        rel["October 2026"] = ms_o
        tables["ext_r6_3_release_changes"] = release_changes(ms, ms_o)
        print(f"Vintage SHA-256 {dig_o[:12]}...")
    tables["ext_r6_3_decomposition"] = decomposition(rel)
    # Item 5
    tables["ext_r6_5_traces"] = traces(ms, c)
    # checks
    chk_rows = list(chk.to_dict("records"))
    he = ms["HE"]
    pw = he[he["GG_OK"].notna() & he["CG"].notna() & (he["SUBNAT"] > 0)]
    chk_rows.append({"Check": "HE pairwise CGSS sample with SG + LG > 0: 570 country-years, 37 countries",
                     "Match": bool(len(pw) == 570 and pw["ISO"].nunique() == 37)})
    nd = noid_sample(he)
    chk_rows.append({"Check": "HE fixed sample without identities: 184 country-years, 22 countries",
                     "Match": bool(len(nd) == 184 and nd["ISO"].nunique() == 22)})
    tables["ext_r6_checks"] = pd.DataFrame(chk_rows)

    for name, t in tables.items():
        t.round(6).to_csv(out / f"{name}.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    for name in ("ext_r6_1_headline", "ext_r6_4_variant_counts", "ext_r6_3_decomposition", "ext_r6_checks"):
        print(f"\n=== {name} ===")
        print(tables[name].round(3).to_string(index=False))
    print(f"\nOutputs in {out}")


if __name__ == "__main__":
    main()
