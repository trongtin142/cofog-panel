"""Markdown for the supplementary material from the outputs of ext_r5f.py.

    python make_esm_r5f.py OUTPUT_DIR
"""
import json
import sys
from pathlib import Path

import pandas as pd


def stars(p):
    return "\\*\\*\\*" if p < 0.01 else "\\*\\*" if p < 0.05 else "\\*" if p < 0.1 else ""


def num(x, d=3):
    return f"{x:.{d}f}".replace("-", "−")


def cell(b, se, p):
    return f"{num(b)}{stars(p)} ({num(se)})"


def pct(v, p):
    return f"{num(v, 1)}{stars(p)}"


def pv(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "output"
    t = pd.read_csv(out / "r5f_divisions.csv", dtype={"Division": str})
    b = pd.read_csv(out / "r5f_both.csv", dtype={"Division": str})
    e = pd.read_csv(out / "r5f_excess.csv")
    summ = json.loads((out / "r5f_summary.json").read_text(encoding="utf8"))

    # rows to append to Table S10 -------------------------------------------------------------------------------
    lab = {"Reference: SUB, same sample": "Baseline, sample with share of total outlays",
           "E1: SUB minus SUBTOT": "Environmental share minus share of total outlays, in place of SUB",
           "E2: residual of SUB on SUBTOT": "Residual of the environmental share on the share of total outlays, in place of SUB",
           "Reference: SUB, sample with all nine other shares": "Baseline, sample with the shares of all nine other functions",
           "E3: residual of SUB on the mean of the nine other shares":
               "Residual of the environmental share on the mean share of the nine other functions, in place of SUB",
           "E3b: residual of SUB on the first principal component of the nine other shares":
               "Residual of the environmental share on the first principal component of the nine other shares, in place of SUB"}
    rows10 = []
    k = 15
    for sname, suffix in (("all", ""), ("excl_central_only", ", without countries with central data alone")):
        for meas in lab:
            r = e[(e["Sample"] == sname) & (e["Measure"] == meas)].iloc[0]
            if sname == "all" and meas == "Reference: SUB, same sample":
                continue  # identical to row (1)
            rows10.append(f"| ({k}) {lab[meas]}{suffix} | {int(r['N']):,} | {int(r['Countries'])} | "
                          f"{cell(r['b'], r['se_b'], r['p_b'])} | {cell(r['bGE'], r['se_bGE'], r['p_bGE'])} |  |  | "
                          f"{pct(r['ME25'], r['p_ME25'])} |  |")
            k += 1
    g = e.set_index(["Sample", "Measure"])
    note10 = ("Rows 15–25: the SUB columns give the coefficient of the measure named in the row and its interaction "
              "with GE. Residuals come from a pooled least-squares regression of the environmental share, on the "
              "estimation sample of the row, on the share of total outlays (slope "
              f"{num(g.loc[('all', 'E2: residual of SUB on SUBTOT'), 'aux_slope'])} in row 16 and "
              f"{num(g.loc[('excl_central_only', 'E2: residual of SUB on SUBTOT'), 'aux_slope'])} in row 22), on the "
              "mean share of the nine other COFOG divisions (slope "
              f"{num(g.loc[('all', 'E3: residual of SUB on the mean of the nine other shares'), 'aux_slope'])} and "
              f"{num(g.loc[('excl_central_only', 'E3: residual of SUB on the mean of the nine other shares'), 'aux_slope'])}), "
              "or on the first principal component of the nine standardised shares, which accounts for "
              f"{100 * g.loc[('all', 'E3b: residual of SUB on the first principal component of the nine other shares'), 'pc1_variance_share']:.0f}% "
              f"and {100 * g.loc[('excl_central_only', 'E3b: residual of SUB on the first principal component of the nine other shares'), 'pc1_variance_share']:.0f}% "
              "of their variance. Rows 17 to 19 and 23 to 25 use the observations with the shares of all nine other "
              "divisions.")

    # Table S11 ----------------------------------------------------------------------------------------------------
    lines = ["**Table S11** Subnational shares of the ten COFOG divisions. Dependent variable: ln PM2.5 exposure. "
             "Specification of Table 2, column 3", "",
             "| Division | Countries (never subnational) | Mean share | N | Share in place of SUB: 25 pp at GE = −0.355 (%) [95% CI] | "
             "Share × GE | With SUB: SUB, 25 pp (%) | With SUB: other share, 25 pp (%) | Difference at GE = −0.355, p (Holm) | "
             "Difference of interactions, p | Joint test, p |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for sname, head in (("all", "All countries"), ("excl_central_only",
                                                   "Without countries with central data alone")):
        lines.append(f"| **{head}** |  |  |  |  |  |  |  |  |  |  |")
        tt = t[t["Sample"] == sname].set_index("Division")
        bb = b[b["Sample"] == sname].set_index("Division")
        for d in tt.index:
            r = tt.loc[d]
            row = (f"| {d} {r['Function']} | {int(r['Countries'])} ({int(r['Countries_never_subnational'])}) | "
                   f"{num(r['mean_share'], 2)} | {int(r['N']):,} | "
                   f"{pct(r['ME25'], r['p_ME25'])} [{num(r['ME25_lo'], 1)}, {num(r['ME25_hi'], 1)}] | "
                   f"{cell(r['bGE'], r['se_bGE'], r['p_bGE'])} | ")
            if d == "05":
                row += " |  |  |  |  |"
            else:
                q = bb.loc[d]
                row += (f"{pct(q['ME25_SUB'], q['p_ME25_SUB'])} | {pct(q['ME25_other'], q['p_ME25_other'])} | "
                        f"{pv(q['p_diff_ME'])} ({pv(q['p_diff_ME_holm9'])}) | {pv(q['p_diff_GE'])} | {pv(q['joint_p'])} |")
            lines.append(row)
    sa, sx = summ["all"], summ["excl_central_only"]
    lines += ["", "*Each division's subnational share is built from the subsector values of that division with the "
              "rule of the environmental share (Section 3.2 of the paper), from complete values, and enters with a "
              "one-year lag. All rows use observations with a complete environmental value, and include ln "
              "environmental spending, GE, the controls of Table 2, and year and sub-region effects. Countries "
              "(never subnational): countries in the estimation sample and, in parentheses, those that never report "
              "state or local government for the division. Share in place of SUB: the division's share and its "
              "interaction with GE replace the environmental share, so division 05 reproduces Table 2, columns 3 "
              "and 4. With SUB: the environmental share and the division's share, each with its interaction with GE, "
              "in one model. Difference at GE = −0.355: Wald test that the two shares have the same association at "
              "the median GE of low- and middle-income countries, with the p-value after the Holm correction for the "
              "nine comparisons of each sample in parentheses. Joint test: χ² test with 2 degrees of freedom that "
              "both the associations at GE = −0.355 and the interactions are equal. The environmental share ranks "
              f"{sa['rank_ME25_env_of_10']} of 10 by the association in place of SUB in all countries and "
              f"{sx['rank_ME25_env_of_10']} without the countries with central data alone, and its interaction "
              f"ranks {sa['rank_bGE_env_most_negative_of_10']} and {sx['rank_bGE_env_most_negative_of_10']} from "
              "the most negative. The defence share averages 0.006, so a change of 25 percentage points lies far "
              "outside its observed range. Standard errors clustered by country in parentheses. \\*\\*\\* p < 0.01, "
              "\\*\\* p < 0.05, \\* p < 0.1.*", ""]
    md = ["<!-- rows to append to Table S10, after row (14) -->", *rows10, "",
          "<!-- sentence to add to the note of Table S10 -->", note10, "", *lines]
    (out / "r5f_esm.md").write_text("\n".join(md), encoding="utf8")
    print(f"wrote {out / 'r5f_esm.md'}")


if __name__ == "__main__":
    main()
