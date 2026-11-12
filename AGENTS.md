# Developer guidance for coding assistants

Guidance for coding assistants (and for people) working on the code of this repository. `CONTRIBUTING.md` covers reports, pull requests and releases.

## Commands

```bash
pip install -e ".[dev]"            # install + pytest
pip install -e ".[dev,gui]"        # + Streamlit >=1.49, so tests/test_gui.py runs (skipped without it)
pip install -e ".[replication]"    # statsmodels, scipy, matplotlib, linearmodels, tabulate for replication/
pytest -q                          # all tests (CI: ubuntu/windows/macos x py3.10/3.12/3.14, plus a gui job)
pytest tests/test_aggregate.py -k <name>   # single test
cofog-panel run --cofog 05         # full pipeline; needs data/gfs_raw_data.csv|xlsx (IMF download, not in repo)
cofog-panel run --cofog 05 --cofog 07   # several functions, one master; split dirs intermediate_splits/05, /07
cofog-panel --debug <command>      # full traceback instead of 2-line error
```

No linter configured. Version lives in `cofog_panel/__init__.py` (`__version__`, read dynamically by pyproject).

## Architecture

Package `cofog_panel/` is a Typer CLI over a 5-stage pipeline; `cli.py` wires stages, `run` chains all five:

1. `checks.py` (`check-format`) — validate IMF metadata/year columns
2. `checks.py` (`check-country-format`) — validate country lookup
3. `master_seed.py` — build master panel (SortKey = ISO3+year, 1972–2025), country lookup bundled at `cofog_panel/data/country_codes.xlsx` (copy also at `data/`)
4. `etl.py` (`split`) — filter one transformation + one COFOG function, write per-country CSV files (`AAA.csv`) into a split dir marked by `.cofog_panel_split` (records the COFOG function, `PUBLICATION_DATE` and year span; never delete files elsewhere). Rows without a COFOG function are counted in a warning, except the series of other indicators (e.g. `TOA_T`, `TOTOUT_T`: fourth field not `GF...`, empty `COFOG` label; `etl._is_other_indicator`)
5. `aggregate.py` — core selection rule `resolve_value`: T1 (GG) → T2 (CGSS+SG+LG) → T3 (central components+SSF+SG+LG); also C1/C2 and D (single sector) methods. Writes value + tier + sectors + completeness (`Y/N`) columns into master.
Supporting: `source.py` reads IMF CSV or xlsx (xlsx preferred if both exist); `options.py` validates `--cofog`/`--filter-type`/`--sector` *before* any file is read (file is ~372k rows, scan is slow); `messages.py` holds the shared two-line error format; `provenance.py` writes the `Provenance` sheet (version, source SHA-256, `PUBLICATION_DATE`, command and options, UTC time, columns created) after `run`; `api.py` holds `build_panel`, the Python interface (the five stages in a temporary folder, tidy DataFrame).

Conventions to keep:
- Every error = `❌ Error:` line + `Hint:` line via `print_error`; exit 1 data/option error, 2 usage error. CI asserts exactly two lines for a missing source file.
- Do not import `click` directly (Typer ≥0.27 doesn't install it); catch Typer's own exception classes. Min Typer 0.18.0.
- Output column names derive from COFOG code: `DATA_05`, `DATA_07_3`; provenance columns take the same suffix. Re-running adds columns to existing master; `--overwrite-master` rebuilds it.
- Values use `Decimal` in the selection rule; shares of total outlays are never summed (T1 only).
- CLI reconfigures stdout/stderr with `errors="replace"` for Windows consoles.

`cofog_panel/gui.py` (optional extra `gui`, Streamlit; started by `cofog-panel gui`, or by `streamlit run gui.py` through the root shim that the launchers use) calls the same stage functions as `run` for one built-in COFOG function with default column names, in a new temporary folder per run (always a new master; no `--zero-as-missing`, `--check-ranges`, `--split-dir`, several functions or non-xlsx lookup); `tests/test_gui.py` drives it with Streamlit's AppTest.

`replication/` (`harmonisation/`, `environment/`) holds scripts reproducing published analyses, each with own README; `cofog.ipynb` is a notebook demo. IMF data is not MIT-licensed (`DATA_LICENSE.md`); the code licence is `LICENSE.txt`. IMF revises releases in place, so report `PUBLICATION_DATE`. Release process: update `CHANGELOG.md`, `CITATION.cff` (version, date, Zenodo DOIs), `__version__`, the `RELEASE` pin in `cofog.ipynb` and the version placeholder in `.github/ISSUE_TEMPLATE/test_report.yml`.

## Document map (read before editing)

| Touching... | Read first |
| --- | --- |
| Selection rule, tiers, output columns, completeness | `README.md` §1, `cofog_panel/aggregate.py` |
| CLI options, errors, exit codes | `README.md` §3, `cofog_panel/options.py`, `messages.py` |
| Data source, licence, vintages | `README.md` §5, `DATA_LICENSE.md` |
| Published results | `replication/<study>/README.md` |
| Past/planned changes | `CHANGELOG.md` ("Planned" list), `docs/TODO.md` |

Never edit from memory: read the module and grep every caller first.

## Working rules

- `README.md` is the spec: update it before changing behaviour, tiers or column names it documents.
- Selection-rule changes alter numbers in the studies under `replication/`: rerun `replication/` scripts and state whether outputs changed (the 1.0.4/1.0.5 changelog entries say "results unchanged" explicitly).
- Add a `CHANGELOG.md` entry for user-visible changes; do not bump version, tag or push unless asked.
- **Plan first.** Non-trivial task: state assumptions, list multiple interpretations if any, ask when ambiguous, agree a plan with verifiable success criteria before coding. Push back with a simpler option; build the user's choice if they insist.
- **Execution ladder, stop at first true:** needn't exist → already in codebase (reuse) → stdlib → installed dep (pandas, openpyxl, typer) → one line → minimum new code. No new dependencies without asking.
- **Minimal and surgical.** Every changed line traces to the task. No adjacent refactors or reformatting; tag pre-existing problems with `TODO:`. Fix root cause, not symptom. Never cut validation, error handling or data-loss protection.
- **Tests:** non-trivial logic gets one runnable check in `tests/`; trivial one-liners none. Match existing style (4-space indent, type hints, short docstrings, comments only for non-obvious why).

## Communication

Concise, decisive, no fluff. State facts and explicitly list what was omitted or not verified.
