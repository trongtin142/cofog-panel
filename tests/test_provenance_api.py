"""The Provenance sheet written by `run` and the Python interface `build_panel`."""
import hashlib

import openpyxl
import pandas as pd
import pytest
from typer.testing import CliRunner

from cofog_panel import PipelineError, __version__, build_panel, read_provenance
from cofog_panel.aggregate import run_aggregation
from cofog_panel.cli import app
from cofog_panel.etl import split_data
from cofog_panel.master_seed import seed_master
from cofog_panel.options import OptionError
from cofog_panel.provenance import PROVENANCE_COLUMNS, format_options
from tests.test_cli import extract  # noqa: F401  (fixture)

runner = CliRunner()


def _run(tmp, raw_path, lookup_path, *cofog):
    return runner.invoke(app, ["run", *cofog, "--source-file", str(raw_path), "--lookup-file", str(lookup_path),
                               "--output-dir", str(tmp / "out"), "--split-dir", str(tmp / "splits")])


def test_run_adds_a_provenance_sheet_and_prints_the_sha256(extract):  # noqa: F811
    tmp, raw_path, lookup_path = extract
    result = _run(tmp, raw_path, lookup_path, "--cofog", "05")
    assert result.exit_code == 0, result.output
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    assert f"SHA-256 {digest}" in result.output
    book = openpyxl.load_workbook(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx", read_only=True)
    assert book.sheetnames == ["MasterData", "Provenance"]
    book.close()
    provenance = read_provenance(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx")
    assert list(provenance.columns) == PROVENANCE_COLUMNS and len(provenance) == 1
    row = provenance.iloc[0]
    assert row["Run"] == "1" and row["cofog-panel version"] == __version__
    assert row["Source file"] == "raw.xlsx" and row["Source SHA-256"] == digest
    assert row["Source size (bytes)"] == str(raw_path.stat().st_size)
    assert row["COFOG"] == "05" and row["Transformation"] == "Percent of GDP"
    assert row["Method (--sector)"] == "General government"
    assert row["Columns created"] == "DATA_05, SOURCE_TIER_05, SOURCE_SECTORS_05, SOURCE_COMPLETE_05"
    assert row["Command"].startswith("cofog-panel run")
    for option in ("--cofog 05", '--filter-type "Percent of GDP"', "--zero-as-missing false", "--start-year 1972"):
        assert option in row["Options"]
    assert row["Time (UTC)"].endswith("Z") and len(row["Time (UTC)"]) == 20


def test_master_data_is_the_same_as_without_the_provenance_sheet(extract):  # noqa: F811
    """The sheet MasterData written by `run` equals the one written by the stages, which add no provenance."""
    tmp, raw_path, lookup_path = extract
    assert _run(tmp, raw_path, lookup_path, "--cofog", "05").exit_code == 0
    master_path, _ = seed_master(lookup_path, tmp / "stages")
    folder, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "stages_split", lookup_path)
    assert run_aggregation(master_path, folder, "DATA_05")
    with_run = pd.read_excel(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx", sheet_name="MasterData", dtype=str)
    pd.testing.assert_frame_equal(with_run, pd.read_excel(master_path, sheet_name="MasterData", dtype=str))
    assert openpyxl.load_workbook(master_path, read_only=True).sheetnames == ["MasterData"]


def test_a_second_run_appends_its_rows(extract):  # noqa: F811
    tmp, raw_path, lookup_path = extract
    assert _run(tmp, raw_path, lookup_path, "--cofog", "05").exit_code == 0
    assert _run(tmp, raw_path, lookup_path, "--cofog", "07", "--cofog", "health").exit_code == 1  # same function twice
    assert _run(tmp, raw_path, lookup_path, "--cofog", "07").exit_code == 0
    provenance = read_provenance(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx")
    assert provenance["Run"].tolist() == ["1", "2"]
    assert provenance["COFOG"].tolist() == ["05", "07"]
    assert provenance["Columns created"].iloc[1].startswith("DATA_07, SOURCE_TIER_07")
    master = pd.read_excel(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx", sheet_name="MasterData")
    assert {"DATA_05", "DATA_07"} <= set(master.columns)


def test_format_options_quotes_values_with_spaces():
    assert format_options({"--cofog": ["05", "07"], "--sector": "General government", "--zero-as-missing": False}) \
        == '--cofog 05 --cofog 07 --sector "General government" --zero-as-missing false'


def test_build_panel_returns_the_master_in_tidy_form(extract):  # noqa: F811
    tmp, raw_path, lookup_path = extract
    assert _run(tmp, raw_path, lookup_path, "--cofog", "05", "--cofog", "07").exit_code == 0
    master = pd.read_excel(tmp / "out" / "COFOG_MASTER_SCHEMA.xlsx", sheet_name="MasterData")
    panel = build_panel(raw_path, ["05", "07"], lookup_file=lookup_path)
    assert list(panel.columns) == ["iso3", "country", "year", "cofog", "value", "tier", "sectors", "complete"]
    for code, suffix in (("05", "05"), ("07", "07")):
        part = panel[panel["cofog"] == code]
        rows = master[master[f"DATA_{suffix}"].notna()]
        assert (part["iso3"] + part["year"].astype(str)).tolist() == rows["SortKey"].tolist()
        assert part["value"].tolist() == rows[f"DATA_{suffix}"].tolist()
        assert part["tier"].tolist() == rows[f"SOURCE_TIER_{suffix}"].tolist()
    aaa = panel[(panel["iso3"] == "AAA") & (panel["year"] == 2000) & (panel["cofog"] == "05")].iloc[0]
    assert (aaa["value"], aaa["tier"], aaa["sectors"], aaa["complete"]) == (pytest.approx(0.6), "T3", "BCG+LG", "Y")
    assert [row["COFOG"] for row in panel.attrs["provenance"]] == ["05", "07"]
    assert panel.attrs["provenance"][0]["Command"] == "build_panel (Python)"


def test_build_panel_options(extract):  # noqa: F811
    tmp, raw_path, lookup_path = extract
    full = build_panel(raw_path, "05", lookup_file=lookup_path, keep_empty=True, start_year=2000, end_year=2001)
    assert len(full) == 4 and full["value"].notna().sum() == 2
    by_label = build_panel(raw_path, "environmental protection", lookup_file=lookup_path, sector="local government")
    assert by_label["cofog"].unique().tolist() == ["Environmental protection"]
    assert by_label["tier"].unique().tolist() == ["D"]


def test_build_panel_errors(extract, tmp_path):  # noqa: F811
    _, raw_path, lookup_path = extract
    with pytest.raises(FileNotFoundError):
        build_panel(tmp_path / "missing.csv", "05")
    with pytest.raises(OptionError, match="Invalid --cofog"):
        build_panel(raw_path, "xx", lookup_file=lookup_path)
    with pytest.raises(ValueError, match="Invalid --filter-type"):
        build_panel(raw_path, "05", filter_type="per cent", lookup_file=lookup_path)
    with pytest.raises(ValueError, match="Invalid --sector"):
        build_panel(raw_path, "05", sector="general govt", lookup_file=lookup_path)
    bad = tmp_path / "bad.csv"
    bad.write_text("A,B\n1,2\n")
    with pytest.raises(PipelineError) as failure:
        build_panel(bad, "05")
    assert "FORMAT VERIFICATION REPORT" in failure.value.log
