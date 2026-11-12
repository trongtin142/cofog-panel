"""
Two extensions of the harmonisation study: consequences of the filling choice on a fixed sample
(Analysis A) and the recording of consolidation in COFOG group 01.8 (Analysis B).

Run from the repository root, after or instead of evaluate_harmonisation.py:
    python replication/sjiaos/evaluate_extensions.py [--source FILE] [--out DIR]

Inputs : data/gfs_raw_data.xlsx (IMF GFS_COFOG 11.0.0, published 2026-02-03; SHA-256 checked)
         data/country_codes.xlsx (UN M49 regions)
         replication/sjiaos/data_ext/wb_NY.GDP.PCAP.PP.KD.json (World Bank WDI)
         replication/sjiaos/data_ext/eurostat_gov10a_exp_S13_TE_pcgdp.tsv (Eurostat gov_10a_exp)
Outputs: ext_*.csv and fig1_coverage_09.png in --out (default replication/sjiaos/output_ext)

Every tier, sum and completeness flag comes from evaluate_harmonisation.harmonise, which calls
cofog_panel.resolve_value and cofog_panel.aggregate.is_complete. The script is deterministic:
the bootstrap uses a fixed seed and no other randomness enters.

Analysis A (divisions 07, 09, 10, their sum and 07 + 09)
  Fixed samples of country-years with reported GG (positive, not flagged) and each alternative a
  user takes when GG is missing: CGSS alone, the complete T2 sum, the complete T3 sum, the value of
  the tiered rule without GG (T2 where CGSS is reported, otherwise T3; complete only), and that
  value after ratio splicing with ratios from overlap years at least d years later (d = 5 and 1).
  Statistics: ratio to GG, error shares, Spearman rank correlation, quintile changes and the
  cross-country income gradient (log spending on log GDP per capita PPP with year effects),
  estimated on the same country-years for GG and for the alternative, with a country-cluster
  bootstrap interval for the difference.
Analysis B (division 01, groups 01.7 and 01.8, total outlays)
  Where GG and a complete subsector sum overlap and SG or LG report spending: the gap between the
  sum and GG in division 01 against the gap in group 01.8, the recording of 01.8 where GG equals
  the unconsolidated sum in divisions 02-10, a country classification of recording practices and
  checks of alternative explanations.
Coverage for education (division 09)
  Table 3 and Figure 1 of the harmonisation study for division 09 (COVERAGE_DIV), drawn with the
  region function and the figure style of evaluate_harmonisation.py, which stays unchanged.
"""
import argparse
import hashlib
import io
import sys
import time
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
import evaluate_harmonisation as eh  # noqa: E402
from cofog_panel.aggregate import (  # noqa: E402
    resolve_value, IMF_TO_ISO, GG, CGSS, CGXSS, BCG, EBCG, SSF, SG, LG,
)

RAW = REPO / "data" / "gfs_raw_data.xlsx"
LOOKUP = REPO / "data" / "country_codes.xlsx"
OUT = HERE / "output_ext"
YEARS = eh.YEARS                       # 1990-2024 (per cent of GDP series end in 2023)
TOL = eh.IDENTITY_TOL                  # relative tolerance for an exact identity
BOOT_REPS, BOOT_SEED = eh.BOOT_REPS, eh.BOOT_SEED
MIN_COUNTRIES_YEAR = 10                # years with fewer countries are skipped in the yearly Spearman
SPLICE_D = (5, 1)                      # minimum distance (years) for the spliced alternatives
GAP_MIN = 0.01                         # a gap counts when it exceeds 1% of GG
F_CUT = 0.10                           # practice threshold: share of consolidation outside division 01
F_CUT_ALT = (0.05, 0.20)
EU_EFTA = ["AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN", "IRL",
           "ITA", "LVA", "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "ESP", "SWE",
           "ISL", "NOR", "CHE"]
GROUP_CODES = {"GF0180_T": "018", "GF0170_T": "017", "TOTOUT_T": "TOT"}
ABBR_TO_SECTOR = {"GG": GG, "CGSS": CGSS, "CGXSS": CGXSS, "BCG": BCG, "EBCG": EBCG, "SSF": SSF, "SG": SG, "LG": LG}
CENTRAL_ABBR = ("CGSS", "CGXSS", "BCG", "EBCG")

MEASURES = [("07", "Health", ["07"]), ("09", "Education", ["09"]), ("10", "Social protection", ["10"]),
            ("HE", "Health and education (07+09)", ["07", "09"]),
            ("SOC", "Social spending (07+09+10)", ["07", "09", "10"])]
ALTERNATIVES = [("CG", "CGSS alone"), ("T2", "T2 sum, complete"), ("T3", "T3 sum, complete"),
                ("RULE", "Tiered rule without GG, complete"),
                ("SPL5", "Tiered rule, spliced (d >= 5)"), ("SPL1", "Tiered rule, spliced (d >= 1)")]
COMMON = ["CG", "T2", "T3", "SPL5"]    # alternatives that define the common sample


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_extract(path: Path, cache_dir: Path):
    """
    Division table (identical to evaluate_harmonisation.load_long) and a table of groups 01.7, 01.8
    and total outlays, both per cent of GDP, from one read of the extract. Cached by checksum.
    """
    digest = sha256(path)
    if digest != eh.RAW_SHA256:
        print(f"WARNING: {path.name} differs from the extract used in the article (SHA-256 {digest[:12]}...).")
    cache = cache_dir / f"_ext_long_{digest[:16]}.pkl"
    if cache.exists():
        return pd.read_pickle(cache) + (digest,)
    raw = pd.read_csv(path, encoding="utf-8-sig", low_memory=False) if path.suffix.lower() == ".csv" else pd.read_excel(path)
    raw = raw[raw["TYPE_OF_TRANSFORMATION"] == "Percent of GDP"].copy()
    parts = raw["SERIES_CODE"].str.split(".", expand=True)
    raw["ISO"] = parts[0].str.upper().replace(IMF_TO_ISO)
    raw["CODE"] = parts[3]
    raw["SECTOR_NORM"] = raw["SECTOR"].str.lower().str.strip()
    ycols = [c for c in raw.columns if str(c).isdigit() and int(c) in YEARS]

    def melt(frame, key):
        long = frame.melt(id_vars=["ISO", key, "SECTOR_NORM"], value_vars=ycols,
                          var_name="YEAR", value_name="VALUE").dropna(subset=["VALUE"])
        long["YEAR"] = long["YEAR"].astype(int)
        return long.drop_duplicates(subset=["ISO", key, "SECTOR_NORM", "YEAR"])

    div = raw.copy()
    div["DIV"] = div["CODE"].str.extract(r"^GF(\d+)_T")[0]
    div = melt(div[div["DIV"].str.len() == 2], "DIV")
    grp = raw[raw["CODE"].isin(GROUP_CODES)].copy()
    grp["GRP"] = grp["CODE"].map(GROUP_CODES)
    grp = melt(grp, "GRP")
    pd.to_pickle((div, grp), cache)
    return div, grp, digest


def regions() -> pd.Series:
    lk = pd.read_excel(LOOKUP)[["alpha-3", "region", "name"]]
    return lk.set_index("alpha-3")


def central_value(row) -> float:
    """Central government value a user takes without GG: CGSS, else CGXSS (or BCG + EBCG) + SSF (package C1/C2)."""
    vals = {s: eh._dec(row[s]) for s in eh.SECTORS}
    v, _, _ = resolve_value(vals, sector_override="Central government including social security")
    return np.nan if v is None else float(v)


def splice(c: pd.DataFrame, d: int, k: int = eh.ADJ_K) -> pd.Series:
    """
    Ratio splicing of the tiered value without GG (column RULE): the value times the median ratio
    GG/value in the k overlap years closest to, and at least d years after, the year, among overlap
    years with the same tier and components (as in evaluate_harmonisation._adjust_eval). Unlike
    that evaluation, years in which the value equals GG are kept, so the sample is fixed.
    """
    o = c[c["GG_OK"].notna() & (c["RULE"] > 0)]
    ratio = o["GG_OK"] / o["RULE"]
    r_hat = pd.Series(np.nan, index=o.index)
    for _, g in o.groupby(["ISO", "DIV", "RULE_SECT"]):
        yrs, rat = g["YEAR"].to_numpy(), ratio[g.index].to_numpy()
        r_hat.loc[g.index] = [eh._later_ratio(yrs, rat, y, d, k) for y in yrs]
    return (r_hat * o["RULE"]).reindex(c.index)


def cell_table(h: pd.DataFrame) -> pd.DataFrame:
    """One row per country, division (07, 09, 10) and year with GG and every alternative."""
    c = h[h["DIV"].isin(["07", "09", "10"])].copy().reset_index(drop=True)
    ok_gg = c[GG].notna() & (c[GG] > 0) & (c["COMPLETE"] == True)  # noqa: E712
    c["GG_OK"] = c[GG].where(ok_gg)
    c["CG"] = c["EST_CG"]
    c["T2"] = c["EST_T2"].where(c["T2_COMPLETE"])
    c["T3"] = c["EST_T3"].where(c["T3_COMPLETE"])
    has_cgss = c[CGSS].notna()
    c["RULE"] = np.where(has_cgss, c["T2"], c["T3"])
    c["RULE_SECT"] = np.where(has_cgss, "T2:" + c["T2_SECTORS"].fillna(""), "T3:" + c["T3_SECTORS"].fillna(""))
    for d in SPLICE_D:
        c[f"SPL{d}"] = splice(c, d)
    c["SUBNAT"] = c[[SG, LG]].fillna(0).sum(axis=1)
    c["CENTRAL"] = c.apply(central_value, axis=1)
    return c


def measure_table(c: pd.DataFrame, divs) -> pd.DataFrame:
    """Values of a measure (sum of divisions) by country-year; a value needs every division."""
    cols = ["GG_OK", "CG", "T2", "T3", "RULE"] + [f"SPL{d}" for d in SPLICE_D] + ["VALUE", "CENTRAL", GG]
    x = c[c["DIV"].isin(divs)].set_index(["ISO", "YEAR", "DIV"])
    w = x[cols + ["TIER", "COMPLETE"]].unstack("DIV")
    m = pd.DataFrame(index=w.index)
    for col in cols:
        sub = w[col].reindex(columns=divs)
        m[col] = sub.sum(axis=1, min_count=len(divs)).where(sub.notna().all(axis=1))
    m["SUBNAT"] = x.groupby(level=["ISO", "YEAR"])["SUBNAT"].sum().reindex(m.index)
    m["NO_GG_TIER"] = w["TIER"].reindex(columns=divs).isin(["T2", "T3"]).all(axis=1)
    m["ALL_COMPLETE"] = (w["COMPLETE"].reindex(columns=divs) == True).all(axis=1)  # noqa: E712
    return m.rename(columns={GG: "GG_ANY"}).reset_index()


# ----------------------------------------------------------------------------
# Analysis A
# ----------------------------------------------------------------------------

def _fwl_slope(x, y, yr, n_yr):
    """Slope of y on x with year effects (Frisch-Waugh-Lovell); y may have several columns."""
    cnt = np.bincount(yr, minlength=n_yr).astype(float)
    cnt[cnt == 0] = 1
    xt = x - (np.bincount(yr, weights=x, minlength=n_yr) / cnt)[yr]
    yt = np.column_stack([y[:, j] - (np.bincount(yr, weights=y[:, j], minlength=n_yr) / cnt)[yr]
                          for j in range(y.shape[1])])
    return (xt @ yt) / (xt @ xt)


def gradient(s: pd.DataFrame) -> dict:
    """Income gradient for GG and the alternative on the same rows, with a cluster bootstrap of the difference."""
    import statsmodels.formula.api as smf
    r = s[(s["GG"] > 0) & (s["ALT"] > 0) & s["GDPPC"].notna()].copy()
    if r["ISO"].nunique() < 10:
        return {"N (regression)": len(r)}
    r["lnGDPPC"] = np.log(r["GDPPC"])
    out = {"N (regression)": len(r), "Countries (regression)": r["ISO"].nunique()}
    groups = pd.factorize(r["ISO"])[0]
    for lab, col in (("GG", "GG"), ("alt", "ALT")):
        r["lny"] = np.log(r[col])
        f = smf.ols("lny ~ lnGDPPC + C(YEAR)", data=r).fit(cov_type="cluster", cov_kwds={"groups": groups})
        out[f"b {lab}"], out[f"se {lab}"] = f.params["lnGDPPC"], f.bse["lnGDPPC"]
    x = r["lnGDPPC"].to_numpy()
    y = np.column_stack([np.log(r["GG"].to_numpy()), np.log(r["ALT"].to_numpy())])
    yr = pd.factorize(r["YEAR"])[0]
    codes = groups
    members = [np.flatnonzero(codes == i) for i in range(codes.max() + 1)]
    rng = np.random.default_rng(BOOT_SEED)
    diff = np.empty(BOOT_REPS)
    for b in range(BOOT_REPS):
        idx = np.concatenate([members[i] for i in rng.integers(0, len(members), len(members))])
        bb = _fwl_slope(x[idx], y[idx], yr[idx], yr.max() + 1)
        diff[b] = bb[1] - bb[0]
    out["Difference (alt - GG)"] = out["b alt"] - out["b GG"]
    out["Difference, bootstrap 2.5%"] = np.percentile(diff, 2.5)
    out["Difference, bootstrap 97.5%"] = np.percentile(diff, 97.5)
    out["Difference, bootstrap se"] = diff.std(ddof=1)
    return out


def fixed_sample_stats(s: pd.DataFrame) -> dict:
    """Statistics of an alternative against GG on one fixed sample (columns ISO, YEAR, GG, ALT, GDPPC, REGION)."""
    r = s["ALT"] / s["GG"]
    err = (r - 1).abs()
    st = {"N": len(s), "Countries": s["ISO"].nunique(),
          "Countries outside Europe": s.loc[s["REGION"] != "Europe", "ISO"].nunique(),
          "Years": f"{s['YEAR'].min()}-{s['YEAR'].max()}",
          "Median ratio": r.median(), "P25 ratio": r.quantile(0.25), "P75 ratio": r.quantile(0.75),
          "Exact identities (%)": 100 * (err <= TOL).mean(),
          "Error > 10% (%)": 100 * (err > 0.10).mean(), "Error > 25% (%)": 100 * (err > 0.25).mean(),
          "Median GG (% GDP)": s["GG"].median(), "Median alt (% GDP)": s["ALT"].median(),
          "Median difference alt - GG (pp GDP)": (s["ALT"] - s["GG"]).median()}
    yearly = [g[["GG", "ALT"]].corr(method="spearman").iat[0, 1]
              for _, g in s.groupby("YEAR") if g["ISO"].nunique() >= MIN_COUNTRIES_YEAR]
    yearly = [v for v in yearly if pd.notna(v)]
    st["Years with >= 10 countries"] = len(yearly)
    st["Spearman by year, median"] = float(np.median(yearly)) if yearly else np.nan
    st["Spearman by year, min"] = float(np.min(yearly)) if yearly else np.nan
    cm = s.groupby("ISO")[["GG", "ALT"]].mean()
    st["Spearman, country means"] = cm.corr(method="spearman").iat[0, 1] if len(cm) > 2 else np.nan
    if len(cm) >= 10:
        q_gg = pd.qcut(cm["GG"].rank(method="first"), 5, labels=False)
        q_alt = pd.qcut(cm["ALT"].rank(method="first"), 5, labels=False)
        st["Countries changing quintile"] = int((q_gg != q_alt).sum())
        st["Countries changing quintile (%)"] = 100 * (q_gg != q_alt).mean()
    st.update(gradient(s))
    return st


def analysis_a(c: pd.DataFrame, gdp: pd.DataFrame, reg: pd.DataFrame):
    rows, inkind, nogg = [], [], []
    for code, name, divs in MEASURES:
        m = measure_table(c, divs).merge(gdp, on=["ISO", "YEAR"], how="left")
        m["REGION"] = m["ISO"].map(reg["region"]).fillna("Unassigned")
        base = m[m["GG_OK"].notna()]
        common = base[base[COMMON].notna().all(axis=1)]
        for sample_name, frame, alts in (("Pairwise", base, [a for a, _ in ALTERNATIVES]),
                                         ("Common", common, COMMON)):
            for sub_name, sub in (("All", frame), ("Subnational > 0", frame[frame["SUBNAT"] > 0])):
                for alt in alts:
                    s = sub[sub[alt].notna()].rename(columns={"GG_OK": "GG"})
                    s = s.assign(ALT=s[alt])[["ISO", "YEAR", "GG", "ALT", "GDPPC", "REGION"]]
                    if s.empty:
                        continue
                    rows.append({"Measure": code, "Function": name, "Sample": sample_name,
                                 "Country-years": sub_name, "Alternative": dict(ALTERNATIVES)[alt],
                                 **fixed_sample_stats(s)})
        # In-kind transfer pool (and other measures): CG-only shortfall where subnational governments spend
        for alt, lab in (("CG", "CGSS alone"), ("RULE", "tiered rule without GG"), ("SPL5", "spliced, d >= 5")):
            g = base[base[alt].notna() & (base["SUBNAT"] > 0)]
            regs = [("All", g)] + (list(g.groupby("REGION")) if alt == "CG" else [])
            for reg_name, x in regs:
                inkind.append(_shortfall_row(code, name, f"GG reported, subnational > 0 ({lab} vs GG)", reg_name,
                                             x["GG_OK"], x[alt], x["ISO"]))
        # Without GG: central value against the tiered value
        for compl_name, mask in (("Complete only", m["ALL_COMPLETE"]), ("All", pd.Series(True, index=m.index))):
            ng = m[m["NO_GG_TIER"] & mask & m["CENTRAL"].notna() & m["VALUE"].notna() & (m["VALUE"] > 0)]
            never = set(ng["ISO"]) - set(m.loc[m["GG_ANY"].notna(), "ISO"])
            for reg_name, x in [("All", ng)] + list(ng.groupby("REGION")):
                r = x["CENTRAL"] / x["VALUE"]
                sp = x["SUBNAT"] > 0
                rs = r[sp]
                nogg.append({"Measure": code, "Function": name, "Tiered values": compl_name, "Region": reg_name,
                             "N": len(x), "Countries": x["ISO"].nunique(),
                             "Countries never reporting GG": len(set(x["ISO"]) & never),
                             "Subnational spending reported (% of cells)": 100 * sp.mean(),
                             "Countries with subnational spending reported": x.loc[sp, "ISO"].nunique(),
                             "Median ratio central/tiered": r.median(),
                             "Central below tiered by > 10% (%)": 100 * (r < 0.9).mean(),
                             "Central below tiered by > 25% (%)": 100 * (r < 0.75).mean(),
                             "Median tiered value (% GDP)": x["VALUE"].median(),
                             "Subnational > 0: median ratio central/tiered": rs.median(),
                             "Subnational > 0: P25 ratio": rs.quantile(0.25),
                             "Subnational > 0: P75 ratio": rs.quantile(0.75),
                             "Subnational > 0: median difference tiered - central (pp GDP)":
                                 (x.loc[sp, "VALUE"] - x.loc[sp, "CENTRAL"]).median()})
            if compl_name == "Complete only":
                ngs = ng[ng["SUBNAT"] > 0]
                for reg_name, x in [("All", ngs)] + list(ngs.groupby("REGION")):
                    inkind.append(_shortfall_row(code, name, "GG not reported, subnational > 0 (central vs tiered, complete)",
                                                 reg_name, x["VALUE"], x["CENTRAL"], x["ISO"]))
    return pd.DataFrame(rows), pd.DataFrame(inkind), pd.DataFrame(nogg)


def _shortfall_row(code, name, basis, region, pool, alt, iso):
    """Shortfall of an alternative against the reference value (GG, or the tiered value without GG); negative = excess."""
    short = pool - alt
    return {"Measure": code, "Function": name, "Basis": basis, "Region": region, "N": len(pool),
            "Countries": iso.nunique(), "Median reference value (% GDP)": pool.median(),
            "Median alternative (% GDP)": alt.median(),
            "Median shortfall (pp GDP)": short.median(), "P25 shortfall (pp GDP)": short.quantile(0.25),
            "P75 shortfall (pp GDP)": short.quantile(0.75),
            "Median shortfall (% of pool)": (100 * short / pool).median(),
            "Shortfall > 1 pp GDP (%)": 100 * (short > 1).mean(),
            "Country median of shortfall (pp GDP)": short.groupby(iso).median().median() if len(pool) else np.nan,
            "Country median of shortfall (% of pool)": (100 * short / pool).groupby(iso).median().median()
            if len(pool) else np.nan}


def main_table_a(a1: pd.DataFrame) -> pd.DataFrame:
    """Proposed main-text table: common sample, all country-years, health and education, and social spending."""
    keep = a1[(a1["Sample"] == "Common") & (a1["Country-years"] == "All") & a1["Measure"].isin(["HE", "SOC"])]
    cols = ["Measure", "Function", "Alternative", "N", "Countries", "Countries outside Europe", "Years",
            "Median ratio", "P25 ratio", "P75 ratio",
            "Error > 10% (%)", "Error > 25% (%)", "Spearman by year, median", "Countries changing quintile",
            "b GG", "b alt", "Difference (alt - GG)", "Difference, bootstrap 2.5%", "Difference, bootstrap 97.5%"]
    return keep[cols]


# ----------------------------------------------------------------------------
# Analysis B
# ----------------------------------------------------------------------------

def group_coverage(grp: pd.DataFrame) -> pd.DataFrame:
    g = grp[grp["YEAR"] <= 2023]
    rows = []
    for (code, sec), x in g.groupby(["GRP", "SECTOR_NORM"]):
        rows.append({"Code": {"018": "01.8", "017": "01.7", "TOT": "Total outlays"}[code],
                     "Sector": eh.SECTOR_ABBR.get(sec, sec), "Countries with a value": x["ISO"].nunique(),
                     "Country-years": len(x), "Positive": int((x["VALUE"] > 0).sum()),
                     "Zero": int((x["VALUE"] == 0).sum()),
                     "Countries with a positive value": x.loc[x["VALUE"] > 0, "ISO"].nunique()})
    order = {s: i for i, s in enumerate(["GG", "CGSS", "CGXSS", "BCG", "EBCG", "SSF", "SG", "LG"])}
    out = pd.DataFrame(rows)
    return out.sort_values(["Code", "Sector"], key=lambda s: s.map(order) if s.name == "Sector" else s)


class GroupValues:
    """Values of 01.7, 01.8 and total outlays by country, year and sector."""

    def __init__(self, grp: pd.DataFrame):
        self.v = grp.set_index(["ISO", "YEAR", "GRP", "SECTOR_NORM"])["VALUE"].to_dict()

    def get(self, iso, yr, code, abbr):
        return self.v.get((iso, yr, code, ABBR_TO_SECTOR[abbr]), np.nan)

    def comp_sum(self, iso, yr, code, comps):
        vals = [self.get(iso, yr, code, a) for a in comps]
        return np.nan if not comps or any(pd.isna(x) for x in vals) else float(sum(vals))


def overlap_cells(h: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Overlap cells (GG positive, not flagged) with a complete sum: kind T2, T3 or RULE (T2 if CGSS reported, else T3)."""
    o = h[h[GG].notna() & (h[GG] > 0) & (h["COMPLETE"] == True)].copy()  # noqa: E712
    if kind == "RULE":
        has = o[CGSS].notna()
        o["S"] = np.where(has, o["EST_T2"].where(o["T2_COMPLETE"]), o["EST_T3"].where(o["T3_COMPLETE"]))
        o["COMPS"] = np.where(has, o["T2_SECTORS"], o["T3_SECTORS"])
        o["KIND"] = np.where(has, "T2", "T3")
    else:
        o["S"] = o[f"EST_{kind}"].where(o[f"{kind}_COMPLETE"])
        o["COMPS"] = o[f"{kind}_SECTORS"]
        o["KIND"] = kind
    o = o[o["S"].notna()].copy()
    o["SUBPOS"] = o[[SG, LG]].fillna(0).sum(axis=1) > 0
    o["IDENT"] = (o["S"] - o[GG]).abs() <= TOL * o[GG].abs()
    o["GAP"] = o["S"] - o[GG]
    return o


def division01_metrics(o: pd.DataFrame, gv: GroupValues) -> pd.DataFrame:
    """Per country-year (division 01, subnational spending): gaps in 01, 01.8, 01.7 and total outlays."""
    x = o[(o["DIV"] == "01") & o["SUBPOS"]]
    recs = []
    for r in x[["ISO", "YEAR", "KIND", "COMPS", "S", GG, "GAP"]].to_dict("records"):
        iso, yr, comps = r["ISO"], r["YEAR"], r["COMPS"].split("+")
        central = [a for a in comps if a in CENTRAL_ABBR]
        rec = {"ISO": iso, "YEAR": yr, "KIND": r["KIND"], "COMPS": r["COMPS"],
               "S01": r["S"], "G01": r[GG], "GAP01": r["GAP"]}
        for code in ("018", "017", "TOT"):
            rec[f"S{code}"] = gv.comp_sum(iso, yr, code, comps)
            rec[f"G{code}"] = gv.get(iso, yr, code, "GG")
            rec[f"GAP{code}"] = rec[f"S{code}"] - rec[f"G{code}"]
        rec["C018"] = gv.comp_sum(iso, yr, "018", central)
        rec["SG018"] = gv.get(iso, yr, "018", "SG")
        recs.append(rec)
    d = pd.DataFrame(recs)
    d["GAP01_POS"] = d["GAP01"] > GAP_MIN * d["G01"]
    d["R018"] = (d["GAP018"] / d["GAP01"]).where(d["GAP01_POS"])
    d["R018_017"] = ((d["GAP018"] + d["GAP017"]) / d["GAP01"]).where(d["GAP01_POS"])
    d["RTOT"] = (d["GAPTOT"] / d["GAP01"]).where(d["GAP01_POS"])
    d["RC018"] = (d["C018"] / d["GAP01"]).where(d["GAP01_POS"])
    return d


def _ratio_row(est, comparator, r, iso):
    r = r.dropna()
    return {"Sum": est, "Gap compared with the 01 gap": comparator, "N": len(r), "Countries": iso[r.index].nunique(),
            "P10": r.quantile(0.10), "P25": r.quantile(0.25), "Median": r.median(), "P75": r.quantile(0.75),
            "P90": r.quantile(0.90), "Within 5% (%)": 100 * ((r - 1).abs() <= 0.05).mean(),
            "Within 10% (%)": 100 * ((r - 1).abs() <= 0.10).mean()}


def test1(h: pd.DataFrame, gv: GroupValues) -> pd.DataFrame:
    rows = []
    for est in ("T2", "T3"):
        d = division01_metrics(overlap_cells(h, est), gv)
        base = {"Cells (01, subnational > 0)": len(d), "Countries (01, subnational > 0)": d["ISO"].nunique(),
                "01 gap > 1% of GG (%)": 100 * d["GAP01_POS"].mean(),
                "01.8 reported for GG and every component (%)": 100 * d["GAP018"].notna().mean(),
                "GG 01.8 zero (%)": 100 * (d.loc[d["G018"].notna(), "G018"] == 0).mean(),
                "Median GG 01.8 (% GDP)": d["G018"].median(), "Median sum 01.8 (% GDP)": d["S018"].median(),
                "Median 01 gap (% GDP)": d["GAP01"].median()}
        for comp, col in (("01.8", "R018"), ("01.8 + 01.7", "R018_017"), ("Central 01.8 alone", "RC018"),
                          ("Total outlays", "RTOT")):
            rows.append({**_ratio_row(est, comp, d[col], d["ISO"]), **base})
    return pd.DataFrame(rows)


def practice_tables(h: pd.DataFrame, gv: GroupValues, reg: pd.DataFrame):
    o = overlap_cells(h, "RULE")
    d = division01_metrics(o, gv)
    # gaps in divisions 02-10 in the same country-year (complete sum of each division); a gap counts
    # when it exceeds GAP_MIN of GG in that division, as for division 01
    f = o[(o["DIV"] != "01")].merge(d[["ISO", "YEAR"]], on=["ISO", "YEAR"])
    f["GAP_C"] = f["GAP"].where(f["GAP"] > GAP_MIN * f[GG], 0.0)
    fg = f.groupby(["ISO", "YEAR"]).agg(N_DIV=("DIV", "size"), N_IDENT=("IDENT", "sum"), FGAP=("GAP_C", "sum"))
    fx = f[~f["DIV"].isin(["07", "10"])].groupby(["ISO", "YEAR"]).agg(FGAP_X=("GAP_C", "sum"))
    d = d.merge(fg.reset_index(), on=["ISO", "YEAR"], how="left").merge(fx.reset_index(), on=["ISO", "YEAR"], how="left")
    g01 = d["GAP01"].where(d["GAP01_POS"], 0.0)
    for col, fcol in (("F", "FGAP"), ("F_X", "FGAP_X")):
        tot = d[fcol] + g01
        d[col] = (d[fcol] / tot.where(tot > 0)).fillna(0.0).where(d["N_DIV"] >= 6)
    # 01.8 recorded by the paying (central) level and accounting for at least half of the 01 gap
    share = d["R018"].where(d["R018"].notna(), d["RC018"])
    d["REC018"] = (d["C018"] > 0) & (share >= 0.5)
    d["ANY_GAP"] = d["GAP01_POS"] | (d["FGAP"] > 0)

    def classify(F, rec, any_gap):
        if pd.isna(F):
            return "U"
        if not any_gap:
            return "E"
        if F <= cut:
            return "A" if rec else "D"
        return "C" if rec else "B"

    labels = {"A": "A. Transfers in 01.8, eliminated there; divisions 02-10 additive",
              "B": "B. No 01.8 record; gaps in divisions 02-10 (eliminated by function)",
              "C": "C. Both: 01.8 recorded and gaps in divisions 02-10",
              "D": "D. Consolidation in 01 outside 01.8 or 01.8 not reported; 02-10 additive",
              "E": "E. No consolidation visible (no gap in 01 or 02-10)",
              "U": "U. Undetermined (fewer than six divisions)"}
    counts = []
    for fcol, cut in [("F", F_CUT)] + [("F", x) for x in F_CUT_ALT] + [("F_X", F_CUT)]:
        cls = [classify(F, rec, gp) for F, rec, gp in zip(d[fcol], d["REC018"], d["ANY_GAP"])]
        name = f"CLASS_{fcol}_{cut:.2f}"
        d[name] = cls
        mode = d.groupby("ISO")[name].agg(lambda s: s.value_counts().sort_index().idxmax())
        lab = f"Countries, threshold {cut:.2f}" + (" (F excluding 07 and 10)" if fcol == "F_X" else "")
        counts.append(mode.value_counts().rename(lab))
    d["CLASS"] = d[f"CLASS_F_{F_CUT:.2f}"]

    # country table
    sub = o[o["SUBPOS"] & o["DIV"].isin(["07", "09", "10"])].copy()
    sub["R_SUM"] = sub["S"] / sub[GG]
    sub["R_CG"] = sub[CGSS] / sub[GG]
    sub["R_SUB"] = sub[[SG, LG]].fillna(0).sum(axis=1) / sub[GG]
    ctry = d.groupby("ISO").agg(**{
        "Country-years": ("YEAR", "size"), "First year": ("YEAR", "min"), "Last year": ("YEAR", "max"),
        "Sum": ("KIND", lambda s: "/".join(sorted(set(s)))),
        "Central 01.8 positive (% of years)": ("C018", lambda s: 100 * (s > 0).mean()),
        "01.8 reported (% of years)": ("GAP018", lambda s: 100 * s.notna().mean()),
        "Median 01.8 gap / 01 gap": ("R018", "median"),
        "Median central 01.8 / 01 gap": ("RC018", "median"),
        "Median 01 gap (% of GG 01)": ("GAP01", lambda s: np.nan),
        "Median share of consolidation outside 01 (F)": ("F", "median"),
        "Median F excluding 07 and 10": ("F_X", "median"),
        "Identities in 02-10 (%)": ("N_IDENT", "sum"),
        "Practice": ("CLASS", lambda s: s.value_counts().sort_index().idxmax()),
        "Years in modal practice (%)": ("CLASS", lambda s: 100 * s.value_counts().max() / len(s))})
    ctry["Median 01 gap (% of GG 01)"] = (100 * d["GAP01"] / d["G01"]).groupby(d["ISO"]).median()
    ctry["Identities in 02-10 (%)"] = 100 * ctry["Identities in 02-10 (%)"] / d.groupby("ISO")["N_DIV"].sum()
    for dv in ("07", "09", "10"):
        x = sub[sub["DIV"] == dv].groupby("ISO")
        ctry[f"Median sum/GG {dv}"] = x["R_SUM"].median()
        ctry[f"Median CGSS/GG {dv}"] = x["R_CG"].median()
        ctry[f"Median (SG+LG)/GG {dv}"] = x["R_SUB"].median()
    ctry.insert(0, "Country", reg["name"].reindex(ctry.index))
    ctry.insert(1, "Region", reg["region"].reindex(ctry.index))
    ctry["Practice label"] = ctry["Practice"].map(labels)
    ctry = ctry.sort_values(["Practice", "Median share of consolidation outside 01 (F)"]).reset_index()

    # summary by practice, with what each practice does to divisions 07, 09, 10
    ident = o[o["SUBPOS"] & (o["DIV"] != "01") & o["IDENT"]]
    cls_of = ctry.set_index("ISO")["Practice"]
    sub["Practice"] = sub["ISO"].map(cls_of)
    ident_cls = ident["ISO"].map(cls_of)
    summ = []
    d_cls = d["ISO"].map(cls_of)
    for p in sorted(labels) + ["BC"]:
        members = ["B", "C"] if p == "BC" else [p]
        cs = ctry[ctry["Practice"].isin(members)]
        dd = d[d_cls.isin(members)]
        row = {"Practice": "B and C together" if p == "BC" else labels[p], "Countries": len(cs),
               "Country-years": int(cs["Country-years"].sum()),
               "Of which EU/EFTA": int(cs["ISO"].isin(EU_EFTA).sum()),
               "Informative identities in 02-10 (% of all)": 100 * ident_cls.isin(members).mean(),
               "Median 01.8 gap / 01 gap": dd["R018"].median(),
               "Median total-outlays gap / 01 gap": dd["RTOT"].median(),
               "Median share of consolidation outside 01 (F)": dd["F"].median()}
        for dv in ("07", "09", "10"):
            x = sub[sub["Practice"].isin(members) & (sub["DIV"] == dv)]
            row[f"{dv}: cells"] = len(x)
            row[f"{dv}: median sum/GG"] = x["R_SUM"].median()
            row[f"{dv}: P75 sum/GG"] = x["R_SUM"].quantile(0.75)
            row[f"{dv}: sum within 1% of GG (%)"] = 100 * ((x["R_SUM"] - 1).abs() <= 0.01).mean()
            row[f"{dv}: median CGSS/GG"] = x["R_CG"].median()
            row[f"{dv}: median (SG+LG)/GG"] = x["R_SUB"].median()
        summ.append(row)
    summ = pd.DataFrame(summ)
    sens = pd.concat(counts, axis=1).reindex(sorted(labels)).fillna(0).astype(int)
    sens.index = [labels[i] for i in sens.index]
    for col in sens.columns:
        summ[col] = summ["Practice"].map(sens[col])
    return d, ctry, summ


def main_table_b(summ: pd.DataFrame) -> pd.DataFrame:
    """Proposed main-text table: practices A, B, C and B with C, with their effect on divisions 07, 09, 10."""
    keep = summ[summ["Practice"].str[:2].isin(["A.", "B.", "C."]) | (summ["Practice"] == "B and C together")]
    cols = ["Practice", "Countries", "Of which EU/EFTA", "Country-years", "Informative identities in 02-10 (% of all)",
            "Median 01.8 gap / 01 gap", "Median total-outlays gap / 01 gap"]
    for dv in ("07", "09", "10"):
        cols += [f"{dv}: median sum/GG", f"{dv}: P75 sum/GG"]
    return keep[cols]


def test2(d: pd.DataFrame, o: pd.DataFrame) -> pd.DataFrame:
    """Recording of 01.8 where GG equals the unconsolidated sum in a division 02-10."""
    f = o[o["SUBPOS"] & (o["DIV"] != "01")].merge(
        d[["ISO", "YEAR", "C018", "SG018", "GAP018", "GAP01_POS", "R018", "CLASS"]],
        on=["ISO", "YEAR"], how="inner")
    f["CAT"] = np.where(f["IDENT"], "Sum equals GG (informative identity)", "Sum differs from GG")
    rows = []
    for kind in ("T2", "T3", "All"):
        g = f if kind == "All" else f[f["KIND"] == kind]
        for cat, x in g.groupby("CAT"):
            rep = x["C018"].notna()
            sgr = x["SG018"].notna()
            r = x["R018"].dropna()
            rows.append({"Sum": kind, "Cells": cat, "N": len(x), "Countries": x["ISO"].nunique(),
                         "Central 01.8 positive (%)": 100 * (x["C018"] > 0).mean(),
                         "Central 01.8 reported zero (%)": 100 * (x["C018"] == 0).mean(),
                         "Central 01.8 not reported (%)": 100 * (~rep).mean(),
                         "Central or state 01.8 positive (%)": 100 * ((x["C018"] > 0) | (x["SG018"] > 0)).mean(),
                         "State 01.8 positive, where SG reports 01.8 (%)": 100 * (x.loc[sgr, "SG018"] > 0).mean() if sgr.any() else np.nan,
                         "01 gap > 1% of GG 01 (%)": 100 * x["GAP01_POS"].mean(),
                         "01.8 gap within 10% of 01 gap (% of defined)": 100 * ((r - 1).abs() <= 0.10).mean() if len(r) else np.nan,
                         "Cells with 01.8 gap defined": len(r)})
    return pd.DataFrame(rows)


def test4(d: pd.DataFrame, o: pd.DataFrame, eu: pd.DataFrame) -> pd.DataFrame:
    """Alternative explanations: GG as a plain subsector sum, subsector data net of grants, Eurostat agreement."""
    rows = []
    has_tot = d["GAPTOT"].notna() & d["GTOT"].notna()
    no_tot_gap = has_tot & (d["GAPTOT"].abs() <= GAP_MIN * d["GTOT"])
    rec = d["C018"] > 0
    rows.append({"Check": "Country-years with total outlays for GG and every component", "N": int(has_tot.sum()),
                 "Countries": d.loc[has_tot, "ISO"].nunique()})
    rows.append({"Check": "No gap in total outlays (sum within 1% of GG)", "N": int(no_tot_gap.sum()),
                 "Countries": d.loc[no_tot_gap, "ISO"].nunique(),
                 "Share (%)": 100 * no_tot_gap.sum() / max(has_tot.sum(), 1)})
    rows.append({"Check": "  of which central 01.8 positive (GG consistent with a plain sum)", "N": int((no_tot_gap & rec).sum()),
                 "Countries": d.loc[no_tot_gap & rec, "ISO"].nunique(), "ISO codes": ", ".join(sorted(set(d.loc[no_tot_gap & rec, "ISO"])))})
    rows.append({"Check": "  of which central 01.8 zero or not reported (net of grants, plain sum or no transfers)",
                 "N": int((no_tot_gap & ~rec).sum()), "Countries": d.loc[no_tot_gap & ~rec, "ISO"].nunique(),
                 "ISO codes": ", ".join(sorted(set(d.loc[no_tot_gap & ~rec, "ISO"])))})
    ident01 = (d["GAP01"].abs() <= TOL * d["G01"].abs())
    rows.append({"Check": "Sum equals GG in division 01", "N": int(ident01.sum()), "Countries": d.loc[ident01, "ISO"].nunique(),
                 "Share (%)": 100 * ident01.mean(), "ISO codes": ", ".join(sorted(set(d.loc[ident01, "ISO"])))})
    gpos = d["G018"] > 0
    not_elim = gpos & d["S018"].notna() & ((d["S018"] - d["G018"]).abs() <= TOL * d["G018"].abs())
    rows.append({"Check": "GG 01.8 positive", "N": int(gpos.sum()), "Countries": d.loc[gpos, "ISO"].nunique(),
                 "Share (%)": 100 * gpos.sum() / max(d["G018"].notna().sum(), 1),
                 "Median": (d.loc[gpos, "G018"] / d.loc[gpos, "S018"]).median(),
                 "ISO codes": ", ".join(sorted(set(d.loc[gpos, "ISO"])))})
    rows.append({"Check": "  of which GG 01.8 equals the sum of subsector 01.8 (not eliminated)", "N": int(not_elim.sum()),
                 "Countries": d.loc[not_elim, "ISO"].nunique(), "ISO codes": ", ".join(sorted(set(d.loc[not_elim, "ISO"])))})
    # Receiving levels reporting net of grants received would put the sum below GG in divisions 02-10
    fo = o[o["SUBPOS"] & (o["DIV"] != "01")]
    below = fo["S"] < (1 - GAP_MIN) * fo[GG]
    above = fo["S"] > (1 + GAP_MIN) * fo[GG]
    rows.append({"Check": "Divisions 02-10, subnational > 0: complete sum below GG by more than 1%", "N": int(below.sum()),
                 "Countries": fo.loc[below, "ISO"].nunique(), "Share (%)": 100 * below.mean()})
    rows.append({"Check": "Divisions 02-10, subnational > 0: complete sum above GG by more than 1%", "N": int(above.sum()),
                 "Countries": fo.loc[above, "ISO"].nunique(), "Share (%)": 100 * above.mean()})
    rows.append({"Check": "Divisions 02-10, subnational > 0: all cells", "N": len(fo), "Countries": fo["ISO"].nunique()})
    # Eurostat agreement in cells where GG equals the unconsolidated sum
    cls_of = d.groupby("ISO")["CLASS"].agg(lambda s: s.value_counts().sort_index().idxmax())
    f = fo.merge(eu, on=["ISO", "DIV", "YEAR"], how="inner")
    f_a = f["ISO"].map(cls_of) == "A"
    for cat, x in (("Eurostat: informative identities in 02-10, |IMF GG - Eurostat| <= 0.1 pp", f[f["IDENT"]]),
                   ("Eurostat: other overlap cells in 02-10, |IMF GG - Eurostat| <= 0.1 pp", f[~f["IDENT"]]),
                   ("Eurostat: practice A countries, identities in 02-10, |IMF GG - Eurostat| <= 0.1 pp", f[f["IDENT"] & f_a])):
        diff = (x[GG] - x["EUROSTAT"]).abs()
        rows.append({"Check": cat, "N": len(x), "Countries": x["ISO"].nunique(), "Share (%)": 100 * (diff <= 0.1).mean(),
                     "Median": diff.median(), "ISO codes": ", ".join(sorted(set(x["ISO"]))) if f_a[x.index].all() else None})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Coverage for another division (Table 3 and Figure 1 of the harmonisation study)
# ----------------------------------------------------------------------------

def coverage_counts(h: pd.DataFrame, div: str) -> pd.DataFrame:
    """Countries with a value by year and tier: the data behind Figure 1 for one division."""
    g = h[(h["DIV"] == div) & (h["TIER"] != "")]
    c = (g.groupby(["YEAR", "TIER"]).size().unstack(fill_value=0)
         .reindex(index=list(YEARS), columns=["T1", "T2", "T3"], fill_value=0))
    c = c.loc[c.index <= 2023]
    c["Total"] = c.sum(axis=1)
    c["T2 and T3 share (%)"] = (100 * (c["T2"] + c["T3"]) / c["Total"].where(c["Total"] > 0)).round(1)
    return c.reset_index().rename(columns={"YEAR": "Year"})


def fig_coverage(h: pd.DataFrame, div: str, path):
    """evaluate_harmonisation.fig_coverage with the division as an argument (same size, colours and dpi)."""
    import matplotlib.pyplot as plt
    g = h[(h["DIV"] == div) & (h["TIER"] != "")]
    c = (g.groupby(["YEAR", "TIER"]).size().unstack(fill_value=0)
         .reindex(index=list(YEARS), columns=["T1", "T2", "T3"], fill_value=0))
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=200)
    bottom = np.zeros(len(c))
    for t, lab in [("T1", "T1 general government"), ("T2", "T2 central + subnational"),
                   ("T3", "T3 component sum")]:
        ax.bar(c.index, c[t], bottom=bottom, color=eh.TIER_COLORS[t], width=0.8,
               edgecolor="white", linewidth=0.8, label=lab)
        bottom += c[t].values
    eh._style(ax)
    ax.set_xlim(1989.5, 2023.5)
    ax.set_ylabel("Countries with a value", color=eh.INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


COVERAGE_DIV = "09"


# ----------------------------------------------------------------------------
# Consistency with the published tables
# ----------------------------------------------------------------------------

def checks(h: pd.DataFrame, a1: pd.DataFrame, c: pd.DataFrame) -> pd.DataFrame:
    """Recompute Table 4 / Online Appendix Table S4 and compare it with the pairwise statistics of Analysis A,
    and compare the spliced values with the adjusted estimates of the Table 5 evaluation."""
    t4 = eh.table_overlap(h)
    rows = []
    for dv in ("07", "09", "10"):
        for est, alt in (("CGSS alone", "CGSS alone"), ("T2 sum, complete", "T2 sum, complete"),
                         ("T3 sum, complete", "T3 sum, complete"),
                         ("CGSS alone, subnational > 0", None)):
            t = t4[(t4["DIV"] == dv) & (t4["Estimator"] == est)].iloc[0]
            if alt is None:
                a = a1[(a1["Measure"] == dv) & (a1["Sample"] == "Pairwise") & (a1["Country-years"] == "Subnational > 0")
                       & (a1["Alternative"] == "CGSS alone")].iloc[0]
            else:
                a = a1[(a1["Measure"] == dv) & (a1["Sample"] == "Pairwise") & (a1["Country-years"] == "All")
                       & (a1["Alternative"] == alt)].iloc[0]
            rows.append({"DIV": dv, "Table S4 estimator": est, "S4 N": t["N"], "Here N": a["N"],
                         "S4 median ratio": t["Median ratio"], "Here median ratio": round(a["Median ratio"], 3),
                         "Match": bool(t["N"] == a["N"] and abs(t["Median ratio"] - round(a["Median ratio"], 3)) < 1e-9)})
    published = REPO / "replication" / "sjiaos" / "output" / "table4_overlap.csv"
    if published.exists():
        norm = lambda s: s.replace("\r\n", "\n").strip()  # noqa: E731
        same = norm(published.read_text(encoding="utf8")) == norm(t4.to_csv(index=False))
        rows.append({"DIV": "All", "Table S4 estimator": "Recomputed Table 4 equals output/table4_overlap.csv",
                     "Match": same})
    # Splicing: where the tiered rule gives a T2 sum and the sum differs from GG, the spliced value equals
    # the adjusted estimate of the Table 5 evaluation (evaluate_harmonisation._adjust_eval)
    for d in SPLICE_D:
        x = eh._adjust_eval(h, "EST_T2", d)
        x = x[x["DIV"].isin(["07", "09", "10"])][["ISO", "DIV", "YEAR", "ADJ"]].merge(
            c[["ISO", "DIV", "YEAR", f"SPL{d}"]], on=["ISO", "DIV", "YEAR"], how="left")
        diff = (x["ADJ"] - x[f"SPL{d}"]).abs().max()
        rows.append({"DIV": "07, 09, 10", "Table S4 estimator": f"Spliced T2 value (d >= {d}) equals Table 5 adjusted estimate",
                     "S4 N": len(x), "Here N": int(x[f"SPL{d}"].notna().sum()),
                     "Match": bool(x[f"SPL{d}"].notna().all() and diff <= 1e-12)})
    # Coverage table and figure: the division-05 versions reproduce the published Table 3 and Figure 1
    out = REPO / "replication" / "sjiaos" / "output"
    if (out / "table3_region_05.csv").exists():
        norm = lambda s: s.replace("\r\n", "\n").strip()  # noqa: E731
        same = norm((out / "table3_region_05.csv").read_text(encoding="utf8")) == norm(
            eh.table_region(h, "05").to_csv(index=False))
        rows.append({"DIV": "05", "Table S4 estimator": "Region table for 05 equals output/table3_region_05.csv",
                     "Match": same})
    if (out / "fig1_coverage_05.png").exists():
        buf = io.BytesIO()
        fig_coverage(h, "05", buf)
        rows.append({"DIV": "05", "Table S4 estimator": "Coverage figure for 05 equals output/fig1_coverage_05.png (bytes)",
                     "Match": buf.getvalue() == (out / "fig1_coverage_05.png").read_bytes()})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------

def main():
    global RAW, OUT
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0].strip())
    ap.add_argument("--source", type=Path, default=RAW, help="IMF GFS COFOG extract, Excel or CSV (default: %(default)s)")
    ap.add_argument("--out", type=Path, default=OUT, help="output folder (default: %(default)s)")
    args = ap.parse_args()
    RAW, OUT = args.source.resolve(), args.out.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    div, grp, digest = load_extract(RAW, OUT)
    h = eh.harmonise(eh.to_wide(div))
    reg = regions()
    gdp = eh.load_gdppc()
    eu = eh.load_eurostat()
    print(f"Extract SHA-256 {digest[:12]}..., {len(h)} cells, {h['ISO'].nunique()} countries ({time.time() - t0:.0f} s)")

    # Analysis A
    c = cell_table(h)
    a1, a3, a2 = analysis_a(c, gdp, reg)
    # Analysis B
    gv = GroupValues(grp)
    b0 = group_coverage(grp)
    b1 = test1(h, gv)
    d, ctry, summ = practice_tables(h, gv, reg)
    o = overlap_cells(h, "RULE")
    b2 = test2(d, o)
    b4 = test4(d, o, eu)
    chk = checks(h, a1, c)

    tables = {"ext_a1_fixed_sample": a1, "ext_a1_main_table": main_table_a(a1), "ext_a2_without_gg_by_region": a2,
              "ext_a3_inkind_shortfall": a3, "ext_b0_group_coverage": b0, "ext_b1_gap01_vs_018": b1,
              "ext_b2_identities_018": b2, "ext_b3_practice_countries": ctry, "ext_b3_practice_summary": summ,
              "ext_b3_main_table": main_table_b(summ), "ext_b4_alternatives": b4, "ext_checks": chk}
    for name, t in tables.items():
        t.round(6).to_csv(OUT / f"{name}.csv", index=False)
    d.round(6).to_csv(OUT / "ext_b_country_years.csv", index=False)
    # Coverage for education: same columns as table3_region_05.csv, and Figure 1 for the division
    t3 = eh.table_region(h, COVERAGE_DIV)
    t3.to_csv(OUT / f"ext_table3_region_{COVERAGE_DIV}.csv", index=False)
    cov = coverage_counts(h, COVERAGE_DIV)
    cov.to_csv(OUT / f"ext_fig1_coverage_{COVERAGE_DIV}_counts.csv", index=False)
    fig_coverage(h, COVERAGE_DIV, OUT / f"fig1_coverage_{COVERAGE_DIV}.png")
    tables[f"ext_table3_region_{COVERAGE_DIV}"] = t3
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    for name in ("ext_a1_main_table", "ext_b1_gap01_vs_018", "ext_b2_identities_018", "ext_b3_main_table",
                 "ext_b4_alternatives", "ext_checks", f"ext_table3_region_{COVERAGE_DIV}"):
        print(f"\n=== {name} ===")
        print(tables[name].round(3).to_string(index=False))
    print(f"\nDone in {time.time() - t0:.0f} s. Outputs in {OUT}")


if __name__ == "__main__":
    main()
