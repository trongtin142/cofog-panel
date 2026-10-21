
# COFOG-Panel: Harmonizing IMF GFS COFOG Data into Reproducible Panel Datasets

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![tests](https://github.com/trongtin142/cofog-panel/actions/workflows/tests.yml/badge.svg)](https://github.com/trongtin142/cofog-panel/actions/workflows/tests.yml) [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23546439.svg)](https://doi.org/10.5281/zenodo.23546439)

COFOG-Panel turns a raw extract of the IMF Government Finance Statistics (GFS) dataset on expenditure by function of government (COFOG) into a country-year panel for any COFOG division or group. Countries report GFS COFOG data for different government subsectors; the tool selects one value per country-year with a documented three-tier rule and records, for every value, where it came from.

## 1. Overview

The pipeline runs locally on Excel files in five stages, each available as a sub-command; `cofog-panel run` executes all of them in sequence.

| Stage | Command | Module | What it does |
| :--- | :--- | :--- | :--- |
| 1 | `check-format` | `checks.py` | Checks the metadata columns and the year columns (contiguous from 1972) of the GFS extract |
| 2 | `check-country-format` | `checks.py` | Checks the country lookup file (`name`, `alpha-2`, `alpha-3`, `country-code`, no duplicates) |
| 3 | `seed-master` | `master_seed.py` | Creates an empty master panel (`SortKey` = ISO3 + year; 1972–2025 by default, `--start-year`/`--end-year`) |
| 4 | `split` | `etl.py` | Filters one transformation and one COFOG function, writes one file per country into a directory it owns |
| 5 | `aggregate` | `aggregate.py` | Applies the selection rule and writes values and traceability columns |

### Selection rule (`--sector "General government"`, default)

| Tier | Value used |
| :--- | :--- |
| T1 | General government (GG), if reported |
| T2 | otherwise, if Central government incl. social security (CGSS) is reported: CGSS + State + Local |
| T3 | otherwise: Central government excluding social security (or, if not reported, Budgetary + Extrabudgetary CG) + Social security funds + State + Local, over the reported sectors |

T2 and T3 are unconsolidated sums: transfers between the levels (and, in T3, between central units) that are recorded under the same function are counted twice. Other `--sector` values: `"Central government including social security"` (C1 = CGSS, C2 = central core + SSF) or any single sector name (D = that sector only).

### Output columns

| Column | Content |
| :--- | :--- |
| `SortKey`, `Country`, `Year` | Panel keys |
| `DATA_NEW` (or `--data-col`) | Selected value |
| `SOURCE_TIER` | T1, T2, T3, C1, C2 or D |
| `SOURCE_SECTORS` | Sectors that entered the value, e.g. `CGSS+LG`, `BCG+SG` |
| `SOURCE_COMPLETE` | `Y`/`N`. A T2/T3/C2 sum is `N` if it misses a level (State, Local, Social security funds, Extrabudgetary CG) that the country reports in another year of the series, or the central core. A T1 value is `N` if GG equals CGSS exactly while State or Local government report positive spending in that year. |

Further rules: reported zeros are kept unless `--zero-as-missing` is given; shares of total outlays are never summed (T1 only); IMF codes KOS and WBG are mapped to ISO XKX and PSE. Values are written as numbers. Running `aggregate` again on the same master keeps earlier columns; use different `--data-col`/`--tier-col` names for each indicator.

## 2. Installation

```bash
git clone https://github.com/trongtin142/cofog-panel.git
cd cofog-panel
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e .                # add [dev] to install pytest
```

Requires Python 3.10 or later. `cofog-panel --version` prints the installed version.

## 3. Usage

Download the GFS COFOG dataset from the [IMF data portal](https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG) as Excel and save it as `data/gfs_raw_data.xlsx`. The file is not included in the repository because the IMF terms of use apply to it (see `DATA_LICENSE.md`).

Full pipeline, environmental protection, per cent of GDP:

```bash
cofog-panel run --source-file data/gfs_raw_data.xlsx --lookup-file data/country_codes.xlsx \
  --cofog "05" --filter-type "Percent of GDP" --sector "General government" --data-col DATA_ENV
```

`--cofog` accepts a COFOG code (`05`, `07.3`) or the exact label used in the file (`"Environmental protection"`). `--filter-type` is one of `"Percent of GDP"`, `"Domestic currency"`, `"Percent of total outlays"`.

Individual stages:

```bash
cofog-panel check-format --source-file data/gfs_raw_data.xlsx
cofog-panel check-country-format --lookup-file data/country_codes.xlsx
cofog-panel seed-master --lookup-file data/country_codes.xlsx --output-dir output
cofog-panel split --source-file data/gfs_raw_data.xlsx --cofog "07" --output-dir intermediate_splits
cofog-panel aggregate --master-file output/COFOG_MASTER_SCHEMA.xlsx --folder-path intermediate_splits \
  --data-col DATA_HEALTH --sector "General government"
```

`split` writes only into an empty directory or one it created before (marked by a `.cofog_panel_split` file), and replaces the country files from its previous run there. It never deletes files in other directories. `aggregate` fails (non-zero exit) if any country file cannot be read.

The selection rule can also be called from Python:

```python
from decimal import Decimal
from cofog_panel import resolve_value

value, tier, sectors = resolve_value({
    "general government": None,
    "central government including social security": Decimal("0.5"),
    "local government": Decimal("0.3"),
})
# Decimal('0.8'), 'T2', ['central government including social security', 'local government']
```

## 4. Tests

```bash
pip install -e .[dev]
pytest
```

## 5. Data

`data/country_codes.xlsx` is an ISO 3166 lookup with Kosovo (XKX) added. The IMF GFS data are not covered by the MIT License: see `DATA_LICENSE.md` for the IMF terms, the required attribution and the transformation notice.

## 6. Citation

See `CITATION.cff`. If you use the software, please cite the release DOI.
