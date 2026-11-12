# Sources of the external data in this folder

| File | Source | Query | Downloaded | Licence |
| :--- | :--- | :--- | :--- | :--- |
| `eurostat_gov10a_exp_S13_TE_pcgdp.tsv` | Eurostat, General government expenditure by function (COFOG), `gov_10a_exp` | SDMX 2.1 API: `A.PC_GDP.S13.GF01+…+GF10.TE.` (general government, total expenditure, % of GDP) | 20 October 2026 | Reuse permitted with acknowledgement of the source (Commission Decision 2011/833/EU). Source: Eurostat (gov_10a_exp). |
| `wb_NY.GDP.PCAP.PP.KD.json` | World Bank, World Development Indicators, GDP per capita, PPP (constant 2021 international $) | API `country/all/indicator/NY.GDP.PCAP.PP.KD?date=1990:2024` | 20 October 2026 | CC BY 4.0. Source: World Bank, WDI. |
| `wb_countries.json` | World Bank country metadata (ISO2–ISO3 codes) | API `country?per_page=400` | 20 October 2026 | CC BY 4.0. Source: World Bank. |
| `gfs_soo_grants_pcgdp.csv` | International Monetary Fund, GFS Statement of Operations, dataset IMF.STA:GFS_SOO version 12.0.0, `PUBLICATION_DATE` 2026-11-12T08:00:28Z, https://data.imf.org/en/datasets/IMF.STA:GFS_SOO | SDMX 2.1 API of the IMF data portal, structure-specific XML: `data/IMF.STA,GFS_SOO,latest/...G26_S13U_T+G26C_S13U_T+G26K_S13U_T+G13_S13U_T+G24_S13U_T.POGDP_PT.A?startPeriod=1990&endPeriod=2024` (all countries and sectors; grants to other general government units, current and capital; grants from them; interest paid to them; % of GDP; annual) | 12 November 2026 (message prepared 2026-11-12T19:33:34Z) | © International Monetary Fund, used under the IMF terms (https://www.imf.org/en/About/copyright-and-terms); see `DATA_LICENSE.md`. Source: IMF, GFS Statement of Operations. |
| `dist_inputs_wid_wdi.csv` | World Inequality Database (WID.world), pre-tax national income per equal-split adult (`gptinc992j`, `sptinc992j`), through Our World in Data (dataset `wid/2026-06-18`, WID accessed 7 July 2026); World Bank, World Development Indicators: GDP (`NY.GDP.MKTP.CD`), GNI (`NY.GNP.MKTP.CD`) and consumption of fixed capital (`NY.ADJ.DKAP.CD`), current US$ | Built by `../fetch_inputs.py` from 24 Our World in Data indicator files (API `v1/indicators/<id>.data.json` and `.metadata.json`) and three WDI bulk CSV files (API `v2/en/indicator/<code>?downloadformat=csv`); every URL, size, SHA-256 and retrieval time is in `dist_inputs_manifest.csv` | 12 November 2026 | CC BY 4.0. Sources: World Inequality Database (via Our World in Data); World Bank, WDI. |

## Checksums and the filtered files

`evaluate_extensions.py` checks the SHA-256 of the grant file it reads (the CSV or the download) and warns if it differs.

| File | Rows | Bytes | SHA-256 | Made from |
| :--- | ---: | ---: | :--- | :--- |
| `gfs_soo_grants_pcgdp.csv` | 79,184 | 3,897,133 | `b17d090c2cbe192eb45bfa1459bccd85b34cab1444308831723d55509f46a3af` | the SDMX-ML download `gfs_soo_grants_pcgdp.xml` (38,049,436 bytes, SHA-256 `6315f830739cdbb2f9546bd1f553c314130feae156823acc27a69c3bf48cb18c`; not distributed, 38 MB), by `python replication/harmonisation/grants_sdmx.py gfs_soo_grants_pcgdp.xml`: every observation with a value, in the order of the download, with the series key, the year and the value as published. Observations without a value and the observation attributes are left out. `evaluate_extensions.py` gives the same outputs from the download and from this file. |
| `dist_inputs_wid_wdi.csv` | 7,324 | 256,691 | `1a591978b7a29be0642303d0404e134d2c51c4729053f1a9129be6efdb9d10b7` | the 27 downloads of `dist_inputs_manifest.csv`, by `fetch_inputs.py`: one row per country (ISO 3166-1 alpha-3) and year 1990–2023 with the Gini and bottom-50% share of pre-tax income (with and without WID interpolations and extrapolations) and net national income / GDP |
| `dist_inputs_manifest.csv` | 27 | 8,316 | `428d74719031796bd62eee4e7807874f3753caa9755aa989b8237a6dc012c4e9` | written by `fetch_inputs.py` during the download |

`.gitattributes` stores these files byte for byte, so their checksums hold on every platform.
