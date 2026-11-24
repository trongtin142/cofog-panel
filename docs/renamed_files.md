# Renamed files

Release 1.2.4 gives the replication scripts, their outputs and one folder of third-party data names that describe their content. The renaming changes no option and no result. Releases 1.2.0 to 1.2.3, archived on Zenodo, use the earlier names in the tables below. Release 1.1.1 and earlier use the names of their own time (see the 1.2.0 entry of `CHANGELOG.md`).

## Scripts, data files and folders

| Earlier name (1.2.0 to 1.2.3) | Name from 1.2.4 |
| :--- | :--- |
| `replication/environment/ext_r2.py` | `replication/environment/ext_further_estimates.py` |
| `replication/environment/ext_r3_counts.py` | `replication/environment/ext_text_counts.py` |
| `replication/environment/ext_r3_table2.py` | `replication/environment/ext_table2_columns.py` |
| `replication/environment/ext_r3c.py` | `replication/environment/ext_source_controls.py` |
| `replication/environment/make_esm_r3c.py` | `replication/environment/make_esm_source_controls.py` |
| `replication/environment/ext_r4.py` | `replication/environment/ext_share_variants.py` |
| `replication/environment/ext_r5f.py` | `replication/environment/ext_divisions.py` |
| `replication/environment/make_esm_r5f.py` | `replication/environment/make_esm_divisions.py` |
| `replication/environment/ext_r5i.py` | `replication/environment/ext_specification.py` |
| `replication/environment/ext_r5i_table4.py` | `replication/environment/ext_specification_table4.py` |
| `replication/environment/ext_r5w.py` | `replication/environment/ext_alt_measures.py` |
| `replication/environment/ext_r5z.py` | `replication/environment/ext_zero_shares.py` |
| `replication/environment/make_r5z_tables.py` | `replication/environment/make_zero_shares_tables.py` |
| `replication/environment/ext_r6.py` | `replication/environment/ext_wofi_panel.py` |
| `replication/environment/ext_r8_counts.py` | `replication/environment/ext_sample_flow.py` |
| `replication/environment/data_ext/CHECKSUMS_r5i.sha256` | `replication/environment/data_ext/CHECKSUMS_specification.sha256` |
| `replication/environment/data_ext/lab` | `replication/environment/data_ext/further` |
| `replication/environment/data_ext/lab/r3c` | `replication/environment/data_ext/further/source_controls` |
| `replication/harmonisation/evaluate_extensions_r6.py` | `replication/harmonisation/evaluate_benchmarks.py` |

## Outputs of `replication/environment` (in `output/`)

| Earlier name | Name from 1.2.4 |
| :--- | :--- |
| `esm_r3c.md` | `esm_source_controls.md` |
| `r2_leave_one_country_out.csv` | `further_leave_one_country_out.csv` |
| `r2_results.json` | `further_estimates.json` |
| `r2b_gbdmaps_matched.csv` | `anthro_gbdmaps_matched.csv` |
| `r3c_binning.csv` | `source_controls_binning.csv` |
| `r3c_burnt_area.csv` | `source_controls_burnt_area.csv` |
| `r3c_ceds_exploratory.csv` | `source_controls_ceds_exploratory.csv` |
| `r3c_equal_weights.csv` | `source_controls_equal_weights.csv` |
| `r3c_fig1_binning.pdf` | `source_controls_fig1_binning.pdf` |
| `r3c_fig1_binning.png` | `source_controls_fig1_binning.png` |
| `r3c_results.json` | `source_controls_results.json` |
| `r3c_source_controls.csv` | `source_controls.csv` |
| `r4_share_variants.csv` | `share_variants.csv` |
| `r5f_both.csv` | `divisions_both.csv` |
| `r5f_divisions.csv` | `divisions_in_place.csv` |
| `r5f_esm.md` | `esm_divisions.md` |
| `r5f_excess.csv` | `divisions_excess.csv` |
| `r5f_fig_divisions.pdf` | `divisions_fig.pdf` |
| `r5f_fig_divisions.png` | `divisions_fig.png` |
| `r5f_summary.json` | `divisions_summary.json` |
| `r5i_channel.csv` | `specification_channel.csv` |
| `r5i_figS1_combined.pdf` | `specification_figS1_combined.pdf` |
| `r5i_figS1_combined.png` | `specification_figS1_combined.png` |
| `r5i_fig_kernel.pdf` | `specification_fig_kernel.pdf` |
| `r5i_fig_kernel.png` | `specification_fig_kernel.png` |
| `r5i_fig_support.pdf` | `specification_fig_support.pdf` |
| `r5i_fig_support.png` | `specification_fig_support.png` |
| `r5i_inference.csv` | `specification_inference.csv` |
| `r5i_kernel.csv` | `specification_kernel.csv` |
| `r5i_moderators.csv` | `specification_moderators.csv` |
| `r5i_plausibility.json` | `specification_plausibility.json` |
| `r5i_results.json` | `specification_results.json` |
| `r5i_sensitivity.csv` | `specification_sensitivity.csv` |
| `r5i_structural.csv` | `specification_structural.csv` |
| `r5i_support.csv` | `specification_support.csv` |
| `r5i_table4_rows.csv` | `specification_table4_rows.csv` |
| `r5w_A_crosssection_data.csv` | `alt_measures_A_crosssection_data.csv` |
| `r5w_A_wofi_crosssection.csv` | `alt_measures_A_wofi_crosssection.csv` |
| `r5w_A_wofi_crosssection_sensitivity.csv` | `alt_measures_A_wofi_crosssection_sensitivity.csv` |
| `r5w_B_comparison_data.csv` | `alt_measures_B_comparison_data.csv` |
| `r5w_B_ordering.csv` | `alt_measures_B_ordering.csv` |
| `r5w_B_validation_groups.csv` | `alt_measures_B_validation_groups.csv` |
| `r5w_C_shares_T1.csv` | `alt_measures_C_shares_T1.csv` |
| `r5w_D_rai.csv` | `alt_measures_D_rai.csv` |
| `r5w_results.json` | `alt_measures_results.json` |
| `r5z_details.json` | `zero_shares_details.json` |
| `r5z_federations.csv` | `zero_shares_federations.csv` |
| `r5z_results.csv` | `zero_shares_results.csv` |
| `r5z_tables.md` | `zero_shares_tables.md` |
| `r5z_terciles.csv` | `zero_shares_terciles.csv` |
| `r6_results.json` | `wofi_panel_results.json` |
| `r6_wofi_panel.csv` | `wofi_panel.csv` |
| `r8_counts.json` | `sample_flow_counts.json` |
| `r8_sample_flow.csv` | `sample_flow.csv` |

## Outputs of `replication/harmonisation`

| Earlier name | Name from 1.2.4 |
| :--- | :--- |
| folder `output_r6/` | folder `output_bench/` |
| `ext_fig_classification_r6.png` | `ext_fig_classification_bench.png` |
| `ext_r6_1_headline.csv` | `ext_bench_1_headline.csv` |
| `ext_r6_1a_benchmark_overlap.csv` | `ext_bench_1a_benchmark_overlap.csv` |
| `ext_r6_1b_benchmark_without_gg.csv` | `ext_bench_1b_benchmark_without_gg.csv` |
| `ext_r6_2_cgss_by_practice.csv` | `ext_bench_2_cgss_by_practice.csv` |
| `ext_r6_3_decomposition.csv` | `ext_bench_3_decomposition.csv` |
| `ext_r6_3_pairwise_main.csv` | `ext_bench_3_pairwise_main.csv` |
| `ext_r6_3_release_changes.csv` | `ext_bench_3_release_changes.csv` |
| `ext_r6_4_country_details.csv` | `ext_bench_4_country_details.csv` |
| `ext_r6_4_fig_classification_data.csv` | `ext_bench_4_fig_classification_data.csv` |
| `ext_r6_4_ssf_history.csv` | `ext_bench_4_ssf_history.csv` |
| `ext_r6_4_variant_counts.csv` | `ext_bench_4_variant_counts.csv` |
| `ext_r6_4_variant_grant_test_a.csv` | `ext_bench_4_variant_grant_test_a.csv` |
| `ext_r6_4_variant_moves.csv` | `ext_bench_4_variant_moves.csv` |
| `ext_r6_5_traces.csv` | `ext_bench_5_traces.csv` |
| `ext_r6_checks.csv` | `ext_bench_checks.csv` |

## Console logs of `replication/environment/run_all.py` (in `output/`)

| Earlier name | Name from 1.2.4 |
| :--- | :--- |
| `run_ext_r5f_log.txt` | `run_ext_divisions_log.txt` |
| `run_ext_r5i_log.txt` | `run_ext_specification_log.txt` |
| `run_ext_r5i_table4_log.txt` | `run_ext_specification_table4_log.txt` |
| `run_ext_r5w_log.txt` | `run_ext_alt_measures_log.txt` |
| `run_ext_r5z_log.txt` | `run_ext_zero_shares_log.txt` |
| `run_ext_r6_log.txt` | `run_ext_wofi_panel_log.txt` |
| `run_ext_r8_counts_log.txt` | `run_ext_sample_flow_log.txt` |
| `run_make_esm_r3c_log.txt` | `run_make_esm_source_controls_log.txt` |
| `run_make_esm_r5f_log.txt` | `run_make_esm_divisions_log.txt` |
| `run_make_r5z_tables_log.txt` | `run_make_zero_shares_tables_log.txt` |
| `run_r2_log.txt` | `run_further_estimates_log.txt` |
| `run_r3c_log.txt` | `run_source_controls_log.txt` |
| `run_r4_log.txt` | `run_share_variants_log.txt` |

Every other script, output and log keeps its name.
