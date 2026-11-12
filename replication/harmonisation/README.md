# Replication: harmonisation study

Reproduces all tables and figures of the harmonisation study (manuscript under review; the reference will be added on publication), its further analyses (`evaluate_extensions.py`) and the redistributive effect of health and education spending under each filling choice (`dist_exhibit.py`).

## Requirements

`pip install -e .[replication]` from the repository root (adds `statsmodels`, `scipy` and `matplotlib`). Tested with Python 3.14, pandas 3.0, statsmodels 0.14, matplotlib 3.10 and 3.11.

## Data

| File | Source |
| :--- | :--- |
| `data/gfs_raw_data.xlsx` (not in the repository; download it) | IMF GFS COFOG, dataset IMF.STA:GFS_COFOG 11.0.0 (published 3 February 2026), downloaded as Excel from the [IMF data portal](https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG) |
| `data_ext/eurostat_gov10a_exp_S13_TE_pcgdp.tsv` | Eurostat gov_10a_exp, S13, total expenditure, % of GDP, GF01–GF10 (SDMX API, downloaded 20 October 2026) |
| `data_ext/wb_NY.GDP.PCAP.PP.KD.json` | World Bank WDI, GDP per capita PPP (API, downloaded 20 October 2026) |
| `data_ext/wb_countries.json` | World Bank country metadata (ISO2 to ISO3 mapping) |
| `data_ext/gfs_soo_grants_pcgdp.csv` | IMF GFS Statement of Operations, dataset IMF.STA:GFS_SOO 12.0.0 (published 12 November 2026): grants to and from other general government units and interest paid to them, by subsector, % of GDP. Filtered CSV (3.9 MB) of the SDMX-ML download (38 MB), made by `grants_sdmx.py` |
| `data_ext/dist_inputs_wid_wdi.csv` | Pre-tax income inequality from the World Inequality Database (via Our World in Data, CC BY 4.0) and net national income / GDP from the World Bank WDI (CC BY 4.0), one row per country and year, built by `fetch_inputs.py`; `data_ext/dist_inputs_manifest.csv` lists every download with its URL, size, SHA-256 and retrieval time |

The IMF COFOG extract is not distributed with the repository. The scripts check the downloaded file against the SHA-256 of the extract used in the article (`91e3db1bdb838f322dcbe648b133f511f3efe1921e50c8bc0d7621f512668cfe`) and warn if it differs. The IMF republished the dataset on 21 October 2026 under the same version number (11.0.0) with revised values; the article uses the release published on 3 February 2026, identified by the `PUBLICATION_DATE` column of the file (2026-02-03) and by the checksum above. A current download therefore gives different numbers. The exact extract is available from the author on request.

Queries, download dates, checksums and licences: `data_ext/SOURCES.md` and `../../DATA_LICENSE.md`.

## Run

From the repository root, in this order (the later scripts compare their results with the outputs of the earlier ones):

```bash
python replication/harmonisation/evaluate_harmonisation.py
python replication/harmonisation/evaluate_extensions.py
python replication/harmonisation/dist_exhibit.py
python replication/harmonisation/compare_vintages.py --source data/gfs_raw_data_2026-10-21.csv
```

| Script | Outputs | Runtime |
| :--- | :--- | :--- |
| `evaluate_harmonisation.py` | `output/`: `table1`–`table7` (Tables 1–7 of the article), `supp_*` (supplementary tables), `fig1`–`fig4` (Figures 1–4), `harmonised_all_divisions.csv`, `results.json` | about 1.5 minutes |
| `evaluate_extensions.py` | `output_ext/`: `ext_*.csv`, `ext_fig_*.png`, `fig1_coverage_09.png` (see below) | about 1.5 minutes, 15 seconds from the cache |
| `dist_exhibit.py` | `output_ext/`: `ext_d1_*.csv`, `ext_fig_d1_redistribution_he.png` | under 10 seconds after `evaluate_extensions.py` |
| `compare_vintages.py` | `output_vintage/` (all tables for the October release) and `output/supp_vintage.csv` (supplementary Table S13) | under a minute for the CSV download |

The scripts call `cofog_panel.resolve_value` and `cofog_panel.aggregate.is_complete`, the same functions used by the command-line tool. Each takes `--source FILE` (Excel or CSV) and `--out DIR` to evaluate another extract or write elsewhere. Output folders (`output*/`) and the caches in them (`_gfs_long_*.pkl`, `_ext_long_<sha>.pkl`) are regenerated and kept out of the repository by `.gitignore`.

## Robustness to the IMF release (supplementary Table S13)

Download the current release of IMF.STA:GFS_COFOG (CSV) as `data/gfs_raw_data_2026-10-21.csv` and run `compare_vintages.py` after `evaluate_harmonisation.py`, as above. The script evaluates the second extract into `output_vintage/` and writes `supp_vintage.csv` (supplementary Table S13) to `output/`: the main statistics of Tables 2, 4, 5 and 7 for both releases and their difference. The release used for S13 was published on 21 October 2026 (SHA-256 of the CSV download `886911700a5ff2a7076935b96d4d40a2751ae3a5003ea40dfbd24329c589ef36`). `evaluate_extensions.py --source data/gfs_raw_data_2026-10-21.csv --out replication/harmonisation/output_ext_oct` runs the further analyses on the same release.

## Further analyses (`evaluate_extensions.py`)

The script imports `evaluate_harmonisation.py` from this folder and calls the package unchanged. Inputs are those of `evaluate_harmonisation.py` plus the grant extract `data_ext/gfs_soo_grants_pcgdp.csv` (`--grants FILE`; the grant-flow tests are skipped when the file is missing). `--grants` also reads the SDMX-ML download itself and gives the same outputs, byte for byte. Outputs go to `output_ext/` by default:

- `ext_a1_*`, `ext_a2_*`, `ext_a3_*`: general government values against CGSS alone, complete T2 and T3 sums and spliced values on fixed samples for health, education, social protection and their sums, central against tiered values without general government by region, and the shortfall of health and education spending in percentage points of GDP.
- `ext_a4_*`: the fixed sample with subnational spending and without exact identities, with median-country statistics and a permutation benchmark for the rank shifts (10,000 permutations).
- `ext_b0_*` to `ext_b4_*`, `ext_b3_by_sum.csv`: coverage of groups 01.7 and 01.8 by subsector, the gap in division 01 against the gap in group 01.8, group 01.8 where general government equals the subsector sum, recording practices by country (majority rule over at least three classified years), the effect by type of sum, and checks of alternative readings. `ext_b_country_years.csv` holds the country-year detail.
- `ext_b5_*`: tests of the recording practices with grant flows between levels of government (GFSM 2014 items 263, 133 and 243).
- `ext_trace.csv`: the counts behind statements in the text.
- `ext_fig_classification.png`, `ext_fig_consequence_he.png` (with its data): the classification and its consequence for health and education.
- `ext_table3_region_09.csv`, `ext_fig1_coverage_09_counts.csv`, `fig1_coverage_09.png`: Table 3 and Figure 1 for education (COFOG 09).
- `ext_checks.csv`: agreement with Tables 3, 4 and 5 and Figure 1 of `evaluate_harmonisation.py`.

The script is deterministic: the country-cluster bootstrap uses 1,000 replications and the permutations 10,000, both with seed 20260203. The first run reads the Excel extract and caches it in the output folder (`_ext_long_<sha>.pkl`).

## Redistributive effect (`dist_exhibit.py`, `fetch_inputs.py`)

`dist_exhibit.py` imports `evaluate_extensions.py` (same tiers, sums, splicing and fixed samples) and computes the redistributive effect of government health and education spending (COFOG 07 + 09), allocated as an equal amount per adult, when the spending total comes from general government, CGSS alone, a complete T2 or T3 sum, the tiered value without general government or the spliced value. Inputs: the extract (as above) and `data_ext/dist_inputs_wid_wdi.csv`. Outputs, in `output_ext/` by default (`--out DIR`): `ext_d1_main_table.csv`, `ext_d1_summary.csv`, `ext_d1_sensitivity.csv` (proportional allocation, directly estimated WID years only, spending relative to GDP, a 45% share of benefits for the bottom half), `ext_d1_coverage.csv`, `ext_d1_country_years.csv`, `ext_d1_checks.csv` (the fixed samples equal those of `ext_a1_*` and `ext_a4_*`; the closed forms equal direct computation) and `ext_fig_d1_redistribution_he.png` with its data. The script is deterministic.

`fetch_inputs.py` rebuilds `data_ext/dist_inputs_wid_wdi.csv`: it downloads the WID series from the Our World in Data indicator API and the WDI series as bulk CSV files into an empty folder, records each download in a manifest and writes the filtered table (no personal information is sent):

```bash
python -I replication/harmonisation/fetch_inputs.py --dl downloads_dist --out dist_inputs.csv --manifest dist_inputs_manifest.csv
python -I replication/harmonisation/fetch_inputs.py --dl downloads_dist --out dist_inputs.csv --offline   # rebuild from the downloads
```

Our World in Data and the World Bank update their series, so a new download can differ from the copy in `data_ext/`, whose SHA-256 is recorded in `data_ext/SOURCES.md`.

## Reproducibility

On the IMF extract of 3 February 2026 (and the release of 21 October 2026 for `compare_vintages.py`), the CSV and JSON outputs of the four scripts are identical, byte for byte, to those of the study. PNG files depend on the matplotlib and Pillow versions as well: with the versions used for the study they are identical too (Figures 1–4 of `evaluate_harmonisation.py`: matplotlib 3.11.2 and Pillow 13.0.0; the figures of `evaluate_extensions.py`, `dist_exhibit.py` and `output_vintage/`: matplotlib 3.10.9 and Pillow 12.2.0), and other versions draw the same figures with different bytes.
