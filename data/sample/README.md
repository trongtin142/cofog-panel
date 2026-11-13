# Sample extract: COFOG group 07.3, IMF release of 3 February 2026

`gfs_cofog_073_sample.csv` holds the rows of the IMF GFS COFOG download of 3 February 2026 for COFOG group 07.3 (hospital services) in per cent of GDP: every country and sector, with all 105 columns of the download. It lets you try COFOG-Panel in a minute, without the full download:

```bash
cofog-panel run --cofog 07.3 --source-file data/sample/gfs_cofog_073_sample.csv --output-dir output/sample --split-dir output/sample/splits
```

The sheet MasterData it gives is that of the full extract for this group, cell for cell: 2,437 filled country-years of 13,500 (T1 1,346, T2 300, T3 791; 633 flagged incomplete) in 135 countries. `tests/test_sample.py` checks these counts and six example rows with their provenance (one of each kind: T1, T2 and T3 values, complete and incomplete, a reported zero).

| | |
| :--- | :--- |
| File | `gfs_cofog_073_sample.csv`: 1,552 rows and a header row, 2,174,517 bytes |
| SHA-256 | `b5758935d1ecf7d449360cd5cdbf7d936970dba149ae4b86ccfcec99b8c40fc2` |
| Taken from | the Excel download of IMF.STA:GFS_COFOG 11.0.0, `PUBLICATION_DATE` 2026-02-03T08:39:08.886374500Z, SHA-256 `91e3db1bdb838f322dcbe648b133f511f3efe1921e50c8bc0d7621f512668cfe` |
| Rows kept | `SERIES_CODE` with function `GF073` and `TYPE_OF_TRANSFORMATION` "Percent of GDP" |
| Format | the layout of the portal's CSV download: UTF-8 with BOM, every field quoted, LF line ends |
| Made by | `python data/sample/make_sample.py data/gfs_raw_data.xlsx`, from the full download, which is archived at <https://doi.org/10.5281/zenodo.24192043> |

No value is changed. Numbers are written as COFOG-Panel reads them from the Excel file, in the shortest form that gives the same number, so the full digits of the download are kept. The IMF has since replaced this release with revised values (21 October 2026, same version number), so a current download gives other values.

## Source and terms of use

Source: International Monetary Fund, Government Finance Statistics: Expenditure by Function of Government (GFS_COFOG), dataset IMF.STA:GFS_COFOG version 11.0.0, published 3 February 2026, <https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG>.

The data are © International Monetary Fund and are distributed here as an unaltered subset under the IMF's terms for statistical data (<https://www.imf.org/en/About/copyright-and-terms>), which allow extracts to be copied and distributed with attribution to the IMF as the source. The MIT License of the code does not apply to this file. Commercial reuse requires permission from the IMF (<copyright@imf.org>). Values that COFOG-Panel computes from it in tiers T2, T3 and C2 are sums of IMF values, not IMF figures; see `DATA_LICENSE.md`.
