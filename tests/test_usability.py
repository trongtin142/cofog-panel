"""Defaults, look-up commands, error format and exit codes of the command-line tool."""
import filecmp
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

import cofog_panel.cli as cli
from cofog_panel.checks import FIXED_HEADERS_SAMPLE
from cofog_panel.master_seed import PACKAGED_LOOKUP
from cofog_panel.options import data_column_for

runner = CliRunner()
REPO = Path(__file__).resolve().parents[1]
YEARS = [str(y) for y in range(1972, 2025)]


def _row(iso, sector_code, sector, cofog_code, label, by_year):
    row = dict.fromkeys(FIXED_HEADERS_SAMPLE, "")
    row.update({
        "SERIES_CODE": f"{iso}.{sector_code}.G2MF.GF{cofog_code}_T.POGDP_PT.A",
        "COUNTRY": iso, "SECTOR": sector, "COFOG": label, "TYPE_OF_TRANSFORMATION": "Percent of GDP",
    })
    row.update({y: by_year.get(int(y)) for y in YEARS})
    return row


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A working directory laid out like the repository: data/gfs_raw_data.xlsx with ARM and ALB series."""
    rows = [
        _row("ARM", "S13", "General government", "05", "Environmental protection", {2013: 0.35}),
        _row("ARM", "S1311B", "Budgetary central government", "05", "Environmental protection", {2014: 0.1}),
        _row("ALB", "S13", "General government", "05", "Environmental protection", {2015: 0.4}),
        _row("ALB", "S13", "General government", "0730", "Hospital services", {2015: 1.1}),
        _row("ALB", "S13", "General government", "07", "Health", {2015: 2.9}),
    ]
    (tmp_path / "data").mkdir()
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(tmp_path / "data" / "gfs_raw_data.xlsx", index=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _master(path):
    return pd.read_excel(path, sheet_name="MasterData", dtype=str).fillna("").set_index("SortKey")


# --- Defaults ---

def test_packaged_lookup_matches_repository_copy():
    assert PACKAGED_LOOKUP.exists()
    assert filecmp.cmp(PACKAGED_LOOKUP, REPO / "data" / "country_codes.xlsx", shallow=False)


@pytest.mark.parametrize("selector, column", [
    ("05", "DATA_05"), ("07.3", "DATA_07_3"), ("07.12", "DATA_07_12"),
    ("Environmental protection", "DATA_05"), ("Hospital services", "DATA_07_3"),
    ("Custom function", "DATA_CUSTOM_FUNCTION"),
])
def test_data_column_from_cofog(selector, column):
    assert data_column_for(selector) == column


def test_run_with_defaults_only_needs_cofog(project):
    result = runner.invoke(cli.app, ["run", "--cofog", "05"])
    assert result.exit_code == 0, result.output
    out = _master(project / "output" / "COFOG_MASTER_SCHEMA.xlsx")
    # Bundled lookup: real countries; derived column names
    assert {"DATA_05", "SOURCE_TIER_05", "SOURCE_SECTORS_05", "SOURCE_COMPLETE_05"} <= set(out.columns)
    assert out.at["ARM2013", "SOURCE_TIER_05"] == "T1"
    assert out.at["ARM2014", "SOURCE_SECTORS_05"] == "BCG"
    assert "DATA_NEW" not in out.columns


def test_explicit_data_new_keeps_legacy_names(project):
    result = runner.invoke(cli.app, ["run", "--cofog", "05", "--data-col", "DATA_NEW"])
    assert result.exit_code == 0, result.output
    out = _master(project / "output" / "COFOG_MASTER_SCHEMA.xlsx")
    assert {"DATA_NEW", "SOURCE_TIER", "SOURCE_SECTORS", "SOURCE_COMPLETE"} <= set(out.columns)


def test_group_code_gives_group_column(project):
    result = runner.invoke(cli.app, ["run", "--cofog", "07.3"])
    assert result.exit_code == 0, result.output
    out = _master(project / "output" / "COFOG_MASTER_SCHEMA.xlsx")
    assert out.at["ALB2015", "DATA_07_3"] == "1.1"
    assert "SOURCE_SECTORS_07_3" in out.columns


def test_aggregate_takes_column_name_from_split(project):
    assert runner.invoke(cli.app, ["seed-master"]).exit_code == 0
    assert runner.invoke(cli.app, ["split", "--cofog", "Environmental protection"]).exit_code == 0
    result = runner.invoke(cli.app, ["aggregate", "--master-file", "output/COFOG_MASTER_SCHEMA.xlsx",
                                     "--folder-path", "intermediate_splits"])
    assert result.exit_code == 0, result.output
    assert "DATA_05" in _master(project / "output" / "COFOG_MASTER_SCHEMA.xlsx").columns


def test_check_commands_use_defaults(project):
    assert runner.invoke(cli.app, ["check-format"]).exit_code == 0
    assert runner.invoke(cli.app, ["check-country-format"]).exit_code == 0


# --- Look-up commands ---

def test_list_sectors():
    result = runner.invoke(cli.app, ["list-sectors"])
    assert result.exit_code == 0
    for value in cli.VALID_SECTORS + ["Percent of GDP", "Domestic currency", "Percent of total outlays"]:
        assert value in result.output


def test_list_cofog(project):
    result = runner.invoke(cli.app, ["list-cofog"])
    assert result.exit_code == 0, result.output
    lines = [line.split() for line in result.output.splitlines()]
    assert ["05", "2", "Environmental", "protection"] in lines
    assert ["07.3", "1", "Hospital", "services"] in lines
    assert "3 COFOG functions" in result.output


# --- Errors: two lines, no traceback, exit codes ---

def _assert_friendly(result, code=1):
    assert result.exit_code == code, result.output
    assert "Error:" in result.output and "Hint:" in result.output
    assert "Traceback" not in result.output


def test_missing_source_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for command in (["run", "--cofog", "05"], ["split", "--cofog", "05"], ["check-format"], ["list-cofog"]):
        result = runner.invoke(cli.app, command)
        _assert_friendly(result)
        assert "Source file not found" in result.output and "data.imf.org" in result.output


def test_missing_lookup_file(project):
    _assert_friendly(runner.invoke(cli.app, ["seed-master", "--lookup-file", "absent.xlsx"]))


def test_wrong_filter_type(project):
    result = runner.invoke(cli.app, ["split", "--cofog", "05", "--filter-type", "per cent of GDP"])
    _assert_friendly(result)
    assert "Percent of total outlays" in result.output


def test_wrong_cofog(project):
    result = runner.invoke(cli.app, ["run", "--cofog", "Health care"])
    _assert_friendly(result)
    assert "list-cofog" in result.output


def test_wrong_sector(project):
    _assert_friendly(runner.invoke(cli.app, ["run", "--cofog", "05", "--sector", "general government"]))


def test_foreign_split_directory(project):
    (project / "mine").mkdir()
    (project / "mine" / "notes.txt").write_text("user file")
    result = runner.invoke(cli.app, ["split", "--cofog", "05", "--output-dir", "mine"])
    _assert_friendly(result)
    assert (project / "mine" / "notes.txt").exists()


def test_missing_master_or_split_directory(project):
    result = runner.invoke(cli.app, ["aggregate", "--master-file", "absent.xlsx", "--folder-path", "splits"])
    _assert_friendly(result)
    assert runner.invoke(cli.app, ["seed-master"]).exit_code == 0
    result = runner.invoke(cli.app, ["aggregate", "--master-file", "output/COFOG_MASTER_SCHEMA.xlsx",
                                     "--folder-path", "no_such_dir"])
    _assert_friendly(result)


def test_usage_errors_exit_with_2():
    assert runner.invoke(cli.app, ["run", "--no-such-option"]).exit_code == 2
    assert runner.invoke(cli.app, ["split"]).exit_code == 2  # --cofog is required


def test_unexpected_error_is_short_unless_debug(project, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("disk exploded")
    monkeypatch.setattr(cli, "split_data", broken)
    result = runner.invoke(cli.app, ["split", "--cofog", "05"])
    _assert_friendly(result)
    assert "RuntimeError: disk exploded" in result.output and "--debug" in result.output

    result = runner.invoke(cli.app, ["--debug", "split", "--cofog", "05"])
    assert isinstance(result.exception, RuntimeError)


# --- CSV download (the IMF portal's default format) ---

def _as_csv(xlsx_path, csv_path):
    """Write the extract as the IMF portal does: UTF-8 with BOM, every field quoted."""
    frame = pd.read_excel(xlsx_path, dtype=str).fillna("")
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig", quoting=1)


def test_csv_and_excel_downloads_give_the_same_panel(project):
    _as_csv(project / "data" / "gfs_raw_data.xlsx", project / "extract.csv")
    for name, source in (("xlsx", "data/gfs_raw_data.xlsx"), ("csv", "extract.csv")):
        result = runner.invoke(cli.app, ["run", "--cofog", "05", "--source-file", source,
                                         "--output-dir", f"out_{name}", "--split-dir", f"split_{name}"])
        assert result.exit_code == 0, result.output
    pd.testing.assert_frame_equal(_master(project / "out_xlsx" / "COFOG_MASTER_SCHEMA.xlsx"),
                                  _master(project / "out_csv" / "COFOG_MASTER_SCHEMA.xlsx"))


def test_csv_is_used_when_there_is_no_xlsx(project):
    _as_csv(project / "data" / "gfs_raw_data.xlsx", project / "data" / "gfs_raw_data.csv")
    (project / "data" / "gfs_raw_data.xlsx").unlink()
    assert runner.invoke(cli.app, ["check-format"]).exit_code == 0
    result = runner.invoke(cli.app, ["list-cofog"])
    assert result.exit_code == 0 and "gfs_raw_data.csv" in result.output
    assert ["07.3", "1", "Hospital", "services"] in [line.split() for line in result.output.splitlines()]
    result = runner.invoke(cli.app, ["run", "--cofog", "Hospital services"])
    assert result.exit_code == 0, result.output
    assert _master(project / "output" / "COFOG_MASTER_SCHEMA.xlsx").at["ALB2015", "DATA_07_3"] == "1.1"


def test_two_indicators_with_defaults_keep_separate_tiers(project):
    assert runner.invoke(cli.app, ["run", "--cofog", "05"]).exit_code == 0
    result = runner.invoke(cli.app, ["run", "--cofog", "07"])
    assert result.exit_code == 0, result.output
    assert "replaced" not in result.output
    out = _master(project / "output" / "COFOG_MASTER_SCHEMA.xlsx")
    assert {"SOURCE_TIER_05", "SOURCE_TIER_07"} <= set(out.columns)
    assert out.at["ARM2014", "SOURCE_TIER_05"] == "T3"
    assert out.at["ALB2015", "SOURCE_TIER_07"] == "T1"


def test_missing_source_prints_exactly_two_lines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli.app, ["run", "--cofog", "05", "--source-file", "nope.xlsx"])
    assert result.exit_code == 1
    lines = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) == 2, result.output
    assert lines[0].startswith("❌ Error: Source file not found: nope.xlsx")
    assert lines[1].lstrip().startswith("Hint:")
    assert "Unexpected" not in result.output


@pytest.mark.parametrize("command", [
    ["split", "--cofog", "05", "--filter-type", "bad"],
    ["run", "--cofog", "5"],
    ["run", "--cofog", "05", "--sector", "bad"],
    ["list-cofog", "--source-file", "nope.csv"],
])
def test_option_errors_are_not_reported_as_unexpected(project, command):
    result = runner.invoke(cli.app, command)
    assert result.exit_code == 1
    assert "Unexpected" not in result.output
    assert len([line for line in result.output.splitlines() if line.strip()]) == 2, result.output
