# Changelog

## Unreleased

Results are unchanged (selection rule untouched).

- `pyproject.toml` lists the issue tracker (`Issues` in `[project.urls]`), so the package page links to it. The README licence badge links to `LICENSE.txt` on GitHub instead of a relative path.

## Planned

- Cache: read the source Excel file once and keep a Parquet copy keyed by its SHA-256, with a `--no-cache` flag.
- One pass over the extract for several `--cofog` values (since 1.1.0 the extract is read once per value).
- Progress bar and summary table instead of one log line per country; `--quiet` and `--verbose` flags; no emoji, or safe handling of the console encoding on Windows.
- `--format xlsx|csv|parquet` and a `--long` option for long-format output.
- A `<master>.provenance.json` file (version, SHA-256 of the source, command run, time, columns created).
- High-level Python API `build_panel(...)` returning a DataFrame.
- "Open in Colab" badge for `cofog.ipynb` in the README.

## 1.1.0 (2026-11-01)

Results are unchanged (selection rule untouched): on the IMF extract of 3 February 2026, `run --cofog 05` and `run --cofog 07` give the same values, tiers, sectors and completeness flags as 1.0.5, and the SJIAOS replication gives the same tables as 1.0.5.

Authors: Thanh-Tung Pham is now an author of the software with Trong Tin Nguyen (`CITATION.cff`, `pyproject.toml`). The README credits him for the early prototype and, in this release, the browser interface and the input validation, and Cam Quyen Tran for contributions to an early version of the code.

- `check-format` (and stage 1 of `run`): unknown extra columns in the extract give a warning instead of failing. Missing columns and a broken year range still fail.
- `aggregate` warns when a country file has several series for one sector with different values (the first series was already used, silently).
- `aggregate` warns when `--data-col` is `DATA_<code>` for a COFOG function other than the one recorded by `split` in `--folder-path`. `split` reports how many rows of the chosen transformation were skipped because their series code has no COFOG function. The series of other indicators that the IMF extract also carries are not counted: total outlays (`TOA_T`, `TOTOUT_T`) and a liability series, recognised by a fourth field of the series code that is not a GF code and an empty `COFOG` label (on the extract of 3 February 2026 they are 3105 rows of Percent of GDP, which would have given a warning on every run). Rows with a `COFOG` label, or with a GF code that cannot be read, are still counted.
- `split` reads `PUBLICATION_DATE` of the selected series, warns when they differ (the extract mixes IMF releases), and records the date(s) and the extract's year span in the split marker. `aggregate` prints the recorded `PUBLICATION_DATE` and warns when the master's years extend beyond the extract's, or the extract's beyond the master's. The date is not written to the master (see TODO H2).
- `aggregate` and `run` get an opt-in `--check-ranges`: it lists selected values that are negative, or above 100 for the two percentage transformations. Values are kept as they are.
- `split` warns when a label given to `--cofog` covers several COFOG functions (their series would be mixed) and when the selected series have different `FREQUENCY` values.
- `run --cofog` can be repeated (`run --cofog 05 --cofog 07`): one master with `DATA_05` and `DATA_07` and their provenance columns, the same result as two separate runs. Each function is split into its own subdirectory of `--split-dir`; the source is read once per function. A single `--cofog` behaves as before. Column-name options are refused with several values.
- The IMF-to-ISO code map (`KOS` to `XKX`, `WBG` to `PSE`) is read from `cofog_panel/data/imf_country_codes.csv` instead of being written in the code. `IMF_TO_ISO` is still importable.
- Optional browser interface (written by Thanh-Tung Pham): `gui.py` (Streamlit) with `run_gui.sh` / `run_gui.bat` launchers and `.streamlit/config.toml` (upload limit 1000 MB). Streamlit is an optional extra, `pip install -e ".[gui]"` (Streamlit 1.49.0 or later); the command line does not need it. The GUI offers one built-in COFOG function per run with default column names, and each run builds a new master in a temporary folder (download it from the page). It shows the stage reports, warnings and errors on the page (before, a failure only said "Failed to split data"), passes the lookup to `split` so countries missing from it are listed, previews rows that have a value, and takes its sector list from `aggregate.DIRECT_SECTORS`. The "Overwrite Master File" box of the first version is removed: there is never a master to keep, so it had no effect. The page uses `width="stretch"` instead of `use_container_width`, which Streamlit has deprecated.
- Faster `split` and `aggregate`: `split` writes one CSV file per country (`AAA.csv`, UTF-8 with BOM) instead of an Excel workbook, and `aggregate` reads them. On a synthetic 200-country extract `run` took 7.4 s instead of 15.7 s; the master is identical. `aggregate` still reads `AAA.xlsx` files from a split made by an earlier version (CSV preferred if both exist), and a new `split` removes both kinds of old country file in its own directory.
- Input validation (selected values are unchanged for valid input):
  - Cells that are not finite numbers (`Infinity`, `1,5`, `..`, `5%`) are read as missing, as before for text, and `aggregate` now lists them per country. `Infinity` used to be accepted as a value.
  - The country is the first field of `SERIES_CODE` instead of its first three characters. Series with a code that is not three letters (`EU`, `G20`, `ABCD`) are reported by `split` and no longer written to a country file that `aggregate` would never read. `list-cofog` counts only three-letter codes.
  - `seed-master` (and `run`, when it creates the master) rejects a lookup with alpha-3 codes that are not three letters or are repeated (compared in upper case); `check-country-format` reports the same. Codes are written in upper case.
  - `seed-master` rejects `--start-year` after `--end-year` (it used to write an empty master).
  - `aggregate` stops before writing when the master has repeated `SortKey` values, or when a selected value could not be written as a number; the master file is left unchanged.
- Further input checks (selected values are unchanged for valid input):
  - `split` takes `--lookup-file` (default: the bundled lookup; `run` passes its own) and lists the countries of the extract that have no row in it, with their names, as a warning. `KOS` and `WBG` are compared as `XKX` and `PSE`. `IMF_TO_ISO` moved from `aggregate.py` to `etl.py`.
  - `--cofog` with a well-formed code that is not in the built-in list (`07.99`) is looked up among the series codes of the extract and rejected with the nearest codes before the scan. Codes of the list are accepted without reading the file. The lookup is skipped for a workbook without a shared-strings part (written by pandas or openpyxl), because reading every row would take minutes.
  - Values in domestic currency are not added when the series of a country differ in `SCALE`, `UNIT` or `CURRENCY`; the country gets reported values only (T1, C1, D) and a warning names the differing columns. Percent of GDP is unaffected.
- Replication: `replication/eeps/env_federalism.py` reproduces the current version of the EEPS article, "Decentralised environmental spending, administrative capacity and PM2.5 exposure: evidence from 110 countries": main models with the subnational share of environmental spending and its interaction with government effectiveness, Mundlak and two-way fixed-effects estimates, robustness checks (general government values only, lagged and start-of-period government effectiveness, among others), estimates leaving out one UN sub-region at a time, the composition of the sample, and two figures (PNG at 600 dpi and PDF). Models and data files of the earlier version that the article no longer reports are removed. `replication/sjiaos` is unchanged.
- The licence file is renamed `LICENSE.txt` (text unchanged); `pyproject.toml`, the README and `DATA_LICENSE.md` refer to it.
- README: section on feedback, with issue templates for test reports and bug reports. `CITATION.cff` cites the concept DOI (all versions) and keeps the DOI of 1.0.5 as an identifier. The notebook installs 1.1.0.
- CI: a job installs `.[dev,gui]`, so the GUI tests run on GitHub Actions (they are skipped without Streamlit). A test compares the `--help` output without ANSI codes, so `--check-ranges` is found on GitHub Actions.
- Internal: one `source.header_row` helper, `cli.VALID_SECTORS` built from `aggregate.DIRECT_SECTORS`, no lazy import of `COUNTRY_FILE_PATTERN`. New tests for these and for completeness/selection edge cases. `docs/` with `architecture.md` and `TODO.md`; `AGENTS.md` with commands, architecture and working rules for coding agents.

## 1.0.5 (2026-10-22)

Replication: robustness of the SJIAOS results to the IMF release. Results for the article extract are unchanged.

- `replication/sjiaos/evaluate_harmonisation.py` takes `--source FILE` (Excel or CSV download) and `--out DIR`. Without options it runs as before.
- New `replication/sjiaos/compare_vintages.py`: evaluates a second IMF extract and writes `supp_vintage.csv` (Supplementary Table S13), which compares the main statistics of the article on the releases of 3 February and 21 October 2026.
- `.gitignore`: dated IMF downloads (`data/gfs_raw_data*.csv`, `.xlsx`) and `replication/*/output_vintage/`.

- DOI: 10.5281/zenodo.23558078

## 1.0.4 (2026-10-22)

Fixes for a fresh installation. Results are unchanged: the SJIAOS replication gives the same tables as 1.0.3.

- Installation: `cli.py` no longer imports click. Typer 0.27 and later do not install click, so a fresh `pip install -e .` failed with `ModuleNotFoundError: No module named 'click'`. The command-line tool now catches Typer's own exception classes and works both with the Typer versions that depend on click and with those that bundle it.
- Minimum Typer version raised to 0.18.0 (`typer>=0.18.0`): Typer 0.16 and 0.17.0 to 0.17.4 install with the current click (8.5) but do not enforce required options or eager flags with it.
- A missing source file printed a third line, "Error: Unexpected Exit:", with recent Typer versions. Every error now prints exactly two lines (error and hint) and exits with code 1. Tests cover this case.
- CI: a new job tests the oldest supported Typer (0.18.0) and the newest one on Python 3.10 and 3.13, each installed in a fresh virtual environment.
- `DATA_LICENSE.md`: current names of the provenance columns, CSV download, note on the IMF release of 21 October 2026.
- `output/COFOG_MASTER_SCHEMA.xlsx` is no longer tracked (it is created by `cofog-panel run` or `seed-master`); `output/` is ignored.

- DOI: 10.5281/zenodo.23557750

## 1.0.3 (2026-10-22)

The core modules (`checks.py`, `cli.py`, `etl.py`, `master_seed.py`, `aggregate.py`, `__init__.py`) were rewritten, and packaging moved from `setup.py` to `pyproject.toml`. The selection rule and the completeness flags are unchanged: the SJIAOS replication gives the same tables as 1.0.2.

Fixes:

- Provenance per indicator. The tier, sectors and completeness columns were shared by all indicators, so a second `aggregate` run overwrote the provenance of the first. They now take their names from `--data-col` (`DATA_ENV` gives `SOURCE_TIER_ENV`, `SOURCE_SECTORS_ENV` and `SOURCE_COMPLETE_ENV`) or from `--tier-col` and the new options `--sectors-col` and `--complete-col`. A data column named `DATA_NEW` keeps `SOURCE_TIER`, `SOURCE_SECTORS` and `SOURCE_COMPLETE`. A warning is printed when a run replaces a column already in the master.
- `cofog-panel run` no longer rebuilds an existing master, which deleted the indicator columns in it. The master is kept and the new columns are added. The new flag `--overwrite-master` rebuilds it, with a warning.
- Options are checked before the extract is read. `--filter-type` ignores letter case and an unknown value is rejected at once with the three accepted values. `--cofog` must be a COFOG code (01 to 10, or a group such as 07.3) or a label present in the file; otherwise the closest codes or labels are suggested. `split` also checks its output directory before the scan.

Easier use (all earlier commands and options still work):

- README: "Quickstart in 3 steps" (install, download the IMF file, one command) with a sample of the output and a short explanation of the tiers and of Y/N; Windows instructions (PowerShell activation, quoted paths with spaces). The README also describes the `[replication]` extra and uses the Zenodo DOI for all versions (10.5281/zenodo.23511907).
- Defaults: `--lookup-file` is optional (the country lookup is bundled with the package), `--source-file` defaults to `data/gfs_raw_data.xlsx`, and the data column is named after the COFOG code (`DATA_05`, `DATA_07_3`) instead of `DATA_NEW`. An explicit `--data-col DATA_NEW` keeps the earlier column names. `aggregate` takes the code from the split directory.
- CSV input: the CSV download, which is the IMF portal's default, can be used directly as `--source-file` (same columns as the Excel download, same panel, read several times faster). Without `--source-file`, `data/gfs_raw_data.xlsx` is used, or `data/gfs_raw_data.csv` if there is no Excel file. The Quickstart follows the portal's download window step by step.
- New commands: `list-cofog` (COFOG codes and labels in the extract, with the number of countries) and `list-sectors` (accepted `--sector` and `--filter-type` values).
- Errors: one line on what went wrong and one `Hint:` line on how to fix it, without traceback unless `--debug` is given. Exit codes: 0 success, 1 data or option error, 2 command-line usage error. `aggregate` now fails on a missing master file or split directory instead of writing empty columns.

Acknowledgements: the README credits Pham Thanh Tung for the early prototype of the pipeline.

- DOI: 10.5281/zenodo.23549086

## 1.0.2 (2026-10-21)

- Relabel the central-government estimator as 'CGSS alone' in the SJIAOS replication; add ORCID to CITATION.cff.
- SJIAOS replication: limit the year axis of Figure 1 to 1990–2023. Tables are unchanged.
- DOI: 10.5281/zenodo.23546439

## 1.0.1 (2026-10-20)

- SJIAOS replication: country-cluster bootstrap intervals and k-sensitivity of the consolidation adjustment (Tables S11–S12).
- DOI: 10.5281/zenodo.23512435

## 1.0.0 (2026-10-20)

- First archived release.
- DOI: 10.5281/zenodo.23511908
