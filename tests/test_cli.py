"""Command-line behaviour: separate provenance per indicator, master reuse, early option checks."""
import re
import shutil
import pandas as pd
import pytest
from typer.testing import CliRunner

from cofog_panel.aggregate import provenance_columns, run_aggregation
from cofog_panel.checks import FIXED_HEADERS_SAMPLE
from cofog_panel.cli import app
from cofog_panel.etl import split_data
from cofog_panel.master_seed import seed_master
from cofog_panel.options import TRANSFORMATIONS, OptionError, check_cofog, normalise_transformation

runner = CliRunner()
YEARS = [str(y) for y in range(1972, 2025)]
SECTOR_CODES = {
    "General government": "S13",
    "Central government including social security": "S1321",
    "Budgetary central government": "S1311B",
    "Local Government": "S1313MIXED",
}


def _series(iso, country, sector, code, label, by_year):
    row = dict.fromkeys(FIXED_HEADERS_SAMPLE, "")
    row.update({
        "SERIES_CODE": f"{iso}.{SECTOR_CODES[sector]}.G2MF.GF{code}_T.POGDP_PT.A",
        "COUNTRY": country, "SECTOR": sector, "COFOG": label,
        "TYPE_OF_TRANSFORMATION": "Percent of GDP",
    })
    row.update({y: by_year.get(int(y)) for y in YEARS})
    return row


@pytest.fixture
def extract(tmp_path):
    """
    AAA reports environmental protection (05) only for budgetary central and local government
    in 2000 (a T3 value) but health (07) for general government in the same year (T1).
    CCC reports health only.
    """
    rows = [
        _series("AAA", "Alpha", "Budgetary central government", "05", "Environmental protection", {2000: 0.4}),
        _series("AAA", "Alpha", "Local Government", "05", "Environmental protection", {2000: 0.2, 2001: 0.3}),
        _series("AAA", "Alpha", "General government", "07", "Health", {2000: 5.0, 2001: 5.5}),
        _series("CCC", "Gamma", "General government", "07", "Health", {2000: 3.0}),
        _series("CCC", "Gamma", "General government", "99", "Custom function", {2000: 1.0}),
    ]
    raw_path = tmp_path / "raw.xlsx"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(raw_path, index=False)
    lookup_path = tmp_path / "countries.xlsx"
    pd.DataFrame({"name": ["Alpha", "Gamma"], "alpha-2": ["AA", "CC"], "alpha-3": ["AAA", "CCC"],
                  "country-code": [1, 3]}).to_excel(lookup_path, index=False)
    return tmp_path, raw_path, lookup_path


def _master(path):
    return pd.read_excel(path, sheet_name="MasterData", dtype=str).fillna("").set_index("SortKey")


# --- B1: provenance columns per indicator ---

def test_provenance_column_names():
    assert provenance_columns("DATA_NEW") == ("SOURCE_SECTORS", "SOURCE_COMPLETE")
    assert provenance_columns("DATA_ENV") == ("SOURCE_SECTORS_ENV", "SOURCE_COMPLETE_ENV")
    assert provenance_columns("HEALTH") == ("SOURCE_SECTORS_HEALTH", "SOURCE_COMPLETE_HEALTH")


def test_second_indicator_leaves_first_provenance_unchanged(extract):
    tmp, raw_path, lookup_path = extract
    master_path, _ = seed_master(lookup_path, tmp)
    env_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "split_05")
    assert run_aggregation(master_path, env_dir, "DATA_ENV", tier_col_out="TIER_ENV")
    env_columns = ["DATA_ENV", "TIER_ENV", "SOURCE_SECTORS_ENV", "SOURCE_COMPLETE_ENV"]
    before = _master(master_path)[env_columns].copy()
    assert before.at["AAA2000", "TIER_ENV"] == "T3"
    assert before.at["AAA2000", "SOURCE_SECTORS_ENV"] == "BCG+LG"

    health_dir, _ = split_data(raw_path, "Percent of GDP", {"07"}, tmp / "split_07")
    result = runner.invoke(app, ["aggregate", "--master-file", str(master_path), "--folder-path", str(health_dir),
                                 "--data-col", "DATA_HEALTH", "--tier-col", "TIER_HEALTH"])
    assert result.exit_code == 0, result.output

    after = _master(master_path)
    pd.testing.assert_frame_equal(after[env_columns], before)
    assert after.at["AAA2000", "TIER_HEALTH"] == "T1"
    assert after.at["AAA2000", "SOURCE_SECTORS_HEALTH"] == "GG"
    # A country-year with health data only carries no environmental provenance
    assert after.at["CCC2000", "DATA_HEALTH"] != ""
    assert after.at["CCC2000", "SOURCE_SECTORS_ENV"] == ""
    assert after.at["CCC2000", "SOURCE_COMPLETE_ENV"] == ""


def test_explicit_provenance_column_names(extract):
    tmp, raw_path, lookup_path = extract
    master_path, _ = seed_master(lookup_path, tmp)
    env_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "split_05")
    result = runner.invoke(app, ["aggregate", "--master-file", str(master_path), "--folder-path", str(env_dir),
                                 "--data-col", "DATA_ENV", "--sectors-col", "ENV_FROM", "--complete-col", "ENV_FULL"])
    assert result.exit_code == 0, result.output
    out = _master(master_path)
    assert {"ENV_FROM", "ENV_FULL"} <= set(out.columns)
    assert "SOURCE_SECTORS_ENV" not in out.columns


# --- B2: `run` keeps an existing master unless --overwrite-master is given ---

def _run(tmp, raw_path, lookup_path, cofog, data_col, *extra):
    return runner.invoke(app, ["run", "--source-file", str(raw_path), "--lookup-file", str(lookup_path),
                               "--cofog", cofog, "--data-col", data_col, "--tier-col", f"TIER_{data_col[5:]}",
                               "--output-dir", str(tmp / "out"), "--split-dir", str(tmp / "splits"), *extra])


def test_run_adds_columns_to_existing_master(extract):
    tmp, raw_path, lookup_path = extract
    first = _run(tmp, raw_path, lookup_path, "05", "DATA_ENV")
    assert first.exit_code == 0, first.output
    second = _run(tmp, raw_path, lookup_path, "07", "DATA_HEALTH")
    assert second.exit_code == 0, second.output
    assert "keeping the existing file" in second.output

    out = _master(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx")
    assert {"DATA_ENV", "TIER_ENV", "SOURCE_SECTORS_ENV", "DATA_HEALTH", "TIER_HEALTH", "SOURCE_SECTORS_HEALTH"} <= set(out.columns)
    assert out.at["AAA2000", "SOURCE_SECTORS_ENV"] == "BCG+LG"


def test_run_overwrite_master_rebuilds_and_warns(extract):
    tmp, raw_path, lookup_path = extract
    assert _run(tmp, raw_path, lookup_path, "05", "DATA_ENV").exit_code == 0
    result = _run(tmp, raw_path, lookup_path, "07", "DATA_HEALTH", "--overwrite-master")
    assert result.exit_code == 0, result.output
    assert "WARNING" in result.output and "--overwrite-master" in result.output

    out = _master(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx")
    assert "DATA_HEALTH" in out.columns
    assert "DATA_ENV" not in out.columns


# --- B3: options are checked before the extract is read ---

def test_filter_type_ignores_letter_case(extract):
    tmp, raw_path, _ = extract
    assert normalise_transformation("percent of GDP") == "Percent of GDP"
    result = runner.invoke(app, ["split", "--source-file", str(raw_path), "--cofog", "05",
                                 "--filter-type", "PERCENT OF GDP", "--output-dir", str(tmp / "s")])
    assert result.exit_code == 0, result.output
    assert (tmp / "s" / "AAA.csv").exists()


def test_invalid_filter_type_fails_before_reading(tmp_path):
    # The source file does not exist: the error must concern the option, not the file
    result = runner.invoke(app, ["split", "--source-file", str(tmp_path / "absent.xlsx"), "--cofog", "05",
                                 "--filter-type", "Percent GDP", "--output-dir", str(tmp_path / "s")])
    assert result.exit_code == 1
    assert "Invalid --filter-type" in result.output
    for name in TRANSFORMATIONS:
        assert name in result.output
    assert "not found" not in result.output
    assert not (tmp_path / "s").exists()


@pytest.mark.parametrize("code", ["01", "05", "07.3", "07.12", "10", "10.9"])
def test_cofog_codes_accepted(code):
    assert check_cofog(code) == code


@pytest.mark.parametrize("value, hint", [
    ("5", "'05' (Environmental protection)"),
    ("7.3", "'07.3' (Hospital services)"),
    ("Enviromental protection", "(Environmental protection)"),
])
def test_cofog_suggestions(value, hint):
    with pytest.raises(OptionError) as error:
        check_cofog(value)
    assert hint in str(error.value)


@pytest.mark.parametrize("value", ["11", "00", "05.123", "Space programme"])
def test_cofog_rejected(value):
    with pytest.raises(OptionError):
        check_cofog(value)


def test_cofog_label_found_in_file(extract):
    _, raw_path, _ = extract
    assert check_cofog("Custom function", raw_path) == "Custom function"
    with pytest.raises(OptionError):
        check_cofog("Custom function")


@pytest.mark.parametrize("value, label", [
    ("environmental protection", "Environmental protection"),
    ("HOSPITAL SERVICES", "Hospital services"),
    ("  health ", "Health"),
])
def test_cofog_labels_ignore_letter_case(value, label):
    assert check_cofog(value) == label


def test_cofog_label_in_other_letter_case_takes_the_spelling_of_the_file(extract, tmp_path):
    _, raw_path, _ = extract
    assert check_cofog("custom FUNCTION", raw_path) == "Custom function"
    rows = [_series("AAA", "Alpha", "General government", "05", "Environmental Protection", {2000: 1.0})]
    renamed = tmp_path / "renamed.csv"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_csv(renamed, index=False)
    assert check_cofog("environmental protection", renamed) == "Environmental Protection"


def test_cofog_label_that_matches_several_spellings_of_the_file_is_rejected(tmp_path):
    rows = [_series("AAA", "Alpha", "General government", "99", label, {2000: 1.0}) for label in ("Odd", "ODD")]
    path = tmp_path / "two.csv"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_csv(path, index=False)
    with pytest.raises(OptionError) as error:
        check_cofog("odd", path)
    assert "'ODD', 'Odd'" in error.value.hint


def test_run_with_a_label_in_other_letter_case_gives_the_same_master(extract):
    tmp, raw_path, lookup_path = extract
    for name, value in (("code", "05"), ("label", "ENVIRONMENTAL protection")):
        result = runner.invoke(app, ["run", "--source-file", str(raw_path), "--lookup-file", str(lookup_path),
                                     "--cofog", value, "--output-dir", str(tmp / f"out_{name}"),
                                     "--split-dir", str(tmp / f"split_{name}")])
        assert result.exit_code == 0, result.output
    by_code = _master(tmp / "out_code" / "COFOG_MASTER_SCHEMA.xlsx")
    pd.testing.assert_frame_equal(by_code, _master(tmp / "out_label" / "COFOG_MASTER_SCHEMA.xlsx"))
    assert by_code.at["AAA2000", "DATA_05"] == "0.6" and by_code.at["AAA2000", "SOURCE_TIER_05"] == "T3"


def test_invalid_cofog_on_command_line(extract):
    tmp, raw_path, lookup_path = extract
    result = runner.invoke(app, ["run", "--source-file", str(raw_path), "--lookup-file", str(lookup_path),
                                 "--cofog", "5", "--output-dir", str(tmp / "out")])
    assert result.exit_code == 1
    assert "Did you mean" in result.output and "'05'" in result.output
    assert not (tmp / "out").exists()


# --- --cofog codes outside the built-in list must be in the file ---

def _as_csv(extract_files):
    """The extract of the fixture as the CSV download (read by row), and as a workbook with a shared-strings part."""
    _, raw_path, _ = extract_files
    csv_path = raw_path.with_suffix(".csv")
    pd.read_excel(raw_path, dtype=str).to_csv(csv_path, index=False)
    return csv_path


def _workbook_with_shared_strings(path, series_codes):
    """Just enough of an Excel download for the check: pandas and openpyxl write strings inline, Excel and the IMF do not."""
    import zipfile
    items = "".join(f"<si><t>{code}</t></si>" for code in series_codes)
    with zipfile.ZipFile(path, "w") as book:
        book.writestr("xl/sharedStrings.xml",
                      f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{items}</sst>')
    return path


def test_cofog_group_missing_from_file_is_rejected_with_nearby_codes(extract):
    csv_path = _as_csv(extract)
    with pytest.raises(OptionError) as error:
        check_cofog("07.99", csv_path)
    assert "'07' (Health)" in error.value.hint and "no series for COFOG 07.99" in error.value.hint
    assert check_cofog("07", csv_path) == "07"


def test_cofog_code_outside_the_list_is_looked_up_in_workbook_shared_strings(tmp_path):
    book = _workbook_with_shared_strings(tmp_path / "imf.xlsx", [
        "ARM.S13.G2MF.GF0799_T.POGDP_PT.A", "ARM.S13.G2MF.GF0710_T.POGDP_PT.A", "Percent of GDP"])
    assert check_cofog("07.99", book) == "07.99"
    assert check_cofog("07.1", book) == "07.1"
    with pytest.raises(OptionError) as error:
        check_cofog("07.98", book)
    assert "'07.99'" in error.value.hint


def test_cofog_code_outside_the_list_is_accepted_when_the_csv_has_it(tmp_path):
    rows = [_series("AAA", "Alpha", "General government", "0799", "Odd group", {2000: 1.0})]
    path_csv = tmp_path / "odd.csv"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_csv(path_csv, index=False)
    assert check_cofog("07.99", path_csv) == "07.99"
    with pytest.raises(OptionError):
        check_cofog("07.98", path_csv)


def test_cofog_code_check_is_skipped_for_a_workbook_without_shared_strings(extract, tmp_path):
    _, raw_path, _ = extract            # written by pandas: strings are inline
    assert check_cofog("07.99", raw_path) == "07.99"   # reading every row would take minutes on the real extract


def test_cofog_code_of_the_list_is_accepted_without_reading_the_file(extract):
    csv_path = _as_csv(extract)
    assert check_cofog("06.1", csv_path) == "06.1"      # in the built-in list, not in this file
    assert check_cofog("06.1", csv_path.parent / "absent.csv") == "06.1"
    assert check_cofog("07.99", csv_path.parent / "absent.csv") == "07.99"   # no file, no check


def test_cofog_group_missing_from_file_fails_the_command_in_two_lines(extract):
    tmp, _, lookup_path = extract
    csv_path = _as_csv(extract)
    for args in (["split", "--output-dir", str(tmp / "s")],
                 ["run", "--output-dir", str(tmp / "o"), "--split-dir", str(tmp / "s")]):
        result = runner.invoke(app, [args[0], "--source-file", str(csv_path), "--cofog", "07.99", *args[1:]])
        lines = result.output.strip().splitlines()
        assert result.exit_code == 1 and len(lines) == 2, result.output
        assert lines[0].startswith("❌ Error: Invalid --cofog '07.99'.")
    assert not (tmp / "s").exists()


# --- split lists countries missing from the lookup ---

def test_split_command_checks_the_bundled_lookup_by_default(extract):
    tmp, raw_path, _ = extract
    result = runner.invoke(app, ["split", "--source-file", str(raw_path), "--cofog", "07", "--output-dir", str(tmp / "s")])
    assert result.exit_code == 0, result.output
    assert "2 countries in the extract have no row in the lookup file" in result.output
    assert "AAA (Alpha)" in result.output and "CCC (Gamma)" in result.output


def test_run_passes_its_lookup_file_to_split(extract):
    tmp, raw_path, lookup_path = extract
    pd.DataFrame({"name": ["Alpha"], "alpha-2": ["AA"], "alpha-3": ["AAA"], "country-code": [1]}).to_excel(
        lookup_path, index=False)
    result = _run(tmp, raw_path, lookup_path, "07", "DATA_H")
    assert result.exit_code == 0, result.output
    assert "1 countries in the extract have no row in the lookup file" in result.output
    assert "CCC (Gamma)" in result.output and "AAA (Alpha)" not in result.output


@pytest.mark.parametrize("data_col, warned", [
    ("DATA_05", True), ("data_05", True), ("DATA_07", False), ("DATA_ENV", False), ("DATA_05_1", True),
])
def test_aggregate_warns_when_data_col_names_another_function(extract, data_col, warned):
    tmp, raw_path, lookup_path = extract
    master_path, _ = seed_master(lookup_path, tmp, start_year=2000, end_year=2001)
    split_data(raw_path, "Percent of GDP", {"07"}, tmp / "s")
    result = runner.invoke(app, ["aggregate", "--master-file", str(master_path), "--folder-path", str(tmp / "s"),
                                 "--data-col", data_col])
    assert result.exit_code == 0, result.output
    assert ("does not match the COFOG function of the split (07" in result.output) is warned


@pytest.mark.parametrize("command", ["aggregate", "run"])
def test_check_ranges_option_is_accepted(command):
    result = runner.invoke(app, [command, "--help"])
    # Rich colours the help on GitHub Actions, so compare the text without ANSI codes
    assert "--check-ranges" in re.sub(r"\x1b\[[0-9;]*m", "", result.output)


def test_aggregate_command_passes_check_ranges(extract):
    tmp, raw_path, lookup_path = extract
    master_path, _ = seed_master(lookup_path, tmp, start_year=2000, end_year=2001)
    split_data(raw_path, "Percent of GDP", {"07"}, tmp / "s")
    args = ["aggregate", "--master-file", str(master_path), "--folder-path", str(tmp / "s")]
    assert "Range check" not in runner.invoke(app, args).output
    result = runner.invoke(app, args + ["--check-ranges"])
    assert result.exit_code == 0 and "Range check: no negative values" in result.output


def test_run_passes_check_ranges_to_aggregate(extract):
    tmp, raw_path, lookup_path = extract
    assert "Range check" not in _run(tmp, raw_path, lookup_path, "07", "DATA_H").output
    result = _run(tmp, raw_path, lookup_path, "07", "DATA_H2", "--check-ranges")
    assert result.exit_code == 0 and "Range check: no negative values" in result.output


def _run_several(tmp, raw_path, lookup_path, *args):
    return runner.invoke(app, ["run", "--source-file", str(raw_path), "--lookup-file", str(lookup_path),
                               "--output-dir", str(tmp / "out"), "--split-dir", str(tmp / "splits"), *args])


def test_run_with_several_cofog_values_fills_one_master(extract):
    tmp, raw_path, lookup_path = extract
    result = _run_several(tmp, raw_path, lookup_path, "--cofog", "05", "--cofog", "07")
    assert result.exit_code == 0, result.output
    master = pd.read_excel(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx")
    for suffix in ("05", "07"):
        assert {f"DATA_{suffix}", f"SOURCE_TIER_{suffix}", f"SOURCE_SECTORS_{suffix}", f"SOURCE_COMPLETE_{suffix}"} <= set(master.columns)
    row = master[master["SortKey"] == "AAA2000"].iloc[0]
    assert row["DATA_07"] == 5.0 and row["SOURCE_TIER_07"] == "T1" and row["SOURCE_TIER_05"] == "T3"
    assert (tmp / "splits" / "05" / ".cofog_panel_split").exists() and (tmp / "splits" / "07" / "AAA.csv").exists()


def test_several_cofog_values_give_the_same_master_as_separate_runs(extract):
    tmp, raw_path, lookup_path = extract
    assert _run_several(tmp, raw_path, lookup_path, "--cofog", "05", "--cofog", "07").exit_code == 0
    together = pd.read_excel(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx")
    for name in ("out", "splits"):
        shutil.rmtree(tmp / name)
    for code in ("05", "07"):
        assert _run_several(tmp, raw_path, lookup_path, "--cofog", code).exit_code == 0
    pd.testing.assert_frame_equal(together, pd.read_excel(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx"))


def test_a_single_cofog_value_still_splits_into_the_split_dir_itself(extract):
    tmp, raw_path, lookup_path = extract
    assert _run_several(tmp, raw_path, lookup_path, "--cofog", "07").exit_code == 0
    assert (tmp / "splits" / "AAA.csv").exists() and not (tmp / "splits" / "07").exists()


@pytest.mark.parametrize("extra, message", [
    (["--data-col", "DATA_X"], "cannot be used with several --cofog values"),
    (["--tier-col", "T"], "cannot be used with several --cofog values"),
    (["--sectors-col", "S"], "cannot be used with several --cofog values"),
    (["--complete-col", "C"], "cannot be used with several --cofog values"),
])
def test_several_cofog_values_refuse_column_names(extract, extra, message):
    tmp, raw_path, lookup_path = extract
    result = _run_several(tmp, raw_path, lookup_path, "--cofog", "05", "--cofog", "07", *extra)
    assert result.exit_code == 1 and message in result.output
    assert not (tmp / "out").exists() and not (tmp / "splits").exists()


def test_several_cofog_values_naming_one_function_are_refused(extract):
    tmp, raw_path, lookup_path = extract
    result = _run_several(tmp, raw_path, lookup_path, "--cofog", "05", "--cofog", "Environmental protection")
    assert result.exit_code == 1 and "give the same data column DATA_05" in result.output
    assert not (tmp / "out").exists()


def test_one_bad_cofog_value_stops_the_run_before_any_file_is_written(extract):
    tmp, raw_path, lookup_path = extract
    result = _run_several(tmp, raw_path, lookup_path, "--cofog", "05", "--cofog", "xx")
    assert result.exit_code == 1 and "Invalid --cofog 'xx'" in result.output
    assert not (tmp / "out").exists() and not (tmp / "splits").exists()


@pytest.mark.parametrize("script", ["cofog_panel/gui.py", "gui.py"])
def test_gui_only_imports_names_that_exist(script):
    """
    The interface (cofog_panel/gui.py) and the launcher shim (gui.py) need Streamlit, which is optional;
    check their cofog_panel imports without running them.
    """
    import ast
    import importlib
    from pathlib import Path
    repo = Path(__file__).parent.parent
    page = ast.parse((repo / "cofog_panel" / "gui.py").read_text(encoding="utf-8"))
    defined_in_page = {node.name for node in page.body if isinstance(node, ast.FunctionDef)}
    tree = ast.parse((repo / script).read_text(encoding="utf-8"))
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module.startswith("cofog_panel")]
    assert imports
    for node in imports:
        if node.module == "cofog_panel.gui":  # imports Streamlit itself
            assert {alias.name for alias in node.names} <= defined_in_page
            continue
        module = importlib.import_module(node.module)
        for alias in node.names:
            assert hasattr(module, alias.name), f"{node.module}.{alias.name}"


def test_gui_command_starts_streamlit_on_the_packaged_page(monkeypatch):
    import subprocess
    import cofog_panel.cli as cli
    calls = []
    monkeypatch.setattr(cli, "_has_streamlit", lambda: True)
    monkeypatch.setattr(subprocess, "call", lambda command: calls.append(command) or 0)
    result = runner.invoke(app, ["gui", "--headless", "--port", "8599"])
    assert result.exit_code == 0, result.output
    command = calls[0]
    assert command[1:4] == ["-m", "streamlit", "run"] and command[4] == str(cli.GUI_SCRIPT)
    assert cli.GUI_SCRIPT.name == "gui.py" and cli.GUI_SCRIPT.parent.name == "cofog_panel" and cli.GUI_SCRIPT.exists()
    assert command[command.index("--server.maxUploadSize") + 1] == "1000"
    assert command[command.index("--server.port") + 1] == "8599"
    assert command[command.index("--server.headless") + 1] == "true"


def test_gui_command_without_streamlit_says_how_to_install_it(monkeypatch):
    import cofog_panel.cli as cli
    monkeypatch.setattr(cli, "_has_streamlit", lambda: False)
    result = runner.invoke(app, ["gui"])
    assert result.exit_code == 1
    assert "Streamlit is not installed" in result.output and 'cofog-panel[gui]' in result.output
