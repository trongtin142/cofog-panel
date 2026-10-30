# TODO

Working list, easy to hard. Status: `[x]` done, `[ ]` open. Numbers in published outputs must not change (rerun `replication/` if the selection rule is touched; none of the items below touch it).

## Easy

- [x] E1 `AGENTS.md`: stage numbering matches the code (5 stages: 2 checks, seed, split, aggregate).
- [x] E2 `checks.py`: comment where `END_YEAR` and `COFOG_LABELS` must be updated for a new IMF release.
- [x] E3 `cli.VALID_SECTORS` built from `aggregate.DIRECT_SECTORS` (one list less to keep in sync).
- [x] E4 `aggregate.py`: top-level import of `COUNTRY_FILE_PATTERN` (the lazy import has no cycle to avoid).
- [x] E5 `source.header_row`: one helper for the header-parsing line repeated in `etl.py` (x2) and `options.py`.
- [ ] E6 Emoji in console output: left to the planned v1.1.0 "no emoji / safe console" item (changes user-visible text).

## Medium

- [x] M1 `aggregate._read_country_file`: warn when a sector has several series with different values (the first was used silently).
- [x] M2 `checks.verify_cofog_format`: unknown extra columns are a warning, not a failure. Missing columns and bad year range still fail.
- [x] M3 Tests: `is_complete` edge cases (EBCG reported but only BCG used); `resolve_value` never returns sectors outside its input.
- [ ] M4 Linter and type checker (ruff, mypy): needs a new dev dependency, ask first.
- [ ] M5 Several `--cofog` values in one run (v1.1.0): needs a design for the master and the split marker.
- [ ] M6 Faster split to aggregate hand-off (Parquet/CSV per country instead of xlsx): changes the on-disk contract, decide first.
- [ ] M7 CSV/Parquet master next to the xlsx (v1.1.0).

## Hard

- [ ] H1 `build_panel(...)` Python API: stage functions return data, the CLI prints (v1.1.0).
- [ ] H2 `<master>.provenance.json` (version, SHA-256 of source, command, time, columns) (v1.1.0).
- [ ] H3 Parquet cache keyed by SHA-256 of the source, `--no-cache` (v1.1.0).
- [ ] H4 Opt-in consolidation adjustment for T2/T3 sums: changes numbers, rerun `replication/`.
- [ ] H5 Warn when a master mixes IMF releases (`PUBLICATION_DATE`).
