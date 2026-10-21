"""Command-line behaviour: separate provenance per indicator, master reuse, early option checks."""
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
    assert (tmp / "s" / "AAA.xlsx").exists()


def test_invalid_filter_type_fails_before_reading(tmp_path):
    # The source file does not exist: the error must concern the option, not the file
    result = runner.invoke(app, ["split", "--source-file", str(tmp_path / "absent.xlsx"), "--cofog", "05",
                                 "--filter-type", "Percent GDP", "--output-dir", str(tmp_path / "s")])
    assert result.exit_code == 2
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
    ("environmental protection", "'Environmental protection'"),
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


def test_invalid_cofog_on_command_line(extract):
    tmp, raw_path, lookup_path = extract
    result = runner.invoke(app, ["run", "--source-file", str(raw_path), "--lookup-file", str(lookup_path),
                                 "--cofog", "5", "--output-dir", str(tmp / "out")])
    assert result.exit_code == 2
    assert "Did you mean" in result.output and "'05'" in result.output
    assert not (tmp / "out").exists()
