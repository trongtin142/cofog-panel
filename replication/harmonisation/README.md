# Replication: harmonisation study

Reproduces all tables and figures of the harmonisation study (manuscript under review; the reference will be added on publication), its further analyses (`evaluate_extensions.py`, `evaluate_extensions_r6.py`), the redistributive effect of health and education spending under each filling choice (`dist_exhibit.py`) and the comparison of the two IMF releases (`compare_vintages.py`, `vintage_headline.py`).

## Requirements

`pip install -e .[replication]` from the repository root (adds `statsmodels`, `scipy`, `matplotlib`, `linearmodels` and `tabulate`). Tested with Python 3.14, pandas 3.0, statsmodels 0.14, matplotlib 3.10 and 3.11.

## Data

| File | Source |
| :--- | :--- |
| `data/gfs_raw_data.xlsx` (not in the repository; download the archived copy) | IMF GFS COFOG, dataset IMF.STA:GFS_COFOG 11.0.0 (published 3 February 2026), downloaded as Excel from the [IMF data portal](https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG); an unaltered copy, `imf_gfs_cofog_2026-02-03.xlsx`, is archived at <https://doi.org/10.5281/zenodo.24192043> |
| `data_ext/eurostat_gov10a_exp_S13_TE_pcgdp.tsv` | Eurostat gov_10a_exp, S13, total expenditure, % of GDP, GF01–GF10 (SDMX API, downloaded 20 October 2026) |
| `data_ext/wb_NY.GDP.PCAP.PP.KD.json` | World Bank WDI, GDP per capita PPP (API, downloaded 20 October 2026) |
| `data_ext/wb_countries.json` | World Bank country metadata (ISO2 to ISO3 mapping) |
| `data_ext/gfs_soo_grants_pcgdp.csv` | IMF GFS Statement of Operations, dataset IMF.STA:GFS_SOO 12.0.0 (published 12 November 2026): grants to and from other general government units and interest paid to them, by subsector, % of GDP. Filtered CSV (3.9 MB) of the SDMX-ML download (38 MB), made by `grants_sdmx.py` |
| `data_ext/ext_benchmarks_wdi.csv` | External benchmarks from the World Bank WDI (CC BY 4.0): domestic general government health expenditure, % of GDP (`SH.XPD.GHED.GD.ZS`, WHO Global Health Expenditure Database), and government expenditure on education, % of GDP (`SE.XPD.TOTL.GD.ZS`, UNESCO Institute for Statistics), one row per country and year, built by `ext_fetch_benchmarks.py`; `data_ext/ext_benchmarks_manifest.csv` records both downloads with URL, size, SHA-256, retrieval time and the update date stated in the files |
| `data_ext/dist_inputs_wid_wdi.csv` | Pre-tax income inequality from the World Inequality Database (via Our World in Data, CC BY 4.0) and net national income / GDP from the World Bank WDI (CC BY 4.0), one row per country and year, built by `fetch_inputs.py`; `data_ext/dist_inputs_manifest.csv` lists every download with its URL, size, SHA-256 and retrieval time |

The IMF COFOG extract is not distributed with the repository. The scripts check the downloaded file against the SHA-256 of the extract used in the article (`91e3db1bdb838f322dcbe648b133f511f3efe1921e50c8bc0d7621f512668cfe`) and warn if it differs. The IMF republished the dataset on 21 October 2026 under the same version number (11.0.0) with revised values; the article uses the release published on 3 February 2026, identified by the `PUBLICATION_DATE` column of the file (2026-02-03) and by the checksum above. A current download therefore gives different numbers. An unaltered copy of the extract used in the article (`imf_gfs_cofog_2026-02-03.xlsx`, 58,389,314 bytes, with the checksum above) is archived under the IMF terms at <https://doi.org/10.5281/zenodo.24192043>; save it as `data/gfs_raw_data.xlsx`.

Queries, download dates, checksums and licences: `data_ext/SOURCES.md` and `../../DATA_LICENSE.md`.

## Run

From the repository root, in this order (the later scripts compare their results with the outputs of the earlier ones):

```bash
python replication/harmonisation/evaluate_harmonisation.py
python replication/harmonisation/evaluate_extensions.py
python replication/harmonisation/dist_exhibit.py
python replication/harmonisation/compare_vintages.py --source data/gfs_raw_data_2026-10-21.csv
python replication/harmonisation/evaluate_extensions.py --source data/gfs_raw_data_2026-10-21.csv --out replication/harmonisation/output_ext_oct
python replication/harmonisation/vintage_headline.py replication/harmonisation/output_ext replication/harmonisation/output_ext_oct replication/harmonisation/output_ext/ext_vintage_headline.csv
python -I replication/harmonisation/evaluate_extensions_r6.py --vintage data/gfs_raw_data_2026-10-21.csv --practice replication/harmonisation/output_ext/ext_b3_practice_countries.csv
```

| Script | Outputs | Runtime |
| :--- | :--- | :--- |
| `evaluate_harmonisation.py` | `output/`: `table1`–`table7` (the main tables of the harmonisation study; an article that uses them numbers its tables in its own order and lists the output file of each table), `supp_*` (supplementary tables), `fig1`–`fig4` (Figures 1–4), `harmonised_all_divisions.csv`, `results.json` | about 1.5 minutes |
| `evaluate_extensions.py` | `output_ext/`: `ext_*.csv`, `ext_fig_*.png`, `fig1_coverage_09.png` (see below) | about 1.5 minutes, 15 seconds from the cache |
| `dist_exhibit.py` | `output_ext/`: `ext_d1_*.csv`, `ext_fig_d1_redistribution_he.png` | under 10 seconds after `evaluate_extensions.py` |
| `compare_vintages.py` | `output_vintage/` (all tables for the October release) and `output/supp_vintage.csv` (comparison of the two releases) | under a minute for the CSV download |
| `evaluate_extensions.py --source <October CSV> --out .../output_ext_oct` | `output_ext_oct/`: the further analyses on the October release | under a minute |
| `vintage_headline.py` | `output_ext/ext_vintage_headline.csv`: headline statistics of the further analyses for both releases and their difference | seconds |
| `evaluate_extensions_r6.py` | `output_r6/`: `ext_r6_*.csv` and `ext_fig_classification_r6.png` (see below) | about 1.5 minutes |

The scripts call `cofog_panel.resolve_value` and `cofog_panel.aggregate.is_complete`, the same functions used by the command-line tool. Each takes `--source FILE` (Excel or CSV) and `--out DIR` to evaluate another extract or write elsewhere. Output folders (`output*/`) and the caches in them (`_gfs_long_*.pkl`, `_ext_long_<sha>.pkl`) are regenerated and kept out of the repository by `.gitignore`.

## Robustness to the IMF release

Save the CSV download of the release of 21 October 2026 as `data/gfs_raw_data_2026-10-21.csv` and run `compare_vintages.py` after `evaluate_harmonisation.py`, as above. The script evaluates the second extract into `output_vintage/` and writes `supp_vintage.csv` (supplementary Table S13) to `output/`: the main statistics of Tables 2, 4, 5 and 7 for both releases and their difference. The release used for S13 was published on 21 October 2026 (SHA-256 of the CSV download `886911700a5ff2a7076935b96d4d40a2751ae3a5003ea40dfbd24329c589ef36`). The IMF portal serves only its latest release, so a later download can differ from that file. Compare its SHA-256 with the value above before running the comparison. `evaluate_extensions.py --source data/gfs_raw_data_2026-10-21.csv --out replication/harmonisation/output_ext_oct` runs the further analyses on the same release.

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

## External benchmarks, results by practice and classification variants (`evaluate_extensions_r6.py`, `ext_fetch_benchmarks.py`)

`evaluate_extensions_r6.py` imports `evaluate_extensions.py` and `dist_exhibit.py` (same tiers, sums, splicing, samples and practice classification; both stay unchanged) and runs after them. Inputs: the extract, `data_ext/ext_benchmarks_wdi.csv` (`--benchmarks`), `data_ext/dist_inputs_wid_wdi.csv` (`--inputs`), the grant extract (`--grants`), the practice table written by `evaluate_extensions.py` (`--practice`, checked against a recomputation) and, optionally, the October release (`--vintage`) for the decomposition across releases. `--out DIR` (default `output_r6/`) and `--cache DIR` (default `--out`) set the folders. Outputs:

- `ext_r6_1_*`: IMF general government values, CGSS alone, complete sums, the tiered value and spliced values against the WHO GHED health and UNESCO UIS education series, in overlap years and in country-years without general government.
- `ext_r6_2_cgss_by_practice.csv`: CGSS alone against general government by recording practice, with the accounting split of the ratio and the error in the redistributive effect.
- `ext_r6_3_*`: pairwise samples with subnational spending for every alternative, with and without exact and near identities, the redistributive effect, the decomposition of the median ratio and the changes between the two releases (with `--vintage`).
- `ext_r6_4_*`, `ext_fig_classification_r6.png`: the classification on T2 sums only and without divisions 07 and 10, grant test (a) for each variant, country details, the social security funds by year, and the classification figure with its data.
- `ext_r6_5_traces.csv`: sample sizes quoted in the text; `ext_r6_checks.csv`: agreement with `evaluate_extensions.py`.

The script is deterministic (fixed seed of `evaluate_extensions.py`). `ext_fetch_benchmarks.py` rebuilds `data_ext/ext_benchmarks_wdi.csv` from the two WDI bulk CSV files, in the same way as `fetch_inputs.py` (no personal information is sent):

```bash
python -I replication/harmonisation/ext_fetch_benchmarks.py --dl downloads_bench --out ext_benchmarks_wdi.csv --manifest ext_benchmarks_manifest.csv
python -I replication/harmonisation/ext_fetch_benchmarks.py --dl downloads_bench --out ext_benchmarks_wdi.csv --offline   # rebuild from the downloads
```

The World Bank updates these series, so a new download can differ from the copy in `data_ext/`, whose SHA-256 is recorded in `data_ext/SOURCES.md`.

## Reproducibility

On the IMF extract of 3 February 2026 (and the release of 21 October 2026 for `compare_vintages.py`), the CSV and JSON outputs of these scripts are identical, byte for byte, to those of the study. PNG files depend on the matplotlib and Pillow versions as well: with the versions used for the study they are identical too (Figures 1, 3 and 4 of `evaluate_harmonisation.py`: matplotlib 3.11.2 and Pillow 13.0.0; Figure 2 of `evaluate_harmonisation.py` and the figures of `evaluate_extensions.py`, `dist_exhibit.py`, `evaluate_extensions_r6.py` and `output_vintage/`: matplotlib 3.10.9 and Pillow 12.2.0), and other versions draw the same figures with different bytes.
