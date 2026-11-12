# COFOG-Panel

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/trongtin142/cofog-panel/blob/main/LICENSE.txt)
[![tests](https://github.com/trongtin142/cofog-panel/actions/workflows/tests.yml/badge.svg)](https://github.com/trongtin142/cofog-panel/actions/workflows/tests.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23511907.svg)](https://doi.org/10.5281/zenodo.23511907)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/trongtin142/cofog-panel/blob/v1.2.0/cofog.ipynb)

COFOG-Panel builds a country-year panel for any COFOG division or group from a raw download (CSV or Excel) of the IMF Government Finance Statistics (GFS) dataset on expenditure by function of government. Countries report these data for different sets of government subsectors. The tool selects one value per country-year with a documented three-tier rule and records, next to every value, the tier, the sectors that entered it and whether it covers every level of government. A sheet `Provenance` in the output records the source file and its SHA-256, the IMF release date, the version and the command. The tool runs from the command line, in a browser page or from Python (`cofog_panel.build_panel`).

The DOI badge points to all versions of the software. Each release also has its own DOI, listed on the Zenodo page and in `CITATION.cff`. The Colab badge opens the notebook `cofog.ipynb` of release 1.2.0 in Google Colab, and the notebook installs that same tagged release.

## Quickstart (GUI)

For users who prefer a graphical interface (a browser page, no command line options to remember):

1. Install Python 3.10 or later from [python.org](https://www.python.org/) (on Windows, tick "Add Python to PATH").
2. Get the repository: on GitHub, **Code** > **Download ZIP**, or the archive of a release on Zenodo, and unzip it. On Windows, unzip it to a short path such as `C:\cofog-panel` (see the note on long paths below).
3. Start the application from that folder: on macOS or Linux run `bash run_gui.sh`, on Windows double-click `run_gui.bat`. The script creates a `.venv` folder, installs the package with the `gui` extra (`pip install -e ".[gui]"`, which adds Streamlit 1.49 or later) and opens the page.
4. In the page, upload the IMF file (or the sample `data/sample/gfs_cofog_073_sample.csv`, with COFOG 07.3), choose the COFOG function, method and transformation in the sidebar, and click **Run Pipeline**. Download the master when it finishes. The page shows the reports and warnings of the stages (the same text the command line prints) in a run log, and the reason when a stage fails.

With the package installed (`pip install "cofog-panel[gui]"`, or `pip install -e ".[gui]"` in a clone), `cofog-panel gui` starts the same page, from any folder; `--port` and `--headless` set the port and keep the browser closed. The page is part of the package (`cofog_panel/gui.py`); `gui.py` at the root of the repository starts it for `streamlit run gui.py` and the launch scripts.

The GUI runs the same five stages as `cofog-panel run` for one COFOG function from the built-in list, with the default column names, and writes the same `Provenance` sheet. It does not offer `--zero-as-missing`, `--check-ranges`, several functions, `--split-dir` or a country lookup in another format than `.xlsx`; use the command line for those. Each run builds a new master with one indicator: uploaded files and the result live in a temporary folder that is deleted when the run ends, so download the master from the page. To collect several indicators in one master, use `cofog-panel run` (Section 3).

## Quickstart (command line)

**1. Install** (Python 3.10 or later):

```bash
git clone https://github.com/trongtin142/cofog-panel.git
cd cofog-panel
pip install -e .
```

On Windows, clone into a short path such as `C:\cofog-panel`, because Windows limits paths to 260 characters unless long paths are enabled.

**2. Try it on the sample** (seconds, no download):

```bash
cofog-panel run --cofog 07.3 --source-file data/sample/gfs_cofog_073_sample.csv --output-dir output/sample --split-dir output/sample/splits
```

`data/sample/gfs_cofog_073_sample.csv` (2.2 MB) holds the rows of the IMF release of 3 February 2026 for COFOG group 07.3 (hospital services) in per cent of GDP, for every country and sector, in the format of the IMF download. The command prints the SHA-256 of the file and writes `output/sample/COFOG_MASTER_SCHEMA.xlsx` (a folder of its own, so that the sample does not end up in the master of your own data): 2,437 filled country-years (T1 1,346, T2 300, T3 791; 633 flagged incomplete), the same as from the full February extract. `data/sample/README.md` gives its source, checksum and terms of use. Without a clone, download that one file from the repository (or from the archive of the release) and give its path.

**3. Download the IMF data** (once, a CSV file of about 530 MB for the release of 21 October 2026):

1. Open the dataset page <https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG> ("GFS Government Expenditures by Function").
2. Click **DOWNLOAD** (top right). A "Download Dataset" window opens.
3. Keep the defaults: **Download full dataset** switched on, **File Format: CSV**, **Data format: Timeseries per row**. Click **DOWNLOAD** in the window.
4. The browser saves a file named like `dataset_2026-..._IMF.STA_GFS_COFOG_11.0.0.csv`. Move it to the `data` folder of the repository and rename it `gfs_raw_data.csv`.

An Excel download (`data/gfs_raw_data.xlsx`) works as well and is used when both files exist; the CSV file is read much faster.

The portal serves the current release only. To work with the release of 3 February 2026, on which the published results and the examples below rest, download the archived copy `imf_gfs_cofog_2026-02-03.xlsx` from its Zenodo record, <https://doi.org/ZENODO_DATA_DOI> (an unaltered copy of the IMF Excel download under the IMF terms, 58,389,314 bytes, SHA-256 `91e3db1bdb838f322dcbe648b133f511f3efe1921e50c8bc0d7621f512668cfe`), and save it as `data/gfs_raw_data.xlsx`.

**4. Run** one command, here for environmental protection (COFOG 05):

```bash
cofog-panel run --cofog 05
```

The panel is written to `output/COFOG_MASTER_SCHEMA.xlsx` (sheet `MasterData`, with the sheet `Provenance` next to it). Five rows of the result:

| SortKey | Country | Year | DATA_05 | SOURCE_TIER_05 | SOURCE_SECTORS_05 | SOURCE_COMPLETE_05 |
| :--- | :--- | ---: | ---: | :--- | :--- | :--- |
| ARG2002 | Argentina | 2002 | 0.018 | T2 | CGSS+SG | Y |
| ARM2012 | Armenia | 2012 | 0.404 | T3 | BCG+LG | N |
| ARM2013 | Armenia | 2013 | 0.349 | T1 | GG | Y |
| ARM2014 | Armenia | 2014 | 0.097 | T3 | BCG | N |
| DEU2015 | Germany | 2015 | 0.541 | T1 | GG | Y |

Values are in per cent of GDP (rounded here; the file keeps all digits). They come from the release published on 3 February 2026; a later download gives revised values.

To reproduce these rows, run the command on the Excel download of the release of 3 February 2026 (SHA-256 `91e3db1bdb838f322dcbe648b133f511f3efe1921e50c8bc0d7621f512668cfe`, recorded in `replication/harmonisation/README.md`). The IMF has since replaced that release with revised values, so the portal now serves a different file; the February extract is archived at <https://doi.org/ZENODO_DATA_DOI> (step 3 above).

* **T1**: general government (GG) as reported. **T2**: central government including social security (CGSS) plus the state and local levels that are reported. **T3**: the central government components (budgetary BCG, extrabudgetary EBCG, social security funds SSF) plus state (SG) and local (LG) government, when neither GG nor CGSS is reported.
* **Y / N**: `Y` when the value covers every level of government that the country reports in its series; `N` when a level is missing (Armenia 2014 lacks the local level it reports in other years), so the value understates spending.

Other useful commands: `cofog-panel list-cofog` lists the COFOG codes and labels in the file, `cofog-panel list-sectors` the accepted `--sector` and `--filter-type` values, and `cofog-panel run --help` all options.

## 1. How it works

The pipeline runs on local files (an Excel master and one CSV file per country between stages 4 and 5) in five stages. Each stage is a sub-command, and `cofog-panel run` runs all five.

| Stage | Command | Module | Purpose |
| :--- | :--- | :--- | :--- |
| 1 | `check-format` | `checks.py` | Checks the IMF metadata columns and the year columns (no gaps, from 1972) of the extract; unknown extra columns give a warning, not an error |
| 2 | `check-country-format` | `checks.py` | Checks the country lookup (`name`, `alpha-2`, `alpha-3`, `country-code`; every alpha-3 is three letters, none repeated; `seed-master` applies the same check) |
| 3 | `seed-master` | `master_seed.py` | Writes the master panel: one row per country and year, `SortKey` = ISO3 + year, 1972–2025 by default; `--start-year` must not be after `--end-year` |
| 4 | `split` | `etl.py` | Lists the countries of the extract that have no row in the lookup (`--lookup-file`, default the bundled one; a warning, the files are still written). Keeps one transformation and one COFOG function and writes one CSV file per country (`AAA.csv`; splits with `.xlsx` country files from versions up to 1.0.5 are still read by `aggregate`) |
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
| `--tier-col` (default `SOURCE_TIER_<suffix>`) | T1, T2, T3, C1, C2 or D |
| `--sectors-col` (default `SOURCE_SECTORS_<suffix>`) | Sectors that entered the value, e.g. `CGSS+LG` or `BCG+SG` |
| `--complete-col` (default `SOURCE_COMPLETE_<suffix>`) | `Y` or `N` (see below) |

The data column is named after the COFOG code unless it is given: `--cofog 05` writes `DATA_05`, `--cofog 07.3` writes `DATA_07_3`, and a label is mapped to its code. The tier, sectors and completeness columns take the suffix of the data column (`DATA_05` gives `SOURCE_TIER_05`, `SOURCE_SECTORS_05` and `SOURCE_COMPLETE_05`), so that several indicators in one master keep separate provenance. A data column given as `DATA_NEW` writes `SOURCE_TIER`, `SOURCE_SECTORS` and `SOURCE_COMPLETE`, as in earlier versions. The tool warns when a run would replace a column that is already in the master.

Completeness: a T2, T3 or C2 sum is `N` when it leaves out a level (state, local, social security funds, extrabudgetary central government) that the country reports in another year of the same series, or the central core. A T1 value is `N` when GG equals CGSS exactly while state or local government report positive spending in that year.

Further rules: reported zeros are kept unless `--zero-as-missing` is given; `--check-ranges` (`aggregate`, `run`) lists selected values that are negative, or above 100 for percentage transformations, and keeps them; shares of total outlays are never summed, so they only give T1 values; the IMF codes KOS and WBG are mapped to the ISO codes XKX and PSE. Values in domestic currency are added only when the series of a country agree in `SCALE`, `UNIT` and `CURRENCY` (letter case ignored); otherwise the country gets reported values only (T1, C1, D) and `aggregate` prints a warning.

### Provenance sheet

`run` (and the browser interface and `build_panel`) adds a sheet `Provenance` to the master, next to `MasterData`. Each run adds one row per COFOG function, and the rows of earlier runs on the same master are kept:

| Column | Content |
| :--- | :--- |
| `Run`, `Time (UTC)` | Run number in this master and time of the run, e.g. `2026-11-12T20:15:03Z` |
| `cofog-panel version` | Version of the package that wrote the columns |
| `Command`, `Options` | The command as typed, and the value of every option, defaults included (paths as given) |
| `Source file`, `Source SHA-256`, `Source size (bytes)` | Name, SHA-256 checksum (computed by the tool) and size of the IMF file that was read |
| `PUBLICATION_DATE` | The IMF release date of the selected series, read from the file |
| `COFOG`, `Transformation`, `Method (--sector)` | The function, transformation and method of the row |
| `Columns created` | The data, tier, sectors and completeness columns written for it |

`run` also prints the SHA-256 of the source file. Report it with the `PUBLICATION_DATE` when you cite the data: the IMF revises the dataset in place (Section 5). `MasterData` is the same as without the sheet, cell for cell. `cofog_panel.read_provenance(path)` reads the sheet into a DataFrame.

## 2. Installation

```bash
git clone https://github.com/trongtin142/cofog-panel.git
cd cofog-panel
python -m venv venv
source venv/bin/activate          # macOS and Linux
pip install -e .                  # the command-line tool
pip install -e ".[dev,gui]"       # adds pytest and Streamlit, to run all the tests (Section 4)
pip install -e ".[gui]"           # adds Streamlit, for the browser interface (cofog-panel gui)
pip install -e ".[replication]"   # adds statsmodels, scipy, matplotlib, linearmodels and tabulate, for replication/
```

`cofog-panel --version` prints the installed version.

A tagged release also installs without a clone, from the tag (`pip install "git+https://github.com/trongtin142/cofog-panel@v1.2.0"`) or from PyPI (`pip install cofog-panel`); add the `gui` extra for the browser interface (`pip install "cofog-panel[gui]"`, then `cofog-panel gui`). The sample extract, the tests and `replication/` come with the repository.

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

A second indicator is added to the same master by running the command again: `cofog-panel run --cofog 07` adds `DATA_07`, `SOURCE_TIER_07`, `SOURCE_SECTORS_07` and `SOURCE_COMPLETE_07`. An existing master is kept and the new columns are added to it. `--overwrite-master` rebuilds the master from the lookup file instead, which deletes the indicator columns it holds; the tool prints a warning when it does so.

Several functions can be added in one command by repeating the option: `cofog-panel run --cofog 05 --cofog 07`. Stages 1-3 run once; stages 4 and 5 run for each function in turn, so the source file is read once per function. Each function gets its own split directory (`intermediate_splits/05`, `intermediate_splits/07`) and its own `DATA_<code>` and provenance columns, exactly as if `run` had been called once per function. All `--cofog` values are checked before any file is written. `--data-col`, `--tier-col`, `--sectors-col` and `--complete-col` cannot be combined with several `--cofog` values, and two values that name the same function are refused.

Options:

* `--cofog` takes a division or group code (`05`, `07.3`) or a label used in the file, in any letter case (`"Environmental protection"` or `"environmental protection"`). A value that is neither is rejected at once, with the closest codes or labels. `cofog-panel list-cofog` lists the codes and labels in the file with two counts (it reads the whole file: seconds for the CSV download, about a minute for the Excel one). `Countries` counts the countries with at least one value for the code, and `Listed` the countries with a series for it, with or without values. A well-formed code that is not in the built-in list (for example `07.99`) is also looked up in the file before the scan and rejected, with the nearest codes, if the file has no series for it; for an Excel download this takes under a second, for a CSV download a few seconds.
* `--filter-type` is one of `"Percent of GDP"`, `"Domestic currency"` and `"Percent of total outlays"`, in any letter case. Any other value is rejected at once.
* `--sector` selects the method described in Section 1, in any letter case; `cofog-panel list-sectors` lists the accepted values.

These checks run before the extract is read, so a mistake is reported within seconds rather than after the scan of the whole file.

Single stages:

```bash
cofog-panel check-format                              # data/gfs_raw_data.xlsx or .csv by default
cofog-panel check-country-format                      # the bundled lookup by default
cofog-panel seed-master --output-dir output
cofog-panel split --cofog "07" --output-dir intermediate_splits
cofog-panel aggregate --master-file output/COFOG_MASTER_SCHEMA.xlsx --folder-path intermediate_splits
```

`seed-master` always writes a new master, replacing a file of the same name. `split` writes only into a new or empty directory, or into one it created earlier (marked by a `.cofog_panel_split` file that also records the COFOG function, the `PUBLICATION_DATE` of the selected series and the extract's year span), where it replaces the country files of its previous run; it never deletes files elsewhere. `split` warns about rows of the transformation whose series code gives no COFOG function; the series of other indicators that the extract also carries (such as total outlays, `TOA_T` and `TOTOUT_T`), which have an empty `COFOG` label, are skipped without a warning. `aggregate` names the data column after the function recorded by `split` (`DATA_07` here) unless `--data-col` is given; a `--data-col` of the form `DATA_<code>` for another function than the recorded one gives a warning.

### Errors and exit codes

Every error prints one line on what went wrong and one line starting with `Hint:` on how to fix it, for example:

```text
❌ Error: Invalid --filter-type 'per cent of GDP'.
   Hint: Choose one of: 'Percent of GDP', 'Domestic currency', 'Percent of total outlays' (letter case does not matter).
```

Unexpected errors are reported in the same form; `cofog-panel --debug <command> ...` shows the full traceback instead. Exit codes: `0` success, `1` data or option error (missing file, invalid `--cofog`, `--filter-type` or `--sector`, unusable split directory, unreadable country files), `2` command-line usage error (unknown option, missing `--cofog`).

### Python

`build_panel` runs the five stages of `cofog-panel run` in a temporary folder and returns the panel as a pandas DataFrame in tidy form: one row per country, year and function with a value, with the provenance of each value. Its values are those of the master that `run` writes for the same file and options.

```python
from cofog_panel import build_panel

panel = build_panel("data/sample/gfs_cofog_073_sample.csv", "07.3")
panel.head()
#   iso3  country  year cofog     value tier sectors complete
panel["tier"].value_counts()          # T1 1346, T3 791, T2 300
panel.attrs["provenance"][0]["Source SHA-256"]
```

Signature: `build_panel(source, cofog, *, start_year=1972, end_year=2025, zero_as_missing=False, filter_type="Percent of GDP", sector="General government", lookup_file=None, keep_empty=False, verbose=False)`. `cofog` is a code or label, or a list of them (one block of rows each); the other arguments mean what the options of `run` mean. Columns: `iso3`, `country`, `year`, `cofog`, `value`, `tier`, `sectors`, `complete`. `keep_empty=True` keeps the country-years without a value (every row of the master). `panel.attrs["provenance"]` holds the rows of the `Provenance` sheet (version, source file and SHA-256, `PUBLICATION_DATE`, options). An invalid option raises `cofog_panel.options.OptionError` (a `ValueError`, with the same message as the command line), a missing file `FileNotFoundError`, and a stage that fails `cofog_panel.PipelineError`, whose `log` attribute holds the reports of the stages; `verbose=True` prints them.

The selection rule itself can also be called from Python:

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
pip install -e ".[dev,gui]"
python -m pytest
```

Run the tests from the repository root. The `gui` extra adds Streamlit, which the tests of the browser interface (`tests/test_gui.py`) need. Without it, these tests are skipped. `tests/test_sample.py` runs the pipeline on the sample extract and checks example rows and tier counts against the full February 2026 extract.

## 5. Data

The source file can be the CSV or the Excel download of IMF.STA:GFS_COFOG; both have the same columns and give the same panel. The IMF revises the dataset in place: a download made on 21 October 2026 still carries the version number 11.0.0 but has a new `PUBLICATION_DATE` and revised values. Keep the downloaded file with your results and report its `PUBLICATION_DATE` (a column of the file) when you cite the data. An unaltered copy of the release of 3 February 2026 is archived at <https://doi.org/ZENODO_DATA_DOI> (file `imf_gfs_cofog_2026-02-03.xlsx`); save it as `data/gfs_raw_data.xlsx` to reproduce results based on that release. `split` warns if the selected series carry several dates, and `aggregate` prints the date it recorded.

`data/sample/gfs_cofog_073_sample.csv` is a small extract of the release of 3 February 2026 (COFOG group 07.3 in per cent of GDP, all countries and sectors), distributed under the IMF terms with its checksum and source in `data/sample/README.md`, for trying the tool and for the tests.

The country lookup (`data/country_codes.xlsx`, also bundled in the package as `cofog_panel/data/country_codes.xlsx`) is an ISO 3166 lookup with Kosovo (XKX) added. The IMF GFS data are not covered by the MIT License: `DATA_LICENSE.md` gives the IMF terms, the required attribution and the notice on transformed data.

## 6. Replication

`replication/` holds the scripts that reproduce the analyses that use COFOG-Panel, each with its own README listing commands, runtimes and outputs. They need the `[replication]` extra. `replication/harmonisation/` reproduces the harmonisation study, its further analyses (recording of consolidation, grant flows) and the redistributive effect of health and education spending; `replication/environment/` reproduces the environmental-spending study.

## 7. Feedback and testing

Reports from users help improve the tool. After a run, please open a short [test report](https://github.com/trongtin142/cofog-panel/issues/new?template=test_report.yml) (version, operating system, command, outcome and what was unclear). Problems go in a [bug report](https://github.com/trongtin142/cofog-panel/issues/new?template=bug_report.yml), and questions or ideas in [Discussions](https://github.com/trongtin142/cofog-panel/discussions). `CONTRIBUTING.md` describes the development setup, pull requests and releases.

## 8. Citation

See `CITATION.cff`. Please cite the DOI of the release you used.

## 9. Authors and acknowledgements

COFOG-Panel is developed by Trong Tin Nguyen and Thanh-Tung Pham. Thanh-Tung Pham wrote the early prototype of the pipeline (March 2026), from which this repository grew, and, in version 1.1.0, the browser interface and the input validation. Cam Quyen Tran (GitHub `qynntrn`) contributed to an early version of the code (the `--sector` option and the notebook) and gave helpful comments.
