"""
Environmental-spending study: counts cited in the text that no table of the paper shows (supplementary material).

    python ext_r3_counts.py [--out DIR]

Reads paperC_panel.csv, sample_composition.json, extensions.json and anthro_results.json in DIR and writes tab_counts.csv and tab_counts_markdown.md there.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(HERE / "output"))
OUT = Path(ap.parse_args().out)

panel = pd.read_csv(OUT / "paperC_panel.csv")
comp = json.loads((OUT / "sample_composition.json").read_text(encoding="utf8"))
ext = json.loads((OUT / "extensions.json").read_text(encoding="utf8"))
anthro = json.loads((OUT / "anthro_results.json").read_text(encoding="utf8"))
tn = comp["text_numbers"]

# estimation sample of Table 2, column 3: complete values with every regressor
need = ["lnPM", "lnENV", "SUB", "GE", "lnY", "lnY2", "IND", "URB", "TRADE", "lnDENS"]
s = panel[panel["COMPLETE_L1"].astype(bool)].dropna(subset=need)
by = s.groupby("ISO").agg(GE=("GE", "mean"), NOSUB=("NOSUB", "max"), T1=("TIER_L1", lambda x: (x == "T1").any()))
added = by[~by["T1"]]
assert len(by) == comp["countries"] and len(added) == comp["countries_added"], "sample differs from Table 2"
# the harmonised panel with coverage gaps coded as zero (108 countries): what the tool adds
cp = comp["coverage_panel"]
s0 = panel[panel["COMPLETE_L1"].astype(bool)].dropna(subset=[c for c in need if c != "SUB"] + ["SUB0"])
by0 = s0.groupby("ISO").agg(GE=("GE", "mean"), NOSUB=("NOSUB", "max"), COVGAP=("COVGAP", "max"),
                            T1=("TIER_L1", lambda x: (x == "T1").any()))
assert len(by0) == cp["countries"], "panel with coverage gaps differs"
added0 = by0[~by0["T1"]]
added_neg = added0[added0["GE"] < 0]

rows = [
    ("1", "Countries with negative mean GE among those entering through subsector data alone",
     f"{len(added_neg)} of {len(added0)}", "paperC_panel.csv"),
    ("1", "Of these, countries in which only central government reports environmental spending",
     f"{int(added_neg['NOSUB'].sum())} of {len(added_neg)}", "paperC_panel.csv"),
    ("1", "Of these, coverage gaps coded as missing in the main sample",
     f"{int(added_neg['COVGAP'].sum())} of {len(added_neg)}", "paperC_panel.csv"),
    ("3.2", "Central-only countries with central government data alone for all ten COFOG functions",
     f"{cp['central_only'] - ext['nosub_with_subnational_other_function']} of {cp['central_only']}",
     "extensions.json"),
    ("3.2", "Coverage gaps: the same, without countries that have no subnational government",
     f"{cp['coverage_gaps']} of {cp['central_only']} ({cp['coverage_gap_obs']} observations)",
     "sample_composition.json"),
    ("3.2", "Central-only countries with subnational total outlays in the GFS",
     f"{ext['nosub_with_subnational_total_outlays']} of {cp['central_only']}",
     "extensions.json"),
    ("3.3", "Natural sources in the exposure of the average sample country, 2017 (%)",
     f"{anthro['natural_share_pct']['mean']:.0f}", "anthro_results.json"),
    ("3.3", "Natural sources in exposure, the sub-regions with the largest shares, 2017 (%)",
     ", ".join(f"{k} {v:.1f}" for k, v in list(anthro['natural_share_pct']['by_subregion_top5'].items())[:3]),
     "anthro_results.json"),
    ("6", "Countries in which the share moves by more than 0.2 over the period",
     f"{tn['countries_sub_range_above_0.2']} of {comp['countries']}", "sample_composition.json"),
    ("6", "Countries in which the mean of the last three years differs from the first three by more than 0.2",
     f"{tn['countries_sub_first3_last3_change_above_0.2']}", "sample_composition.json"),
    ("6", "Year-to-year changes of the share larger than 0.2 (countries)",
     f"{tn['yearly_changes_above_0.2']} ({tn['countries_with_such_changes']})", "sample_composition.json"),
    ("6", "Of these changes, reversed within two years",
     f"{tn['such_changes_reversed_within_2_years']}", "sample_composition.json"),
]
t = pd.DataFrame(rows, columns=["Section", "Count", "Value", "Output file"])
t.to_csv(OUT / "tab_counts.csv", index=False)
md = ["| Section | Count | Value |", "|---|---|---|"] + [f"| {r[0]} | {r[1]} | {r[2]} |" for r in rows]
(OUT / "tab_counts_markdown.md").write_text("\n".join(md) + "\n", encoding="utf8")
print("\n".join(md))
