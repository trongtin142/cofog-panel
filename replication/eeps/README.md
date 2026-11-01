# Replication: environmental-spending study

Reproduces all tables and figures of the environmental-spending study (manuscript under review; the reference will be added on publication) and of its Online Resource 1.

## Run

```bash
pip install -e .[replication]
python replication/sjiaos/evaluate_harmonisation.py   # builds the harmonised panel (needs data/gfs_raw_data.xlsx)
python replication/eeps/fetch_data.py                 # downloads the third-party data not distributed here
python replication/eeps/run_all.py                    # runs the scripts below in order
```

`run_all.py` runs the scripts in this order, from `replication/eeps`, and writes each console output to `output/run_<step>_log.txt`. All outputs go to `replication/eeps/output/`. The table numbers in some output file names are working labels, and Online Resource 1 numbers its tables in its own order. The run takes about ten minutes, and about two minutes more the first time, when `env_federalism.py` reads the IMF extract.

| Step | Script | Outputs |
| :--- | :--- | :--- |
| 1 | `env_federalism.py` | Tables of the article and of the further estimates: `tabC1_descriptives`, `tabC2_main`, `tabC3_mundlak`, `tabC3b_twfe`, `tabC4_robustness`, `tabC4b_leave_one_out`, `tabC5_specificity`, `tabC6_oster`, `tabC7_cofog_groups` (CSV); `sample_composition.json`, `extensions.json` and `further_tests.json` (numbers quoted in the text that are not in a table); figures `figC1_marginal_subshare`, `figC2_ge_by_source`, `figC3_binned_by_ge` (PNG at 600 dpi and PDF, with the values of the last one in a JSON file); the estimation panel `paperC_panel.csv`; caches `_harmonised_total.csv` and `_harmonised_groups.csv` |
| 2 | `paperC_esm_wofi.py` | `ESM1_TableS1_countries.csv` (countries of the estimation sample), `ESM1_TableS2_gap_GG_05.csv` (subsector sums against reported general government values for environmental protection), `ESM1_TableS3_sngwofi_comparison.csv` (subnational share against SNG-WOFI), `ESM1_TableS4_central_only_in_sngwofi.csv`, `ESM1_results.json` |
| 3 | `paperC_ext_r3_table2.py` | `tabC2_cols45.csv`: columns 4 and 5 of Table 2 |
| 4 | `paperC_ext_anthro.py` | `tab_anthro.csv`, `anthro_results.json`, `r2b_gbdmaps_matched.csv`: anthropogenic PM2.5 from the GBD-MAPS source contributions as outcome |
| 5 | `paperC_ext_r3_counts.py` | `tab_counts.csv`, `tab_counts_markdown.md`: counts quoted in the text |
| 6 | `paperC_ext_es.py` | `es_events.csv`, `es_eventtime.csv`, `es_results.json`, `es_figure` (PNG and PDF): event study of regional decentralisation reforms (Regional Authority Index), 999 bootstrap samples |
| 7 | `paperC_ext_es_esm.py` | `esm_section_S6.md`: the event-study section of Online Resource 1 |
| 8 | `paperC_ext_iv.py` | `tabIV_results.csv`, `iv_details.json`: instrumental-variable estimates |
| 9 | `paperC_ext_iv_esm.py` | `tabIV_markdown.md` |
| 10 | `paperC_ext_mech.py` | `mech_results.csv`, `mech_results.json`: emissions of carbonaceous aerosols by sector (CEDS) and waste collection (What a Waste) |
| 11 | `paperC_ext_r2.py` | `r2_results.json`, `r2_leave_one_country_out.csv`: samples without countries that report central data alone, other functions, terrain ruggedness and ethnic fractionalisation, influence of single countries, fit with SNG-WOFI |
| 12 | `paperC_ext_r3c.py` | `r3c_source_controls.csv`, `r3c_burnt_area.csv`, `r3c_ceds_exploratory.csv`, `r3c_binning.csv`, `r3c_equal_weights.csv`, `r3c_results.json`, `r3c_fig1_binning` (PNG and PDF): controls for the main sources of PM2.5, a binning estimator of the interaction and equal country weights |
| 13 | `make_esm_r3c.py` | `esm_r3c.md` |
| 14 | `paperC_ext_r4.py` | `r4_share_variants.csv`: variants of the subnational share |
| 15 | `paperC_esm_tables.py` | `esm_tables.md`: the tables of Online Resource 1, rendered from the outputs above |
| 16 | `paperC_ext_r5z.py` | `r5z_results.csv`, `r5z_federations.csv`, `r5z_terciles.csv`, `r5z_details.json`: the zero shares (coverage gaps coded as zero, without the central-only countries, reported zeros also coded as missing, bounds for the zeros of the central-only countries), the exclusion of post-socialist countries, tier and central-only indicators, ln environmental spending on a single basis; federal and populous countries outside the sample, and countries by tercile of government effectiveness |
| 17 | `make_r5z_tables.py` | `r5z_tables.md` |
| 18 | `paperC_ext_r5w.py` (run with `-I`) | `r5w_A_wofi_crosssection.csv`, `r5w_A_wofi_crosssection_sensitivity.csv`, `r5w_A_crosssection_data.csv`, `r5w_B_validation_groups.csv`, `r5w_B_ordering.csv`, `r5w_B_comparison_data.csv`, `r5w_C_shares_T1.csv`, `r5w_D_rai.csv`, `r5w_results.json`: the SNG-WOFI share as an independent measure (cross-section of 2019), agreement with SNG-WOFI by source group and the ordering of the two shares in unitary countries, spending and financing shares on the same general government observations, and the self-rule components of the Regional Authority Index against the share |
| 19 | `paperC_ext_r5f.py` | `r5f_divisions.csv`, `r5f_both.csv`, `r5f_excess.csv`, `r5f_summary.json`, `r5f_fig_divisions` (PNG and PDF): the subnational shares of the ten COFOG divisions in place of, and together with, the environmental share, and the environmental share net of the share of total outlays or of the other divisions |
| 20 | `make_esm_r5f.py` | `r5f_esm.md` |
| 21 | `paperC_ext_r5i.py` | `r5i_moderators.csv`, `r5i_sensitivity.csv`, `r5i_structural.csv`, `r5i_inference.csv`, `r5i_channel.csv`, `r5i_kernel.csv`, `r5i_support.csv`, `r5i_results.json`, `r5i_fig_kernel` and `r5i_fig_support` (PNG and PDF): other governance indicators as moderator, functional form, omitted variables, the sources of exposure, structural controls (manufacturing, energy intensity, fuel exports) and inference |
| 22 | `paperC_ext_r5i_table4.py` | `r5i_table4_rows.csv`, `r5i_plausibility.json`, `r5i_figS1_combined` (PNG and PDF): the rows of step 21 in the format of Table 4, the arithmetic for the sources of exposure, and a two-panel figure of the linear, binning and kernel estimates with their common support |
| 23 | `paperC_ext_r6.py` (run with `-I`) | `r6_split.csv`, `r6_wofi_panel.csv`, `r6_results.json`: central and subnational spending in place of the share, and the panel model on the countries covered by both the share and SNG-WOFI |
| 24 | `paperC_ext_r8_counts.py` | `r8_sample_flow.csv` (countries and observations left at each step from the COFOG extract to the main sample), `r8_counts.json` (observations and countries below the reference value of government effectiveness, income groups of the main sample) |

`paperC_samples.py` is a module, not a step: it defines the central-only countries, the coverage gaps and the countries without subnational government (see Sample).

The outputs of the study were produced with Python 3.14, pandas 3.0.3, numpy 2.4.6, statsmodels 0.14.6, scipy 1.17.1, linearmodels 7.0, formulaic 1.2.1, tabulate 0.10.0, matplotlib 3.10.9 and Pillow 12.2.0. With these versions every table, JSON and Markdown output and every PNG figure is identical byte for byte to those of the study, and the PDF figures differ only in their creation date. Other versions of the packages can change the last digits of some values and the layout of the figures.

## Sample

A country is central-only when, in every year of its estimation sample, environmental protection is reported for central government alone, so its subnational share is zero by construction. A central-only country has a coverage gap when the COFOG data of the IMF cover central government alone for all ten functions in every year: its zero then reflects what the data cover, not what subnational governments spend. `env_federalism.py` codes the share of these countries as missing. Countries without subnational government keep a share of zero, because their zero is a true zero; the only such country is Singapore (`NO_SUBNATIONAL_GOVERNMENT` in `paperC_samples.py`, with its source). `paperC_samples.coverage_gaps()` derives the list from the data and checks it against `COVERAGE_GAPS`. `gaps_as_zero()` in `env_federalism.py` gives the construction with the coverage gaps coded as zero, which step 16 reports.

## Data

- **IMF GFS COFOG.** The harmonised COFOG panel comes from the harmonisation replication (`replication/sjiaos/output/harmonised_all_divisions.csv`), so it needs the IMF extract described in `replication/sjiaos/README.md` (`data/gfs_raw_data.xlsx`, release of 3 February 2026); another release gives different numbers. `env_federalism.py` also reads the extract directly for total outlays by subsector (`TOTOUT_T`), for transfers of a general character between levels of government (`GF0180_T`) and for the six COFOG groups of environmental protection (`GF0510_T` to `GF0560_T`), in per cent of GDP, harmonises them with `cofog_panel.resolve_value` and `is_complete`, and compares the file with the SHA-256 of the extract used in the study. The first run caches the harmonised series in `output/`; the caches are rebuilt when the extract is newer than them.
- **World Bank** (`data_ext/`): World Development Indicators and Worldwide Governance Indicators, CC BY 4.0, distributed with the repository. The World Bank country metadata (`data_ext/wb_countries.json`) give the current income classification used for the income groups. Six further series used by step 21 were downloaded from the World Bank API on 3 November 2026 (`https://api.worldbank.org/v2/country/all/indicator/<code>?format=json&per_page=20000`, with `source=3` for the WGI series); their SHA-256 are also in `data_ext/CHECKSUMS_r5i.sha256`:

  | File | Series | SHA-256 |
  | :--- | :--- | :--- |
  | `wb_NV.IND.MANF.ZS.json` | WDI, manufacturing, value added (% of GDP) | `faeec80f3479e4d5e6205019c1a192119d527ea30be7ce73d41cd92bb6306d16` |
  | `wb_EG.EGY.PRIM.PP.KD.json` | WDI, energy intensity level of primary energy (MJ per 2021 PPP dollar of GDP) | `733ca707bc39f6ca707e1fc079c207fee4bcbb287670814d8c90e9650f51c08a` |
  | `wb_TX.VAL.FUEL.ZS.UN.json` | WDI, fuel exports (% of merchandise exports) | `bdc358c8f9d30ecc66f2a91cefdbd907b6ddf202d833fcf312bb8fbedee5550e` |
  | `wgi_GOV_WGI_VA.EST.json` | WGI, voice and accountability, estimate | `57e3e67e2ece10b2aaf9088cadb3896ccf781e4f67c00c919f38ea0c76a1db55` |
  | `wgi_GOV_WGI_RQ.EST.json` | WGI, regulatory quality, estimate | `929e2b1b6ce727aa950815f4c6dbcd6a59690407c9f8634b1ce780148e28c263` |
  | `wgi_GOV_WGI_RL.EST.json` | WGI, rule of law, estimate | `fc1541725fb019f4baf97c1993c6f66c3b109424d60be9df50af422bd49bef5b` |

  Licence CC BY 4.0; cite "World Bank, World Development Indicators" and "World Bank, Worldwide Governance Indicators".
- **Further data** (`data_ext/lab/`): the Regional Authority Index, terrain ruggedness, CEDS emissions and the OECD SNG-WOFI functional data are not distributed with the repository; `fetch_data.py` downloads them from their sources and compares each file with the SHA-256 of the copy used in the study. If a download fails, the script prints the URL and the place to save the file by hand. What a Waste, the Historical Index of Ethnic Fractionalization, the GBD-MAPS source contributions, two further WDI series, the CRU climate series of the World Bank Climate Change Knowledge Portal and the burnt area of Our World in Data are distributed here (CC BY 4.0 or CC0). Sources, URLs, download dates and licences: `data_ext/SOURCES.md`.
- **Federal countries.** The list in `env_federalism.py` follows the country chapters (chapters 2–27) of Griffiths et al. (2020), *The Forum of Federations Handbook of Federal Countries 2020*, https://doi.org/10.1007/978-3-030-42088-8, without the European Union and without Cyprus, a unitary state whose chapter covers proposals for a federation.
- **Economies in transition.** The list in `env_federalism.py` follows Table B of the country classification in United Nations (2024), *World Economic Situation and Prospects 2024*, statistical annex (South-Eastern Europe; Commonwealth of Independent States and Georgia).
