# Data licences

The **code** in this repository is released under the MIT License (see `LICENSE`). The MIT License does **not** apply to the data described below.

## IMF Government Finance Statistics (`data/gfs_raw_data.csv` or `.xlsx`, not distributed)

Source: International Monetary Fund, Government Finance Statistics: Expenditure by Function of Government (GFS_COFOG), dataset IMF.STA:GFS_COFOG version 11.0.0, published 3 February 2026, https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG

The data are © International Monetary Fund and are used under the IMF's terms for statistical data (https://www.imf.org/en/About/copyright-and-terms). Users must attribute the source as above, must not alter the data, and must state any transformation. Commercial reuse requires permission from the IMF (copyright@imf.org).

**Transformation notice.** Values produced by COFOG-Panel in tiers T2, T3 and C2 are *not* IMF figures: they are unconsolidated sums of IMF subsector values computed by this software. Their provenance is recorded in the tier, sectors and completeness columns written next to each indicator (for example `SOURCE_TIER_05`, `SOURCE_SECTORS_05` and `SOURCE_COMPLETE_05`). T1, C1 and D values are IMF values as published.

The IMF extract is not included in the repository. Users download it from the IMF portal and save it as `data/gfs_raw_data.csv` or `data/gfs_raw_data.xlsx` (see `README.md`). The IMF revises the dataset in place: the release of 21 October 2026 keeps the version number 11.0.0. Keep the file used for a study and report its `PUBLICATION_DATE`.

## Country codes (`data/country_codes.xlsx`)

ISO 3166-1 country names and codes (alpha-2, alpha-3, numeric) with UN M49 regions, plus Kosovo (XKX, a user-assigned code used by the European Commission and others).

## Replication data (`replication/*/data_ext/`)

See `SOURCES.md` in each replication folder.
