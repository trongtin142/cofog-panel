# COFOG-Panel

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![tests](https://github.com/trongtin142/cofog-panel/actions/workflows/tests.yml/badge.svg)](https://github.com/trongtin142/cofog-panel/actions/workflows/tests.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23511907.svg)](https://doi.org/10.5281/zenodo.23511907)

COFOG-Panel builds a country-year panel for any COFOG division or group from a raw download (CSV or Excel) of the IMF Government Finance Statistics (GFS) dataset on expenditure by function of government. Countries report these data for different sets of government subsectors. The tool selects one value per country-year with a documented three-tier rule and records, next to every value, the tier, the sectors that entered it and whether it covers every level of government.

The DOI badge points to all versions of the software. Each release also has its own DOI, listed on the Zenodo page and in `CITATION.cff`.

## Quickstart in 3 steps

**1. Install** (Python 3.10 or later):

```bash
git clone https://github.com/trongtin142/cofog-panel.git
cd cofog-panel
pip install -e .
```

**2. Download the IMF data** (once, about 220 MB):

1. Open the dataset page <https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG> ("GFS Government Expenditures by Function").
2. Click **DOWNLOAD** (top right). A "Download Dataset" window opens.
3. Keep the defaults: **Download full dataset** switched on, **File Format: CSV**, **Data format: Timeseries per row**. Click **DOWNLOAD** in the window.
4. The browser saves a file named like `dataset_2026-..._IMF.STA_GFS_COFOG_11.0.0.csv`. Move it to the `data` folder of the repository and rename it `gfs_raw_data.csv`.

An Excel download (`data/gfs_raw_data.xlsx`) works as well and is used when both files exist; the CSV file is read much faster.

**3. Run** one command, here for environmental protection (COFOG 05):

```bash
cofog-panel run --cofog 05
```

The panel is written to `output/COFOG_MASTER_SCHEMA.xlsx` (sheet `MasterData`). Five rows of the result:

| SortKey | Country | Year | DATA_05 | SOURCE_TIER | SOURCE_SECTORS_05 | SOURCE_COMPLETE_05 |
| :--- | :--- | ---: | ---: | :--- | :--- | :--- |
| ARG2002 | Argentina | 2002 | 0.018 | T2 | CGSS+SG | Y |
| ARM2012 | Armenia | 2012 | 0.404 | T3 | BCG+LG | N |
| ARM2013 | Armenia | 2013 | 0.349 | T1 | GG | Y |
| ARM2014 | Armenia | 2014 | 0.097 | T3 | BCG | N |
| DEU2015 | Germany | 2015 | 0.541 | T1 | GG | Y |

Values are in per cent of GDP (rounded here; the file keeps all digits). They come from the release published on 3 February 2026; a later download gives revised values.

* **T1**: general government (GG) as reported. **T2**: central government including social security (CGSS) plus the state and local levels that are reported. **T3**: the central government components (budgetary BCG, extrabudgetary EBCG, social security funds SSF) plus state (SG) and local (LG) government, when neither GG nor CGSS is reported.
* **Y / N**: `Y` when the value covers every level of government that the country reports in its series; `N` when a level is missing (Armenia 2014 lacks the local level it reports in other years), so the value understates spending.

Other useful commands: `cofog-panel list-cofog` lists the COFOG codes and labels in the file, `cofog-panel list-sectors` the accepted `--sector` and `--filter-type` values, and `cofog-panel run --help` all options.

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
| `--data-col` (default `DATA_<COFOG code>`, e.g. `DATA_05`, `DATA_07_3`) | Selected value, as a number |
| `--tier-col` (default `SOURCE_TIER`) | T1, T2, T3, C1, C2 or D |
| `--sectors-col` (default `SOURCE_SECTORS_<suffix>`) | Sectors that entered the value, e.g. `CGSS+LG` or `BCG+SG` |
| `--complete-col` (default `SOURCE_COMPLETE_<suffix>`) | `Y` or `N` (see below) |

The data column is named after the COFOG code unless it is given: `--cofog 05` writes `DATA_05`, `--cofog 07.3` writes `DATA_07_3`, and a label is mapped to its code. The sectors and completeness columns take the suffix of the data column (`DATA_05` gives `SOURCE_SECTORS_05` and `SOURCE_COMPLETE_05`), so that several indicators in one master keep separate provenance. A data column given as `DATA_NEW` writes `SOURCE_SECTORS` and `SOURCE_COMPLETE`, as in earlier versions. Give each indicator its own `--tier-col` as well (e.g. `--tier-col TIER_05`). The tool warns when a run would replace a column that is already in the master.

Completeness: a T2, T3 or C2 sum is `N` when it leaves out a level (state, local, social security funds, extrabudgetary central government) that the country reports in another year of the same series, or the central core. A T1 value is `N` when GG equals CGSS exactly while state or local government report positive spending in that year.

Further rules: reported zeros are kept unless `--zero-as-missing` is given; shares of total outlays are never summed, so they only give T1 values; the IMF codes KOS and WBG are mapped to the ISO codes XKX and PSE.

## 2. Installation

```bash
git clone https://github.com/trongtin142/cofog-panel.git
cd cofog-panel
python -m venv venv
source venv/bin/activate          # macOS and Linux
pip install -e .                  # the command-line tool
pip install -e ".[dev]"           # adds pytest, to run the tests
pip install -e ".[replication]"   # adds statsmodels and matplotlib, for the scripts in replication/
```

`cofog-panel --version` prints the installed version.

### Windows (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .
```

If PowerShell refuses to run `Activate.ps1`, allow local scripts once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use `venv\Scripts\activate.bat` in the Command Prompt. Put paths that contain spaces in double quotes, and use a backtick (`` ` ``) instead of a backslash to continue a command on the next line:

```powershell
cofog-panel run --cofog 05 `
  --source-file "D:\WORKING PAPER\data\gfs_raw_data.xlsx" `
  --output-dir "D:\WORKING PAPER\output"
```

## 3. Usage

Defaults: `--source-file` is `data/gfs_raw_data.xlsx`, or `data/gfs_raw_data.csv` if there is no Excel file (relative to the current directory), `--lookup-file` is the country lookup bundled with the package, `--filter-type` is `"Percent of GDP"`, `--sector` is `"General government"` and the data column is named after the COFOG code. Only `--cofog` is required.

A second indicator is added to the same master by running the command again: `cofog-panel run --cofog 07 --tier-col TIER_07` adds `DATA_07`, `TIER_07`, `SOURCE_SECTORS_07` and `SOURCE_COMPLETE_07`. An existing master is kept and the new columns are added to it. `--overwrite-master` rebuilds the master from the lookup file instead, which deletes the indicator columns it holds; the tool prints a warning when it does so.

Options:

* `--cofog` takes a division or group code (`05`, `07.3`) or the exact label used in the file (`"Environmental protection"`). A value that is neither is rejected at once, with the closest codes or labels. `cofog-panel list-cofog` lists the codes and labels in the file with the number of countries (it reads the whole file: seconds for the CSV download, about a minute for the Excel one).
* `--filter-type` is one of `"Percent of GDP"`, `"Domestic currency"` and `"Percent of total outlays"`, in any letter case. Any other value is rejected at once.
* `--sector` selects the method described in Section 1; `cofog-panel list-sectors` lists the accepted values.

These checks run before the extract is read, so a mistake is reported within seconds rather than after the scan of the whole file.

Single stages:

```bash
cofog-panel check-format                              # data/gfs_raw_data.xlsx or .csv by default
cofog-panel check-country-format                      # the bundled lookup by default
cofog-panel seed-master --output-dir output
cofog-panel split --cofog "07" --output-dir intermediate_splits
cofog-panel aggregate --master-file output/COFOG_MASTER_SCHEMA.xlsx --folder-path intermediate_splits \
  --tier-col TIER_07
```

`seed-master` always writes a new master, replacing a file of the same name. `split` writes only into a new or empty directory, or into one it created earlier (marked by a `.cofog_panel_split` file that also records the COFOG function), where it replaces the country files of its previous run; it never deletes files elsewhere. `aggregate` names the data column after the function recorded by `split` (`DATA_07` here) unless `--data-col` is given.

### Errors and exit codes

Every error prints one line on what went wrong and one line starting with `Hint:` on how to fix it, for example:

```text
❌ Error: Invalid --filter-type 'per cent of GDP'.
   Hint: Choose one of: 'Percent of GDP', 'Domestic currency', 'Percent of total outlays' (letter case does not matter).
```

Unexpected errors are reported in the same form; `cofog-panel --debug <command> ...` shows the full traceback instead. Exit codes: `0` success, `1` data or option error (missing file, invalid `--cofog`, `--filter-type` or `--sector`, unusable split directory, unreadable country files), `2` command-line usage error (unknown option, missing `--cofog`).

### Python

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

The source file can be the CSV or the Excel download of IMF.STA:GFS_COFOG; both have the same columns and give the same panel. The IMF revises the dataset in place: a download made on 21 October 2026 still carries the version number 11.0.0 but has a new `PUBLICATION_DATE` and revised values. Keep the downloaded file with your results and report its `PUBLICATION_DATE` (a column of the file) when you cite the data.

The country lookup (`data/country_codes.xlsx`, also bundled in the package as `cofog_panel/data/country_codes.xlsx`) is an ISO 3166 lookup with Kosovo (XKX) added. The IMF GFS data are not covered by the MIT License: `DATA_LICENSE.md` gives the IMF terms, the required attribution and the notice on transformed data.

## 6. Replication

`replication/` holds the scripts that reproduce the published analyses that use COFOG-Panel, each with its own README. They need the `[replication]` extra.

## 7. Citation

See `CITATION.cff`. Please cite the DOI of the release you used.
