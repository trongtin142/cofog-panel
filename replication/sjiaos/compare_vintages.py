"""
Robustness of the SJIAOS results to the IMF release (Supplementary Table S13).

Runs evaluate_harmonisation.py on a second IMF GFS COFOG extract and compares its main statistics with
the outputs for the article extract. Run from the repository root, after evaluate_harmonisation.py:
    python replication/sjiaos/compare_vintages.py --source data/gfs_raw_data_2026-10-21.csv

Inputs : replication/sjiaos/output/ (article extract, published 2026-02-03)
         --source: the second extract (Excel or CSV), e.g. the release published 2026-10-21
Outputs: replication/sjiaos/output_vintage/ (all tables for the second extract)
         replication/sjiaos/output/supp_vintage.csv (Supplementary Table S13)
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
BASE = HERE / "output"
NEW = HERE / "output_vintage"


def _row(t: pd.DataFrame, **match) -> pd.Series:
    m = pd.Series(True, index=t.index)
    for col, val in match.items():
        m &= t[col].astype(str) == str(val)
    assert m.sum() == 1, match
    return t[m].iloc[0]


def statistics(out: Path) -> list:
    """(statistic, source table, value, is_count) for the results reported in the article."""
    read = lambda name: pd.read_csv(out / f"{name}.csv", dtype={"DIV": str})
    res = json.loads((out / "results.json").read_text(encoding="utf8"))
    t2, t4, t5, t7 = read("table2_coverage"), read("table4_overlap"), read("table5_adjustment"), read("table7_regression")
    env = _row(t2, DIV="05")
    rows = [
        ("Cells with a harmonised value, all divisions", "Data", res["country_years_any"], True),
        ("Countries", "Data", res["countries"], True),
        ("05 Environmental protection: countries, GG only", "Table 2", env["Countries GG-only"], True),
        ("05 Environmental protection: countries, T1-T3", "Table 2", env["Countries T1-T3"], True),
        ("05 Environmental protection: gain vs GG only (%)", "Table 2", env["Gain vs GG-only (%)"], False),
    ]
    for est in ("T2 sum, complete", "T3 sum, complete"):
        r = _row(t4, DIV="All", Estimator=est)
        rows += [(f"All divisions, {est}: exact identities (%)", "Table 4", r["Exact identities (%)"], False),
                 (f"All divisions, {est}: within 5% excl. identities (%)", "Table 4",
                  r["Within 5% excl. identities (%)"], False)]
    for div, name in (("05", "05 Environmental protection"), ("01", "01 General public services"), ("All", "All divisions")):
        for est in ("T2 sum, complete", "T3 sum, complete"):
            r = _row(t4, DIV=div, Estimator=est)
            rows.append((f"{name}, {est}: median ratio excl. identities", "Table 4",
                         r["Median ratio excl. identities"], False))
    for est in ("T2 sum", "T3 sum"):
        r = _row(t5, DIV="All", Estimator=est, **{"Min. distance (years)": 5})
        rows += [(f"All divisions, {est}, d >= 5: unadjusted within 5% (%)", "Table 5", r["Unadjusted within 5% (%)"], False),
                 (f"All divisions, {est}, d >= 5: adjusted within 5% (%)", "Table 5", r["Adjusted within 5% (%)"], False)]
    for _, r in t7.iterrows():
        rows.append((f"{r['Model']}: b(lnGDPPC)", "Table 7", r["b(lnGDPPC)"], False))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0].strip())
    ap.add_argument("--source", type=Path, required=True, help="second IMF GFS COFOG extract, Excel or CSV")
    ap.add_argument("--out", type=Path, default=NEW, help="output folder for the second extract (default: %(default)s)")
    ap.add_argument("--base-label", default="Release of 3 February 2026")
    ap.add_argument("--new-label", default="Release of 21 October 2026")
    args = ap.parse_args()
    if not (BASE / "results.json").exists():
        sys.exit(f"Missing {BASE / 'results.json'}: run replication/sjiaos/evaluate_harmonisation.py first.")
    subprocess.run([sys.executable, str(HERE / "evaluate_harmonisation.py"), "--source", str(args.source),
                    "--out", str(args.out)], check=True, stdout=subprocess.DEVNULL)

    base, new = statistics(BASE), statistics(args.out)
    # object columns keep counts as integers next to shares and ratios
    num = lambda x, is_count: int(x) if is_count else round(float(x), 3)
    old_v = [num(r[2], r[3]) for r in base]
    new_v = [num(r[2], r[3]) for r in new]
    t = pd.DataFrame({
        "Statistic": [r[0] for r in base],
        "Table": [r[1] for r in base],
        args.base_label: pd.Series(old_v, dtype=object),
        args.new_label: pd.Series(new_v, dtype=object),
        "Difference": pd.Series([num(b - a, r[3]) for a, b, r in zip(old_v, new_v, base)], dtype=object),
    })
    t.to_csv(BASE / "supp_vintage.csv", index=False)
    print(t.to_string(index=False))


if __name__ == "__main__":
    main()
