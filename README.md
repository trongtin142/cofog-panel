# COFOG-Panel

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![tests](https://github.com/trongtin142/cofog-panel/actions/workflows/tests.yml/badge.svg)](https://github.com/trongtin142/cofog-panel/actions/workflows/tests.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23511907.svg)](https://doi.org/10.5281/zenodo.23511907)

COFOG-Panel builds a country-year panel for any COFOG division or group from a raw Excel extract of the IMF Government Finance Statistics (GFS) dataset on expenditure by function of government. Countries report these data for different sets of government subsectors. The tool selects one value per country-year with a documented three-tier rule and records, next to every value, the tier, the sectors that entered it and whether it covers every level of government.

The DOI badge points to all versions of the software. Each release also has its own DOI, listed on the Zenodo page and in `CITATION.cff`.

## 1. How it works

The pipeline runs on local Excel files in five stages. Each stage is a sub-command, and `cofog-panel run` runs all five.

| Stage | Command | Module | Purpose |
| :--- | :--- | :--- | :--- |
| 1 | `check-format` | `checks.py` | Checks the IMF metadata columns and the year columns (no gaps, from 1972) of the extract |
| 2 | `check-country-format` | `checks.py` | Checks the country lookup (`name`, `alpha-2`, `alpha-3`, `country-code`, no repeated alpha-3) |
| 3 | `seed-master` | `master_seed.py` | Writes the master panel: one row per country and year, `SortKey` = ISO3 + year, 1972–2025 by default |
| 4 | `split` | `etl.py` | Keeps one transformation and one COFOG function and writes one file per country |
| 5 | `aggregate` | `aggregate.py` | Applies the selection rule and adds the values and their provenance to the master |

### Selection rule (`--sector "General government"`, the default)

| Tier | Value used |
| :--- | :--- |
| T1 | General government (GG), if reported |
| T2 | otherwise, if central government including social security (CGSS) is reported: CGSS + state + local |
| T3 | otherwise: central government excluding social security (or, if that is not reported, budgetary + extrabudgetary central government) + social security funds + state + local, over the sectors reported |

T2 and T3 are unconsolidated sums: transfers between levels of government (and, in T3, between central government units) that are recorded under the same function are counted twice. Two other methods are available: `--sector "Central government including social security"` (C1 = CGSS, C2 = central core + social security funds) and any single sector name (D = that sector alone).

### Output columns

| Column | Content |
| :--- | :--- |
| `SortKey`, `Country`, `Year` | Panel keys |
| `--data-col` (default `DATA_NEW`) | Selected value, as a number |
| `--tier-col` (default `SOURCE_TIER`) | T1, T2, T3, C1, C2 or D |
| `--sectors-col` | Sectors that entered the value, e.g. `CGSS+LG` or `BCG+SG` |
| `--complete-col` | `Y` or `N` (see below) |

The sectors and completeness columns take their names from the data column unless they are given: `--data-col DATA_ENV` writes `SOURCE_SECTORS_ENV` and `SOURCE_COMPLETE_ENV`, so that several indicators in one master keep separate provenance. The default data column `DATA_NEW` writes `SOURCE_SECTORS` and `SOURCE_COMPLETE`, as in earlier versions. Give each indicator its own `--tier-col` as well (e.g. `--tier-col TIER_ENV`). The tool warns when a run would replace a column that is already in the master.

Completeness: a T2, T3 or C2 sum is `N` when it leaves out a level (state, local, social security funds, extrabudgetary central government) that the country reports in another year of the same series, or the central core. A T1 value is `N` when GG equals CGSS exactly while state or local government report positive spending in that year.

Further rules: reported zeros are kept unless `--zero-as-missing` is given; shares of total outlays are never summed, so they only give T1 values; the IMF codes KOS and WBG are mapped to the ISO codes XKX and PSE.

## 2. Installation

```bash
git clone https://github.com/trongtin142/cofog-panel.git
cd cofog-panel
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -e .                  # the command-line tool
pip install -e ".[dev]"           # adds pytest, to run the tests
pip install -e ".[replication]"   # adds statsmodels and matplotlib, for the scripts in replication/
```

Python 3.10 or later is required. `cofog-panel --version` prints the installed version.

## 3. Usage

Download the GFS COFOG dataset as Excel from the [IMF data portal](https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG) and save it as `data/gfs_raw_data.xlsx`. The file is not part of the repository because the IMF terms of use apply to it (see `DATA_LICENSE.md`).

All five stages, environmental protection, per cent of GDP:

```bash
cofog-panel run --source-file data/gfs_raw_data.xlsx --lookup-file data/country_codes.xlsx \
  --cofog "05" --filter-type "Percent of GDP" --data-col DATA_ENV --tier-col TIER_ENV
```

A second indicator is added to the same master by running the command again with other column names, e.g. `--cofog "07" --data-col DATA_HEALTH --tier-col TIER_HEALTH`. An existing master is kept and the new columns are added to it. `--overwrite-master` rebuilds the master from the lookup file instead, which deletes the indicator columns it holds; the tool prints a warning when it does so.

Options:

* `--cofog` takes a division or group code (`05`, `07.3`) or the exact label used in the file (`"Environmental protection"`). A value that is neither is rejected at once, with the closest codes or labels.
* `--filter-type` is one of `"Percent of GDP"`, `"Domestic currency"` and `"Percent of total outlays"`, in any letter case. Any other value is rejected at once.
* `--sector` selects the method described in Section 1.

These checks run before the extract is read, so a mistake is reported within a second rather than after the scan of the whole file.

Single stages:

```bash
cofog-panel check-format --source-file data/gfs_raw_data.xlsx
cofog-panel check-country-format --lookup-file data/country_codes.xlsx
cofog-panel seed-master --lookup-file data/country_codes.xlsx --output-dir output
cofog-panel split --source-file data/gfs_raw_data.xlsx --cofog "07" --output-dir intermediate_splits
cofog-panel aggregate --master-file output/COFOG_MASTER_SCHEMA.xlsx --folder-path intermediate_splits \
  --data-col DATA_HEALTH --tier-col TIER_HEALTH
```

`seed-master` always writes a new master, replacing a file of the same name. `split` writes only into a new or empty directory, or into one it created earlier (marked by a `.cofog_panel_split` file), where it replaces the country files of its previous run; it never deletes files elsewhere. `aggregate` ends with a non-zero exit code if any country file cannot be read.

The selection rule can be called from Python:

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
pip install -e ".[dev]"
pytest
```

## 5. Data

`data/country_codes.xlsx` is an ISO 3166 lookup with Kosovo (XKX) added. The IMF GFS data are not covered by the MIT License: `DATA_LICENSE.md` gives the IMF terms, the required attribution and the notice on transformed data.

## 6. Replication

`replication/` holds the scripts that reproduce the published analyses that use COFOG-Panel, each with its own README. They need the `[replication]` extra.

## 7. Citation

See `CITATION.cff`. Please cite the DOI of the release you used.
