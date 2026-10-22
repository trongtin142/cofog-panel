# Changelog

## Planned (v1.1.0)

- Cache: read the source Excel file once and keep a Parquet copy keyed by its SHA-256, with a `--no-cache` flag.
- `--cofog` accepts several codes in one run.
- Progress bar and summary table instead of one log line per country; `--quiet` and `--verbose` flags; no emoji, or safe handling of the console encoding on Windows.
- `--format xlsx|csv|parquet` and a `--long` option for long-format output.
- A `<master>.provenance.json` file (version, SHA-256 of the source, command run, time, columns created).
- High-level Python API `build_panel(...)` returning a DataFrame.
- "Open in Colab" badge for `cofog.ipynb`.

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
