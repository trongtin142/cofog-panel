# Changelog

## Planned

- Cache: read the source Excel file once and keep a Parquet copy keyed by its SHA-256, with a `--no-cache` flag.
- One pass over the extract for several `--cofog` values (since 1.1.0 the extract is read once per value).
- Progress bar and summary table instead of one log line per country; `--quiet` and `--verbose` flags; no emoji, or safe handling of the console encoding on Windows.
- `--format xlsx|csv|parquet` and a `--long` option for long-format output.
- A `<master>.provenance.json` file (version, SHA-256 of the source, command run, time, columns created).
- High-level Python API `build_panel(...)` returning a DataFrame.

## 1.1.2 (2026-11-12)

The selection rule is unchanged (`resolve_value` and `is_complete` are untouched). On the IMF extract of 3 February 2026, `run --cofog 05` and `run --cofog 07.3` give the same master as 1.1.1, cell for cell, and the same country files, byte for byte.

- `split` reports the number of data rows it read. "Total Processed" also counted the header row, so it was one too high (372,482 instead of 372,481 rows on the February extract).
- `list-cofog` gives two counts for each code. `Countries` counts the countries with at least one value for the code, in any sector, transformation and year. `Listed` counts the countries with a series for it, with or without values, which is the count of earlier versions. On the February extract, every code had 194 countries under the earlier count, against 144 countries with a value for environmental protection (05). `etl.list_cofog` returns both counts.
- `--cofog` accepts a label in any letter case (`"environmental protection"`). The label is passed on as the file spells it, or as the built-in list spells it, so the split and the data column are those of the exact label. Two labels of the file that differ only in letter case are refused with both spellings.
- `run_gui.bat` stops with a message when `pip install` fails, instead of starting Streamlit without the package.
- Metadata: `pyproject.toml` lists both authors without e-mail addresses. `CITATION.cff` adds the DOI of 1.1.1 (10.5281/zenodo.24144305), describes each version DOI by its version number alone, and gives the School of Business in the first author's affiliation.
- README: an "Open in Colab" badge for the notebook of this release, the size of the CSV download (about 530 MB for the release of 21 October 2026), and the SHA-256 of the February 2026 extract for reproducing the example rows, with a note that the IMF has since replaced that release. Also a note on short clone paths on Windows, the PyPI package (`pip install cofog-panel`), and `pip install -e ".[dev,gui]"` for the tests. The notebook installs 1.1.2.
- Changelog: the earlier entries name the harmonisation study and its replication without the journal. The replication folders take the names of the studies, `replication/harmonisation` and `replication/environment`, and the paths in the entries below use these names. The archives of 1.1.1 and earlier versions keep the folder names of their time.
- `--sector` accepts its values in any letter case, as `--filter-type` does, and the error lists them one by one.
- `run_gui.sh` stops with a message when `pip install` fails, as `run_gui.bat` now does. `.gitattributes` keeps LF in shell scripts and CRLF in batch files in every checkout.
- Tests on GitHub Actions also run for each release tag, on demand and every Monday.
- `CONTRIBUTING.md` describes reports, the development setup, pull requests and releases. `.gitignore` covers every output folder of the replication scripts.
- Replication: `evaluate_extensions.py` in the folder of the harmonisation study adds further analyses of that study (fixed-sample comparisons of the filling choices, consolidation in COFOG group 01.8, coverage of education). `evaluate_harmonisation.py` and the package are unchanged.
- Tests for each of these fixes.

## 1.1.1 (2026-11-11)

The package code and the selection rule are unchanged. On the IMF extract of 3 February 2026, `replication/harmonisation` gives the same harmonised panel as 1.1.0, byte for byte.

- Replication: `replication/environment` reproduces the environmental-spending study and its supplementary material. `run_all.py` runs the 24 steps in order and `fetch_data.py` downloads the third-party data; `replication/environment/README.md` lists the steps and their outputs.
  - `env_federalism.py`: the subnational share is missing in a year in which a subnational level that the country reports in other years has no value, which makes the estimation sample smaller than in 1.1.0. Coverage gaps, the countries whose COFOG data cover central government alone for all ten functions in every year, have a missing share instead of a zero; a country without subnational government (Singapore) keeps its zero. `paperC_samples.py` defines these groups, and `gaps_as_zero()` gives the construction with the coverage gaps coded as zero. New rows in the robustness table (region-specific slopes of government effectiveness; countries without subnational data, with their own intercept and slope or left out; the share at the start of each country's period; land area, federal countries and economies in transition); the subnational shares of total outlays, of two other COFOG functions and of the COFOG groups 05.1 and 05.3 (read from the IMF extract, harmonised with `resolve_value` and `is_complete`, and cached in `output/`); coefficient stability (Oster 2019); Wald tests; the association at the median government effectiveness of low- and middle-income countries in every row; a binned figure; and the numbers quoted in the text (`sample_composition.json`, `extensions.json`, `further_tests.json`). The estimation panel gains the columns `NOSUB` and `EVER_GG`. Figures are 119 mm wide, in Arial, without a title inside the figure.
  - New scripts for the supplementary material and the further estimates: the country table, the gap between subsector sums and reported general government values and the comparison with the OECD SNG-WOFI functional data (`paperC_esm_wofi.py`); columns 4 and 5 of Table 2; anthropogenic PM2.5 from the GBD-MAPS source contributions; counts quoted in the text; an event study of regional decentralisation reforms (Regional Authority Index); instrumental-variable estimates; emissions of carbonaceous aerosols by sector (CEDS) and waste collection (What a Waste); samples without countries that report central data alone, other functions, terrain ruggedness and ethnic fractionalisation, and the influence of single countries; controls for the main sources of PM2.5, a binning estimator and equal country weights; variants of the share; the Markdown tables of the supplementary material; the zero shares (coverage gaps coded as zero, bounds for the zeros of the central-only countries) and the measurement basis of environmental spending; the SNG-WOFI share as an independent measure, agreement with SNG-WOFI and the self-rule of the Regional Authority Index; the subnational shares of the ten COFOG divisions; other governance indicators as moderator, functional form, omitted variables, the sources of exposure, structural controls and inference; central and subnational spending in place of the share; and the flow of countries and observations from the COFOG extract to the main sample.
  - Data: the third-party files are in `data_ext/lab/`, with sources, URLs, download dates and licences in `data_ext/SOURCES.md`. Files under CC BY 4.0 or CC0 are distributed (What a Waste, the Historical Index of Ethnic Fractionalization, the GBD-MAPS source contributions, two WDI series, CRU climate series of the World Bank Climate Change Knowledge Portal, burnt area of Our World in Data), as are WDI population and six further WDI and WGI series in `data_ext/` (CC BY 4.0, SHA-256 in `data_ext/CHECKSUMS_r5i.sha256`). The Regional Authority Index, terrain ruggedness, the CEDS emissions and SNG-WOFI are downloaded by `fetch_data.py`, checked against the SHA-256 of the copies used in the study, and kept out of the repository (`.gitignore`, `DATA_LICENSE.md`). `.gitattributes` stores the distributed files byte for byte, so their checksums hold on every platform.
- The READMEs and script headers in `replication/`, and the 1.1.0 entry of this changelog, describe the two studies without their titles; the references will be added on publication.
- Packaging: `scipy`, `linearmodels` and `tabulate`, used by the scripts in `replication/environment`, are part of the `[replication]` extra. `cofog_panel.data` is declared as a package, which removes a setuptools warning. `MANIFEST.in` adds `CITATION.cff`, `CHANGELOG.md`, `DATA_LICENSE.md`, the browser interface (`gui.py`, its launchers and `.streamlit/config.toml`), `data/country_codes.xlsx` and the tests to the source distribution, so the test suite runs from it. The licence badge of the README uses an absolute link, which also works outside GitHub, and `pyproject.toml` lists the issue tracker (`Issues` in `[project.urls]`), so the package page links to it. The notebook installs 1.1.1.

## 1.1.0 (2026-11-01)

Results are unchanged (selection rule untouched): on the IMF extract of 3 February 2026, `run --cofog 05` and `run --cofog 07` give the same values, tiers, sectors and completeness flags as 1.0.5, and the harmonisation replication gives the same tables as 1.0.5.

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
- Replication: `replication/environment/env_federalism.py` reproduces the current version of the environmental-spending study (manuscript under review): main models with the subnational share of environmental spending and its interaction with government effectiveness, Mundlak and two-way fixed-effects estimates, robustness checks (general government values only, lagged and start-of-period government effectiveness, among others), estimates leaving out one UN sub-region at a time, the composition of the sample, and two figures (PNG at 600 dpi and PDF). Models and data files of the earlier version that the article no longer reports are removed. `replication/harmonisation` is unchanged.
- The licence file is renamed `LICENSE.txt` (text unchanged); `pyproject.toml`, the README and `DATA_LICENSE.md` refer to it.
- README: section on feedback, with issue templates for test reports and bug reports. `CITATION.cff` cites the concept DOI (all versions) and keeps the DOI of 1.0.5 as an identifier. The notebook installs 1.1.0.
- CI: a job installs `.[dev,gui]`, so the GUI tests run on GitHub Actions (they are skipped without Streamlit). A test compares the `--help` output without ANSI codes, so `--check-ranges` is found on GitHub Actions.
- Internal: one `source.header_row` helper, `cli.VALID_SECTORS` built from `aggregate.DIRECT_SECTORS`, no lazy import of `COUNTRY_FILE_PATTERN`. New tests for these and for completeness/selection edge cases. `docs/` with `architecture.md` and `TODO.md`; `AGENTS.md` with commands, architecture and working rules for coding agents.

## 1.0.5 (2026-10-22)

Replication: robustness of the results of the harmonisation study to the IMF release. Results for the extract of the study are unchanged.

- `replication/harmonisation/evaluate_harmonisation.py` takes `--source FILE` (Excel or CSV download) and `--out DIR`. Without options it runs as before.
- New `replication/harmonisation/compare_vintages.py`: evaluates a second IMF extract and writes `supp_vintage.csv` (Supplementary Table S13), which compares the main statistics of the article on the releases of 3 February and 21 October 2026.
- `.gitignore`: dated IMF downloads (`data/gfs_raw_data*.csv`, `.xlsx`) and `replication/*/output_vintage/`.

- DOI: 10.5281/zenodo.23558078

## 1.0.4 (2026-10-22)

Fixes for a fresh installation. Results are unchanged: the harmonisation replication gives the same tables as 1.0.3.

- Installation: `cli.py` no longer imports click. Typer 0.27 and later do not install click, so a fresh `pip install -e .` failed with `ModuleNotFoundError: No module named 'click'`. The command-line tool now catches Typer's own exception classes and works both with the Typer versions that depend on click and with those that bundle it.
- Minimum Typer version raised to 0.18.0 (`typer>=0.18.0`): Typer 0.16 and 0.17.0 to 0.17.4 install with the current click (8.5) but do not enforce required options or eager flags with it.
- A missing source file printed a third line, "Error: Unexpected Exit:", with recent Typer versions. Every error now prints exactly two lines (error and hint) and exits with code 1. Tests cover this case.
- CI: a new job tests the oldest supported Typer (0.18.0) and the newest one on Python 3.10 and 3.13, each installed in a fresh virtual environment.
- `DATA_LICENSE.md`: current names of the provenance columns, CSV download, note on the IMF release of 21 October 2026.
- `output/COFOG_MASTER_SCHEMA.xlsx` is no longer tracked (it is created by `cofog-panel run` or `seed-master`); `output/` is ignored.

- DOI: 10.5281/zenodo.23557750

## 1.0.3 (2026-10-22)

The core modules (`checks.py`, `cli.py`, `etl.py`, `master_seed.py`, `aggregate.py`, `__init__.py`) were rewritten, and packaging moved from `setup.py` to `pyproject.toml`. The selection rule and the completeness flags are unchanged: the harmonisation replication gives the same tables as 1.0.2.

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

- Relabel the central-government estimator as 'CGSS alone' in the harmonisation replication; add ORCID to CITATION.cff.
- Harmonisation replication: limit the year axis of Figure 1 to 1990–2023. Tables are unchanged.
- DOI: 10.5281/zenodo.23546439

## 1.0.1 (2026-10-20)

- Harmonisation replication: country-cluster bootstrap intervals and k-sensitivity of the consolidation adjustment (Tables S11–S12).
- DOI: 10.5281/zenodo.23512435

## 1.0.0 (2026-10-20)

- First archived release.
- DOI: 10.5281/zenodo.23511908
