"""Markdown table for the supplementary material from the outputs of ext_r3c.py.

    python make_esm_r3c.py OUTPUT_DIR
"""
import sys
from pathlib import Path

import pandas as pd


def stars(p):
    return "\\*\\*\\*" if p < 0.01 else "\\*\\*" if p < 0.05 else "\\*" if p < 0.1 else ""


def cell(b, se, p):
    return f"{b:.3f}{stars(p)} ({se:.3f})".replace("-", "−")


def me(v, p):
    v = 0.0 if abs(v) < 0.05 else v
    return f"{v:.1f}{stars(p)}".replace("-", "−")


def main():
    out = Path(sys.argv[1])
    t = pd.read_csv(out / "r3c_source_controls.csv")
    b = pd.read_csv(out / "r3c_burnt_area.csv")
    w = pd.read_csv(out / "r3c_equal_weights.csv")
    c = pd.read_csv(out / "r3c_ceds_exploratory.csv")
    lab = {"110": "All countries", "74": "Without central-only countries", "GG": "GG values only"}
    lines = ["**Table SX** Controls for sources of PM2.5, equal country weights and emission outcomes. "
             "Specification of Table 2, column 3", "",
             "| Sample | Specification | N | Countries | SUB | SUB × GE | 25 pp at the median GE of LMICs (%) |",
             "|---|---|---|---|---|---|---|"]
    for _, r in pd.concat([t, w]).iterrows():
        lines.append(f"| {lab[r['Sample']]} | {r['Model']} | {r['N']:,} | {r['Countries']} | "
                     f"{cell(r['SUB'], r['se_SUB'], r['p_SUB'])} | {cell(r['SUB:GE'], r['se_SUB:GE'], r['p_SUB:GE'])} | "
                     f"{me(r['ME25_LMIC'], r['p_ME25_LMIC'])} |")
    for _, r in b.iterrows():
        lines.append(f"| All countries, 2012–2023 | {r['Model']} | {r['N']:,} | {r['Countries']} | "
                     f"{cell(r['SUB'], r['se_SUB'], r['p_SUB'])} | {cell(r['SUB:GE'], r['se_SUB:GE'], r['p_SUB:GE'])} | "
                     f"{me(r['ME25_LMIC'], r['p_ME25_LMIC'])} |")
    for _, r in c.iterrows():
        lines.append(f"| All countries | Outcome: {r['Model']} (exploratory) | {r['N']:,} | {r['Countries']} | "
                     f"{cell(r['SUB'], r['se_SUB'], r['p_SUB'])} | {cell(r['SUB:GE'], r['se_SUB:GE'], r['p_SUB:GE'])} | "
                     f"{me(r['ME25_LMIC'], r['p_ME25_LMIC'])} |")
    lines += ["", "*PM2.5 source controls: access to clean fuels and technologies for cooking (% of population, "
              "World Bank 2026, from 2000), electricity production from coal (% of total, World Bank 2026), mean "
              "annual temperature and ln annual precipitation (CRU TS 4.08 country means, Harris et al. 2020), and "
              "ln(1 + population-weighted PM2.5 from open fires) and ln(1 + population-weighted PM2.5 from windblown "
              "dust) in 2017 (McDuffie et al. 2021). The rows marked \"sample with all source controls\" re-estimate "
              "the baseline on the observations with every control available. Equal weight for each country: "
              "weighted least squares with weights equal to the inverse of each country's number of observations. "
              "Burnt area: annual area burnt by wildfires from the Global Wildfire Information System, as published by "
              "Our World in Data, available from 2012, entered as ln(1 + burnt area as % of land area). Emission "
              "outcomes (exploratory): emissions per person from the Community Emissions Data System, release "
              "v_2025_03_18 (Hoesly et al. 2018), summed over all sectors for SO2, NOx and NH3, and for residential "
              "combustion (sector 1A4b) for black and organic carbon, with the right-hand side of Table 2, column 3. "
              "Standard errors clustered by country in parentheses. \\*\\*\\* p < 0.01, \\*\\* p < 0.05, \\* p < 0.1.*",
              ""]
    bn = pd.read_csv(out / "r3c_binning.csv")
    lines += ["**Table SY** Binning estimator of the marginal association of the subnational share, terciles of "
              "government effectiveness (Hainmueller et al. 2019). Specification of Table 2, column 3", "",
              "| Tercile | GE range | GE median | N | Countries | Binning estimate | Linear model at the median |",
              "|---|---|---|---|---|---|---|"]
    for _, r in bn.iterrows():
        lines.append(f"| {int(r['bin'])} | {r['GE_from']:.2f} to {r['GE_to']:.2f} | {r['GE_median']:.2f} | "
                     f"{int(r['N']):,} | {int(r['Countries'])} | {cell(r['bin_me'], r['bin_se'], r['bin_p'])} | "
                     f"{r['linear_me']:.3f} ({r['linear_se']:.3f}) |".replace("-", "−").replace(" to −", " to −"))
    lines += ["", "*Each tercile has its own intercept, coefficient on the subnational share, slope of GE and "
              "interaction, with GE centred at the tercile median, and ln environmental spending, the controls, "
              "year and sub-region effects in common. Countries appear in more than one tercile when their "
              "effectiveness changes over time. The joint Wald test that the three binning estimates equal the "
              "linear model at the tercile medians gives χ²(3) = 5.04, p = 0.17. Standard errors clustered by "
              "country in parentheses. \\*\\*\\* p < 0.01, \\*\\* p < 0.05, \\* p < 0.1.*", ""]
    (out / "esm_r3c.md").write_text("\n".join(lines), encoding="utf8")
    print(f"wrote {out / 'esm_r3c.md'}")


if __name__ == "__main__":
    main()
