"""
Online Resource 1 of the environmental-spending study: country table, comparison of the subnational share with SNG-WOFI,
and the gap between subsector sums and general government values for environmental protection.
The subnational share follows the rule of env_federalism.subnational_share: a subnational level that the
country reports in some year but not in this year makes the share missing.

Usage (from any folder):
    python -I paperC_esm_wofi.py <repository_root> <sng_wofi_cofog_csv> <out_dir>

<repository_root>     the repository root (reads replication/eeps/output/paperC_panel.csv,
                      replication/sjiaos/output/harmonised_all_divisions.csv,
                      replication/sjiaos/output/table4_overlap.csv, data/country_codes.xlsx)
<sng_wofi_cofog_csv>  OECD SDMX download of OECD.CFE.RDG,DSD_SNG_WOFI@DF_COFOG,1.0 (csvfilewithlabels)
<out_dir>             where the CSV and JSON outputs are written
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT, WOFI, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)

GG, CGSS = "general government", "central government including social security"
CGXSS = "central government excluding social security"
BCG, EBCG, SSF = "budgetary central government", "extrabudgetary central government", "social security funds"
SG, LG = "state government", "local government"
BASE_NEEDED = ["lnPM", "lnENV", "lnY", "IND", "URB", "TRADE", "lnDENS", "GE", "SUBREGION"]

# ---------------------------------------------------------------- estimation sample (Table 2, col. 3)
p = pd.read_csv(ROOT / "replication/eeps/output/paperC_panel.csv")
s = p[p["COMPLETE_L1"]].dropna(subset=BASE_NEEDED + ["SUB"]).copy()
# The harmonised panel with coverage gaps coded as zero (108 countries): the country list covers all of it
s0 = p[p["COMPLETE_L1"]].dropna(subset=BASE_NEEDED + ["SUB0"]).copy()
print("estimation sample", len(s), s["ISO"].nunique(), "with coverage gaps", len(s0), s0["ISO"].nunique())

lk = pd.read_excel(ROOT / "data/country_codes.xlsx")[["alpha-3", "name"]]
names = dict(zip(lk["alpha-3"], lk["name"]))

g = s0.sort_values(["ISO", "YEAR"]).groupby("ISO")
tab = pd.DataFrame({
    "ISO3": g.size().index,
    "Country": [names.get(c, c) for c in g.size().index],
    "Region": g["REGION"].first().values,
    "Subregion": g["SUBREGION"].first().values,
    "First_year": g["YEAR"].min().values,
    "Last_year": g["YEAR"].max().values,
    "Obs": g.size().values,
    "Obs_T1": g["TIER_L1"].apply(lambda x: (x == "T1").sum()).values,
    "Obs_T2": g["TIER_L1"].apply(lambda x: (x == "T2").sum()).values,
    "Obs_T3": g["TIER_L1"].apply(lambda x: (x == "T3").sum()).values,
    "Mean_SUB": g["SUB0"].mean().round(6).values,  # 6 decimals, so the 2-decimal Table S6 rounds only once
    "Central_only": g["NOSUB"].max().astype(int).values,
    "Coverage_gap": g["COVGAP"].max().astype(int).values,
    "In_main_sample": g.size().index.isin(s["ISO"].unique()).astype(int),
    "Any_GG_series": g["EVER_GG"].max().astype(int).values,
    "Mean_GE": g["GE"].mean().round(2).values,
    "Mean_PM25": g["PM25"].mean().round(1).values,
})
tab = tab.sort_values(["Region", "Subregion", "Country"]).reset_index(drop=True)
print("obs", tab["Obs"].sum(), "central-only", tab["Central_only"].sum(),
      "tiers", (tab["Obs_T1"].sum(), tab["Obs_T2"].sum(), tab["Obs_T3"].sum()),
      "countries without T1", int((tab["Obs_T1"] == 0).sum()))
tab.to_csv(OUT / "ESM1_TableS1_countries.csv", index=False, encoding="utf-8")

# ---------------------------------------------------------------- subnational share in a given year
h = pd.read_csv(ROOT / "replication/sjiaos/output/harmonised_all_divisions.csv", dtype={"DIV": str})
e = h[h["DIV"] == "05"].copy()
sub = e[[SG, LG]].fillna(0).sum(axis=1)
central = e[CGSS].fillna(e[[CGXSS, SSF]].sum(axis=1, min_count=1).where(e[CGXSS].notna()))
central = central.fillna(e[[BCG, EBCG, SSF]].sum(axis=1, min_count=1))
share = sub / (sub + central)
gap = (e["EVER_SG"].astype(bool) & e[SG].isna()) | (e["EVER_LG"].astype(bool) & e[LG].isna())
share[(central.isna()) | ((sub + central) <= 0) | (e["COMPLETE"] != True) | gap] = np.nan
e["SUBSHARE"] = share.clip(0, 1)
e["NOSUB"] = (~(e["EVER_SG"].astype(bool) | e["EVER_LG"].astype(bool))).astype(int)

# ---------------------------------------------------------------- SNG-WOFI, environmental protection
w = pd.read_csv(WOFI, dtype=str)
w["v"] = pd.to_numeric(w["OBS_VALUE"], errors="coerce")
w = w[w["COFOG"] == "GF05"]
years = sorted(w["TIME_PERIOD"].unique())
ref_year = int(years[0]) if len(years) == 1 else None
assert ref_year is not None, years
fnc = (w[(w["UNIT_MEASURE"] == "PT_OTE_S13_FNC") & (w["SECTOR"] == "S13M")]
       .set_index("REF_AREA")["v"].dropna() / 100)
gdp = w[w["UNIT_MEASURE"] == "PT_B1GQ"].pivot_table(index="REF_AREA", columns="SECTOR", values="v",
                                                     aggfunc="first")
wofi = pd.DataFrame({"WOFI_share": fnc}).join(gdp.rename(columns=lambda c: f"WOFI_pctGDP_{c}"), how="outer")
wofi.index.name = "ISO3"

y = e[e["YEAR"] == ref_year].set_index("ISO")[["SUBSHARE", "TIER", "NOSUB"]]
y = y.rename(columns={"SUBSHARE": f"SUB_{ref_year}", "TIER": f"TIER_{ref_year}"})
# Sensitivity: the complete value closest to the reference year, within two years
near = e.dropna(subset=["SUBSHARE"]).assign(dist=lambda x: (x["YEAR"] - ref_year).abs())
near = near[near["dist"] <= 2].sort_values(["ISO", "dist", "YEAR"]).drop_duplicates("ISO").set_index("ISO")
y = y.join(near[["SUBSHARE", "YEAR"]].rename(columns={"SUBSHARE": "SUB_near", "YEAR": "YEAR_near"}),
           how="outer")
cmp_ = wofi.join(y, how="left")
cmp_["In_sample"] = cmp_.index.isin(s["ISO"].unique()).astype(int)
cmp_["In_panel_with_gaps"] = cmp_.index.isin(tab["ISO3"]).astype(int)
cmp_["Coverage_gap"] = cmp_.index.map(dict(zip(tab["ISO3"], tab["Coverage_gap"])))
cmp_["Central_only"] = cmp_.index.map(dict(zip(tab["ISO3"], tab["Central_only"])))
cmp_.to_csv(OUT / "ESM1_TableS3_sngwofi_comparison.csv", encoding="utf-8")


def stats(d: pd.DataFrame, col: str = f"SUB_{ref_year}") -> dict:
    d = d.dropna(subset=[col, "WOFI_share"])
    a, b = d[col], d["WOFI_share"]
    diff = a - b
    return {"countries": int(len(d)),
            "pearson": round(float(a.corr(b)), 3),
            "spearman": round(float(a.corr(b, method="spearman")), 3),
            "mean_SUB": round(float(a.mean()), 3), "mean_WOFI": round(float(b.mean()), 3),
            "mean_diff": round(float(diff.mean()), 3),
            "median_abs_diff": round(float(diff.abs().median()), 3),
            "share_within_0.10": round(float((diff.abs() <= 0.10).mean()), 3),
            "share_within_0.20": round(float((diff.abs() <= 0.20).mean()), 3)}


both = cmp_.dropna(subset=[f"SUB_{ref_year}", "WOFI_share"])
res = {"wofi_reference_year": ref_year,
       "wofi_countries_with_env_share": int(fnc.size),
       "all_overlap": stats(both),
       "sample_overlap": stats(both[both["In_sample"] == 1]),
       "sample_overlap_excl_central_only": stats(both[(both["In_sample"] == 1) & (both["Central_only"] == 0)]),
       "sample_overlap_nearest_year": stats(cmp_[cmp_["In_sample"] == 1], "SUB_near"),
       "sample_overlap_nearest_year_excl_central_only":
           stats(cmp_[(cmp_["In_sample"] == 1) & (cmp_["Central_only"] == 0)], "SUB_near"),
       "largest_gaps": both.assign(d=both[f"SUB_{ref_year}"] - both["WOFI_share"])
                           .reindex(columns=[f"SUB_{ref_year}", "WOFI_share", "d", f"TIER_{ref_year}"])
                           .sort_values("d", key=abs, ascending=False).head(8).round(3)
                           .reset_index().to_dict(orient="records")}

# Sensitivity: the IMF share one year before and after the reference year
for yy in (ref_year - 1, ref_year + 1):
    sy = e[e["YEAR"] == yy].set_index("ISO")["SUBSHARE"].rename(f"SUB_{yy}")
    dd = cmp_[cmp_["In_sample"] == 1].join(sy)
    res[f"sample_overlap_year_{yy}"] = stats(dd, f"SUB_{yy}")

# What SNG-WOFI records for the 36 central-only countries
co = tab.loc[tab["Central_only"] == 1, "ISO3"].tolist()
rows = []
for c in co:
    r = {"ISO3": c, "Country": names.get(c, c), "In_SNG_WOFI_COFOG": int(c in set(w["REF_AREA"]))}
    if c in wofi.index:
        for k in ["WOFI_share", "WOFI_pctGDP_S13", "WOFI_pctGDP_S13M", "WOFI_pctGDP_S1313", "WOFI_pctGDP_S1312"]:
            r[k] = wofi.loc[c].get(k, np.nan)
    rows.append(r)
co_t = pd.DataFrame(rows)
co_t.to_csv(OUT / "ESM1_TableS4_central_only_in_sngwofi.csv", index=False, encoding="utf-8")
has_sng = co_t.get("WOFI_pctGDP_S13M")
res["central_only"] = {
    "countries": len(co),
    "in_sng_wofi_cofog": int(co_t["In_SNG_WOFI_COFOG"].sum()),
    "with_sng_env_value": int(has_sng.notna().sum()) if has_sng is not None else 0,
    "with_sng_env_value_positive": int((has_sng > 0).sum()) if has_sng is not None else 0,
    "with_sng_env_share": int(co_t.get("WOFI_share", pd.Series(dtype=float)).notna().sum()),
    "detail": co_t[co_t["In_SNG_WOFI_COFOG"] == 1].round(4).replace({np.nan: None}).to_dict(orient="records"),
}

# ---------------------------------------------------------------- gap between subsector sums and GG (COFOG 05)
ov = pd.read_csv(ROOT / "replication/sjiaos/output/table4_overlap.csv", dtype={"DIV": str})
ov = ov[ov["DIV"] == "05"]
ov.to_csv(OUT / "ESM1_TableS2_gap_GG_05.csv", index=False, encoding="utf-8")
res["gap_GG_05"] = ov.drop(columns=["DIV", "Function"]).to_dict(orient="records")

(OUT / "ESM1_results.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k not in ("gap_GG_05",)}, indent=1, default=str))
print(ov.to_string(index=False))
