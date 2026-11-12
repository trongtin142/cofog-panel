"""Environmental-spending study, supplementary material: tables rendered from the replication outputs.

Writes output/esm_tables.md, one block per table, each headed by a line "<!-- key -->". The table
numbers are left as "Table S?" and set when the blocks are placed in the supplementary material.

    python esm_tables.py [OUT_DIR]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "output"
MINUS = "−"
STARS = " \\*\\*\\* p < 0.01, \\*\\* p < 0.05, \\* p < 0.1."


def num(x, d=3):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    s = f"{x:,.{d}f}"
    if s.startswith("-"):
        s = MINUS + s[1:]
        if float(s[1:].replace(",", "")) == 0:
            s = s[1:]
    return s


def star(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return ""
    return "\\*\\*\\*" if p < 0.01 else "\\*\\*" if p < 0.05 else "\\*" if p < 0.1 else ""


def coef(b, se, p, d=3):
    if b is None or (isinstance(b, float) and np.isnan(b)):
        return ""
    return f"{num(b, d)}{star(p)} ({num(se, d)})"


def pct(v, p, d=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    return f"{num(v, d)}{star(p)}"


def n(x):
    return f"{int(x):,}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def jload(name):
    return json.loads((OUT / name).read_text(encoding="utf8"))


blocks = {}
sc = jload("sample_composition.json")
GE_REF = sc["ge_median_by_income"]["LMIC"]
REF = f"GE = {num(GE_REF)}"
ME_COL = f"25 pp at {REF} (%)"

# ------------------------------------------------------------------ SNG-WOFI comparison
cty = pd.read_csv(OUT / "ESM1_TableS1_countries.csv")
names = dict(zip(cty["ISO3"], cty["Country"]))
cmp_ = pd.read_csv(OUT / "ESM1_TableS3_sngwofi_comparison.csv")
both = cmp_[(cmp_["In_sample"] == 1) & cmp_["SUB_2019"].notna() & cmp_["WOFI_share"].notna()].copy()
both["Country"] = both["ISO3"].map(names)
both = both.sort_values("Country")
rows = [[r.ISO3, r.Country, num(r.SUB_2019), num(r.WOFI_share), num(r.SUB_2019 - r.WOFI_share), r.TIER_2019,
         str(int(r.Central_only))] for r in both.itertuples()]
blocks["sngwofi"] = (
    "**Table S?** Subnational share of environmental protection expenditure, 2019: this paper and SNG-WOFI\n\n"
    + table(["ISO3", "Country", "Share, this paper", "Share, SNG-WOFI", "Difference", "Tier", "Central only"], rows)
    + "\n\n*Countries of the estimation sample with both values for 2019. Share, SNG-WOFI: state and local government "
      "expenditure on environmental protection as a fraction of general government expenditure on the same function. "
      "Tier: tier of the IMF value in 2019. Sources: IMF GFS COFOG dataset of 3 February 2026, and OECD Data "
      "Explorer, dataflow OECD.CFE.RDG:DSD_SNG_WOFI@DF_COFOG, version 1.0, accessed 1 November 2026.*")

# ------------------------------------------------------------------ central-only countries in SNG-WOFI
co = pd.read_csv(OUT / "ESM1_TableS4_central_only_in_sngwofi.csv")
co = co[co["In_SNG_WOFI_COFOG"] == 1].sort_values("Country")


def dash(x, d):
    return "–" if pd.isna(x) else num(x, d)


rows = [[r.ISO3, r.Country, dash(r.WOFI_pctGDP_S13, 3), dash(r.WOFI_pctGDP_S13M, 4),
         dash(r.WOFI_share if pd.notna(r.WOFI_share) else (r.WOFI_pctGDP_S13M / r.WOFI_pctGDP_S13
                                                            if pd.notna(r.WOFI_pctGDP_S13M) and r.WOFI_pctGDP_S13 > 0
                                                            and r.WOFI_pctGDP_S13M > 0 else np.nan), 3)]
        for r in co.itertuples()]
blocks["centralonly"] = (
    "**Table S?** Central-only countries in the SNG-WOFI functional data, 2019\n\n"
    + table(["ISO3", "Country", "GG, % of GDP", "State and local, % of GDP", "Subnational share"], rows)
    + f"\n\n*Central-only: countries of the estimation sample in which neither state nor local government reports "
      f"spending on environmental protection in the IMF data in any year. Shown are the {len(co)} of 36 such countries "
      "that appear in the SNG-WOFI functional data. Subnational share: as reported by SNG-WOFI, or the ratio of the "
      "two percentages of GDP where SNG-WOFI gives no share (Côte d'Ivoire). A dash marks a value missing from "
      "SNG-WOFI.*")

# ------------------------------------------------------------------ countries of the estimation sample
rows = [[r.ISO3, r.Country, r.Subregion, f"{r.First_year}–{r.Last_year}", str(r.Obs), str(r.Obs_T1), str(r.Obs_T2),
         str(r.Obs_T3), num(r.Mean_SUB, 2), str(r.Central_only), str(r.Coverage_gap), str(r.Any_GG_series),
         num(r.Mean_GE, 2), num(r.Mean_PM25, 1)] for r in cty.itertuples()]
tot = cty[["Obs", "Obs_T1", "Obs_T2", "Obs_T3"]].sum()
main = cty[cty["In_main_sample"] == 1]
tot_main = main[["Obs", "Obs_T1", "Obs_T2", "Obs_T3"]].sum()
blocks["countries"] = (
    "**Table S?** Countries of the harmonised panel, with the coverage gaps that the estimation sample of Table 2, "
    "column 3, codes as missing\n\n"
    + table(["ISO3", "Country", "Sub-region", "Years", "Obs.", "T1", "T2", "T3", "Mean SUB", "Central only",
             "Coverage gap", "GG series", "Mean GE", "Mean PM2.5"], rows)
    + "\n\n*Years: first and last year in the sample. Obs.: country-years. T1–T3: observations by tier of the lagged "
      "expenditure value. Mean SUB: mean subnational share (t−1). Central only: 1 if neither state nor local "
      "government reports spending on environmental protection in any year. Coverage gap: 1 if, in addition, the COFOG "
      "data cover central government alone for all ten functions in every year, so that the estimation sample codes "
      "the share as missing (it is zero in the column Mean SUB). GG series: 1 if the country reports a GG "
      "value for environmental protection in some year. Mean GE: government effectiveness (WGI). Mean PM2.5: "
      "population-weighted exposure (µg/m³). Countries are ordered by UN region and sub-region. Totals: "
      f"{n(tot.Obs)} observations ({n(tot.Obs_T1)} T1, {n(tot.Obs_T2)} T2, {n(tot.Obs_T3)} T3), {len(cty)} countries, "
      f"{int(cty.Central_only.sum())} of them central-only, {int(cty.Coverage_gap.sum())} coverage gaps, and "
      f"{int((cty.Obs_T1 == 0).sum())} without a T1 value in the sample. Estimation sample of Table 2, column 3: "
      f"{n(tot_main.Obs)} observations ({n(tot_main.Obs_T1)} T1, {n(tot_main.Obs_T2)} T2, {n(tot_main.Obs_T3)} T3) "
      f"in {len(main)} countries.*")

# ------------------------------------------------------------------ binning
b = pd.read_csv(OUT / "r3c_binning.csv")
wald = jload("r3c_results.json")["binning_wald"]
rows = [[str(r.bin), f"{num(r.GE_from, 2)} to {num(r.GE_to, 2)}", num(r.GE_median, 2), n(r.N), str(r.Countries),
         coef(r.bin_me, r.bin_se, r.bin_p), f"{num(r.linear_me)} ({num(r.linear_se)})"] for r in b.itertuples()]
blocks["binning"] = (
    f"**Table S?** Binning estimator of the marginal association of the subnational share, terciles of government "
    f"effectiveness (Hainmueller et al. 2019). N = {n(b.N.sum())}, {sc['countries']} countries\n\n"
    + table(["Tercile", "GE range", "GE median", "N", "Countries", "Binning estimate", "Linear model at the median"],
            rows)
    + "\n\n*Each tercile has its own intercept, coefficient on the subnational share, slope of GE and interaction, "
      "with GE centred at the tercile median, and ln environmental spending, the controls, year and sub-region "
      "effects in common. Countries appear in more than one tercile when their effectiveness changes over time. The "
      "joint Wald test that the three binning estimates equal the linear model at the tercile medians gives "
      f"χ²({wald['wald_df']}) = {wald['wald_bins_equal_linear_chi2']:.2f}, p = {wald['wald_p']:.2f}. "
      "Standard errors clustered by country in parentheses." + STARS + "*")

# ------------------------------------------------------------------ anthropogenic exposure
a = pd.read_csv(OUT / "tab_anthro.csv")
ar = jload("anthro_results.json")
labels = {
    "P1 paper outcome, matched sample": "(1) Panel, total exposure (Table 2, column 3)",
    "P1 anthropogenic PM2.5 (ANTHRO)": "(2) Panel, anthropogenic exposure",
    "P3 controllable PM2.5 (CONTROL)": "(3) Panel, anthropogenic exposure without open fires",
    "P2 cross-section: mean ln WDI PM2.5": "(4) Country means, total exposure (mean over sample years)",
    "P2 cross-section: ln total PM2.5 2017": "(5) Country means, total exposure 2017 (GBD-MAPS)",
    "P2 cross-section: ln ANTHRO 2017": "(6) Country means, anthropogenic exposure 2017",
    "P3 cross-section: ln CONTROL 2017": "(7) Country means, anthropogenic exposure without open fires 2017",
    "P4 exploratory: ln LOCAL 2017": "(8) Country means, residential, commercial, waste and fugitive dust sources 2017",
    "P4 exploratory: ln NATIONAL 2017": "(9) Country means, energy and industry sources 2017"}
rows = []
for _, r in a.iterrows():
    rows.append([labels[r["Model"]], n(r["N"]), str(r["Countries"]), coef(r["SUB"], r["se_SUB"], r["p_SUB"]),
                 coef(r["SUB:GE"], r["se_SUB:GE"], r["p_SUB:GE"]), pct(r["ME25_LMIC"], r["p_ME25_LMIC"])])
p4 = ar["P4_stacked_national_minus_local"]
blocks["anthro"] = (
    "**Table S?** Anthropogenic PM2.5 exposure. Dependent variable: ln PM2.5 exposure as indicated\n\n"
    + table(["Outcome", "N", "Countries", "SUB", "SUB × GE", ME_COL], rows)
    + "\n\n*Rows 1–3: specification of Table 2, column 3, with the outcome multiplied by each country's 2017 share of "
      "exposure from the indicated sources (McDuffie et al. 2021), standard errors clustered by country. Rows 4–9: "
      "one observation per country, regressors are country means over the estimation sample (the interaction is the "
      "product of the means of the share and of GE), outcome as indicated, sub-region effects, HC3 standard errors. "
      "Anthropogenic: all sources except windblown dust and the remaining natural sources, which include sea salt, "
      "biogenic, volcanic, lightning and soil emissions. Without open fires: also excludes wildfires and other open "
      "fires. Rows 8 and 9 are exploratory: the difference between their last-column coefficients is "
      f"{num(p4['me_diff'])} (standard error {num(p4['se'])}, p = {p4['p']:.2f}) in a stacked regression clustered "
      f"by country. Last column: percent change in exposure for a subnational share 25 percentage points higher at "
      f"{REF}, the median GE of low- and middle-income countries." + STARS + "*")

# ------------------------------------------------------------------ PM2.5 source controls and emission outcomes
smap = {"110": "All countries", "74": "Without central-only countries", "GG": "GG values only"}
rows = []
for f in ("r3c_source_controls.csv", "r3c_equal_weights.csv"):
    for _, r in pd.read_csv(OUT / f).iterrows():
        rows.append([smap[str(r["Sample"])], r["Model"], n(r["N"]), str(r["Countries"]),
                     coef(r["SUB"], r["se_SUB"], r["p_SUB"]), coef(r["SUB:GE"], r["se_SUB:GE"], r["p_SUB:GE"]),
                     pct(r["ME25_LMIC"], r["p_ME25_LMIC"])])
for _, r in pd.read_csv(OUT / "r3c_burnt_area.csv").iterrows():
    rows.append(["All countries, 2012–2023", r["Model"], n(r["N"]), str(r["Countries"]),
                 coef(r["SUB"], r["se_SUB"], r["p_SUB"]), coef(r["SUB:GE"], r["se_SUB:GE"], r["p_SUB:GE"]),
                 pct(r["ME25_LMIC"], r["p_ME25_LMIC"])])
for _, r in pd.read_csv(OUT / "r3c_ceds_exploratory.csv").iterrows():
    rows.append(["All countries", f"Outcome: {r['Model']} (exploratory)", n(r["N"]), str(r["Countries"]),
                 coef(r["SUB"], r["se_SUB"], r["p_SUB"]), coef(r["SUB:GE"], r["se_SUB:GE"], r["p_SUB:GE"]),
                 pct(r["ME25_LMIC"], r["p_ME25_LMIC"])])
blocks["sources"] = (
    "**Table S?** Controls for sources of PM2.5, equal country weights and emission outcomes. Specification of "
    "Table 2, column 3\n\n"
    + table(["Sample", "Specification", "N", "Countries", "SUB", "SUB × GE", ME_COL], rows)
    + "\n\n*PM2.5 source controls: access to clean fuels and technologies for cooking (% of population, World Bank "
      "2026, from 2000), electricity production from coal (% of total, World Bank 2026), mean annual temperature and "
      "ln annual precipitation (CRU TS 4.08 country means, Harris et al. 2020), and ln(1 + population-weighted PM2.5 "
      "from open fires) and ln(1 + population-weighted PM2.5 from windblown dust) in 2017 (McDuffie et al. 2021). The "
      "rows marked \"sample with all source controls\" re-estimate the baseline on the observations with every control "
      "available. Equal weight for each country: weighted least squares with weights equal to the inverse of each "
      "country's number of observations. Burnt area: annual area burnt by wildfires from the Global Wildfire "
      "Information System (Our World in Data 2026), available from 2012, entered as ln(1 + burnt area as % of land "
      "area). Emission outcomes (exploratory): emissions per person from the Community Emissions Data System, release "
      "v_2025_03_18 (Hoesly et al. 2018), summed over all sectors for SO2, NOx and NH3, and for residential combustion "
      "(sector 1A4b) for black and organic carbon, with the right-hand side of Table 2, column 3. Standard errors "
      "clustered by country in parentheses." + STARS + "*")

# ------------------------------------------------------------------ other functions
t5 = pd.read_csv(OUT / "tabC5_specificity.csv")
r2 = jload("r2_results.json")
ft = jload("further_tests.json")
ext = jload("extensions.json")


def other(r):
    for v in ("SUBTOT", "SUBTOTN", "SUB08", "SUB09"):
        if pd.notna(r.get(v)):
            return v
    return None


lab5 = ["(1) Baseline, sample with share of total outlays", "(2) Adds share of total outlays",
        "(3) Adds share of total outlays and its GE interaction", "(4) Share of total outlays in place of SUB",
        "(5) Adds share of total outlays net of general transfers, and its GE interaction",
        "(6) Share of recreation, culture and religion in place of SUB", "(7) Share of education in place of SUB",
        "(8) Adds share of education and its GE interaction",
        "(9) Adds share of recreation, culture and religion and its GE interaction"]
rows = []
for i, (_, r) in enumerate(t5.iterrows()):
    v = other(r)
    sub = coef(r["SUB"], r["se_SUB"], r["p_SUB"]) if pd.notna(r["SUB"]) else ""
    sge = coef(r["SUB:GE"], r["se_SUB:GE"], r["p_SUB:GE"]) if pd.notna(r["SUB:GE"]) else ""
    o = coef(r[v], r[f"se_{v}"], r[f"p_{v}"]) if v else ""
    oge = coef(r[f"{v}:GE"], r[f"se_{v}:GE"], r[f"p_{v}:GE"]) if v and pd.notna(r.get(f"{v}:GE")) else ""
    me = pct(r["ME25_SUB"], r["p_ME25_SUB"]) if pd.notna(r["ME25_SUB"]) else ""
    ome = pct(r[f"ME25_{v}"], np.nan) if v and pd.notna(r.get(f"ME25_{v}")) else ""
    rows.append([lab5[i], n(r["N"]), str(r["Countries"]), sub, sge, o, oge, me, ome])
pe = r2["2_placebo_excl_central_only"]


def c2(d, k):
    return coef(d[k]["b"], d[k]["se"], d[k]["p"]) if k in d else ""


def m2(d, k):
    return pct(d[k]["pct"], d[k]["p"]) if k in d else ""


ex = " without countries with central data alone"
rows += [
    ["(10) Baseline, sample with share of recreation, culture and religion," + ex,
     n(pe["a_baseline_sample_SUB08"]["N"]), str(pe["a_baseline_sample_SUB08"]["countries"]),
     c2(pe["a_baseline_sample_SUB08"], "SUB"), c2(pe["a_baseline_sample_SUB08"], "SUB:GE"), "", "",
     m2(pe["a_baseline_sample_SUB08"], "ME25_SUB"), ""],
    ["(11) Share of recreation, culture and religion in place of SUB," + ex, n(pe["b_SUB08_in_place"]["N"]),
     str(pe["b_SUB08_in_place"]["countries"]), "", "", c2(pe["b_SUB08_in_place"], "SUB08"),
     c2(pe["b_SUB08_in_place"], "SUB08:GE"), "", num(pe["b_SUB08_in_place"]["ME25_SUB08"]["pct"], 1)],
    ["(12) Share of education in place of SUB," + ex, n(pe["c_SUB09_in_place"]["N"]),
     str(pe["c_SUB09_in_place"]["countries"]), "", "", c2(pe["c_SUB09_in_place"], "SUB09"),
     c2(pe["c_SUB09_in_place"], "SUB09:GE"), "", num(pe["c_SUB09_in_place"]["ME25_SUB09"]["pct"], 1)],
    ["(13) Adds share of education and its GE interaction," + ex, n(pe["e_SUB_and_SUB09"]["N"]),
     str(pe["e_SUB_and_SUB09"]["countries"]), c2(pe["e_SUB_and_SUB09"], "SUB"), c2(pe["e_SUB_and_SUB09"], "SUB:GE"),
     c2(pe["e_SUB_and_SUB09"], "SUB09"), c2(pe["e_SUB_and_SUB09"], "SUB09:GE"), m2(pe["e_SUB_and_SUB09"], "ME25_SUB"),
     num(pe["e_SUB_and_SUB09"]["ME25_SUB09"]["pct"], 1)],
    ["(14) Adds share of recreation, culture and religion and its GE interaction," + ex,
     n(pe["d_SUB_and_SUB08"]["N"]), str(pe["d_SUB_and_SUB08"]["countries"]), c2(pe["d_SUB_and_SUB08"], "SUB"),
     c2(pe["d_SUB_and_SUB08"], "SUB:GE"), c2(pe["d_SUB_and_SUB08"], "SUB08"), c2(pe["d_SUB_and_SUB08"], "SUB08:GE"),
     m2(pe["d_SUB_and_SUB08"], "ME25_SUB"), num(pe["d_SUB_and_SUB08"]["ME25_SUB08"]["pct"], 1)]]
w8 = ft["wald_SUBxGE_equals_recreation_culture_religionxGE"]
wt, we, wr = (ft["wald_marginal_at_ge_ref_SUB_equals_total_outlays"],
              ft["wald_marginal_at_ge_ref_SUB_equals_education"],
              ft["wald_marginal_at_ge_ref_SUB_equals_recreation_culture_religion"])
e9, d8 = pe["e_SUB_and_SUB09"], pe["d_SUB_and_SUB08"]
blocks["functions"] = (
    "**Table S?** Environmental decentralisation and the decentralisation of total outlays and of other functions. "
    "Dependent variable: ln PM2.5 exposure. Specification of Table 2, column 3\n\n"
    + table(["Specification", "N", "Countries", "SUB", "SUB × GE", "Other share", "Other share × GE",
             f"SUB, {ME_COL}", f"Other share, {ME_COL}"], rows)
    + "\n\n*Other share: subnational share of total government outlays in rows 1–4, of total outlays net of transfers "
      "of a general character between levels of government (COFOG group 01.8) paid by each subsector in row 5, of "
      "spending on recreation, culture and religion (COFOG 08) in rows 6, 9, 10, 11 and 14, and of spending on "
      "education (COFOG 09) in rows 7, 8, 12 and 13. All shares are computed like the environmental share, from "
      "complete values, and enter with a one-year lag. Standard errors clustered by country in parentheses. "
      f"Correlation of the environmental share with the share of total outlays: {ext['corr_sub_subtot_obs']:.2f} "
      f"across observations, {ext['corr_sub_subtot_country_means']:.2f} across country means. In row 9, the "
      f"difference between the two interactions with GE is {num(w8['difference'])} (standard error {num(w8['se'])}, "
      f"p = {w8['p']:.2f}). At {REF}, the coefficient of the environmental share exceeds that of the share of total "
      f"outlays by {num(wt['difference'])} ({num(wt['se'])}, p = {wt['p']:.2f}), of education by "
      f"{num(we['difference'])} ({num(we['se'])}, p = {we['p']:.2f}) and of recreation, culture and religion by "
      f"{num(wr['difference'])} ({num(wr['se'])}, p = {wr['p']:.2f}), each in the model with both shares. Rows 10–14 "
      "exclude the 36 countries in which only central government reports environmental spending. In row 13, the "
      f"coefficient of the environmental share at {REF} exceeds that of the education share by "
      f"{num(e9['wald_ME_SUB_minus_SUB09_at_LMIC_median']['est'])} "
      f"({num(e9['wald_ME_SUB_minus_SUB09_at_LMIC_median']['se'])}, "
      f"p = {e9['wald_ME_SUB_minus_SUB09_at_LMIC_median']['p']:.2f}), and the difference between the two interactions "
      f"with GE is {num(e9['wald_SUBxGE_minus_SUB09xGE']['est'])} ({num(e9['wald_SUBxGE_minus_SUB09xGE']['se'])}, "
      f"p = {e9['wald_SUBxGE_minus_SUB09xGE']['p']:.2f}). In row 14, the corresponding differences with the share of "
      f"recreation, culture and religion are {num(d8['wald_ME_SUB_minus_SUB08_at_LMIC_median']['est'])} "
      f"({num(d8['wald_ME_SUB_minus_SUB08_at_LMIC_median']['se'])}, "
      f"p = {d8['wald_ME_SUB_minus_SUB08_at_LMIC_median']['p']:.2f}) and "
      f"{num(d8['wald_SUBxGE_minus_SUB08xGE']['est'])} ({num(d8['wald_SUBxGE_minus_SUB08xGE']['se'])}, "
      f"p = {d8['wald_SUBxGE_minus_SUB08xGE']['p']:.2f}). Excluding in addition the countries whose share for "
      "education or for recreation, culture and religion is zero by construction leaves rows 11–14 unchanged."
      + STARS + "*")

# ------------------------------------------------------------------ Oster
o = pd.read_csv(OUT / "tabC6_oster.csv")
rows = []
for _, r in o.iterrows():
    tgt = (f"Subnational share at {REF}" if r["Target"].startswith("Marginal") else "SUB × GE")
    var = "Added with the controls" if "among added" in r["Variant"] else "In both regressions"
    rows.append([tgt, var, f"{num(r['beta_short'])} ({num(r['R2_short'])})", f"{num(r['beta_long'])} "
                 f"({num(r['R2_long'])})", num(r["R2_max"]), num(r["beta_at_delta_1"]), num(r["delta_for_beta_0"], 1)])
mind = o.loc[o["Target"].str.startswith("Marginal"), "delta_for_beta_0"].abs().min()
blocks["oster"] = (
    f"**Table S?** Coefficient stability (Oster 2019). Specification of Table 2, column 3, N = {n(o['N'].iloc[0])}, "
    f"{sc['countries']} countries\n\n"
    + table(["Coefficient", "Sub-region effects", "Short regression: coefficient (R²)", "Full model: coefficient (R²)",
             "R²max", "Bias-adjusted coefficient, δ = 1", "δ for a coefficient of zero"], rows)
    + f"\n\n*The short regression contains the subnational share, its interaction with GE (centred at {num(GE_REF)} "
      "for the first two rows), GE and year effects. The full model adds ln environmental spending, the controls of "
      "Table 2 and, in the rows marked \"Added with the controls\", sub-region effects. The other terms are partialled "
      "out of both regressions, and R² refers to the partialled regressions. R²max is 1.3 times the R² of the full "
      "model. δ is the ratio of selection on unobserved to selection on observed variables (Oster 2019), computed with "
      "the exact solution of the estimator. Because adding the observed controls moves both coefficients away from "
      "zero, the bias-adjusted coefficients lie further from zero than the estimates, and a coefficient of zero at "
      f"{REF} would require |δ| of {num(mind, 1)} or more.*")

# ------------------------------------------------------------------ IV
ivmd = (OUT / "tabIV_markdown.md").read_text(encoding="utf8").strip().split("\n")
ivtab = "\n".join(l for l in ivmd if l.startswith("|")).replace("; ", " and ")
ivr = pd.read_csv(OUT / "tabIV_results.csv")
r4 = ivr.iloc[3]
blocks["iv"] = (
    "**Table S?** Instrumental-variable estimates of the association of the subnational share with ln PM2.5 "
    "exposure\n\n" + ivtab
    + "\n\n*Dependent variable: ln PM2.5 exposure. Rows 1–4: controls of Table 2, year and sub-region effects, "
      "standard errors clustered by country. Rows 5–6: country means, controls of Table 2 and sub-region effects, "
      "heteroskedasticity-robust standard errors. First stage: coefficient of the instrument in the regression of the "
      "subnational share. Effective F: cluster-robust first-stage F, equal to the effective F of Montiel Olea and "
      "Pflueger (2013) with a single instrument. In row 4 it is the joint Wald F of the two instruments. AR 95% set: "
      "coefficients not rejected by the Anderson–Rubin test at 5%, on a grid of 0.005. AR set, 25 pp: percent change "
      "in PM2.5 for a share 25 percentage points higher. Conley bounds: union of 95% confidence intervals over direct "
      "effects of a federal constitution on ln PM2.5 between −γ and γ. Row 4: LIML "
      f"{num(r4['b_LIML'])} ({num(r4['se_LIML'])}), Hansen J {r4['HansenJ']:.2f} (p = {r4['HansenJ_p']:.3f}). "
      "Regional Authority Index: country file of April 2021.*")

# ------------------------------------------------------------------ CEDS and What a Waste
m = pd.read_csv(OUT / "mech_results.csv")
mj = jload("mech_results.json")
lab = ["(1) ln BC + OC from waste burning, per capita", "(2) ln BC + OC from power and industry, per capita",
       "(3) ln BC from waste burning, per capita", "(4) ln OC from waste burning, per capita",
       "(5) ln BC from power and industry, per capita", "(6) ln OC from power and industry, per capita",
       "(7) Waste collection coverage, % of population (country means)", "(8) Open dumping, % of waste (country means)"]
rows = []
for i, (_, r) in enumerate(m.iterrows()):
    unit = "%" if r["effect_unit"] == "percent" else " pp"
    rows.append([lab[i], n(r["N"]), str(r["Countries"]), coef(r["SUB"], r["se_SUB"], r["p_SUB"]),
                 coef(r["SUBxGE"], r["se_SUBxGE"], r["p_SUBxGE"]),
                 f"{num(r['effect_25pp_at_ge_ref'], 1)}{unit}{star(r['p_effect'])}"])
st = mj["P3_stacked"]
blocks["ceds"] = (
    "**Table S?** Sector emissions of carbonaceous aerosols and waste collection. Specification of Table 2, "
    "column 3\n\n"
    + table(["Outcome", "N", "Countries", "SUB", "SUB × GE", f"Share, 25 pp at {REF}"], rows)
    + "\n\n*Rows 1–6: emissions of black carbon (BC) and organic carbon (OC), kg of carbon per person, from the "
      "Community Emissions Data System, release v_2025_03_18 (Hoesly et al. 2018), in the year of the outcome. Waste "
      "burning is sector 5C. Power and industry are sectors 1A1a, 1A2 and 2, chosen as a comparison for nationally "
      "regulated sources. CEDS builds waste-burning emissions from the 2010 estimates of Wiedinmyer et al. (2014), "
      "which combine population, urban share, waste generation and the share of waste collected in each country, and "
      f"extends them over time, so {round(100 * mj['share_of_variance_between_countries_waste'])}% of their variance "
      "lies between countries. Country-years with zero waste-burning emissions, mostly European countries whose "
      f"inventories report none, are excluded ({mj['zeros_or_missing_ln_waste_BCOC']} observations). In a stacked "
      f"regression on the {n(st['N_per_outcome'])} observations with both outcomes, the difference between rows 1 "
      f"and 2 in the coefficient of the share at {REF} is {num(st['diff_marginal_at_ge_ref'])} (standard error "
      f"{num(st['se'])}, p = {st['p']:.2f}). Rows 7–8: cross-section of country means over the estimation sample, "
      "What a Waste database (Kaza et al. 2018), UN sub-region effects, heteroskedasticity-robust standard errors. "
      "Last column: percent change (rows 1–6) or percentage-point change (rows 7–8) for a share 25 percentage points "
      f"higher at {REF}. Standard errors clustered by country in parentheses (rows 1–6)." + STARS + "*")

# ------------------------------------------------------------------ diversity of local conditions
d = r2["3_prop2iii"]
rows = []
for key, lab_ in (("primary_ruggedness", "Terrain ruggedness"), ("secondary_ethnic_fractionalisation",
                                                                   "Ethnic fractionalisation")):
    x = d[key]
    rows.append([lab_, n(x["N"]), str(x["countries"]), c2(x, "SUB"), c2(x, "SUB:GE"), c2(x, "SUB:H"),
                 c2(x, "SUB:GE:H"), coef(x["dME_dH_at_GE_1.0"]["est"], x["dME_dH_at_GE_1.0"]["se"],
                                         x["dME_dH_at_GE_1.0"]["p"]),
                 f"{num(x['threshold_at_H_-1SD']['g'], 2)} ({num(x['threshold_at_H_-1SD']['se'], 2)})",
                 f"{num(x['threshold_at_H_+1SD']['g'], 2)} ({num(x['threshold_at_H_+1SD']['se'], 2)})"])
ru, ef = d["primary_ruggedness"], d["secondary_ethnic_fractionalisation"]
blocks["diversity"] = (
    "**Table S?** Diversity of local conditions and the threshold. Dependent variable: ln PM2.5 exposure. "
    "Specification of Table 2, column 3, with H, SUB × H, GE × H and SUB × GE × H added\n\n"
    + table(["Measure of diversity H", "N", "Countries", "SUB", "SUB × GE", "SUB × H", "SUB × GE × H",
             "Derivative of the association with respect to H at GE = 1.0", "Threshold at H = −1 SD",
             "Threshold at H = +1 SD"], rows)
    + "\n\n*H is standardised over the sample countries. The derivative with respect to H at GE = 1.0 is "
      "b(SUB × H) + b(SUB × GE × H). Threshold: the value of GE at which the marginal association is zero, with "
      "delta-method standard errors in parentheses. At the mean of H the thresholds are "
      f"{num(ru['threshold_at_H_+0SD']['g'], 2)} ({num(ru['threshold_at_H_+0SD']['se'], 2)}) and "
      f"{num(ef['threshold_at_H_+0SD']['g'], 2)} ({num(ef['threshold_at_H_+0SD']['se'], 2)}). At {REF} the derivative "
      f"is {num(ru['dME_dH_at_LMIC_median']['est'])} ({num(ru['dME_dH_at_LMIC_median']['se'])}, "
      f"p = {ru['dME_dH_at_LMIC_median']['p']:.2f}) for ruggedness and {num(ef['dME_dH_at_LMIC_median']['est'])} "
      f"({num(ef['dME_dH_at_LMIC_median']['se'])}, p = {ef['dME_dH_at_LMIC_median']['p']:.3f}) for ethnic "
      f"fractionalisation. Ruggedness is missing for {len(d['proxy_missing_ruggedness'])} sample country, "
      f"ethnic fractionalisation for {len(d['proxy_missing_EF'])} countries, most of them small island states. "
      "Standard errors clustered by country in parentheses." + STARS + "*")

# ------------------------------------------------------------------ COFOG groups
g = pd.read_csv(OUT / "tabC7_cofog_groups.csv")
labg = ["(1) Baseline, sample with the share of waste management",
        "(2) Share of waste management (05.1) in place of SUB",
        "(3) Baseline, sample with the share of pollution abatement",
        "(4) Share of pollution abatement (05.3) in place of SUB"]
rows = [[labg[i], n(r["N"]), str(r["Countries"]), coef(r["SUB"], r["se_SUB"], r["p_SUB"]),
         coef(r["SUB:GE"], r["se_SUB:GE"], r["p_SUB:GE"]), pct(r["ME25_LMIC"], r["p_ME25_LMIC"])]
        for i, (_, r) in enumerate(g.iterrows())]
pan = pd.read_csv(OUT / "paperC_panel.csv")
main = pan[pan["COMPLETE_L1"] == True].dropna(subset=["lnPM", "lnENV", "lnY", "IND", "URB", "TRADE", "lnDENS",
                                                        "GE", "SUBREGION", "SUB"])
blocks["groups"] = (
    "**Table S?** Subnational shares of COFOG groups 05.1 and 05.3. Dependent variable: ln PM2.5 exposure. "
    "Specification of Table 2, column 3\n\n"
    + table(["Specification", "N", "Countries", "Share", "Share × GE", f"Share, {ME_COL}"], rows)
    + "\n\n*Rows 1 and 3: the subnational share of the whole division (SUB) on the samples of rows 2 and 4. Group "
      "shares are computed like the environmental share, from complete values, and enter with a one-year lag. About "
      f"three quarters of the observations are from Europe, against a mean GE of {num(main['GE'].mean(), 2)} in the "
      "main sample. Standard errors clustered by country in parentheses. "
      f"All p-values exceed {np.floor(100 * min(g['p_SUB'].min(), g['p_SUB:GE'].min())) / 100:.2f}.*")

# ------------------------------------------------------------------ further variations of Table 2, column 3
t4 = pd.read_csv(OUT / "tabC4_robustness.csv").set_index("Model")
var = pd.read_csv(OUT / "r4_share_variants.csv").set_index("Variant")
infl = r2["4_influence"]
cc_me = ft["cc_row_effect_25pp_at_cc_median_lmic"]
moved = [("GE at start of period in the interaction", "GE at start of period in the interaction"),
         ("Control of corruption in place of GE", "Control of corruption instead of GE"),
         ("Adds natural resource rents", "Adds natural resource rents"),
         ("Adds ln land area, federal indicator and its GE interaction",
          "Adds ln land area, federal indicator and its interaction with GE"),
         ("Five-year averages", "Five-year averages")]
rows = []
for label, key in moved:
    r = t4.loc[key]
    me = (pct(cc_me[0], cc_me[1]) if key.startswith("Control of corruption") else pct(r["ME25_LMIC"], r["p_ME25_LMIC"]))
    rows.append([label, n(r["N"]), str(int(r["Countries"])), coef(r["SUB"], r["se_SUB"], r["p_SUB"]),
                 coef(r["SUB:GE"], r["se_SUB:GE"], r["p_SUB:GE"]), me])
for label, key in (("Reported zeros of state and local government excluded",
                    "B1: reported zeros of state and local government excluded"),
                   ("Consolidated financing share for GG years",
                    "F: consolidated financing share for general government years")):
    r = var.loc[key]
    rows.append([label, n(r["N"]), str(int(r["Countries"])), coef(r["SUB"], r["se_SUB"], r["p_SUB"]),
                 coef(r["SUB:GE"], r["se_SUB:GE"], r["p_SUB:GE"]), pct(r["ME25_LMIC"], r["p_ME25_LMIC"])])
for label, key in (("Without the countries with the largest influence on SUB × GE", "drop_primary_SUBxGE"),
                   ("Without the countries with the largest influence on the last column", "drop_secondary_ME")):
    x = infl[key]
    rows.append([label, n(x["N"]), str(x["countries"]), c2(x, "SUB"), c2(x, "SUB:GE"),
                 m2(x, "ME25_at_LMIC_median")])
lo = pd.read_csv(OUT / "tabC4b_leave_one_out.csv")
inc = sc["income_interaction"]
wb = sc["wild_bootstrap_subregion"]
tw = pd.read_csv(OUT / "tabC3b_twfe.csv").iloc[0]
blocks["further"] = (
    "**Table S?** Further variations of Table 2, column 3. Dependent variable: ln PM2.5 exposure\n\n"
    + table(["Specification", "N", "Countries", "SUB", "SUB × GE", ME_COL], rows)
    + "\n\n*All specifications include ln environmental spending (t−1), GE, the controls of Table 2, and year (period) "
      "and sub-region effects. GE at start of period: GE in the interaction averaged over each country's first three "
      f"sample years. For control of corruption, the last column is evaluated at {num(ft['cc_median_lmic'], 2)}, the "
      "median of low- and middle-income countries on that indicator. Federal countries: the 24 federal countries with "
      f"a chapter in Griffiths et al. (2020), {ext['federal_countries_in_sample']} of them in the sample. Reported "
      "zeros: country-years in which every state and local level that the country reports has a value of zero. "
      "Financing share: one minus central government over general government spending on environmental protection, "
      "a consolidated measure, for T1 values. Influence: countries whose DFBETA for the coefficient indicated exceeds "
      f"2/√{sc['countries']} ({num(infl['threshold'])}) in absolute value, "
      f"{len(infl['drop_primary_SUBxGE']['countries_dropped'])} and "
      f"{len(infl['drop_secondary_ME']['countries_dropped'])} countries. Leaving out one country at a time gives "
      f"SUB × GE between {num(infl['SUBxGE_range'][0])} and {num(infl['SUBxGE_range'][1])} "
      f"(p ≤ {infl['p_SUBxGE_max']:.3f}) and a last column between {num(infl['ME25_range'][0], 1)} and "
      f"{num(infl['ME25_range'][1], 1)} (p ≤ {infl['p_ME_max']:.3f}). Leaving out one of the "
      f"{lo.shape[0]} UN sub-regions at a time gives SUB × GE between {num(lo['SUB:GE'].min())} and "
      f"{num(lo['SUB:GE'].max())} (p ≤ {lo['p_SUB:GE'].max():.3f}) and a last column between "
      f"{num(lo['ME25_LMIC'].min(), 1)} and {num(lo['ME25_LMIC'].max(), 1)} (p ≤ {lo['p_ME25_LMIC'].max():.3f}). "
      f"Adding the interaction of the share with ln GDP per capita gives {num(inc['SUB:lnY'][0])} "
      f"({num(inc['SUB:lnY'][1])}, p = {inc['SUB:lnY'][2]:.2f}) for that interaction and {num(inc['SUB:GE'][0])} "
      f"({num(inc['SUB:GE'][1])}, p = {inc['SUB:GE'][2]:.3f}) for SUB × GE. With inference clustered by sub-region, "
      f"the wild cluster bootstrap p-value of SUB × GE is {wb['p_wild']:.3f} ({wb['clusters']} clusters, "
      f"{n(wb['replications'])} replications). Two-way fixed effects give SUB {coef(tw['SUB'], tw['se_SUB'], tw['p_SUB'])} "
      f"and SUB × GE {coef(tw['SUB:GE'], tw['se_SUB:GE'], tw['p_SUB:GE'])}." + STARS + "*")

text = "\n\n".join(f"<!-- {k} -->\n{v}" for k, v in blocks.items()) + "\n"
(OUT / "esm_tables.md").write_text(text, encoding="utf8")
print("\n".join(blocks))
