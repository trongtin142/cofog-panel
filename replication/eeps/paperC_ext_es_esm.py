"""Write the Online Resource section S6 (event study) from the outputs of paperC_ext_es.py."""
import json
import sys
from pathlib import Path

import pandas as pd

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "output"
r = json.loads((out / "es_results.json").read_text(encoding="utf8"))
ev = pd.read_csv(out / "es_events.csv")
names = {}
try:
    tab = pd.read_csv(Path(sys.argv[2])) if len(sys.argv) > 2 else None
    if tab is not None:
        names = dict(zip(tab["ISO3"], tab["Country"]))
        names.update({"BOL": "Bolivia", "NLD": "Netherlands", "GBR": "United Kingdom", "TUR": "Türkiye"})
except Exception:
    pass


def f(x, d=3):
    return f"{x:.{d}f}".replace("-", "−")


def star(p):
    return "" if p is None else "\\*\\*\\*" if p < 0.01 else "\\*\\*" if p < 0.05 else "\\*" if p < 0.1 else ""


def cell(v):
    return f"{f(v['est'])}{star(v['p'])} ({f(v['se'])})"


m, L = r["main"], r["large_reforms"]
rows = [
    ("Share of environmental spending, threshold 1 point", m, "first_stage"),
    ("ln PM2.5, threshold 1 point", m, "reduced_form"),
    ("ln PM2.5, region-by-year effects", m, "reduced_form_region_year"),
    ("ln PM2.5, outcome years 1990–2018", m, "reduced_form_to_2018"),
    ("Share of environmental spending, threshold 2 points", L, "first_stage"),
    ("ln PM2.5, threshold 2 points", L, "reduced_form"),
]
lines = ["| Outcome and specification | Treated countries | All | Baseline GE below 1.0 | Baseline GE 1.0 or above | Difference |",
         "|---|---|---|---|---|---|"]
for lab, blk, key in rows:
    x = blk[key]
    lines.append(f"| {lab} | {x['n_treated_contributing']} | {cell(x['att'])} | {cell(x['att_low'])} | "
                 f"{cell(x['att_high'])} | {cell(x['att_low_minus_high'])} |")

tr = ev[ev["status"] == "treated"].sort_values(["E", "ISO"])
evl = ", ".join(f"{names.get(i, i)} {int(e)}" for i, e in zip(tr["ISO"], tr["E"]))
fs, rf = m["first_stage"], m["reduced_form"]
text = f"""# S6. Regional decentralisation reforms

This section uses reforms of regional government to study changes within countries. Events are increases in the self-rule of regional governments, the authority of a regional tier over its own territory, in the country file of the Regional Authority Index (Hooghe et al. 2016, Shair-Rosenfield et al. 2021, version of April 2021, 1950–2018). The index covers regional tiers with an average population of at least 150,000, so municipal reforms lie outside it. Of the {r['sample_countries']} countries in the estimation sample, {r['rai_countries_in_sample']} are covered. A country is treated in the year of its first increase of at least 1 point between 1996 and 2018, unless another such increase occurred in the five years before. Countries with no change of 1 point or more, up or down, between 1991 and 2018 form the comparison group. This rule gives {m['treated']} treated and {m['never']} comparison countries. The treated countries and event years are {evl}. The design, the outcomes and the decision rule were set down before the estimation.

The estimator is the imputation estimator of Borusyak et al. (2024). Country and year effects are estimated on comparison countries and on treated countries before their event. The difference between the outcome and its imputed value is then averaged over the first eleven years from the event. Standard errors come from 999 bootstrap samples of countries. Two outcomes enter: the subnational share of environmental spending, observed for {m['first_stage_treated']} treated countries before and after their event, and ln PM2.5 exposure, observed from 1990. Baseline effectiveness is the country mean of GE in 1996–1998, and the cut-off of 1.0 is the level at which the marginal association of Table 2, column 3 changes sign.

After the reforms, the environmental share changes by {f(fs['att']['est'])} on average (standard error {f(fs['att']['se'])}, p = {fs['att']['p']:.2f}). In the {fs['n_low']} of these countries with baseline effectiveness below 1.0 it rises by {f(fs['att_low']['est'])} (p = {fs['att_low']['p']:.2f}), and in the other {fs['n_high']} it changes by {f(fs['att_high']['est'])} (p = {fs['att_high']['p']:.2f}). ln PM2.5 exposure changes by {f(rf['att']['est'])} (95% interval {f(rf['att']['ci95'][0])} to {f(rf['att']['ci95'][1])}) in the {rf['n_treated_contributing']} treated countries, by {f(rf['att_low']['est'])} (p = {rf['att_low']['p']:.2f}) in the {rf['n_low']} with baseline effectiveness below 1.0 and by {f(rf['att_high']['est'])} (p = {rf['att_high']['p']:.2f}) in the other {rf['n_high']}. Before the events, the five lead coefficients of ln PM2.5 have a joint p-value of {m['reduced_form_pretrend']['p']:.2f}, and those of the share {m['first_stage_pretrend']['p']:.2f} (test 1 of Borusyak et al. 2024). With a threshold of 2 points, {L['treated']} countries are treated, {L['treated_low_ge']} of them below a baseline effectiveness of 1.0. In the {L['first_stage']['n_low']} of them with data on the share, the share rises by {f(L['first_stage']['att_low']['est'])} (p = {L['first_stage']['att_low']['p']:.2f}) and in all {L['reduced_form']['n_low']} ln PM2.5 changes by {f(L['reduced_form']['att_low']['est'])} (p = {L['reduced_form']['att_low']['p']:.2f}) (Table S8). Region-by-year effects and outcome years up to 2018 change the estimates for ln PM2.5 little.

The reforms move the environmental share by small amounts on average, so the event study speaks to regional authority more than to the share. The changes in PM2.5 exposure after the reforms are small and imprecise, in line with the near-zero within-country coefficients of Section 5.2.

**Table S8** Regional decentralisation reforms: average effects over years 0 to 10 after the event. Imputation estimator, country cluster bootstrap

{chr(10).join(lines)}

*Standard errors from 999 bootstrap samples of countries in parentheses. Treated countries: countries that contribute effects. Difference: below 1.0 minus 1.0 or above. With a threshold of 2 points, the group with baseline GE of 1.0 or above has {L['treated_high_ge']} countries, so its estimate is descriptive. Source of events: Regional Authority Index, country file of April 2021. \\*\\*\\* p < 0.01, \\*\\* p < 0.05, \\* p < 0.1.*

![**Fig. S2** Event-time estimates for the subnational share of environmental spending (left) and ln PM2.5 exposure (right) around increases in the self-rule of regional governments, with 95% confidence intervals. Leads (years −5 to −1) come from the pre-trend test on untreated observations, and years 0 to 10 from the imputation estimator](figures/FigS2.png){{width=100%}}
"""
(out / "esm_section_S6.md").write_text(text, encoding="utf8")
print(text.encode("ascii", "replace").decode())
