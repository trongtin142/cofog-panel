"""
Runs the replication of the environmental-spending study (the reference will be added on publication) and of its
supplementary material, in order. Run from the repository root, after the
harmonisation replication and fetch_data.py:
    python replication/harmonisation/evaluate_harmonisation.py
    python replication/environment/fetch_data.py
    python replication/environment/run_all.py
Each step writes its console output to replication/environment/output/run_<step>_log.txt and the run stops at the first
step that fails. The event study (ext_es.py, 999 bootstrap samples) takes a few minutes.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = "output"
GBDMAPS = "data_ext/further/gbdmaps/41467_2021_23853_MOESM4_ESM.xlsx"

# (log name, script, arguments, isolated mode); arguments are relative to replication/environment
STEPS = [
    ("run_log.txt", "env_federalism.py", [], False),
    ("run_esm_wofi_log.txt", "esm_wofi.py",
     [str(REPO), "data_ext/further/sngwofi/oecd_sng_wofi_cofog.csv", OUT], True),
    ("run_table2_log.txt", "ext_table2_columns.py", ["--out", OUT], False),
    ("run_anthro_log.txt", "ext_anthro.py", ["--main", "env_federalism.py", "--gbdmaps", GBDMAPS, "--out", OUT],
     False),
    ("run_counts_log.txt", "ext_text_counts.py", ["--out", OUT], False),
    ("run_es_log.txt", "ext_es.py", ["--out", OUT, "--rai", "data_ext/further/RAI_country-april-2021.xlsx"], False),
    ("run_es_esm_log.txt", "ext_es_esm.py", [OUT, f"{OUT}/ESM1_TableS1_countries.csv"], False),
    ("run_iv_log.txt", "ext_iv.py", [OUT], False),
    ("run_iv_esm_log.txt", "ext_iv_esm.py", [OUT], False),
    ("run_mech_log.txt", "ext_mech.py", ["--ext", "data_ext/further", "--out", OUT], False),
    ("run_further_estimates_log.txt", "ext_further_estimates.py",
     ["--ext", "data_ext/further", "--esm", f"{OUT}/ESM1_TableS3_sngwofi_comparison.csv", "--out", OUT], False),
    ("run_source_controls_log.txt", "ext_source_controls.py",
     ["--main", "env_federalism.py", "--anthro", "ext_anthro.py", "--dl", "data_ext/further/source_controls",
      "--gbdmaps", GBDMAPS, "--ceds-bcoc", "data_ext/further/ceds", "--out", OUT], True),
    ("run_make_esm_source_controls_log.txt", "make_esm_source_controls.py", [OUT], False),
    ("run_share_variants_log.txt", "ext_share_variants.py", ["--out", OUT], False),
    ("run_esm_tables_log.txt", "esm_tables.py", [OUT], False),
    ("run_ext_zero_shares_log.txt", "ext_zero_shares.py", [], False),
    ("run_make_zero_shares_tables_log.txt", "make_zero_shares_tables.py", [], False),
    ("run_ext_alt_measures_log.txt", "ext_alt_measures.py", [], True),
    ("run_ext_divisions_log.txt", "ext_divisions.py", [], False),
    ("run_make_esm_divisions_log.txt", "make_esm_divisions.py", [], False),
    ("run_ext_specification_log.txt", "ext_specification.py", [], False),
    ("run_ext_specification_table4_log.txt", "ext_specification_table4.py", [], False),
    ("run_ext_wofi_panel_log.txt", "ext_wofi_panel.py", ["--out", OUT], True),
    ("run_ext_sample_flow_log.txt", "ext_sample_flow.py", ["--out", OUT], False),
    ("run_ext_between_within_log.txt", "ext_between_within.py", ["--out", OUT, "--inputs", OUT], False),
    ("run_make_esm_between_within_log.txt", "make_esm_between_within.py", [OUT], False),
]
NEEDED = ["data_ext/further/RAI_country-april-2021.xlsx", "data_ext/further/rugged/rugged_data.csv",
          "data_ext/further/sngwofi/oecd_sng_wofi_cofog.csv",
          "data_ext/further/ceds/BC_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
          "data_ext/further/source_controls/ceds/SO2_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
          str(REPO / "data" / "gfs_raw_data.xlsx"),
          str(REPO / "replication" / "harmonisation" / "output" / "harmonised_all_divisions.csv")]


def main() -> int:
    missing = [f for f in NEEDED if not (HERE / f).exists()]
    if missing:
        print("Missing input files:\n  " + "\n  ".join(missing))
        print("Run replication/harmonisation/evaluate_harmonisation.py and replication/environment/fetch_data.py first "
              "(see replication/environment/README.md).")
        return 1
    (HERE / OUT).mkdir(exist_ok=True)
    for log, script, args, isolated in STEPS:
        cmd = [sys.executable] + (["-I"] if isolated else []) + [script] + args
        with open(HERE / OUT / log, "w", encoding="utf8") as fh:
            r = subprocess.run(cmd, cwd=HERE, stdout=fh, stderr=subprocess.STDOUT)
        print(f"{script:28} exit {r.returncode}", flush=True)
        if r.returncode:
            print(f"Step failed; see {OUT}/{log}")
            return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
