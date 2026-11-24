"""Section S11 of the supplementary material (text and Tables S21 to S25) from the outputs of ext_between_within.py.

    python make_esm_between_within.py [OUTPUT_DIR]

Reads bw_results.json, bw_leave_one_country_out.csv and bw_leave_one_subregion_out.csv from OUTPUT_DIR (default
output) and writes esm_section_S11.md there. Every number of the section is formatted from these files.
"""
import json
import math
import sys
from pathlib import Path

import pandas as pd

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "output"
R = json.loads((OUT / "bw_results.json").read_text(encoding="utf8"))
LOC = pd.read_csv(OUT / "bw_leave_one_country_out.csv")
LOS = pd.read_csv(OUT / "bw_leave_one_subregion_out.csv")
MINUS = "−"


def get(path):
    x = R
    for k in path.split("/"):
        x = x[k]
    return x


def num(v, d):
    s = f"{v:,.{d}f}"
    return s.replace("-", MINUS)


def pval(p):
    if p < 0.001:
        return "< 0.001"
    return f"{p:.3f}" if p < 0.1 else f"{p:.2f}"


def p_eq(p):
    return "p < 0.001" if p < 0.001 else f"p = {pval(p)}"


def stars(p):
    return "\\*\\*\\*" if p < 0.01 else "\\*\\*" if p < 0.05 else "\\*" if p < 0.1 else ""


def coef(t):
    return f"{num(t['estimate'], 3)}{stars(t['p'])} ({num(t['se'], 3)})"


def eff(t):
    return num(t["effect25_pct"], 1)


def eff_st(t):
    return f"{num(t['effect25_pct'], 1)}{stars(t['p'])}"


def ci(t):
    return f"{num(t['effect25_lo'], 1)} to {num(t['effect25_hi'], 1)}"


def rng(series, d):
    lo, hi = num(series.min(), d), num(series.max(), d)
    return lo if lo == hi else f"{lo} to {hi}"


def row(*cells):
    return "| " + " | ".join(cells) + " |"


def term(sec, model, name):
    return get(f"{sec}/{model}/terms/{name}")


def nc(sec, model):
    m = get(f"{sec}/{model}")
    return f"{m['N']:,}", str(m["countries"])


# ------------------------------------------------------------------------------------------------ Table S21
im = "income_moderator"
info = get(f"{im}/info")
gp = get("ge_percentiles/info/ge_values")
pc = "ge_percentiles"
hic = get("ge_percentiles/info/ge_hic_median")
mt = get("moderator_tests")
t21 = ["**Table S21** Government effectiveness or income (ln GDP per capita) as the moderator, and the association at "
       "percentiles of effectiveness. Specification of Table 2, column 3, and of Table 3 of the paper, N = 1,352, "
       "76 countries. Dependent variable: ln PM2.5 exposure", "",
       row("Model or point of GE", "SUB × GE", "SUB × ln GDP per capita", "25 pp (%)"), row("---", "---", "---", "---"),
       row("*A. Moderators*", "", "", "")]
A = [("Pooled, GE (Table 2, column 3)", "baseline_centred", "SUB", "SUB:GEc", None),
     ("Pooled, ln GDP per capita in place of GE", "income_in_place_of_ge", "SUB", None, "SUB:lnYc"),
     ("Pooled, both interactions", "both_interactions", "SUB", "SUB:GEc", "SUB:lnYc"),
     ("Between countries, GE (Table 3)", "mundlak_ge_only", "SUB_m", "SUB_m:GE_mc", None),
     ("Between countries, ln GDP per capita in place of GE", "mundlak_income_only", "SUB_m", None, "SUB_m:lnY_mc"),
     ("Between countries, both interactions", "mundlak_both", "SUB_m", "SUB_m:GE_mc", "SUB_m:lnY_mc"),
     ("Within countries, GE (Table 3)", "mundlak_ge_only", "SUB_w", "SUB_w:GE_mc", None),
     ("Within countries, ln GDP per capita in place of GE", "mundlak_income_only", "SUB_w", None, "SUB_w:lnY_mc"),
     ("Within countries, both interactions", "mundlak_both", "SUB_w", "SUB_w:GE_mc", "SUB_w:lnY_mc")]
for label, model, main, g, y in A:
    t21.append(row(label, coef(term(im, model, g)) if g else "", coef(term(im, model, y)) if y else "",
                   eff_st(term(im, model, main))))
t21.append(row("*B. Association at percentiles of GE*", "", "", ""))
B = [("Pooled, 10th percentile of observations", "baseline", "slope_at_obs_P10", "obs_P10"),
     ("Pooled, reference value", "baseline", "slope_at_ref", "ref"),
     ("Pooled, 25th percentile of observations", "baseline", "slope_at_obs_P25", "obs_P25"),
     ("Pooled, median of observations", "baseline", "slope_at_obs_P50", "obs_P50"),
     ("Pooled, 10th percentile of country means", "baseline", "slope_at_country_P10", "country_P10"),
     ("Pooled, 25th percentile of country means", "baseline", "slope_at_country_P25", "country_P25"),
     ("Pooled, median of country means", "baseline", "slope_at_country_P50", "country_P50"),
     ("Pooled, median of high-income countries", "baseline", "slope_at_hic_median", "hic"),
     ("Between countries, 10th percentile of country means", "mundlak_between", "slope_at_country_P10", "country_P10"),
     ("Between countries, reference value", "mundlak_between", "slope_at_ref", "ref"),
     ("Between countries, 25th percentile of country means", "mundlak_between", "slope_at_country_P25",
      "country_P25"),
     ("Between countries, median of country means", "mundlak_between", "slope_at_country_P50", "country_P50"),
     ("Between countries, median of high-income countries", "mundlak_between", "slope_at_hic_median", "hic")]
gp_all = {**gp, "hic": hic}
for label, model, name, g in B:
    t = term(pc, model, name)
    t21.append(row(f"{label} (GE {num(gp_all[g], 2 if g != 'ref' else 3)})", "", "", f"{eff_st(t)} ({ci(t)})"))
within_pts = [term(pc, "mundlak_within", n)["effect25_pct"] for n in
              ("slope_at_country_P10", "slope_at_ref", "slope_at_country_P25", "slope_at_country_P50",
               "slope_at_hic_median")]
psd, msd = get(f"{im}/both_interactions_per_sd/terms"), get(f"{im}/mundlak_both_per_sd/terms")
mp, mb = mt["both_interactions"], mt["mundlak_both"]
t21 += ["", f"*25 pp: percentage change in PM2.5 exposure for a share 25 percentage points higher, in panel A at "
            f"GE = −0.355 and at the median ln GDP per capita of low- and middle-income countries in the harmonised "
            f"panel of 108 countries ({num(info['median_lnY_lmic_panel108'], 2)}), at which both moderators are "
            f"centred, and in panel B at the GE value of the row, with the 95% confidence interval in parentheses. "
            f"Between and within countries: the components of the correlated random effects model of Table 3, with "
            f"the interactions formed with the country means of the moderators. Per standard deviation of the "
            f"country means ({num(info['sd_country_mean_GE'], 2)} for GE and {num(info['sd_country_mean_lnY'], 2)} "
            f"for ln GDP per capita), the interactions of the models with both moderators are "
            f"{num(psd['SUB:GEc']['estimate'], 3)} and {num(psd['SUB:lnYc']['estimate'], 3)} (pooled) and "
            f"{num(msd['SUB_m:GE_mc']['estimate'], 3)} and {num(msd['SUB_m:lnY_mc']['estimate'], 3)} (between "
            f"countries). The country means of GE and ln GDP per capita correlate at "
            f"{num(info['corr_country_means_GE_lnY'], 2)}. In the models with both moderators, the two interactions "
            f"correlate at {num(mp['corr_interactions'], 2)} across observations (pooled) and at "
            f"{num(mb['corr_interactions'], 2)} (between countries). Their variance inflation factors are "
            f"{num(mp['vif']['SUB:GEc'], 0)} for SUB × GE and {num(mp['vif']['SUB:lnYc'], 0)} for SUB × ln GDP per "
            f"capita (pooled), and {num(mb['vif']['SUB_m:GE_mc'], 0)} and {num(mb['vif']['SUB_m:lnY_mc'], 0)} "
            f"(between countries). A joint "
            f"Wald test of the two interactions gives {p_eq(mp['wald_both_interactions']['p'])} (pooled) and "
            f"{p_eq(mb['wald_both_interactions']['p'])} (between countries). At the GE values of panel B, the "
            f"within-country association is {num(min(within_pts), 1)}% to {num(max(within_pts), 1)}%. Standard errors "
            f"clustered by country. \\*\\*\\* p < 0.01, \\*\\* p < 0.05, \\* p < 0.1.*"]

# ------------------------------------------------------------------------------------------------ Table S22
hdr = row("Model", "N", "Countries", "SUB × GE", "25 pp at GE = −0.355 (%)", "95% CI", "p")
sep = row("---", "---", "---", "---", "---", "---", "---")


def line(label, sec, model, slope, inter=None):
    n, c = nc(sec, model)
    t = term(sec, model, slope)
    i = get(inter) if inter and "/" in inter else term(sec, model, inter) if inter else None
    return row(label, n, c, coef(i) if i else "", eff(t), ci(t), pval(t["p"]))


lr, rc, fy, be, rec = ("long_run_within", "reporting_changes", "first_year_share", "between_estimators",
                       "recording")
t22 = ["**Table S22** Between and within countries: estimators of the between-country association, longer "
       "differences, changes in reporting and the share of the first sample year. Dependent variable: ln PM2.5 "
       "exposure", "", hdr, sep, row("*A. Between countries*", "", "", "", "", "", ""),
       line("Correlated random effects, between component (Table 3)", be, "mundlak", "between_slope_at_ref",
            "SUBGE_m"),
       line("Country means, equal weights", be, "country_means", "slope_at_ref", "SUB:GE"),
       line("Country means, weighted by observations", be, "country_means_weighted", "slope_at_ref", "SUB:GE"),
       row("*B. Within countries*", "", "", "", "", "", ""),
       line("Correlated random effects, within component (Table 3)", be, "mundlak", "within_slope_at_ref",
            f"{im}/mundlak_ge_only/terms/SUB_w:GE_mc"),
       line("Two-way fixed effects", lr, "annual_twfe", "slope_at_ref", "SUB:GE"),
       line("Same, without SUB × GE", lr, "annual_twfe_no_interaction", "SUB"),
       line("Five-year averages, country and period effects", lr, "five_year_country_effects", "slope_at_ref",
            "SUB:GE"),
       line("Same, without SUB × GE", lr, "five_year_country_effects_no_interaction", "SUB"),
       line("Ten-year differences", lr, "ten_year_differences", "slope_at_ref", "dSUBxGE"),
       line("Same, without SUB × GE", lr, "ten_year_differences_no_interaction", "dSUB"),
       line("Five-year averages, SUB × country-mean GE, country and period effects", lr,
            "five_year_country_effects_mean_ge", "slope_at_ref", "SUBGEm"),
       line("Ten-year differences, change of SUB × country-mean GE", lr, "ten_year_differences_mean_ge",
            "slope_at_ref", "dSUBGEm"),
       line("Same, the two windows ending in 2013 and 2023", lr, "ten_year_nonoverlapping_mean_ge", "slope_at_ref",
            "dSUBGEm"),
       line("Same, all windows, with country effects", lr, "ten_year_country_effects_mean_ge", "slope_at_ref",
            "dSUBGEm"),
       line("Two-way fixed effects, without the years of a change in reporting", rc, "without_change_years_twfe",
            "slope_at_ref", "SUB:GE"),
       line("Same, without SUB × GE", rc, "without_change_years_twfe_no_interaction", "SUB"),
       line("Effects for each country and spell of unchanged reporting", rc, "spell_effects", "slope_at_ref",
            "SUB:GE"),
       line("Same, without SUB × GE", rc, "spell_effects_no_interaction", "SUB"),
       row("*C. Share of the first sample year in place of the current share*", "", "", "", "", "", ""),
       line("All sample years", fy, "all_years", "slope_at_ref", "SUB:GE"),
       line("From the fourth sample year", fy, "from_fourth_sample_year", "slope_at_ref", "SUB:GE"),
       line("Ten or more years after the first sample year", fy, "ten_or_more_years_after_first", "slope_at_ref",
            "SUB:GE"),
       line("From the fourth sample year, GE of the first sample year as the moderator", fy,
            "first_year_share_and_ge", "slope_at_ref", "SUB0:GE0"),
       line("Same, with ln PM2.5 exposure of the first sample year", fy, "first_year_share_and_ge_first_year_pm",
            "slope_at_ref", "SUB0:GE0"),
       line("Same years, country means on values of the first sample year", fy, "cross_section_later_means",
            "slope_at_ref", "SUB0:GE0"),
       row("*D. Within countries, without the years of a change in reporting*", "", "", "", "", "", ""),
       line("Correlated random effects, within component (Table 3)", rec, "mundlak_without_change_years",
            "within_slope_at_ref"),
       line("Five-year averages, SUB × country-mean GE", rec, "five_year_without_change_years",
            "within_slope_at_ref"),
       line("Ten-year differences, change of SUB × country-mean GE", rec, "ten_year_without_change_years",
            "within_slope_at_ref"),
       row("*E. Within countries, also without reversed jumps of the share*", "", "", "", "", "", ""),
       line("Correlated random effects, within component (Table 3)", rec,
            "mundlak_without_change_years_and_reversed_jumps", "within_slope_at_ref"),
       line("Two-way fixed effects", rec, "twfe_without_change_years_and_reversed_jumps", "within_slope_at_ref"),
       line("Five-year averages, SUB × country-mean GE", rec, "five_year_without_change_years_and_reversed_jumps",
            "within_slope_at_ref"),
       line("Ten-year differences, change of SUB × country-mean GE", rec,
            "ten_year_without_change_years_and_reversed_jumps", "within_slope_at_ref")]
li, ri, rci = get(f"{lr}/info"), get(f"{rc}/info"), get(f"{rec}/info")
wb = term(be, "mundlak", "within_slope_at_ref")
rise = rci["change_in_full_sample_se"]
rise_c = [v for k, v in rise.items() if not k.endswith("reversed_jumps")]
rise_d = [v for k, v in rise.items() if k.endswith("reversed_jumps")]
nov = li["nonoverlapping_pairs_by_end_year"]
n_big, n_big_in = rci["share_changes_above_0.2"], rci["share_changes_above_0.2_in_change_years"]
big_in_change = (f"The {n_big} year-to-year changes of the share larger than 0.2 (Table S5) all fall outside these "
                 f"country-years." if n_big_in == 0 else
                 f"Of the {n_big} year-to-year changes of the share larger than 0.2 (Table S5), {n_big_in} fall in "
                 f"these country-years.")
t22 += ["", f"*25 pp at GE = −0.355: percentage change in PM2.5 exposure for a share 25 percentage points higher at "
            f"the reference value of GE, or for the share coefficient in the rows without SUB × GE. Panel A: the "
            f"between component of Table 3, and regressions of the country means of ln PM2.5 exposure on the country "
            f"means of the regressors of Table 2, column 3, with sub-region effects and heteroskedasticity-robust "
            f"standard errors (HC1). Panel B: the within component of Table 3 ({p_eq(wb['p'])}), two-way fixed "
            f"effects on annual data (country and year effects), five-year averages with country and period effects "
            f"({li['five_year_cells']} country-periods, {li['five_year_countries_with_2plus_periods']} countries with "
            f"two or more periods), and ten-year differences of all variables with year effects "
            f"({li['ten_year_pairs']} pairs). The standard deviation of the ten-year change of the share is "
            f"{num(li['sd_ten_year_change_share'], 2)}, against {num(li['sd_annual_within_share'], 2)} for annual "
            f"deviations from the country mean. In the rows with SUB × country-mean GE, the share interacts with the "
            f"mean GE of the country in the main sample, as in the within component of Table 3. The column SUB × "
            f"GE then gives that interaction. The two ten-year windows ending in 2013 and 2023 hold "
            f"{nov['2013'] + nov['2023']} pairs. In {ri['countries_with_change_year']} countries, "
            f"{ri['change_years']} country-years change the tier or the subsectors that report COFOG division 05, and "
            f"the spell effects give each of the {ri['spells']} spells of unchanged reporting its own effect "
            f"({ri['countries_with_2plus_spells']} countries have two or more spells). {big_in_change} Panel C: the "
            f"specification of Table 2, column 3, with the share of each "
            f"country's first sample year in every year. The next two rows use the share and GE of the first sample "
            f"year (SUB × GE is their product), with current GE as a control. The last row is a cross-section of the "
            f"country means of ln PM2.5 exposure over the same years on the share, GE and the regressors of the first sample year, with "
            f"sub-region effects and HC3 standard errors. Panel D leaves out the country-years of a change in "
            f"reporting, and the five-year periods and ten-year windows that contain one. Panel E also leaves out "
            f"the {rci['share_changes_above_0.2_reversed_within_2_years']} reversed jumps "
            f"({rci['reversed_jump_years']} country-years in {rci['countries_with_reversed_jump']} countries, from the "
            f"jump to the year before the opposite change). A reversed jump is a change of the share larger than 0.2 "
            f"that a change of more than 0.1 in the opposite direction follows within two sample years. Against the same estimator on all observations, the "
            f"association changes by {num(min(rise_c), 2)} to {num(max(rise_c), 2)} standard errors in panel D and in the "
            f"two-way fixed effects row of panel B. In panel E, it changes by {num(min(rise_d), 2)} to {num(max(rise_d), 2)}. "
            f"Standard errors clustered by country unless stated. \\*\\*\\* p < 0.01, \\*\\* p < 0.05, \\* p < 0.1.*"]

# ------------------------------------------------------------------------------------------------ Table S23
inf, ps = "influence", "post_socialist"
loc_info = get(f"{inf}/info/leave_one_country_out")


def eff_row(label, sec, model, slope, inter=None):
    n, c = nc(sec, model)
    t = term(sec, model, slope)
    return row(label, n, c, coef(term(sec, model, inter)) if inter else "", eff(t), ci(t), pval(t["p"]))


tk = "influence_top_k"


def topk(tag, prefix):
    """The deletions of the k = 1 to 5 most influential countries: N, countries, interaction, association, p."""
    ms = [get(f"{tk}/without_top{k}_{tag}") for k in range(1, 6)]
    inter = "pooled_SUB:GE" if prefix == "pooled" else "between_SUBGE_m"
    return pd.DataFrame({"N": [m["N"] for m in ms], "countries": [m["countries"] for m in ms],
                         "inter": [m["terms"][inter]["estimate"] for m in ms],
                         "eff": [m["terms"][f"{prefix}_slope_at_ref"]["effect25_pct"] for m in ms],
                         "p": [m["terms"][f"{prefix}_slope_at_ref"]["p"] for m in ms],
                         "p_sub_m": [m["terms"]["between_SUB_m"]["p"] for m in ms]})


TKP, TKB = topk("pooled_ranking", "pooled"), topk("between_ranking", "between")


def pmax(series):
    """Largest p-value, rounded up so that the printed bound holds."""
    m = float(series.max())
    if m < 0.001:
        return "< 0.001"
    return f"≤ {math.ceil(m * 1000) / 1000:.3f}" if m < 0.1 else f"≤ {math.ceil(m * 100) / 100:.2f}"


def num_unsigned_zero(v, d):
    """As num(), without a sign on a value that is zero at the printed precision."""
    s = num(v, d)
    return s[1:] if s.startswith(MINUS) and float(s[1:].replace(",", "")) == 0 else s


t23 = ["**Table S23** Influence of single countries and sub-regions, and the post-socialist group. Specification of "
       "Table 2, column 3 (pooled) and of Table 3 (between countries). Dependent variable: ln PM2.5 exposure", "",
       row("Sample or model", "N", "Countries", "SUB × GE", "25 pp (%)", "95% CI", "p"), sep,
       row("*A. Countries and sub-regions left out*", "", "", "", "", "", ""),
       row(f"One country at a time, between countries ({loc_info['runs']} runs)", rng(LOC["N"], 0),
           rng(LOC["countries"], 0), rng(LOC["between_SUBGE_m"], 3), rng(LOC["between_effect25_at_ref"], 1), "",
           f"≤ {LOC['between_p_slope_at_ref'].max():.3f}"),
       row(f"One country at a time, pooled ({loc_info['runs']} runs)", rng(LOC["N"], 0), rng(LOC["countries"], 0),
           rng(LOC["pooled_SUBxGE"], 3), rng(LOC["pooled_effect25_at_ref"], 1), "",
           "< 0.001" if LOC["pooled_p_slope_at_ref"].max() < 0.001 else f"≤ {LOC['pooled_p_slope_at_ref'].max():.3f}"),
       row(f"One sub-region at a time, between countries ({len(LOS)} runs)", rng(LOS["N"], 0),
           rng(LOS["countries"], 0), rng(LOS["between_SUBGE_m"], 3), rng(LOS["between_effect25_at_ref"], 1), "",
           f"≤ {LOS['between_p_slope_at_ref'].max():.2f}"),
       row("Without the k = 1 to 5 countries that move the pooled association most, pooled",
           rng(TKP["N"], 0), rng(TKP["countries"], 0), rng(TKP["inter"], 3), rng(TKP["eff"], 1), "", pmax(TKP["p"])),
       row("Without the k = 1 to 5 countries that move the between-country association most, between countries",
           rng(TKB["N"], 0), rng(TKB["countries"], 0), rng(TKB["inter"], 3), rng(TKB["eff"], 1), "", pmax(TKB["p"])),
       eff_row("Without Russia and Ukraine, pooled", inf, "without_RUS_UKR", "pooled_slope_at_ref", "pooled_SUB:GE"),
       eff_row("Without Russia and Ukraine, between countries", inf, "without_RUS_UKR", "between_slope_at_ref",
               "between_SUBGE_m"),
       eff_row("Without the nine post-socialist countries below the reference value, pooled", inf,
               "without_postsocialist_below_ref", "pooled_slope_at_ref", "pooled_SUB:GE"),
       eff_row("Same, between countries", inf, "without_postsocialist_below_ref", "between_slope_at_ref",
               "between_SUBGE_m"),
       eff_row("Without the 16 countries below the reference value, pooled", inf, "without_all_below_ref",
               "pooled_slope_at_ref", "pooled_SUB:GE"),
       eff_row("Same, between countries", inf, "without_all_below_ref", "between_slope_at_ref", "between_SUBGE_m"),
       row("*B. Post-socialist group*", "", "", "", "", "", ""),
       eff_row("All countries, with SUB × post-socialist: other countries", ps, "interaction_with_group",
               "slope_at_ref_other", "SUB:GE"),
       eff_row("Same: post-socialist countries", ps, "interaction_with_group", "slope_at_ref_group"),
       eff_row("All countries, also with GE × post-socialist: other countries", ps, "interaction_with_group_and_ge",
               "slope_at_ref_other", "SUB:GE"),
       eff_row("Same: post-socialist countries", ps, "interaction_with_group_and_ge", "slope_at_ref_group"),
       eff_row("Post-socialist countries only", ps, "group_only_no_interaction", "SUB"),
       eff_row("Post-socialist countries only, with SUB × GE", ps, "group_only_with_interaction", "slope_at_ref",
               "SUB:GE"),
       eff_row("Post-socialist countries only, within component", ps, "group_only_mundlak", "SUB_w"),
       eff_row("Post-socialist countries only, between component", ps, "group_only_mundlak", "SUB_m"),
       eff_row("Other countries only", ps, "other_only_no_interaction", "SUB"),
       eff_row("Other countries only, within component", ps, "other_only_mundlak", "SUB_w"),
       eff_row("Other countries only, between component", ps, "other_only_mundlak", "SUB_m")]
sb, sa = get(f"{inf}/info/support_below_ref"), get(f"{inf}/info/support_above_ref")
sps, ind = term(ps, "interaction_with_group", "SUB:PS"), term(ps, "interaction_with_group", "PS")
w1, w2 = get(f"{ps}/group_only_no_interaction/wild_SUB"), get(f"{ps}/group_only_mundlak/wild_SUB_m")
r1 = get(f"{ps}/group_only_no_interaction/wild_rademacher_SUB")
r2 = get(f"{ps}/group_only_with_interaction/wild_rademacher_SUB")
r3 = get(f"{ps}/group_only_mundlak/wild_rademacher_SUB_m")
gps, gge = term(ps, "interaction_with_group_and_ge", "SUB:PS"), term(ps, "interaction_with_group_and_ge", "GE:PS")
shift = loc_info["largest_shift_between"]


def names_list(xs):
    return ", ".join(xs[:-1]) + " and " + xs[-1]


top_p, top_b = get(f"{tk}/info/top5_pooled_ranking"), get(f"{tk}/info/top5_between_ranking")
t23 += ["", f"*25 pp: percentage change in PM2.5 exposure for a share 25 percentage points higher at GE = −0.355 in "
            f"the models with SUB × GE, otherwise for the share coefficient. Panel A: ranges over the runs, with the "
            f"largest p-value of the association. The largest change of the between-country slope at the reference "
            f"value, {num(shift['shift_in_full_se'], 2)} standard errors of the full sample, comes from leaving out "
            f"one country. The k most influential countries are those whose single deletion changes the association "
            f"at the reference value most. They are left out together in the order {names_list(top_p)} (pooled) and "
            f"{names_list(top_b)} (between countries). Table S25 gives the distributions over the single "
            f"deletions. The 16 countries whose mean GE lies below the reference value have a mean share of "
            f"{num(sb['mean_share'], 2)} ({num(sb['min_share'], 2)} to {num(sb['max_share'], 2)}), and the "
            f"{sa['countries']} others {num(sa['mean_share'], 2)} ({num(sa['min_share'], 2)} to "
            f"{num(sa['max_share'], 2)}). Panel B: the 25 post-socialist countries of Table S9, note "
            f"({get(f'{ps}/info/obs_in_group')} observations). With SUB × post-socialist and the post-socialist "
            f"indicator in the model of all countries, the interaction is {coef(sps)} ({p_eq(sps['p'])}) and the "
            f"indicator {coef(ind)}. With GE × post-socialist added as well, SUB × post-socialist is {coef(gps)} "
            f"({p_eq(gps['p'])}) and GE × post-socialist {coef(gge)} ({p_eq(gge['p'])}). Within and between "
            f"components: the correlated random effects model of Table 3 without SUB × GE. Wild cluster bootstrap "
            f"p-values (null imposed, {w1['clusters']} clusters), with Webb weights and {w1['replications']:,} "
            f"replications: {pval(w1['p_wild'])} for the post-socialist countries only and {pval(w2['p_wild'])} for "
            f"their between component. With Rademacher weights and {r1['replications']:,} replications: "
            f"{pval(r1['p_wild'])}, {pval(r2['p_wild'])} at the reference value with SUB × GE, and "
            f"{pval(r3['p_wild'])} for the between component. Standard errors clustered by country. "
            f"\\*\\*\\* p < 0.01, \\*\\* p < 0.05, \\* p < 0.1.*"]

# ------------------------------------------------------------------------------------------------ Table S24
ov = "overlap"
ovi = get(f"{ov}/info")
LABEL = {"SUB": "Subnational share (SUB)", "lnY": "ln GDP per capita", "IND": "Industry (% of GDP)",
         "URB": "Urban population (%)", "TRADE": "Trade (% of GDP)", "lnDENS": "ln population density"}
t24 = ["**Table S24** Overlap between weak and strong government effectiveness: observations below and above the "
       "reference value (panel A) and the lowest and highest thirds of country-mean GE (panel B). Main sample of "
       "Table 2, column 3", "",
       row("Variable or bin of SUB", "Weak", "Strong", "SD, weak", "SD, strong", "Normalised difference",
           "Log ratio of SD", "Weak inside the range of strong", "Strong inside the range of weak"),
       row(*["---"] * 9)]
for lab, key in [("*A. GE below −0.355 (weak) and at or above it (strong)*", "obs_below_ref"),
                 ("*B. Lowest (weak) and highest (strong) third of country-mean GE*", "country_thirds")]:
    g = ovi[key]
    t24.append(row(lab, f"{g['weak']['obs']:,} obs., {g['weak']['countries']} countries",
                   f"{g['strong']['obs']:,} obs., {g['strong']['countries']} countries", *[""] * 6))
    for v, x in g["variables"].items():
        t24.append(row(LABEL[v], num(x["mean_weak"], 2), num(x["mean_strong"], 2), num(x["sd_weak"], 2),
                       num(x["sd_strong"], 2), num(x["normalised_difference"], 2), num_unsigned_zero(x["log_sd_ratio"], 2),
                       num(x["weak_inside_strong_range"], 2), num(x["strong_inside_weak_range"], 2)))
    for b, x in g["share_bins"].items():
        t24.append(row(f"Share of observations with SUB {'= 0' if b == '0' else 'in ' + b}", num(x["weak"], 2),
                       num(x["strong"], 2), *[""] * 6))
csi = ovi["common_support"]
cs_s, cs_i = term(ov, "common_support", "slope_at_ref"), term(ov, "common_support", "SUB:GE")
base_ref = term(inf, "full_pooled", "slope_at_ref")
t24 += ["", f"*Weak and strong: means, or for the bins of SUB the share of the group's observations. Normalised "
            f"difference: difference of the means over the square root of the mean of the two variances. Range: the "
            f"2.5th to 97.5th percentiles of the other group. In panel A, {ovi['obs_below_ref']['weak_countries_mean_share_above_0.25']} "
            f"of the {ovi['obs_below_ref']['weak']['countries']} countries with observations below the reference value "
            f"have a mean share above 0.25 in those observations. In panel B, "
            f"{ovi['country_thirds']['weak_countries_mean_share_above_0.25']} of the "
            f"{ovi['country_thirds']['weak']['countries']} countries of the lowest third do. Common support: a logit of "
            f"the probability that an observation lies below the reference value, on the six variables of the table "
            f"(pseudo R² {num(csi['pseudo_r2'], 2)}), gives a fitted probability for each observation. Common support "
            f"keeps the {csi['obs']:,} observations ({csi['countries']} countries) with a probability between 0.1 and "
            f"0.9, {csi['weak_obs']} of them below the reference value ({csi['weak_countries']} countries). On these "
            f"observations, the specification of Table 2, column 3 gives SUB × GE = {coef(cs_i)}. Its association at "
            f"the reference value is {eff(cs_s)}% ({ci(cs_s)}, {p_eq(cs_s['p'])}), against {eff(base_ref)}% ({ci(base_ref)}) on all observations. Standard errors "
            f"clustered by country. \\*\\*\\* p < 0.01, \\*\\* p < 0.05, \\* p < 0.1.*"]

# ------------------------------------------------------------------------------------------------ Table S25
sgl = get(f"{tk}/info")
STAT = [("pooled_SUB", "Pooled, SUB", 3), ("pooled_SUBxGE", "Pooled, SUB × GE", 3),
        ("pooled_slope_at_ref", "Pooled, 25 pp at the reference value (%)", 1),
        ("between_SUB_m", "Between countries, SUB", 3), ("between_SUBGE_m", "Between countries, SUB × GE", 3),
        ("between_slope_at_ref", "Between countries, 25 pp at the reference value (%)", 1)]
t25 = ["**Table S25** Estimates with one country or one sub-region left out at a time: distribution over the runs and "
       "the five deletions that change each estimate most. Specification of Table 2, column 3 (pooled) and of Table 3 "
       "(between countries). Dependent variable: ln PM2.5 exposure", "",
       row("Estimate", "Min", "P5", "P25", "Median", "P75", "P95", "Max", "p < 0.05", "p < 0.10",
           "Largest changes (standard errors of the full-sample estimate)"), row(*["---"] * 11)]
for lab, key in [("*A. One country at a time*", "single_countries"), ("*B. One sub-region at a time*",
                                                                       "single_subregions")]:
    g = sgl[key]
    t25.append(row(f"{lab[:-1]} ({g['runs']} runs)*", *[""] * 10))
    for st, name, dec in STAT:
        x = g[st]
        dd = x.get("effect25_distribution", x["distribution"])
        moves = ", ".join(f"{m['left_out']} ({num(m['change_in_se'], 2)})" for m in x["largest_moves"])
        t25.append(row(name, *[num(dd[q], dec) for q in ("min", "p5", "p25", "p50", "p75", "p95", "max")],
                       str(x["p_lt_005"]), str(x["p_lt_010"]), moves))
t25 += ["", "*SUB and SUB × GE: coefficients. 25 pp at the reference value: percentage change in PM2.5 exposure for a "
            "share 25 percentage points higher at GE = −0.355. p < 0.05 and p < 0.10: number of runs with a p-value "
            "below the threshold. Largest changes: the estimate without the country or sub-region minus the estimate "
            "on the full sample. The changes are in standard errors of the full-sample estimate (for 25 pp, of the "
            "slope at the reference value). Standard errors clustered by country.*"]

# ------------------------------------------------------------------------------------------------ text
both, inc = term(im, "both_interactions", "SUB:GEc"), term(im, "both_interactions", "SUB:lnYc")
inc_only = term(im, "income_in_place_of_ge", "SUB:lnYc")
mb_g, mb_y = term(im, "mundlak_both", "SUB_m:GE_mc"), term(im, "mundlak_both", "SUB_m:lnY_mc")
mi_y = term(im, "mundlak_income_only", "SUB_m:lnY_mc")
bref, wref = term(be, "mundlak", "between_slope_at_ref"), term(be, "mundlak", "within_slope_at_ref")
cm, cmw = term(be, "country_means", "slope_at_ref"), term(be, "country_means_weighted", "slope_at_ref")
cmi, cmwi = term(be, "country_means", "SUB:GE"), term(be, "country_means_weighted", "SUB:GE")
fy5, f10 = term(lr, "five_year_country_effects", "slope_at_ref"), term(lr, "ten_year_differences", "slope_at_ref")
sp, spn = term(rc, "spell_effects", "slope_at_ref"), term(rc, "spell_effects_no_interaction", "SUB")
f4, f4i = term(fy, "from_fourth_sample_year", "slope_at_ref"), term(fy, "from_fourth_sample_year", "SUB:GE")
f10y = term(fy, "ten_or_more_years_after_first", "slope_at_ref")
p10, p25, p50 = (term(pc, "baseline", n) for n in ("slope_at_obs_P10", "slope_at_obs_P25", "slope_at_obs_P50"))
los_min = LOS.loc[LOS["between_effect25_at_ref"].idxmin()]
nops = term(inf, "without_postsocialist_below_ref", "pooled_slope_at_ref")
nops_b = term(inf, "without_postsocialist_below_ref", "between_slope_at_ref")
g_only, g_int = term(ps, "group_only_no_interaction", "SUB"), term(ps, "group_only_with_interaction", "slope_at_ref")
o_only = term(ps, "other_only_no_interaction", "SUB")
sw, se_, sd = get("source_power/waste"), get("source_power/energy_and_industry"), get("source_power/stacked_difference")
sa_, spg = get("source_power/agriculture"), get("source_power/postsocialist_group")
share_below = get("ge_percentiles/info/share_obs_below_ref")
hic_b, hic_m = term(pc, "baseline", "slope_at_hic_median"), term(pc, "mundlak_between", "slope_at_hic_median")
g5 = term(lr, "five_year_country_effects_mean_ge", "slope_at_ref")
g10 = term(lr, "ten_year_differences_mean_ge", "slope_at_ref")
g10n = term(lr, "ten_year_nonoverlapping_mean_ge", "slope_at_ref")
g10c = term(lr, "ten_year_country_effects_mean_ge", "slope_at_ref")
nov_c = get(f"{lr}/ten_year_nonoverlapping_mean_ge/countries")
rc_m, rc_5, rc_10 = (term(rec, f"{e}_without_change_years", "within_slope_at_ref")
                     for e in ("mundlak", "five_year", "ten_year"))
rd = {e: term(rec, f"{e}_without_change_years_and_reversed_jumps", "within_slope_at_ref")
      for e in ("mundlak", "twfe", "five_year", "ten_year")}
big_rise = [k for k, v in rise.items() if v > 1]
if big_rise == ["ten_year_without_change_years_and_reversed_jumps"]:
    rise_text = (f"Only the ten-year differences without both sets of years rise by more than one standard error of "
                 f"their value on all observations ({num(rise[big_rise[0]], 2)})")
elif big_rise:
    rise_text = f"{len(big_rise)} of the estimates rise by more than one standard error of their value on all observations"
else:
    rise_text = (f"The estimates change by at most {num(max(abs(v) for v in rise.values()), 2)} standard errors of "
                 f"their value on all observations")
fyb = term(fy, "first_year_share_and_ge", "slope_at_ref")
fyc = term(fy, "first_year_share_and_ge_first_year_pm", "slope_at_ref")
fy_pm0 = term(fy, "first_year_share_and_ge_first_year_pm", "lnPM0")
fyd = term(fy, "cross_section_later_means", "slope_at_ref")
ob, ot = ovi["obs_below_ref"], ovi["country_thirds"]
ndv = ob["variables"]


def nd(v):
    return num(ndv[v]["normalised_difference"], 2)


def n_of(k, n):
    return f"all {n}" if k == n else f"{k} of the {n}"


def rng_pct(series):
    lo, hi = num(series.min(), 1), num(series.max(), 1)
    return f"{lo}%" if lo == hi else f"{lo}% to {hi}%"


def p_range(series):
    return "p < 0.001" if series.max() < 0.001 else f"p {pmax(series)}"


ge_ps_o = term(ps, "interaction_with_group_and_ge", "slope_at_ref_other")
ge_ps_g = term(ps, "interaction_with_group_and_ge", "slope_at_ref_group")
subm_p = max(TKP["p_sub_m"].max(), TKB["p_sub_m"].max())
subm_text = "p < 0.05" if subm_p < 0.05 else f"p {pmax(pd.Series([subm_p]))}"

text = f"""# S11. Between and within countries, the moderator and influential countries

This section gives the estimates that Sections 5.1 to 5.6 of the paper cite from Tables S21 to S24, with further specifications of the same tests. They use the main sample of the paper (1,352 observations, 76 countries) unless stated, with standard errors clustered by country, and report the percentage change in PM2.5 exposure for a share 25 percentage points higher (25 pp).

- Effectiveness or income. Income is measured by ln GDP per capita, whose country means correlate with those of GE at {num(info['corr_country_means_GE_lnY'], 2)}. With the share interacted with both, the interaction with GE is {num(both['estimate'], 3)} ({p_eq(both['p'])}) and that with ln GDP per capita {num(inc['estimate'], 3)} ({p_eq(inc['p'])}), and between countries {num(mb_g['estimate'], 3)} ({p_eq(mb_g['p'])}) and {num(mb_y['estimate'], 3)} ({p_eq(mb_y['p'])}). With ln GDP per capita in place of GE, the interaction is {num(inc_only['estimate'], 3)} ({p_eq(inc_only['p'])}) pooled and {num(mi_y['estimate'], 3)} ({p_eq(mi_y['p'])}) between countries. The two interactions are highly collinear, with variance inflation factors of {num(mp['vif']['SUB:GEc'], 0)} and {num(mp['vif']['SUB:lnYc'], 0)} pooled and of {num(mb['vif']['SUB_m:GE_mc'], 0)} and {num(mb['vif']['SUB_m:lnY_mc'], 0)} between countries. Their joint Wald test gives {p_eq(mp['wald_both_interactions']['p'])} pooled and {p_eq(mb['wald_both_interactions']['p'])} between countries. The decline of the association follows effectiveness rather than income (Table S21, panel A). The model in which GE also interacts with each of the other continuous regressors is in Table S14.
- Percentiles of effectiveness. The reference value GE = −0.355 has {num(100 * share_below, 1)}% of the observations below it. The baseline association is {eff(p10)}% at the 10th percentile of the observations, {eff(p25)}% at the 25th and {eff(p50)}% at the median ({p_eq(p50['p'])}), against {eff(term(pc, 'baseline', 'slope_at_ref'))}% at the reference value. At the median GE of high-income countries ({num(hic, 2)}), it is {eff(hic_b)}% ({p_eq(hic_b['p'])}), and {eff(hic_m)}% ({p_eq(hic_m['p'])}) between countries (Table S21, panel B).
- Overlap of weak and strong effectiveness. The observations below the reference value differ from the others by more than 0.25 in normalised difference in {n_of(ob['n_normalised_difference_above_0.25'], len(ndv))} variables of Table S24. The largest differences are in ln GDP per capita ({nd('lnY')}), the share ({nd('SUB')}) and the urban share ({nd('URB')}). The lowest and highest thirds of country-mean GE differ by more than 0.25 in {n_of(ot['n_normalised_difference_above_0.25'], len(ndv))} of them. On the {csi['obs']:,} observations of common support, the baseline association at the reference value is {eff(cs_s)}% ({ci(cs_s)}, {p_eq(cs_s['p'])}). This lies below the lower bound of its interval on all observations ({num(base_ref['effect25_lo'], 1)}%). The association at low effectiveness thus rests on a comparison of groups that differ in development and structure (Table S24). The binning estimator of Table S7, which estimates the association within thirds of effectiveness, is the reference for its shape.
- Between and within countries. At the reference value, the between component of Table 3 gives {eff(bref)}% ({ci(bref)}) and the within component {eff(wref)}% ({p_eq(wref['p'])}). Regressions on country means give {eff(cm)}% ({p_eq(cm['p'])}) with equal weights and {eff(cmw)}% ({p_eq(cmw['p'])}) with weights by observations, with interactions of {num(cmi['estimate'], 3)} ({p_eq(cmi['p'])}) and {num(cmwi['estimate'], 3)} ({p_eq(cmwi['p'])}). Five-year averages with country and period effects give {eff(fy5)}% ({ci(fy5)}) and ten-year differences {eff(f10)}% ({ci(f10)}), both below the between-country estimate. With the share interacted with the country mean of GE, as in Table 3, they give {eff(g5)}% ({ci(g5)}) and {eff(g10)}% ({ci(g10)}). The two ten-year windows ending in 2013 and 2023 ({nov['2013'] + nov['2023']} pairs, {nov_c} countries) give {eff(g10n)}% ({ci(g10n)}), and ten-year differences with country effects {eff(g10c)}% ({ci(g10c)}). Without the years of a change in reporting, two-way fixed effects give {eff(term(rc, 'without_change_years_twfe', 'slope_at_ref'))}%. With an effect for each spell of unchanged reporting, the association is {eff(sp)}% ({p_eq(sp['p'])}), or {eff(spn)}% ({p_eq(spn['p'])}) without SUB × GE (Table S22, panels A and B).
- Changes in reporting and reversed jumps. {big_in_change} Without the years of a change in reporting, the within association at the reference value is {eff(rc_m)}% for the within component of Table 3, {eff(rc_5)}% with five-year averages and {eff(rc_10)}% ({p_eq(rc_10['p'])}) with ten-year differences. Also without the {rci['share_changes_above_0.2_reversed_within_2_years']} reversed jumps of the share, it is {eff(rd['mundlak'])}%, {eff(rd['twfe'])}%, {eff(rd['five_year'])}% and {eff(rd['ten_year'])}% ({p_eq(rd['ten_year']['p'])}) for the within component, two-way fixed effects, five-year averages and ten-year differences. {rise_text} (Table S22, panels D and E).
- Share of the first sample year. With the share of each country's first sample year in place of the current share, the association is {eff(f4)}% ({p_eq(f4['p'])}) from the fourth sample year on, with an interaction of {num(f4i['estimate'], 3)} ({p_eq(f4i['p'])}). Ten or more years after the first sample year, it is {eff(f10y)}% ({p_eq(f10y['p'])}). With GE of the first sample year as the moderator and current GE as a control, it is {eff(fyb)}% ({p_eq(fyb['p'])}) from the fourth sample year on. Once ln PM2.5 exposure of the first sample year is added, it is {eff(fyc)}% ({p_eq(fyc['p'])}), with a coefficient of {num(fy_pm0['estimate'], 3)} on that exposure. A cross-section of the country means over the same years on the values of the first sample year gives {eff(fyd)}% ({p_eq(fyd['p'])}) (Table S22, panel C). The share of the first sample year thus goes with later exposure through differences already present in the first year. A lasting association and a share that responded to earlier pollution both explain them.
- Countries and sub-regions. With one country left out at a time, the between-country association at the reference value ranges from {num(LOC['between_effect25_at_ref'].min(), 1)}% to {num(LOC['between_effect25_at_ref'].max(), 1)}%, and all {loc_info['runs']} estimates have p < 0.01. With one sub-region left out at a time, it ranges from {num(LOS['between_effect25_at_ref'].min(), 1)}% to {num(LOS['between_effect25_at_ref'].max(), 1)}%, the lowest without {los_min['subregion_left_out']} ({p_eq(los_min['between_p_slope_at_ref'])}). Without the k = 1 to 5 countries whose single deletion changes the pooled association most, the pooled association is {rng_pct(TKP['eff'])} ({p_range(TKP['p'])}). Without the k = 1 to 5 countries that change the between-country association most, the between-country association is {rng_pct(TKB['eff'])} ({p_range(TKB['p'])}). The between coefficient of the share keeps {subm_text} in all ten of these deletions. Without the nine post-socialist countries below the reference value, the association is {eff(nops)}% ({p_eq(nops['p'])}) pooled and {eff(nops_b)}% ({p_eq(nops_b['p'])}) between countries (Table S23, panel A). Table S25 gives the distribution of each estimate over the single deletions and the deletions that change it most.
- Post-socialist group. Inside the 25 post-socialist countries, the association of the share is {eff(g_only)}% ({ci(g_only)}, {p_eq(g_only['p'])}, wild cluster bootstrap p = {pval(w1['p_wild'])} with Webb weights and {pval(r1['p_wild'])} with Rademacher weights), and {eff(g_int)}% ({p_eq(g_int['p'])}) at the reference value with SUB × GE. The slope of the share inside and outside the group differs by {num(sps['estimate'], 3)} ({p_eq(sps['p'])}). With GE × post-socialist as well, it differs by {num(gps['estimate'], 3)} ({p_eq(gps['p'])}), with associations of {eff(ge_ps_o)}% for the other countries and {eff(ge_ps_g)}% for the group. In the other {get(f'{ps}/other_only_no_interaction/countries')} countries alone, the association is {eff(o_only)}% ({p_eq(o_only['p'])}) (Table S23, panel B).
- Power of the source contrast. The cross-section of Table S11 ({sw['N']} countries) is refitted here with the same specification. At the 5% level (two-sided) with 80% power, the minimum detectable association is {num(sw['mde_effect25_pct'], 1)}% for exposure from waste, whose estimate is {num(sw['effect25_pct'], 1)}% ({p_eq(sw['p'])}), and {num(se_['mde_effect25_pct'], 1)}% for exposure from energy and industry, whose estimate is {num(se_['effect25_pct'], 1)}% ({p_eq(se_['p'])}). With 50% power, the two are {num(sw['mde50_effect25_pct'], 1)}% and {num(se_['mde50_effect25_pct'], 1)}%. For exposure from agriculture ({sa_['N']} countries, estimate {num(sa_['effect25_pct'], 1)}%, {p_eq(sa_['p'])}), they are {num(sa_['mde_effect25_pct'], 1)}% and {num(sa_['mde50_effect25_pct'], 1)}%. The stacked difference between energy and industry and waste is {num(sd['coefficient'], 3)} (standard error {num(sd['se'], 3)}, {p_eq(sd['p'])}), with a minimum detectable difference of {num(sd['mde_coefficient'], 3)} and a power of {num(sd['power_at_estimate'], 2)} at its estimate. Inside the post-socialist group, the minimum detectable association is {num(spg['mde_effect25_pct'], 1)}% with 80% power and {num(spg['mde50_effect25_pct'], 1)}% with 50% power, against an estimate of {num(spg['effect25_pct'], 1)}%.

"""
md = (text + "\n".join(t21) + "\n\n" + "\n".join(t22) + "\n\n" + "\n".join(t23) + "\n\n" + "\n".join(t24) + "\n\n"
      + "\n".join(t25) + "\n")
(OUT / "esm_section_S11.md").write_text(md, encoding="utf8")
print("esm_section_S11.md written:", len(md), "characters")
