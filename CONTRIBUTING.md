# Contributing to COFOG-Panel

Test reports, bug reports, questions and code are welcome.

## Reports and questions

- After a run, a short [test report](https://github.com/trongtin142/cofog-panel/issues/new?template=test_report.yml) tells us what worked and what was unclear. Problems go in a [bug report](https://github.com/trongtin142/cofog-panel/issues/new?template=bug_report.yml), and questions or ideas in [Discussions](https://github.com/trongtin142/cofog-panel/discussions).
- A useful report gives the version (`cofog-panel --version`), the operating system, the command, the full output and the `PUBLICATION_DATE` of the extract, which `aggregate` prints.
- Please do not attach the IMF extract. The IMF terms of use apply to it (`DATA_LICENSE.md`), and its `PUBLICATION_DATE` and SHA-256 checksum identify it.

## Development setup

```bash
git clone https://github.com/trongtin142/cofog-panel.git
cd cofog-panel
python -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -e ".[dev,gui]"
python -m pytest
```

On Windows, clone into a short path such as `C:\cofog-panel`. Streamlit installs files with long paths, and Windows limits paths to 260 characters unless long paths are enabled.

`docs/architecture.md` maps the five stages to the modules, and `AGENTS.md` gives the working rules that coding assistants follow in this repository.

## Pull requests

- Each pull request makes one change and adds a test that fails before the change and passes after it.
- GitHub Actions runs the tests on Linux, macOS and Windows. A pull request is merged when every job passes.
- The selection rule (`resolve_value`, `is_complete`) determines published numbers. A pull request that changes it describes the change in `CHANGELOG.md`, reruns the scripts in `replication/` and states whether their outputs change.
- Messages to users keep the two-line form (the error and a hint) and the exit codes described in the README (Section 3).
- Contributions are released under the MIT License of the repository (`LICENSE.txt`).

## Releases

1. Set the version in `cofog_panel/__init__.py` and the version and date in `CITATION.cff`, and add an entry to `CHANGELOG.md`.
2. Tag the commit `vX.Y.Z` and publish a GitHub release. Zenodo archives the release and gives it a DOI, which goes into `CITATION.cff` and the changelog in the next commit.
3. Build the wheel and the source distribution (`python -m build`), check them (`twine check dist/*`) and upload them to PyPI.
