# TODO

Working list, easy to hard. Status: `[x]` done, `[ ]` open. Numbers in published outputs must not change (rerun `replication/` if the selection rule is touched; none of the items below touch it).

## Easy

- [x] E1 `AGENTS.md`: stage numbering matches the code (5 stages: 2 checks, seed, split, aggregate).
- [x] E2 `checks.py`: comment where `END_YEAR` and `COFOG_LABELS` must be updated for a new IMF release.
- [x] E3 `VALID_SECTORS` built from `DIRECT_SECTORS`, both in `options.py` with `normalise_sector`, shared by the command line, the GUI and `build_panel` (one list less to keep in sync).
- [x] E4 `aggregate.py`: top-level import of `COUNTRY_FILE_PATTERN` (the lazy import has no cycle to avoid).
- [x] E5 `source.header_row`: one helper for the header-parsing line repeated in `etl.py` (x2) and `options.py`.
- [ ] E6 Emoji in console output: left to the planned "no emoji / safe console" item in `CHANGELOG.md` (changes user-visible text).
- [x] E7 `gui.py`: the "Overwrite Master File" box had no effect (each run starts in a new temporary folder) and is removed; `width="stretch"` replaces the deprecated `use_container_width` (Streamlit >= 1.49).
- [ ] E8 `gui.py`: accept a `.csv` or `.xls` country lookup, as the command line does (the uploader takes `.xlsx` only).

## Medium

- [x] M1 `aggregate._read_country_file`: warn when a sector has several series with different values (the first was used silently).
- [x] M2 `checks.verify_cofog_format`: unknown extra columns are a warning, not a failure. Missing columns and bad year range still fail.
- [x] M3 Tests: `is_complete` edge cases (EBCG reported but only BCG used); `resolve_value` never returns sectors outside its input.
- [ ] M4 Linter and type checker (ruff, mypy): needs a new dev dependency, ask first.
- [x] M5 `run --cofog 05 --cofog 07`: stages 4-5 per function, one split subdirectory each (so the marker format is unchanged), same master as separate runs. The source is read once per function; a single scan for all functions is open.
- [x] M6 Faster split to aggregate hand-off: one CSV per country instead of xlsx (stdlib, no new dependency). Older `.xlsx` splits are still read.
- [ ] M7 CSV/Parquet master next to the xlsx (planned).

## Input validation (first batch done)

- [x] V1 `Infinity`/`-inf` are not values; unreadable cell texts are reported per country.
- [x] V2 Country = first field of `SERIES_CODE`; non-three-letter codes reported, not split.
- [x] V3 Lookup alpha-3 checked (three letters, unique) by `seed-master` and `check-country-format`.
- [x] V4 `seed-master` rejects `--start-year` > `--end-year`.
- [x] V5 `aggregate` refuses a master with repeated `SortKey` and never writes values it could not convert.
- [x] V6 Scale/currency/unit uniform within a country before summing (Domestic currency); otherwise no sums, warning.
- [x] V7 `split` lists countries of the extract without a lookup row (warning).
- [x] V8 `--cofog` codes outside the built-in list (e.g. `07.99`) checked against the extract before the scan (xlsx with shared strings, CSV).
- [x] V9 Warn when `--data-col` is `DATA_<code>` of another function than the one recorded in the split marker (custom names are not warned about).
- [x] V10 `split` reads `PUBLICATION_DATE` (selected series only), warns on mixed dates, records it in the marker; `aggregate` prints it. Not written to the master: H2 (provenance file) is the place for it.
- [x] V11 `--check-ranges` (`aggregate`, `run`): lists negative values and percentages above 100; values are kept.
- [x] V12 `split` counts rows of the transformation skipped because the series code has no COFOG function. Series of other indicators (`TOA_T`, `TOTOUT_T`, a liability series: fourth field not `GF...`, empty `COFOG` label) are not counted.
- [x] V13 Marker records the extract's year span; `aggregate` warns when it differs from the master's years.
- [x] V14 `IMF_TO_ISO` read from `cofog_panel/data/imf_country_codes.csv` (listed in package data).
- [x] V15 `split` warns when a label selector covers several COFOG codes, and when the selected series mix `FREQUENCY` values. Which value means annual is not assumed (needs real data).

## Hard

- [x] H1 `build_panel(...)` Python API (1.2.0): runs the stages in a temporary folder and returns a tidy DataFrame; the stage functions still print, `build_panel` captures their output. Stage functions that return data remain open.
- [x] H2 File-level provenance (1.2.0): a sheet `Provenance` in the master (version, SHA-256 of source, `PUBLICATION_DATE`, command and options, time, columns), not a separate JSON file, so it travels with the master.
- [ ] H3 Parquet cache keyed by SHA-256 of the source, `--no-cache` (planned).
- [ ] H4 Opt-in consolidation adjustment for T2/T3 sums: changes numbers, rerun `replication/`.
- [ ] H5 Warn when a master mixes IMF releases (`PUBLICATION_DATE`).
