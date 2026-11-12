"""Markdown for the IV table of the supplementary material, from tabIV_results.csv in OUT_DIR (default output).

    python ext_iv_esm.py [OUT_DIR]
"""
import json
import sys
from pathlib import Path

import pandas as pd

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "output"
t = pd.read_csv(OUT / "tabIV_results.csv")
lab = {"P1 Low-GE half, FED": "(1) GE below the sample median, federal constitution",
       "P2 Full sample, FED": "(2) Full sample, federal constitution",
       "P3a RAI sample, RAI90": "(3) Countries with RAI data, regional authority 1990–1995",
       "P3b RAI sample, FED + RAI90": "(4) Countries with RAI data, both instruments",
       "P4 Country means, low-GE half, FED": "(5) Country means, GE below the median, federal constitution",
       "P4 Country means, full sample, FED": "(6) Country means, full sample, federal constitution"}


def f3(x):
    return "" if pd.isna(x) else f"{x:.3f}".replace("-", "−")


def f1(x):
    return f"{x:.1f}".replace("-", "−")


def iv(s, fmt=f3):
    return " ∪ ".join(f"[{fmt(x)}, {fmt(y)}]" for x, y in json.loads(s))


rows = ["| Specification | N | Countries | First stage (s.e.) | Effective F | 2SLS (s.e.) | AR 95% set | "
        "AR set, 25 pp (%) | OLS, same sample (s.e.) | Conley bounds, γ ≤ 0.05 | Conley bounds, γ ≤ 0.10 |",
        "|---|---|---|---|---|---|---|---|---|---|---|"]
for _, r in t.iterrows():
    c05 = "" if pd.isna(r.get("Conley_UCI_0.05")) else iv("[" + r["Conley_UCI_0.05"] + "]")
    c10 = "" if pd.isna(r.get("Conley_UCI_0.10")) else iv("[" + r["Conley_UCI_0.10"] + "]")
    rows.append(f"| {lab[r['Model']]} | {int(r['N']):,} | {int(r['Countries'])} | {r['FS_coef'].replace('-', '−')} | "
                f"{r['Effective_F']:.1f} | {f3(r['b_2SLS'])} ({f3(r['se_2SLS'])}) | {iv(r['AR_set'])} | "
                f"{iv(r['AR_set_pct25'], f1)} | {f3(r['b_OLS_same_sample'])} ({f3(r['se_OLS'])}) | {c05} | {c10} |")
r4 = t[t["Model"].str.startswith("P3b")].iloc[0]
out = "\n".join(rows) + (f"\n\nRow 4: LIML {f3(r4['b_LIML'])} ({f3(r4['se_LIML'])}), Hansen J {r4['HansenJ']:.2f} "
                         f"(p = {r4['HansenJ_p']:.3f}).\n")
(OUT / "tabIV_markdown.md").write_text(out, encoding="utf8")
