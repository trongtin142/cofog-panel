# Sources of the external data of the environmental-spending replication

Files marked "downloaded" are not distributed with the repository: `fetch_data.py` downloads them from the source and compares each with the SHA-256 of the copy used in the study (the checksums are in `fetch_data.py`). The other files are distributed here under the licence shown, with attribution to the source.

## World Bank (`data_ext/`)

| File | Source | Query | Downloaded | Licence |
| :--- | :--- | :--- | :--- | :--- |
| `wb_EN.ATM.PM25.MC.M3.json`, `wb_NY.GDP.PCAP.PP.KD.json`, `wb_NV.IND.TOTL.ZS.json`, `wb_SP.URB.TOTL.IN.ZS.json`, `wb_NE.TRD.GNFS.ZS.json`, `wb_EN.POP.DNST.json`, `wb_NY.GDP.TOTL.RT.ZS.json`, `wb_SP.POP.TOTL.json` | World Bank, World Development Indicators | World Bank API, indicator `<code>`, 1990–2024 | 20 October 2026 | CC BY 4.0. Source: World Bank, WDI. |
| `wb_AG.LND.TOTL.K2.json` | World Bank, World Development Indicators, land area | as above | 1 November 2026 | CC BY 4.0. Source: World Bank, WDI. |
| `wgi_GOV_WGI_GE.EST.json`, `wgi_GOV_WGI_CC.EST.json` | World Bank, Worldwide Governance Indicators | World Bank API, 1996–2024 | 20 October 2026 | CC BY 4.0. Source: World Bank, WGI. |
| `wb_NV.IND.MANF.ZS.json`, `wb_EG.EGY.PRIM.PP.KD.json`, `wb_TX.VAL.FUEL.ZS.UN.json` | World Bank, World Development Indicators: manufacturing value added; energy intensity of primary energy; fuel exports | World Bank API, indicator `<code>`, `per_page=20000` (SHA-256 in `CHECKSUMS_r5i.sha256`) | 3 November 2026 | CC BY 4.0. Source: World Bank, WDI. |
| `wgi_GOV_WGI_VA.EST.json`, `wgi_GOV_WGI_RQ.EST.json`, `wgi_GOV_WGI_RL.EST.json` | World Bank, Worldwide Governance Indicators: voice and accountability; regulatory quality; rule of law | World Bank API, source 3 (SHA-256 in `CHECKSUMS_r5i.sha256`) | 3 November 2026 | CC BY 4.0. Source: World Bank, WGI. |
| `wb_countries.json` | World Bank country metadata (codes, income groups) | API `country?per_page=400` | 20 October 2026 | CC BY 4.0. Source: World Bank. |

## Further data (`data_ext/lab/`)

| File | Source | URL | Downloaded | Licence | In repository |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `RAI_country-april-2021.xlsx` | Regional Authority Index, country file, April 2021 (Hooghe, Marks, Schakel et al. 2016; Shair-Rosenfield et al. 2021) | https://garymarks.web.unc.edu/wp-content/uploads/sites/13018/2021/04/RAI_country-april-2021.xlsx | 1 November 2026 | Public download with citation of the sources (https://garymarks.web.unc.edu/data/regional-authority-2/) | downloaded |
| `rugged/rugged_data.csv` | Terrain ruggedness, Nunn and Puga (2012), from `rugged_data.zip` | https://diegopuga.org/data/rugged/rugged_data.zip | 1 November 2026 | Terms of the authors' data page; cite Nunn and Puga (2012) | downloaded |
| `ceds/BC_…`, `ceds/OC_…`, `r3c/ceds/SO2_…`, `r3c/ceds/NOx_…`, `r3c/ceds/NH3_CEDS_estimates_by_country_sector_v_2025_03_18.csv` | Community Emissions Data System (CEDS), release v_2025_03_18, aggregate data, from `CEDS_v_2025_03_18_aggregate.zip` (Zenodo record 15059443) | https://zenodo.org/records/15059443 | 1 November 2026 | CC BY 4.0 (large files) | downloaded |
| `sngwofi/oecd_sng_wofi_cofog.csv` | OECD and UCLG, World Observatory on Subnational Government Finance and Investment (SNG-WOFI), subnational government functional expenditure (COFOG), dataflow `OECD.CFE.RDG:DSD_SNG_WOFI@DF_COFOG` version 1.0, CSV with labels | https://sdmx.oecd.org/public/rest/data/OECD.CFE.RDG,DSD_SNG_WOFI@DF_COFOG,1.0/all?format=csvfilewithlabels | 1 November 2026 | OECD terms and conditions | downloaded |
| `what_a_waste_country_level_data.csv` | World Bank, What a Waste Global Database, country-level data | https://datacatalogfiles.worldbank.org/ddh-published/0039597/DR0049199/country_level_data.csv | 1 November 2026 | CC BY 4.0. Source: World Bank, What a Waste Global Database. | yes |
| `HIEF_data.csv` | Historical Index of Ethnic Fractionalization, Drazanova (2019), Harvard Dataverse, doi:10.7910/DVN/4JQRCL | https://dataverse.harvard.edu/api/access/datafile/3476857?format=original | 1 November 2026 | CC0 1.0 | yes |
| `gbdmaps/41467_2021_23853_MOESM4_ESM.xlsx` | GBD-MAPS, McDuffie et al. (2021), Nature Communications 12:3594, Supplementary Data 1, https://doi.org/10.1038/s41467-021-23853-y | https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-021-23853-y/MediaObjects/41467_2021_23853_MOESM4_ESM.xlsx | 1 November 2026 | CC BY 4.0. Source: McDuffie et al. (2021). | yes |
| `r3c/wb_EG.CFT.ACCS.ZS.json`, `r3c/wb_EG.ELC.COAL.ZS.json` | World Bank, World Development Indicators: access to clean fuels and technologies for cooking; electricity production from coal | https://api.worldbank.org/v2/country/all/indicator/EG.CFT.ACCS.ZS?format=json&per_page=20000&date=1990:2024 (EG.ELC.COAL.ZS analogous) | 1 November 2026 | CC BY 4.0. Source: World Bank, WDI. | yes |
| `r3c/cckp_tas_cru408.json`, `r3c/cckp_pr_cru408.json` | World Bank Climate Change Knowledge Portal, CRU TS 4.08 country means of annual temperature and precipitation, 1901–2023 | https://cckpapi.worldbank.org/cckp/v1/cru-x0.5_timeseries_tas_timeseries_annual_1901-2023_mean_historical_cru_ts4.08_mean/all_countries?_format=json (`pr` analogous) | 1 November 2026 | CC BY 4.0. Source: World Bank CCKP; CRU TS 4.08 (University of East Anglia, Climatic Research Unit). | yes |
| `r3c/owid_burnt.csv` | Our World in Data, annual area burnt by wildfires, from the Global Wildfire Information System (GWIS) | https://ourworldindata.org/grapher/annual-area-burnt-by-wildfires.csv | 1 November 2026 | CC BY 4.0. Source: Our World in Data, based on GWIS. | yes |
