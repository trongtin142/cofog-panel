"""
Headline statistics of evaluate_extensions.py for two IMF releases, side by side (reads two output folders).

Run from the repository root, after evaluate_extensions.py on the release of 3 February 2026 (output_ext) and
on the release of 21 October 2026 (output_ext_oct):
    python replication/harmonisation/vintage_headline.py replication/harmonisation/output_ext
        replication/harmonisation/output_ext_oct replication/harmonisation/output_ext/ext_vintage_headline.csv

Arguments: the output folder for February, the output folder for October, and the CSV file to write.
"""
import sys
from pathlib import Path
import pandas as pd

feb, oct_, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])


def stats(folder: Path) -> dict:
    r = lambda f: pd.read_csv(folder / f)  # noqa: E731
    s = {}
    ctry = r("ext_b3_practice_countries.csv")
    for p in "ABCDEU":
        s[f"Countries in practice {p} (majority rule)"] = int((ctry["Practice"] == p).sum())
    b5 = r("ext_b5_grant_tests.csv")
    for kind in ("T2", "T3"):
        x = b5[b5["Test"].str.startswith("(a)") & (b5["Practice"] == "A") & (b5["Sum"] == kind)].iloc[0]
        s[f"Practice A, central 01.8 / central 263, median ({kind})"] = x["Median"]
        s[f"Practice A, central 01.8 / central 263, within 10% (%) ({kind})"] = x["Within 10% (%)"]
        s[f"Practice A, central 01.8 / central 263, cells ({kind})"] = x["Cells"]
    cc = r("ext_b5_grant_countries.csv")
    a = cc[cc["Practice"] == "A"]
    s["Practice A countries passing (a) at the country median"] = int(a["Passes (a): within 10%"].sum())
    s["Practice A countries with grant data"] = len(a)
    b1 = r("ext_b1_gap01_vs_018.csv")
    x = b1[(b1["Sum"] == "T2") & (b1["Gap compared with the 01 gap"] == "01.8")].iloc[0]
    s["01.8 gap / 01 gap, median (T2)"] = x["Median"]
    s["01.8 gap / 01 gap, within 10% (%) (T2)"] = x["Within 10% (%)"]
    s["01.8 gap / 01 gap, cells (T2)"] = x["N"]
    bs = r("ext_b3_by_sum.csv")
    x = bs[(bs["Practice"] == "B and C together") & (bs["Sum"] == "T2")].iloc[0]
    for dv in ("07", "09", "10"):
        s[f"Practices B and C, T2 sum/GG median, {dv}"] = x[f"{dv}: median sum/GG"]
    a4 = r("ext_a4_fixed_sample_noident.csv")
    x = a4[a4["Sample"].str.startswith("Common") & (a4["Measure"] == "HE") & (a4["Alternative"] == "CGSS alone")].iloc[0]
    s["No-identity fixed sample, HE: country-years"] = x["N"]
    s["No-identity fixed sample, HE: countries"] = x["Countries"]
    s["No-identity fixed sample, HE, CGSS alone: median ratio"] = x["Median ratio"]
    s["No-identity fixed sample, HE, CGSS alone: mean abs. quintile shift"] = x["Mean abs. quintile shift"]
    s["No-identity fixed sample, HE, CGSS alone: permutation p"] = x["Mean abs. quintile shift, permutation p"]
    a1 = r("ext_a1_main_table.csv")
    x = a1[(a1["Measure"] == "HE") & (a1["Alternative"] == "CGSS alone")].iloc[0]
    s["Common sample, HE, CGSS alone: median ratio"] = x["Median ratio"]
    s["Common sample, HE: country-years"] = x["N"]
    return s


f, o = stats(feb), stats(oct_)
t = pd.DataFrame({"Statistic": list(f), "February 2026": list(f.values()), "October 2026": [o[k] for k in f]})
t["Difference (October - February)"] = t["October 2026"] - t["February 2026"]
t.round(4).to_csv(out, index=False)
print(t.round(3).to_string(index=False))
