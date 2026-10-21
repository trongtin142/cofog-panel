# Changelog

## 1.0.3 (2026-10-22)

The core modules (`checks.py`, `cli.py`, `etl.py`, `master_seed.py`, `aggregate.py`, `__init__.py`) were rewritten, and packaging moved from `setup.py` to `pyproject.toml`. The selection rule and the completeness flags are unchanged: the SJIAOS replication gives the same tables as 1.0.2.

Fixes:

- Provenance per indicator. The sectors and completeness columns were shared by all indicators, so a second `aggregate` run overwrote the provenance of the first. They now take their names from `--data-col` (`DATA_ENV` gives `SOURCE_SECTORS_ENV` and `SOURCE_COMPLETE_ENV`) or from the new options `--sectors-col` and `--complete-col`. The default `DATA_NEW` keeps `SOURCE_SECTORS` and `SOURCE_COMPLETE`. A warning is printed when a run replaces a column already in the master.
- `cofog-panel run` no longer rebuilds an existing master, which deleted the indicator columns in it. The master is kept and the new columns are added. The new flag `--overwrite-master` rebuilds it, with a warning.
- Options are checked before the extract is read. `--filter-type` ignores letter case and an unknown value is rejected at once with the three accepted values. `--cofog` must be a COFOG code (01 to 10, or a group such as 07.3) or a label present in the file; otherwise the closest codes or labels are suggested. `split` also checks its output directory before the scan.

Other changes: the README describes the `[replication]` extra and uses the Zenodo DOI for all versions (10.5281/zenodo.23511907).

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
