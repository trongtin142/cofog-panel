# Data licences

The **code** in this repository is released under the MIT License (see `LICENSE.txt`). The MIT License does **not** apply to the data described below.

## IMF Government Finance Statistics (`data/gfs_raw_data.csv` or `.xlsx`, not distributed)

Source: International Monetary Fund, Government Finance Statistics: Expenditure by Function of Government (GFS_COFOG), dataset IMF.STA:GFS_COFOG version 11.0.0, published 3 February 2026, https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG

The data are © International Monetary Fund and are used under the IMF's terms for statistical data (https://www.imf.org/en/About/copyright-and-terms, "Special Terms for Statistical Data"). These terms allow users to extract, copy, publish and distribute the data, provided that the data appear accurately with attribution to the IMF as the source, that they are not altered in a way that affects their nature or accuracy, and that any material transformation is stated with the source citation. Commercial reuse requires permission from the IMF (copyright@imf.org). Whoever passes on IMF data from this repository should keep this attribution and these conditions with it.

**Transformation notice.** Values produced by COFOG-Panel in tiers T2, T3 and C2 are *not* IMF figures: they are unconsolidated sums of IMF subsector values computed by this software. Their provenance is recorded in the tier, sectors and completeness columns written next to each indicator (for example `SOURCE_TIER_05`, `SOURCE_SECTORS_05` and `SOURCE_COMPLETE_05`). T1, C1 and D values are IMF values as published. The sheet `Provenance` of the master records the source file, its SHA-256 and the IMF `PUBLICATION_DATE`.

The full IMF extract is not included in the repository. Users download it from the IMF portal and save it as `data/gfs_raw_data.csv` or `data/gfs_raw_data.xlsx` (see `README.md`). The IMF revises the dataset in place: the release of 21 October 2026 keeps the version number 11.0.0. Keep the file used for a study and report its `PUBLICATION_DATE`.

## IMF data distributed in the repository

Two small extracts of IMF data are distributed under the IMF terms above, for testing and replication. Both are subsets: rows (and, for the second, fields) are selected, and every value is copied as published, without any change.

- `data/sample/gfs_cofog_073_sample.csv`. Source: International Monetary Fund, Government Finance Statistics: Expenditure by Function of Government (GFS_COFOG), dataset IMF.STA:GFS_COFOG version 11.0.0, published 3 February 2026, https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG. The rows of COFOG group 07.3 (hospital services) in per cent of GDP, all countries and sectors, with all columns of the download, including the IMF's own licence and citation fields. `data/sample/README.md` describes it.
- `replication/harmonisation/data_ext/gfs_soo_grants_pcgdp.csv`. Source: International Monetary Fund, GFS Statement of Operations, dataset IMF.STA:GFS_SOO version 12.0.0, published 12 November 2026, https://data.imf.org/en/datasets/IMF.STA:GFS_SOO. Grants to and from other general government units and interest paid to them, by subsector, in per cent of GDP: the observations with a value of the query recorded in `replication/harmonisation/data_ext/SOURCES.md`, with the series key, the year and the value.

Results computed from them (sums across subsectors, ratios, tests) are not IMF figures.

## Country codes (`data/country_codes.xlsx`)

ISO 3166-1 country names and codes (alpha-2, alpha-3, numeric) with UN M49 regions, plus Kosovo (XKX, a user-assigned code used by the European Commission and others).

## Third-party data of `replication/environment/data_ext/lab/`

The Regional Authority Index, terrain ruggedness (Nunn and Puga 2012), CEDS emissions and the OECD SNG-WOFI functional data are not distributed: `replication/environment/fetch_data.py` downloads them from their sources. The other files of that folder are distributed under CC BY 4.0 or CC0 with attribution to their sources. Sources, URLs and licences: `replication/environment/data_ext/SOURCES.md`.

## Replication data (`replication/*/data_ext/`)

See `SOURCES.md` in each replication folder. In `replication/harmonisation/data_ext/`, the Eurostat series are reused with acknowledgement of the source (Commission Decision 2011/833/EU), and the World Bank WDI series, `ext_benchmarks_wdi.csv` (WDI series from the WHO Global Health Expenditure Database and the UNESCO Institute for Statistics) and `dist_inputs_wid_wdi.csv` (World Inequality Database through Our World in Data, and WDI) are distributed under CC BY 4.0 with attribution to their sources.
