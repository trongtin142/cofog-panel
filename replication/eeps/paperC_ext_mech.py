"""
Mechanism test for the environmental-spending study: carbonaceous aerosol emissions by sector (CEDS) and waste
collection (What a Waste).

    python paperC_ext_mech.py [--main PATH_TO_env_federalism.py] [--ext DATA_DIR] [--out OUTPUT_DIR]

DATA_DIR must hold, besides the World Bank files used by the main script:
    ceds/BC_CEDS_estimates_by_country_sector_v_2025_03_18.csv
    ceds/OC_CEDS_estimates_by_country_sector_v_2025_03_18.csv
        from CEDS_v_2025_03_18_aggregate.zip, Zenodo record 15059443 (CC BY 4.0)
    what_a_waste_country_level_data.csv
        World Bank What a Waste Global Database, country_level_data.csv (CC BY 4.0)
Writes mech_results.csv and mech_results.json to OUTPUT_DIR.
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
CEDS_VERSION = "v_2025_03_18"
WASTE = ["5C_Waste-combustion"]
POWER = ["1A1a_Electricity-autoproducer", "1A1a_Electricity-public", "1A1a_Heat-production"]
RHS = ["lnENV", "SUB", "SUBxGE", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]


def load_main(path: Path):
    spec = importlib.util.spec_from_file_location("pc", path)
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)
    return pc


def ceds_emissions(ext: Path) -> pd.DataFrame:
    """BC + OC (ktC) by country and year for the waste-combustion sector and for power plus industry."""
    frames = []
    for sp in ("BC", "OC"):
        d = pd.read_csv(ext / "ceds" / f"{sp}_CEDS_estimates_by_country_sector_{CEDS_VERSION}.csv")
        yrs = [c for c in d.columns if c.startswith("X") and 1995 <= int(c[1:]) <= 2023]
        d = d[["country", "sector"] + yrs].melt(["country", "sector"], var_name="YEAR", value_name="kt")
        d["YEAR"] = d["YEAR"].str[1:].astype(int)
        d["ISO"] = d["country"].str.upper()
        d["sp"] = sp
        frames.append(d)
    d = pd.concat(frames)
    industry = [s for s in d["sector"].unique() if s.startswith(("1A2", "2"))]
    d["group"] = np.select([d["sector"].isin(WASTE), d["sector"].isin(POWER + industry)],
                           ["waste", "placebo"], "other")
    e = d[d["group"] != "other"].pivot_table(index=["ISO", "YEAR"], columns=["group", "sp"], values="kt",
                                              aggfunc="sum")
    e.columns = [f"{g}_{sp}" for g, sp in e.columns]
    for g in ("waste", "placebo"):
        e[f"{g}_BCOC"] = e[f"{g}_BC"] + e[f"{g}_OC"]
    return e.reset_index()


def per_capita_logs(s: pd.DataFrame, e: pd.DataFrame, pop: pd.DataFrame) -> pd.DataFrame:
    """ln kg of carbon per person; zeros become missing and are counted."""
    d = s.merge(e, on=["ISO", "YEAR"], how="left").merge(pop, on=["ISO", "YEAR"], how="left")
    for c in [c for c in e.columns if c not in ("ISO", "YEAR")]:
        pc_ = d[c] * 1e6 / d["POP"]
        d[f"ln_{c}"] = np.log(pc_.where(pc_ > 0))
    return d


def me25(r, ge, b="SUB", bx="SUBxGE"):
    V = r.cov_params()
    m = r.params[b] + r.params[bx] * ge
    se = np.sqrt(V.loc[b, b] + ge ** 2 * V.loc[bx, bx] + 2 * ge * V.loc[b, bx])
    return m, se, 2 * stats.norm.sf(abs(m / se))


def fit(d: pd.DataFrame, y: str):
    f = f"{y} ~ {' + '.join(RHS)} + C(YEAR) + C(SUBREGION)"
    x = d.dropna(subset=[y] + RHS + ["SUBREGION"])
    r = smf.ols(f, data=x).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(x["ISO"])[0]})
    return r, x


def row(name, r, x, ge, linear=False):
    m, se, p = me25(r, ge)
    eff = 0.25 * m if linear else 100 * (np.exp(0.25 * m) - 1)
    return {"Model": name, "N": int(r.nobs), "Countries": x["ISO"].nunique(), "R2": round(r.rsquared, 3),
            "SUB": round(r.params["SUB"], 3), "se_SUB": round(r.bse["SUB"], 3), "p_SUB": round(r.pvalues["SUB"], 3),
            "SUBxGE": round(r.params["SUBxGE"], 3), "se_SUBxGE": round(r.bse["SUBxGE"], 3),
            "p_SUBxGE": round(r.pvalues["SUBxGE"], 3),
            "effect_25pp_at_ge_ref": round(eff, 2), "p_effect": round(p, 4),
            "effect_unit": "percentage points" if linear else "percent"}


def stacked(d: pd.DataFrame, ge: float) -> dict:
    """Waste and placebo outcomes stacked, every coefficient and fixed effect specific to the outcome."""
    x = d.dropna(subset=["ln_waste_BCOC", "ln_placebo_BCOC"] + RHS + ["SUBREGION"]).copy()
    parts = []
    for k, y in enumerate(("ln_waste_BCOC", "ln_placebo_BCOC")):
        z = x[["ISO", "YEAR", "SUBREGION"] + RHS].copy()
        z["Y"], z["D"] = x[y].values, k
        parts.append(z)
    z = pd.concat(parts, ignore_index=True)
    for v in RHS:
        z[f"{v}_w"] = z[v] * (z["D"] == 0)
        z[f"{v}_p"] = z[v] * (z["D"] == 1)
    z["YD"] = z["YEAR"].astype(str) + "_" + z["D"].astype(str)
    z["SRD"] = z["SUBREGION"].astype(str) + "_" + z["D"].astype(str)
    terms = " + ".join(f"{v}_w + {v}_p" for v in RHS)
    r = smf.ols(f"Y ~ {terms} + C(YD) + C(SRD)", data=z).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(z["ISO"])[0]})
    names = list(r.params.index)
    c = np.zeros(len(names))
    c[names.index("SUB_w")], c[names.index("SUBxGE_w")] = 1, ge
    c[names.index("SUB_p")], c[names.index("SUBxGE_p")] = -1, -ge
    t1 = r.t_test(c)
    c2 = np.zeros(len(names))
    c2[names.index("SUBxGE_w")], c2[names.index("SUBxGE_p")] = 1, -1
    t2 = r.t_test(c2)
    return {"N_per_outcome": int(len(x)), "Countries": x["ISO"].nunique(),
            "diff_marginal_at_ge_ref": round(float(t1.effect[0]), 3), "se": round(float(t1.sd[0][0]), 3),
            "p": round(float(t1.pvalue), 4),
            "diff_SUBxGE": round(float(t2.effect[0]), 3), "se_SUBxGE": round(float(t2.sd[0][0]), 3),
            "p_SUBxGE": round(float(t2.pvalue), 4),
            "check_waste_SUB": round(r.params["SUB_w"], 3), "check_placebo_SUB": round(r.params["SUB_p"], 3)}


def waste_collection(s: pd.DataFrame, ext: Path, ge: float) -> list:
    """Exploratory: country means of the estimation sample against What a Waste indicators (cross-section)."""
    w = pd.read_csv(ext / "what_a_waste_country_level_data.csv")
    w = w.rename(columns={"iso3c": "ISO",
                          "waste_collection_coverage_total_percent_of_population": "COLL",
                          "waste_treatment_open_dump_percent": "DUMP"})[["ISO", "COLL", "DUMP"]]
    m = s.groupby("ISO").agg({**{v: "mean" for v in ["SUB", "GE", "lnENV", "lnY", "IND", "URB", "TRADE", "lnDENS"]},
                              "SUBREGION": "first"}).reset_index()
    m["lnY2"] = m["lnY"] ** 2
    m["SUBxGE"] = m["SUB"] * m["GE"]
    m = m.merge(w, on="ISO", how="left")
    out = []
    for y, name in (("COLL", "E1 What a Waste: collection coverage, % of population"),
                    ("DUMP", "E2 What a Waste: open dumping, % of waste")):
        x = m.dropna(subset=[y] + RHS)
        r = smf.ols(f"{y} ~ {' + '.join(RHS)} + C(SUBREGION)", data=x).fit(cov_type="HC1")
        out.append(row(name, r, x, ge, linear=True))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", default=str(HERE / "env_federalism.py"))
    ap.add_argument("--ext", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    pc = load_main(Path(a.main))
    ext = Path(a.ext) if a.ext else pc.EXT
    out = Path(a.out) if a.out else pc.OUT
    out.mkdir(parents=True, exist_ok=True)

    p = pc.build_panel()
    ge = pc.ge_reference(p)["LMIC"]
    s = p[p["COMPLETE_L1"]].dropna(subset=pc.BASE_NEEDED + ["SUB"]).copy()
    s["SUBxGE"] = s["SUB"] * s["GE"]
    pop = pc._wb(pc.EXT / "wb_SP.POP.TOTL.json", "POP")
    d = per_capita_logs(s, ceds_emissions(ext), pop)

    rows, notes = [], {"ge_ref": ge, "sample_obs": len(s), "sample_countries": s["ISO"].nunique()}
    # check: the main specification reproduces Table 2, column 3 on this panel
    r0, x0 = fit(s, "lnPM")
    notes["table2_col3_check"] = {"SUB": round(r0.params["SUB"], 3), "SUBxGE": round(r0.params["SUBxGE"], 3),
                                  "N": int(r0.nobs)}
    for y, name in (("ln_waste_BCOC", "P1 Waste combustion, BC+OC per capita"),
                    ("ln_placebo_BCOC", "P2 Power and industry, BC+OC per capita (placebo)"),
                    ("ln_waste_BC", "E3 Waste combustion, BC per capita"),
                    ("ln_waste_OC", "E3 Waste combustion, OC per capita"),
                    ("ln_placebo_BC", "E3 Power and industry, BC per capita"),
                    ("ln_placebo_OC", "E3 Power and industry, OC per capita")):
        notes[f"zeros_or_missing_{y}"] = int(d[y].isna().sum())
        r, x = fit(d, y)
        rows.append(row(name, r, x, ge))
    notes["P3_stacked"] = stacked(d, ge)
    x = d.dropna(subset=["ln_waste_BCOC"])
    lw = x["ln_waste_BCOC"]
    notes["share_of_variance_between_countries_waste"] = round(
        float(lw.groupby(x["ISO"]).transform("mean").var() / lw.var()), 3)
    rows += waste_collection(s, ext, ge)

    res = pd.DataFrame(rows)
    res.to_csv(out / "mech_results.csv", index=False)
    (out / "mech_results.json").write_text(json.dumps(notes, indent=2), encoding="utf8")
    print(res.to_string(index=False))
    print(json.dumps(notes, indent=2))


if __name__ == "__main__":
    main()
