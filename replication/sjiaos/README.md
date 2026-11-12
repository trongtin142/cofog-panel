# Replication: harmonisation study

Reproduces all tables and figures of the harmonisation study (manuscript under review; the reference will be added on publication).

## Requirements

`pip install -e .[replication]` from the repository root (adds `statsmodels` and `matplotlib`). Tested with Python 3.14, pandas 3.0, statsmodels 0.14, matplotlib 3.10.

## Data

| File | Source |
| :--- | :--- |
| `data/gfs_raw_data.xlsx` (not in the repository; download it) | IMF GFS COFOG, dataset IMF.STA:GFS_COFOG 11.0.0 (published 3 February 2026), downloaded as Excel from the [IMF data portal](https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG) |
| `data_ext/eurostat_gov10a_exp_S13_TE_pcgdp.tsv` | Eurostat gov_10a_exp, S13, total expenditure, % of GDP, GF01–GF10 (SDMX API, downloaded 20 October 2026) |
| `data_ext/wb_NY.GDP.PCAP.PP.KD.json` | World Bank WDI, GDP per capita PPP (API, downloaded 20 October 2026) |
| `data_ext/wb_countries.json` | World Bank country metadata (ISO2 to ISO3 mapping) |

The IMF extract is not distributed with the repository. The script checks the downloaded file against the SHA-256 of the extract used in the article (`91e3db1bdb838f322dcbe648b133f511f3efe1921e50c8bc0d7621f512668cfe`) and warns if it differs. The IMF republished the dataset on 21 October 2026 under the same version number (11.0.0) with revised values; the article uses the release published on 3 February 2026, identified by the `PUBLICATION_DATE` column of the file (2026-02-03) and by the checksum above. A current download therefore gives different numbers. The exact extract is available from the author on request.

Licences and exact queries: `data_ext/SOURCES.md` and `../../DATA_LICENSE.md`.

## Run

```bash
python replication/sjiaos/evaluate_harmonisation.py
```

Outputs are written to `replication/sjiaos/output/`: `table1`–`table7` correspond to Tables 1–7 of the article, `supp_*` to the supplementary tables, `fig1`–`fig4` to Figures 1–4. The script calls `cofog_panel.resolve_value` and `cofog_panel.aggregate.is_complete`, the same functions used by the command-line tool. Runtime is about two minutes. Another extract can be evaluated with `--source FILE` (Excel or CSV) and `--out DIR`.

## Robustness to the IMF release (Supplementary Table S13)

Download the current release of IMF.STA:GFS_COFOG (CSV) as `data/gfs_raw_data_2026-10-21.csv` and run, after the script above:

```bash
python replication/sjiaos/compare_vintages.py --source data/gfs_raw_data_2026-10-21.csv
```

The script evaluates the second extract into `replication/sjiaos/output_vintage/` and writes `supp_vintage.csv` (Supplementary Table S13) to `replication/sjiaos/output/`: the main statistics of Tables 2, 4, 5 and 7 for both releases and their difference. The release used for S13 was published on 21 October 2026 (SHA-256 of the CSV download `886911700a5ff2a7076935b96d4d40a2751ae3a5003ea40dfbd24329c589ef36`). Runtime is about three minutes.

## Further analyses (`evaluate_extensions.py`)

The script imports `evaluate_harmonisation.py` from this folder and calls the package unchanged. It runs after or instead of that script, from the repository root:

```bash
python replication/sjiaos/evaluate_extensions.py [--source FILE] [--out DIR]
```

Requirements and inputs are those of `evaluate_harmonisation.py`: the February 2026 extract `data/gfs_raw_data.xlsx` (its SHA-256 is checked at the start, with a warning if it differs), `data/country_codes.xlsx` and `data_ext/`. Outputs go to `replication/sjiaos/output_ext/` by default:

- `ext_a1_*`, `ext_a2_*`, `ext_a3_*`: general government values against CGSS alone, complete T2 and T3 sums and spliced values on fixed samples for health, education, social protection and their sums, central against tiered values without general government by region, and the shortfall of health and education spending in percentage points of GDP.
- `ext_b0_*` to `ext_b4_*`: coverage of groups 01.7 and 01.8 by subsector, the gap in division 01 against the gap in group 01.8, group 01.8 where general government equals the subsector sum, recording practices by country, and checks of alternative readings. `ext_b_country_years.csv` holds the country-year detail.
- `ext_table3_region_09.csv`, `ext_fig1_coverage_09_counts.csv`, `fig1_coverage_09.png`: Table 3 and Figure 1 for education (COFOG 09).
- `ext_checks.csv`: agreement with Tables 3, 4 and 5 and Figure 1 of `evaluate_harmonisation.py`.

The script is deterministic: the country-cluster bootstrap uses 1,000 replications and seed 20260203. The first run takes about 90 seconds, most of it to read the Excel extract. Later runs take about 15 seconds, from a cache of the extract (`_ext_long_<sha>.pkl`) in the output folder, which `.gitignore` keeps out of the repository.
