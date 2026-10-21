# Replication: subsector harmonisation of IMF GFS COFOG data

Reproduces all tables and figures of the article on subsector harmonisation of the IMF GFS COFOG data.

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

Outputs are written to `replication/sjiaos/output/`: `table1`–`table7` correspond to Tables 1–7 of the article, `supp_*` to the supplementary tables, `fig1`–`fig4` to Figures 1–4. The script calls `cofog_panel.resolve_value` and `cofog_panel.aggregate.is_complete`, the same functions used by the command-line tool. Runtime is about two minutes.
