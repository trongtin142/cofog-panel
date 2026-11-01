"""Markdown for the paper (Table 5) and Online Resource 1 (rows of Table S7, panel B of Table S5) from r5z outputs."""
import re
from pathlib import Path

import pandas as pd

import sys

HERE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "output"
r = pd.read_csv(HERE / "r5z_results.csv").set_index("Row")
fed = pd.read_csv(HERE / "r5z_federations.csv")
terc = pd.read_csv(HERE / "r5z_terciles.csv")


def stars(p):
    return "\\*\\*\\*" if p < 0.01 else "\\*\\*" if p < 0.05 else "\\*" if p < 0.1 else ""


def line(label, k):
    x = r.loc[k]
    cells = [label, f"{int(x['N']):,}", str(int(x["Countries"])),
             f"{x['SUB']:.3f}{stars(x['p_SUB'])} ({x['se_SUB']:.3f})",
             f"{x['SUB:GE']:.3f}{stars(x['p_SUB:GE'])} ({x['se_SUB:GE']:.3f})",
             f"{x['ME25']:.1f}{stars(x['p_ME25'])}"]
    return "| " + " | ".join([cells[0]] + [c.replace("-", "−") for c in cells[1:]]) + " |"


T5 = [("Baseline (Table 2, column 3): coverage gaps coded as missing", "Baseline: coverage gaps coded as missing"),
      ("Coverage gaps coded as zero (Table 2, column 4)", "Coverage gaps coded as zero"),
      ("Without the central-only countries", "Without the central-only countries"),
      ("Reported subnational zeros also coded as missing", "Reported subnational zeros also coded as missing"),
      ("Same, GG values only", "Reported subnational zeros also coded as missing, GG values only"),
      ("Central-only countries at alternative values",
       "Central-only countries at alternative values: share of total outlays, World Observatory"),
      ("Central-only countries at high values",
       "High values: as above, other central-only countries at the regional mean"),
      ("Excl. post-socialist countries", "Excl. post-socialist countries"),
      ("Excl. post-socialist countries, coverage gaps coded as zero",
       "Excl. post-socialist countries, coverage gaps coded as zero"),
      ("Adds tier and central-only indicators", "Adds tier and central-only indicators")]
S7 = [("Adds tier indicators", "Adds tier indicators"),
      ("Without ln ENV", "Without ln ENV"),
      ("ln ENV as the unconsolidated sum of central, state and local government",
       "ln ENV as the unconsolidated sum of central, state and local government")]
head = ["| Specification | N | Countries | SUB | SUB × GE | 25 pp at GE = −0.355 (%) |", "|---|---|---|---|---|---|"]
out = ["## Table 5 (main text)", ""] + head + [line(a, b) for a, b in T5]
out += ["", "## Rows for Table S7 (Online Resource 1)", ""] + head + [line(a, b) for a, b in S7]

NAMES = {"PAK": "Pakistan", "BGD": "Bangladesh", "ARE": "United Arab Emirates", "BIH": "Bosnia and Herzegovina", "CAN": "Canada", "COM": "Comoros",
         "ETH": "Ethiopia", "IND": "India", "KNA": "Saint Kitts and Nevis", "MEX": "Mexico", "MYS": "Malaysia",
         "NGA": "Nigeria", "USA": "United States"}
WHY = {"coverage gap: COFOG data for central government alone, share coded as missing":
           "Coverage gap: COFOG data for central government alone, so the share is coded as missing",
       "no COFOG 05 record": "No record for environmental protection in the COFOG data",
       "COFOG 05 reported as zero or not positive in every year": "Environmental protection reported as zero in every year",
       "general government values only, without subsector values": "General government values without subsector values, so the share cannot be computed",
       "no complete value": "Subsector values only, none complete",
       "missing in the years with a share: TRADE": "Trade openness missing in its one year with a complete value"}
out += ["", "## Panel B of Table S5 (Online Resource 1)", "",
        "| ISO3 | Country | Among the ten most populous | Years with a COFOG 05 value | Of these, positive and complete | Reason |",
        "|---|---|---|---|---|---|"]
for _, x in fed[fed["Reason"] != "in sample"].iterrows():
    out.append(f"| {x['ISO3']} | {NAMES[x['ISO3']]} | {'yes' if x['Populous'] else 'no'} | {int(x['COFOG05_years'])} | "
               f"{int(x['complete_positive_years'])} | {WHY[x['Reason']]} |")
inside = fed[(fed["Reason"] == "in sample") & (fed["Federal"] == 1)]["ISO3"].tolist()
out += ["", f"Federal countries in the sample ({len(inside)}): {', '.join(inside)}"]
out += ["", "## Terciles of country-mean GE (for the caption of Fig. S2)", "", terc.to_markdown(index=False)]
(HERE / "r5z_tables.md").write_text("\n".join(out) + "\n", encoding="utf8")
print("wrote r5z_tables.md")
