"""
Empirical evaluation of the tiered harmonisation rule for IMF GFS COFOG data (Paper B).

Replication script for the SJIAOS article on subsector harmonisation. Run from the repository root:
    python replication/sjiaos/evaluate_harmonisation.py

Inputs : data/gfs_raw_data.xlsx (IMF GFS_COFOG 11.0.0, published 2026-02-03)
         data/country_codes.xlsx
         replication/sjiaos/data_ext/eurostat_gov10a_exp_S13_TE_pcgdp.tsv  (Eurostat gov_10a_exp)
         replication/sjiaos/data_ext/wb_NY.GDP.PCAP.PP.KD.json, wb_countries.json (World Bank WDI)
Outputs: replication/sjiaos/output/table*.csv (manuscript tables), supp_*.csv (supplementary tables),
         fig*.png, harmonised_all_divisions.csv, results.json
"""
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from cofog_panel.aggregate import (  # noqa: E402
    resolve_value, is_complete, IMF_TO_ISO, COVERAGE_LEVELS, SECTOR_ABBR,
    GG, CGSS, CGXSS, BCG, EBCG, SSF, SG, LG,
)

RAW = REPO / "data" / "gfs_raw_data.xlsx"
# SHA-256 of the extract used in the article (IMF.STA:GFS_COFOG 11.0.0)
RAW_SHA256 = "91e3db1bdb838f322dcbe648b133f511f3efe1921e50c8bc0d7621f512668cfe"
LOOKUP = REPO / "data" / "country_codes.xlsx"
EXT = HERE / "data_ext"
OUT = HERE / "output"
OUT.mkdir(parents=True, exist_ok=True)

YEARS = range(1990, 2025)
DIVISIONS = {
    "01": "General public services", "02": "Defence", "03": "Public order and safety",
    "04": "Economic affairs", "05": "Environmental protection", "06": "Housing and community amenities",
    "07": "Health", "08": "Recreation, culture and religion", "09": "Education", "10": "Social protection",
}
SECTORS = [GG, CGSS, CGXSS, BCG, EBCG, SSF, SG, LG]
IDENTITY_TOL = 1e-6          # relative tolerance for "estimate equals reported GG"
ADJ_K = 3                    # overlap years used for the consolidation ratio
ADJ_DISTANCES = (1, 3, 5)    # minimum distance (years) between held-out year and ratio years
ADJ_K_ALT = (1, 3, 5)        # sensitivity of the adjustment to k
BOOT_REPS = 1000             # country-cluster bootstrap replications
BOOT_SEED = 20260203

# Reference palette, categorical slots 1-3 (validated all-pairs, light mode)
TIER_COLORS = {"T1": "#2a78d6", "T2": "#eb6834", "T3": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


# ----------------------------------------------------------------------------
# 1. Load raw GFS data into a long table: ISO, division, sector, year, value
# ----------------------------------------------------------------------------

def check_raw():
    if not RAW.exists():
        sys.exit(f"Missing {RAW}: download the GFS COFOG extract from https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG "
                 "(see replication/sjiaos/README.md).")
    digest = hashlib.sha256(RAW.read_bytes()).hexdigest()
    if digest != RAW_SHA256:
        print(f"WARNING: {RAW.name} differs from the extract used in the article (SHA-256 {digest[:12]}..., "
              f"expected {RAW_SHA256[:12]}...). Results will reflect a different IMF vintage.")


def load_long() -> pd.DataFrame:
    check_raw()
    cache = OUT / f"_gfs_long_pcgdp_{YEARS.start}_{YEARS.stop - 1}.pkl"
    if cache.exists() and cache.stat().st_mtime > RAW.stat().st_mtime:
        return pd.read_pickle(cache)
    raw = pd.read_excel(RAW)
    raw = raw[raw["TYPE_OF_TRANSFORMATION"] == "Percent of GDP"].copy()
    parts = raw["SERIES_CODE"].str.split(".", expand=True)
    raw["ISO"] = parts[0].str.upper().replace(IMF_TO_ISO)
    raw["DIV"] = parts[3].str.extract(r"^GF(\d+)_T")[0]
    raw = raw[raw["DIV"].str.len() == 2]          # top-level divisions only
    raw["SECTOR_NORM"] = raw["SECTOR"].str.lower().str.strip()
    ycols = [c for c in raw.columns if str(c).isdigit() and int(c) in YEARS]
    long = raw.melt(id_vars=["ISO", "DIV", "SECTOR_NORM"], value_vars=ycols,
                    var_name="YEAR", value_name="VALUE").dropna(subset=["VALUE"])
    long["YEAR"] = long["YEAR"].astype(int)
    long = long.drop_duplicates(subset=["ISO", "DIV", "SECTOR_NORM", "YEAR"])
    long.to_pickle(cache)
    return long


def to_wide(long: pd.DataFrame) -> pd.DataFrame:
    """One row per (ISO, DIV, YEAR), one column per sector."""
    w = long.pivot_table(index=["ISO", "DIV", "YEAR"], columns="SECTOR_NORM",
                         values="VALUE", aggfunc="first")
    for s in SECTORS:
        if s not in w.columns:
            w[s] = np.nan
    return w[SECTORS]


def _dec(x):
    return None if pd.isna(x) else Decimal(repr(float(x)))


def _abbr(used):
    return "+".join(SECTOR_ABBR.get(u, u) for u in used)


def _identity(est: pd.Series, truth: pd.Series) -> pd.Series:
    return (est - truth).abs() <= IDENTITY_TOL * truth.abs()


# ----------------------------------------------------------------------------
# 2. Apply the package rule and counterfactual estimators to every country-year
# ----------------------------------------------------------------------------

def harmonise(w: pd.DataFrame) -> pd.DataFrame:
    """
    For every cell: the value the package selects, and what the T2 and T3 fallbacks would
    give if GG (and, for T3, also CGSS) were not reported. All values, tiers and
    completeness flags come from cofog_panel.resolve_value / is_complete.
    """
    ever = {s: w[s].groupby(level=["ISO", "DIV"]).transform(lambda x: x.notna().any()) for s in COVERAGE_LEVELS}
    recs = []
    for i, (key, row) in enumerate(zip(w.index, w.itertuples(index=False))):
        vals = {s: _dec(v) for s, v in zip(SECTORS, row)}
        levels = [s for s in COVERAGE_LEVELS if ever[s].iat[i]]
        v, tier, used = resolve_value(vals)
        complete = is_complete(tier, used, levels, vals)
        v_zam, tier_zam, _ = resolve_value(vals, zero_as_missing=True)
        # counterfactual T2: GG withheld
        no_gg = dict(vals, **{GG: None})
        e2, t2, u2 = resolve_value(no_gg) if vals.get(CGSS) is not None else (None, "", [])
        # counterfactual T3: GG and CGSS withheld
        e3, t3, u3 = resolve_value(dict(no_gg, **{CGSS: None}))
        recs.append((*key, None if v is None else float(v), tier, _abbr(used), complete,
                     None if v_zam is None else float(v_zam), tier_zam,
                     None if e2 is None else float(e2), _abbr(u2), is_complete(t2, u2, levels) if e2 is not None else None,
                     None if e3 is None else float(e3), _abbr(u3), is_complete(t3, u3, levels) if e3 is not None else None))
    cols = ["ISO", "DIV", "YEAR", "VALUE", "TIER", "SECTORS", "COMPLETE", "VALUE_ZAM", "TIER_ZAM",
            "EST_T2", "T2_SECTORS", "T2_COMPLETE", "EST_T3", "T3_SECTORS", "T3_COMPLETE"]
    h = pd.DataFrame(recs, columns=cols).set_index(["ISO", "DIV", "YEAR"]).join(w)
    for s, e in ever.items():
        h[f"EVER_{SECTOR_ABBR[s]}"] = e
    h["EST_CG"] = h[CGSS]
    h["T2_COMPLETE"] = h["T2_COMPLETE"].fillna(False).astype(bool)
    h["T3_COMPLETE"] = h["T3_COMPLETE"].fillna(False).astype(bool)
    gg = h[GG]
    for est in ("EST_T2", "EST_T3", "EST_CG"):
        h[f"IDENT_{est[4:]}"] = h[est].notna() & gg.notna() & _identity(h[est], gg)
    return h.reset_index()


# ----------------------------------------------------------------------------
# 3. Tables
# ----------------------------------------------------------------------------

def table_reporting(h: pd.DataFrame) -> pd.DataFrame:
    """Share of country-years (any sector reported) in which each sector is reported."""
    rows = []
    for div, g in h.groupby("DIV"):
        r = {"DIV": div, "Function": DIVISIONS[div], "Country-years": len(g),
             "Countries": g["ISO"].nunique(),
             "Countries with GG": g.loc[g[GG].notna(), "ISO"].nunique()}
        for s, lab in [(GG, "GG"), (CGSS, "CGSS"), (CGXSS, "CGXSS"), (BCG, "BCG"), (EBCG, "EBCG"),
                       (SSF, "SSF"), (SG, "SG"), (LG, "LG")]:
            r[lab] = round(100 * g[s].notna().mean(), 1)
        rows.append(r)
    return pd.DataFrame(rows)


def table_coverage(h: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for div, g in h.groupby("DIV"):
        n1, n2, n3 = [(g["TIER"] == t).sum() for t in ("T1", "T2", "T3")]
        rows.append({
            "DIV": div, "Function": DIVISIONS[div],
            "T1": n1, "T2": n2, "T3": n3, "Total": n1 + n2 + n3,
            "Cells without value": int((g["TIER"] == "").sum()),
            "Gain vs GG-only (%)": round(100 * (n2 + n3) / n1, 1),
            "Countries GG-only": g.loc[g["TIER"] == "T1", "ISO"].nunique(),
            "Countries T1-T3": g.loc[g["TIER"] != "", "ISO"].nunique(),
            "T1 flagged (GG = CGSS, subnational > 0)": int(((g["TIER"] == "T1") & (g["COMPLETE"] == False)).sum()),
            "T2 incomplete (% of T2)": round(100 * (g.loc[g["TIER"] == "T2", "COMPLETE"] == False).mean(), 1),
            "T3 incomplete (% of T3)": round(100 * (g.loc[g["TIER"] == "T3", "COMPLETE"] == False).mean(), 1),
            "T3 using CGXSS (%)": round(100 * g.loc[g["TIER"] == "T3", "SECTORS"].str.contains("CGXSS").mean(), 1),
        })
    return pd.DataFrame(rows)


def table_region(h: pd.DataFrame, div: str = "05") -> pd.DataFrame:
    """Coverage by UN region: who is lost when only GG values are kept."""
    lk = pd.read_excel(LOOKUP)[["alpha-3", "region"]].rename(columns={"alpha-3": "ISO"})
    g = h[(h["DIV"] == div) & (h["TIER"] != "")].merge(lk, on="ISO", how="left")
    rows = []
    for reg, x in g.groupby("region"):
        rows.append({"Region": reg,
                     "Countries GG-only": x.loc[x["TIER"] == "T1", "ISO"].nunique(),
                     "Countries T1-T3": x["ISO"].nunique(),
                     "Country-years GG-only": int((x["TIER"] == "T1").sum()),
                     "Country-years T1-T3": len(x),
                     "Fallback share (%)": round(100 * (x["TIER"] != "T1").mean(), 1),
                     "Incomplete (% of all)": round(100 * (x["COMPLETE"] == False).mean(), 1)})
    return pd.DataFrame(rows)


def _err_stats(est: pd.Series, truth: pd.Series) -> dict:
    ok = est.notna() & truth.notna() & (truth > 0)
    e, t = est[ok], truth[ok]
    if len(e) == 0:
        return {"N": 0}
    ratio = e / t
    ape = (ratio - 1).abs()
    return {"N": int(ok.sum()), "Median ratio": round(ratio.median(), 3),
            "P10 ratio": round(ratio.quantile(0.10), 3), "P90 ratio": round(ratio.quantile(0.90), 3),
            "Within 5% (%)": round(100 * (ape <= 0.05).mean(), 1),
            "Within 10% (%)": round(100 * (ape <= 0.10).mean(), 1)}


def table_overlap(h: pd.DataFrame) -> pd.DataFrame:
    """
    Fallback estimators against GG in years where GG is reported and positive.
    Exact identities (estimate = GG) are reported separately, because they reflect how GG
    is compiled rather than independent agreement.
    """
    rows = []
    gg_obs = h[h[GG].notna() & (h[GG] > 0) & (h["COMPLETE"] == True)]
    sub_pos = lambda g: g[[SG, LG]].fillna(0).sum(axis=1) > 0  # noqa: E731
    for div, g in list(gg_obs.groupby("DIV")) + [("All", gg_obs)]:
        for name, est, ident, mask in [
            ("CG proxy", "EST_CG", "IDENT_CG", g["EST_CG"].notna()),
            ("CG proxy, subnational > 0", "EST_CG", "IDENT_CG", g["EST_CG"].notna() & sub_pos(g)),
            ("T2 sum, complete", "EST_T2", "IDENT_T2", g["T2_COMPLETE"]),
            ("T2 sum, incomplete", "EST_T2", "IDENT_T2", g["EST_T2"].notna() & ~g["T2_COMPLETE"]),
            ("T3 sum, complete", "EST_T3", "IDENT_T3", g["T3_COMPLETE"]),
            ("T3 sum, incomplete", "EST_T3", "IDENT_T3", g["EST_T3"].notna() & ~g["T3_COMPLETE"]),
        ]:
            x = g[mask & g[est].notna()]
            allst = _err_stats(x[est], x[GG])
            ex = x[~x[ident]]
            exst = _err_stats(ex[est], ex[GG])
            rows.append({"DIV": div, "Function": DIVISIONS.get(div, "All divisions"), "Estimator": name,
                         **allst,
                         "Exact identities (%)": round(100 * x[ident].mean(), 1) if len(x) else None,
                         "N excl. identities": exst.get("N", 0),
                         "Median ratio excl. identities": exst.get("Median ratio"),
                         "P90 ratio excl. identities": exst.get("P90 ratio"),
                         "Within 5% excl. identities (%)": exst.get("Within 5% (%)")})
    return pd.DataFrame(rows)


def _later_ratio(years: np.ndarray, ratios: np.ndarray, y: int, d: int, k: int = ADJ_K) -> float:
    """Median of the k ratios observed closest to, and at least d years after, year y."""
    later = np.flatnonzero(years >= y + d)
    if len(later) == 0:
        return np.nan
    nearest = later[np.argsort(years[later] - y, kind="stable")[:k]]
    return float(np.median(ratios[nearest]))


ADJ_SPECS = {"EST_T2": ("T2_COMPLETE", "T2_SECTORS", "IDENT_T2"), "EST_T3": ("T3_COMPLETE", "T3_SECTORS", "IDENT_T3")}


def _adjust_eval(h: pd.DataFrame, est: str, d: int, k: int = ADJ_K) -> pd.DataFrame:
    """Held-out overlap years with the ratio predicted from later years (column ADJ = adjusted estimate)."""
    compl, sect, ident = ADJ_SPECS[est]
    o = h[h[GG].notna() & (h[GG] > 0) & (h["COMPLETE"] == True) & h[compl] & (h[est] > 0)].copy()
    o["RATIO"] = o[GG] / o[est]
    r_hat = pd.Series(np.nan, index=o.index)
    for _, g in o.groupby(["ISO", "DIV", sect]):
        yrs, rat = g["YEAR"].to_numpy(), g["RATIO"].to_numpy()
        r_hat.loc[g.index] = [_later_ratio(yrs, rat, y, d, k) for y in yrs]
    x = o[r_hat.notna() & ~o[ident]].copy()
    x["ADJ"] = r_hat[x.index] * x[est]
    return x


def table_adjustment(h: pd.DataFrame) -> pd.DataFrame:
    """
    Out-of-sample test of the consolidation adjustment, designed like its actual use.

    Fallback years mostly precede the first GG year, so the ratio GG/sum is predicted only from
    overlap years at least d years LATER than the held-out year, with the same set of
    components (SECTORS). Evaluation is on held-out years where the sum is not identical to GG.
    """
    rows = []
    for est, label in [("EST_T2", "T2 sum"), ("EST_T3", "T3 sum")]:
        for d in ADJ_DISTANCES:
            x = _adjust_eval(h, est, d)
            for div, g in list(x.groupby("DIV")) + [("All", x)]:
                un, ad = _err_stats(g[est], g[GG]), _err_stats(g["ADJ"], g[GG])
                rows.append({"DIV": div, "Function": DIVISIONS.get(div, "All divisions"), "Estimator": label,
                             "Min. distance (years)": d, "N": un.get("N", 0),
                             "Unadjusted median ratio": un.get("Median ratio"),
                             "Unadjusted within 5% (%)": un.get("Within 5% (%)"),
                             "Adjusted median ratio": ad.get("Median ratio"),
                             "Adjusted within 5% (%)": ad.get("Within 5% (%)"),
                             "Adjusted P10 ratio": ad.get("P10 ratio"),
                             "Adjusted P90 ratio": ad.get("P90 ratio")})
    return pd.DataFrame(rows)


def table_adjust_k(h: pd.DataFrame) -> pd.DataFrame:
    """Sensitivity of the adjustment to the number k of overlap years used for the ratio."""
    rows = []
    for est, label in [("EST_T2", "T2 sum"), ("EST_T3", "T3 sum")]:
        for d in ADJ_DISTANCES:
            for k in ADJ_K_ALT:
                x = _adjust_eval(h, est, d, k)
                for div, g in [(v, x[x["DIV"] == v]) for v in ("01", "05", "09")] + [("All", x)]:
                    ad = _err_stats(g["ADJ"], g[GG])
                    rows.append({"DIV": div, "Function": DIVISIONS.get(div, "All divisions"), "Estimator": label,
                                 "Min. distance (years)": d, "k": k, "N": ad.get("N", 0),
                                 "Adjusted median ratio": ad.get("Median ratio"),
                                 "Adjusted within 5% (%)": ad.get("Within 5% (%)"),
                                 "Adjusted P90 ratio": ad.get("P90 ratio")})
    return pd.DataFrame(rows)


def _boot_ci(iso: np.ndarray, ratio: np.ndarray, rng: np.random.Generator) -> dict:
    """95% country-cluster bootstrap intervals for the median ratio and the share within 5%."""
    codes, inv = np.unique(iso, return_inverse=True)
    groups = [np.flatnonzero(inv == i) for i in range(len(codes))]
    med, w5 = np.empty(BOOT_REPS), np.empty(BOOT_REPS)
    for b in range(BOOT_REPS):
        r = ratio[np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])]
        med[b], w5[b] = np.median(r), 100 * np.mean(np.abs(r - 1) <= 0.05)
    return {"Countries": len(codes),
            "Median ratio, 95% CI": f"{np.percentile(med, 2.5):.2f}–{np.percentile(med, 97.5):.2f}",
            "Within 5% (%), 95% CI": f"{np.percentile(w5, 2.5):.1f}–{np.percentile(w5, 97.5):.1f}"}


def table_bootstrap(h: pd.DataFrame) -> pd.DataFrame:
    """Country-cluster bootstrap intervals for the key statistics of Tables 4 and 5."""
    rng = np.random.default_rng(BOOT_SEED)
    rows = []
    gg_obs = h[h[GG].notna() & (h[GG] > 0) & (h["COMPLETE"] == True)]
    for div, g in list(gg_obs.groupby("DIV")) + [("All", gg_obs)]:
        for name, est, ident, compl in [("T2 sum, complete", "EST_T2", "IDENT_T2", "T2_COMPLETE"),
                                        ("T3 sum, complete", "EST_T3", "IDENT_T3", "T3_COMPLETE")]:
            x = g[g[compl] & g[est].notna() & ~g[ident]]
            x = x[x[GG] > 0]
            r = (x[est] / x[GG]).to_numpy()
            rows.append({"Table": "4 (excl. identities)", "DIV": div, "Function": DIVISIONS.get(div, "All divisions"),
                         "Estimator": name, "Min. distance (years)": None, "N": len(r),
                         "Median ratio": round(float(np.median(r)), 3),
                         "Within 5% (%)": round(100 * float(np.mean(np.abs(r - 1) <= 0.05)), 1),
                         **_boot_ci(x["ISO"].to_numpy(), r, rng)})
    for est, label in [("EST_T2", "T2 sum"), ("EST_T3", "T3 sum")]:
        for d in ADJ_DISTANCES:
            x = _adjust_eval(h, est, d)
            for div, g in [(v, x[x["DIV"] == v]) for v in ("01", "05", "09")] + [("All", x)]:
                for kind, col in (("unadjusted", est), ("adjusted", "ADJ")):
                    r = (g[col] / g[GG]).to_numpy()
                    rows.append({"Table": "5", "DIV": div, "Function": DIVISIONS.get(div, "All divisions"),
                                 "Estimator": f"{label}, {kind}", "Min. distance (years)": d, "N": len(r),
                                 "Median ratio": round(float(np.median(r)), 3),
                                 "Within 5% (%)": round(100 * float(np.mean(np.abs(r - 1) <= 0.05)), 1),
                                 **_boot_ci(g["ISO"].to_numpy(), r, rng)})
    return pd.DataFrame(rows)


def table_adjust_reach(h: pd.DataFrame) -> pd.DataFrame:
    """Share of actual complete fallback values that the adjustment can reach."""
    rows = []
    for div, g in list(h.groupby("DIV")) + [("All", h)]:
        fb = g[g["TIER"].isin(["T2", "T3"]) & (g["COMPLETE"] == True)]
        ov = {}
        for tier, est, compl, sect in [("T2", "EST_T2", "T2_COMPLETE", "T2_SECTORS"),
                                       ("T3", "EST_T3", "T3_COMPLETE", "T3_SECTORS")]:
            o = g[g[GG].notna() & (g[GG] > 0) & (g["COMPLETE"] == True) & g[compl] & (g[est] > 0)]
            for (iso, div_, s), yrs in o.groupby(["ISO", "DIV", sect])["YEAR"]:
                ov[(tier, iso, div_, s)] = yrs.to_numpy()
        first_gg = g[g[GG].notna()].groupby(["ISO", "DIV"])["YEAR"].min().to_dict()
        n_same, n_before, dist = 0, 0, []
        for iso, div_, y, tier, s in zip(fb["ISO"], fb["DIV"], fb["YEAR"], fb["TIER"], fb["SECTORS"]):
            yrs = ov.get((tier, iso, div_, s))
            if yrs is None:
                continue
            n_same += 1
            n_before += int(y < first_gg.get((iso, div_), 9999))
            dist.append(int(np.min(np.abs(yrs - y))))
        rows.append({"DIV": div, "Function": DIVISIONS.get(div, "All divisions"),
                     "Complete fallback values": len(fb),
                     "With overlap years, same components (%)": round(100 * n_same / max(len(fb), 1), 1),
                     "Of which before first GG year (%)": round(100 * n_before / max(n_same, 1), 1),
                     "Median distance to nearest overlap year": float(np.median(dist)) if dist else None})
    return pd.DataFrame(rows)


def table_breaks(h: pd.DataFrame) -> pd.DataFrame:
    """
    Breaks within country series: a change in the set of contributing subsectors between
    consecutive years. Sizes are absolute changes in log values (positive pairs only).
    """
    rows = []
    v = h[h["TIER"] != ""].sort_values(["ISO", "DIV", "YEAR"]).copy()
    grp = v.groupby(["ISO", "DIV"])
    for c in ("YEAR", "VALUE", "TIER", "SECTORS", "COMPLETE"):
        v[f"PREV_{c}"] = grp[c].shift()
    pairs = v[v["PREV_YEAR"] == v["YEAR"] - 1].copy()
    pairs["BREAK"] = pairs["SECTORS"] != pairs["PREV_SECTORS"]
    pairs["BOTH_COMPLETE"] = (pairs["COMPLETE"] == True) & (pairs["PREV_COMPLETE"] == True)
    pos = (pairs["VALUE"] > 0) & (pairs["PREV_VALUE"] > 0)
    pairs["DLOG"] = np.where(pos, np.log(pairs["VALUE"].where(pos) / pairs["PREV_VALUE"].where(pos)).abs(), np.nan)
    for div, g in list(pairs.groupby("DIV")) + [("All", pairs)]:
        series = v[v["DIV"] == div] if div != "All" else v
        br = g[g["BREAK"]]
        med = lambda s: round(float(s.median()), 3) if s.notna().any() else None  # noqa: E731
        rows.append({"DIV": div, "Function": DIVISIONS.get(div, "All divisions"),
                     "Series": series.groupby(["ISO", "DIV"]).ngroups,
                     "Series with a break": br.groupby(["ISO", "DIV"]).ngroups,
                     "Breaks": len(br),
                     "Breaks involving an incomplete value": int((~br["BOTH_COMPLETE"]).sum()),
                     "Median |dlog|, break, both complete": med(br.loc[br["BOTH_COMPLETE"], "DLOG"]),
                     "Median |dlog|, break, incomplete involved": med(br.loc[~br["BOTH_COMPLETE"], "DLOG"]),
                     "Median |dlog|, no break, T1": med(g.loc[~g["BREAK"] & (g["TIER"] == "T1"), "DLOG"]),
                     "Median |dlog|, no break, fallback": med(g.loc[~g["BREAK"] & (g["TIER"] != "T1"), "DLOG"]),
                     "Breaks with |dlog| > 0.5 (%)": round(100 * (br["DLOG"] > 0.5).mean(), 1)})
    return pd.DataFrame(rows)


def table_zeros(h: pd.DataFrame) -> pd.DataFrame:
    """Reported zeros, and 'structural zeros': GG zero in every year of a country's function series."""
    rows = []
    for div, g in h.groupby("DIV"):
        z = g[g[GG] == 0]
        gg_series = g[g[GG].notna()].groupby("ISO")[GG]
        structural = sorted(i for i, s in gg_series if (s == 0).all())
        rows.append({"DIV": div, "Function": DIVISIONS[div], "GG zero cells": len(z),
                     "Countries with GG zero": z["ISO"].nunique(),
                     "GG zero, all reported levels zero": int(z["VALUE_ZAM"].isna().sum()),
                     "Countries with GG zero in every year": len(structural),
                     "Those countries": ", ".join(structural)})
    return pd.DataFrame(rows)


# --- Eurostat cross-check ---

def load_eurostat() -> pd.DataFrame:
    f = EXT / "eurostat_gov10a_exp_S13_TE_pcgdp.tsv"
    e = pd.read_csv(f, sep="\t")
    key = e.columns[0]
    k = e[key].str.split(",", expand=True)
    e["DIV"] = k[3].str[2:]
    e["GEO2"] = k[5]
    e = e.melt(id_vars=["DIV", "GEO2"], value_vars=[c for c in e.columns if c.strip().isdigit()],
               var_name="YEAR", value_name="RAW")
    e["YEAR"] = e["YEAR"].str.strip().astype(int)
    e["EUROSTAT"] = pd.to_numeric(e["RAW"].astype(str).str.extract(r"([-\d.]+)")[0], errors="coerce")
    wbc = json.loads((EXT / "wb_countries.json").read_text(encoding="utf8"))[1]
    iso2to3 = {c["iso2Code"]: c["id"] for c in wbc}
    iso2to3.update({"EL": "GRC", "UK": "GBR"})
    e["ISO"] = e["GEO2"].map(iso2to3)
    return e.dropna(subset=["ISO", "EUROSTAT"])[["ISO", "DIV", "YEAR", "EUROSTAT"]]


def table_eurostat(h: pd.DataFrame, eu: pd.DataFrame) -> tuple:
    m = h.merge(eu, on=["ISO", "DIV", "YEAR"], how="inner")
    m = m[m["TIER"] != ""]
    rows = []
    for div, gd in list(m.groupby("DIV")) + [("All", m)]:
        for tier in ["T1", "T2", "T3"]:
            g = gd[gd["TIER"] == tier]
            if g.empty:
                continue
            diff = g["VALUE"] - g["EUROSTAT"]
            rows.append({"DIV": div, "Tier": tier, "N": len(g), "Countries": g["ISO"].nunique(),
                         "Mean diff (pp GDP)": round(diff.mean(), 3),
                         "Median |diff| (pp GDP)": round(diff.abs().median(), 3),
                         "|diff| <= 0.1 pp (%)": round(100 * (diff.abs() <= 0.1).mean(), 1),
                         "Corr.": round(np.corrcoef(g["VALUE"], g["EUROSTAT"])[0, 1], 3) if len(g) > 2 else None})
    return pd.DataFrame(rows), m


# --- Regression sensitivity ---

def load_gdppc() -> pd.DataFrame:
    js = json.loads((EXT / "wb_NY.GDP.PCAP.PP.KD.json").read_text(encoding="utf8"))[1]
    return pd.DataFrame([{"ISO": r["countryiso3code"], "YEAR": int(r["date"]), "GDPPC": r["value"]}
                         for r in js if r["value"] is not None and r["countryiso3code"]])


def table_regression(h: pd.DataFrame, gdp: pd.DataFrame) -> pd.DataFrame:
    import statsmodels.formula.api as smf
    d = h[(h["DIV"] == "05") & (h["TIER"] != "") & (h["VALUE"] > 0)].merge(gdp, on=["ISO", "YEAR"])
    d["lnGDPPC"] = np.log(d["GDPPC"])
    d["lnENV"] = np.log(d["VALUE"])
    d["T2"] = (d["TIER"] == "T2").astype(int)
    d["T3"] = (d["TIER"] == "T3").astype(int)
    samples = [
        ("(1) T1 only", d[d["TIER"] == "T1"], "lnENV ~ lnGDPPC + C(YEAR)"),
        ("(2) T1-T3", d, "lnENV ~ lnGDPPC + C(YEAR)"),
        ("(3) T1-T3 + tier dummies", d, "lnENV ~ lnGDPPC + T2 + T3 + C(YEAR)"),
        ("(4) Complete values only", d[d["COMPLETE"] == True], "lnENV ~ lnGDPPC + C(YEAR)"),
        ("(5) T1 only, country FE", d[d["TIER"] == "T1"], "lnENV ~ lnGDPPC + C(YEAR) + C(ISO)"),
        ("(6) T1-T3, country FE", d, "lnENV ~ lnGDPPC + C(YEAR) + C(ISO)"),
        ("(7) T1-T3 + tier dummies, country FE", d, "lnENV ~ lnGDPPC + T2 + T3 + C(YEAR) + C(ISO)"),
    ]
    rows = []
    for name, s, f in samples:
        r = smf.ols(f, data=s).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(s["ISO"])[0]})
        row = {"Model": name, "N": int(r.nobs), "Countries": s["ISO"].nunique(),
               "b(lnGDPPC)": round(r.params["lnGDPPC"], 3), "se": round(r.bse["lnGDPPC"], 3)}
        for t in ("T2", "T3"):
            if t in r.params:
                row[f"b({t})"] = round(r.params[t], 3)
                row[f"se({t})"] = round(r.bse[t], 3)
        rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# 4. Figures (no in-figure titles: the captions carry them)
# ----------------------------------------------------------------------------

def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def fig_coverage(h: pd.DataFrame, path: Path):
    import matplotlib.pyplot as plt
    g = h[(h["DIV"] == "05") & (h["TIER"] != "")]
    c = (g.groupby(["YEAR", "TIER"]).size().unstack(fill_value=0)
         .reindex(index=list(YEARS), columns=["T1", "T2", "T3"], fill_value=0))
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=200)
    bottom = np.zeros(len(c))
    for t, lab in [("T1", "T1 general government"), ("T2", "T2 central + subnational"),
                   ("T3", "T3 component sum")]:
        ax.bar(c.index, c[t], bottom=bottom, color=TIER_COLORS[t], width=0.8,
               edgecolor="white", linewidth=0.8, label=lab)
        bottom += c[t].values
    _style(ax)
    ax.set_ylabel("Countries with a value", color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def fig_overlap(h: pd.DataFrame, path: Path):
    """Ratio estimate/GG in overlap years, excluding exact identities."""
    import matplotlib.pyplot as plt
    g = h[h[GG].notna() & (h[GG] > 0) & (h["COMPLETE"] == True)]
    order = list(DIVISIONS)[::-1]
    panels = [("EST_CG", "IDENT_CG", g["EST_CG"].notna(), "CG proxy", INK2),
              ("EST_T2", "IDENT_T2", g["T2_COMPLETE"], "T2 sum, complete", TIER_COLORS["T2"]),
              ("EST_T3", "IDENT_T3", g["T3_COMPLETE"], "T3 sum, complete", TIER_COLORS["T3"]),
              ("EST_T3", "IDENT_T3", g["EST_T3"].notna() & ~g["T3_COMPLETE"], "T3 sum, incomplete", TIER_COLORS["T3"])]
    fig, axes = plt.subplots(2, 2, figsize=(9, 8), dpi=200, sharex=True)
    for k, (ax, (est, ident, mask, title, col)) in enumerate(zip(axes.flat, panels)):
        data = []
        for d in order:
            x = g[mask & (g["DIV"] == d) & ~g[ident]]
            r = (x[est] / x[GG]).replace([np.inf, -np.inf], np.nan).dropna()
            data.append(np.log(r[r > 0]).to_numpy())
        bp = ax.boxplot(data, orientation="horizontal", widths=0.55, showfliers=False, patch_artist=True,
                        medianprops={"color": INK, "linewidth": 1.5},
                        whiskerprops={"color": INK2}, capprops={"color": INK2})
        for b in bp["boxes"]:
            b.set_facecolor(col)
            b.set_alpha(0.55)
            b.set_edgecolor(col)
        ax.axvline(0, color=INK, linewidth=0.8)
        _style(ax)
        ax.tick_params(labelsize=10)
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        ax.yaxis.grid(False)
        ax.set_title(title, fontsize=11, color=INK, loc="left")
        ax.set_xlim(-3, 1.5)
        if k % 2 == 0:
            ax.set_yticks(range(1, len(order) + 1), [f"{d} {DIVISIONS[d]}" for d in order], fontsize=10)
        else:
            ax.set_yticks(range(1, len(order) + 1), [d for d in order], fontsize=10)
        if k >= 2:
            ax.set_xlabel("log(estimate / GG)", fontsize=10, color=INK2)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def fig_example(h: pd.DataFrame, iso: str, name: str, div: str, path: Path):
    import matplotlib.pyplot as plt
    g = h[(h["ISO"] == iso) & (h["DIV"] == div) & (h["TIER"] != "")].sort_values("YEAR")
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
    ax.plot(g["YEAR"], g["VALUE"], color=INK2, linewidth=1, zorder=1)
    markers = ["o", "s", "D", "^"]
    for t in ["T1", "T2", "T3"]:
        for compl in (True, False):
            for j, (sect, s) in enumerate(g[(g["TIER"] == t) & (g["COMPLETE"] == compl)].groupby("SECTORS", sort=False)):
                ax.scatter(s["YEAR"], s["VALUE"], s=44, zorder=2, marker=markers[j % len(markers)],
                           color=TIER_COLORS[t] if compl else "white",
                           edgecolor="white" if compl else TIER_COLORS[t], linewidth=1.5,
                           label=f"{t} ({sect})" + ("" if compl else ", incomplete"))
    _style(ax)
    ax.set_ylabel(f"{name}, % of GDP", color=INK2, fontsize=9)
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=8, loc="lower left", ncol=3, bbox_to_anchor=(0, -0.42))
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_eurostat(m: pd.DataFrame, path: Path):
    import matplotlib.pyplot as plt
    g = m[(m["DIV"] == "05") & (m["TIER"] == "T1")]
    fig, ax = plt.subplots(figsize=(4.6, 4.2), dpi=200)
    lo = min(g["VALUE"].min(), g["EUROSTAT"].min(), 0) - 0.05
    hi = max(g["VALUE"].max(), g["EUROSTAT"].max()) * 1.05
    ax.plot([lo, hi], [lo, hi], color=INK2, linewidth=0.8)
    ax.scatter(g["EUROSTAT"], g["VALUE"], s=14, color=TIER_COLORS["T1"], alpha=0.8,
               edgecolor="white", linewidth=0.5)
    _style(ax)
    ax.set_xlabel("Eurostat gov_10a_exp, % of GDP", fontsize=9, color=INK2)
    ax.set_ylabel("IMF GFS general government (T1), % of GDP", fontsize=9, color=INK2)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


# ----------------------------------------------------------------------------

def main():
    long = load_long()
    h = harmonise(to_wide(long))
    h.to_csv(OUT / "harmonised_all_divisions.csv", index=False)

    eu = load_eurostat()
    t_eu, m_eu = table_eurostat(h, eu)
    tables = {
        # manuscript tables
        "table1_reporting": table_reporting(h),
        "table2_coverage": table_coverage(h),
        "table3_region_05": table_region(h, "05"),
        "table4_overlap": table_overlap(h),
        "table5_adjustment": table_adjustment(h),
        "table6_breaks": table_breaks(h),
        "table7_regression": table_regression(h, load_gdppc()),
        # supplementary tables
        "supp_adjust_reach": table_adjust_reach(h),
        "supp_zeros": table_zeros(h),
        "supp_eurostat": t_eu,
        "supp_bootstrap": table_bootstrap(h),
        "supp_adjust_k": table_adjust_k(h),
    }
    for name, t in tables.items():
        t.to_csv(OUT / f"{name}.csv", index=False)
        print(f"\n=== {name} ===")
        print(t.to_string(index=False))

    fig_coverage(h, OUT / "fig1_coverage_05.png")
    fig_overlap(h, OUT / "fig2_overlap.png")
    fig_example(h, "ARM", "Armenia", "05", OUT / "fig3_example_ARM_05.png")
    fig_eurostat(m_eu, OUT / "fig4_eurostat_05.png")

    summary = {
        "country_years_any": int(len(h)),
        "countries": int(h["ISO"].nunique()),
        "tiers_all": h["TIER"].value_counts().to_dict(),
    }
    (OUT / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    print(summary)


if __name__ == "__main__":
    main()
