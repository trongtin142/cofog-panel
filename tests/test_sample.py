"""
The sample extract in data/sample (COFOG group 07.3 of the IMF release of 3 February 2026) gives the
master of the full extract: the rows of Table 2 of the software paper and the tier counts.
"""
import hashlib
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from cofog_panel import __version__, build_panel, read_provenance
from cofog_panel.cli import app

SAMPLE = Path(__file__).parent.parent / "data" / "sample" / "gfs_cofog_073_sample.csv"
SAMPLE_SHA256 = "b5758935d1ecf7d449360cd5cdbf7d936970dba149ae4b86ccfcec99b8c40fc2"
PUBLICATION_DATE = "2026-02-03T08:39:08.886374500Z"
# SortKey: (DATA_07_3, tier, sectors, complete), as in the master of the full Excel download (SHA-256 91e3db1b...)
TABLE_2 = {
    "NPL2018": (0.470262180783715, "T3", "BCG", "N"),
    "NPL2019": (0.510641031199198, "T2", "CGSS", "N"),
    "NPL2020": (0.501560976378763, "T1", "GG", "Y"),
    "NPL2023": (0.6968833190971057, "T3", "BCG+SG+LG", "Y"),
    "ZAF2008": (0.0, "T3", "SSF+LG", "N"),
    "ZAF2009": (1.90184841686204, "T1", "GG", "Y"),
}
# Counts of the full extract, which the sample reproduces
TIERS = {"T1": 1346, "T2": 300, "T3": 791}
FILLED, INCOMPLETE, MASTER_ROWS, COUNTRIES_WITH_VALUES = 2437, 633, 13500, 135

pytestmark = pytest.mark.skipif(not SAMPLE.exists(), reason="data/sample comes with the repository and the sdist")


@pytest.fixture(scope="module")
def sample_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sample")
    result = CliRunner().invoke(app, ["run", "--cofog", "07.3", "--source-file", str(SAMPLE),
                                      "--output-dir", str(tmp / "output"), "--split-dir", str(tmp / "splits")])
    assert result.exit_code == 0, result.output
    return tmp / "output" / "COFOG_MASTER_SCHEMA.xlsx", result.output


def test_sample_is_the_published_file():
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == SAMPLE_SHA256


def test_sample_reproduces_the_rows_of_table_2(sample_run):
    master = pd.read_excel(sample_run[0], sheet_name="MasterData").set_index("SortKey")
    for key, (value, tier, sectors, complete) in TABLE_2.items():
        row = master.loc[key]
        assert row["DATA_07_3"] == value, key
        assert (row["SOURCE_TIER_07_3"], row["SOURCE_SECTORS_07_3"], row["SOURCE_COMPLETE_07_3"]) == (tier, sectors, complete)


def test_sample_reproduces_the_tier_counts(sample_run):
    master = pd.read_excel(sample_run[0], sheet_name="MasterData")
    assert len(master) == MASTER_ROWS
    assert master["SOURCE_TIER_07_3"].value_counts().to_dict() == TIERS
    assert int(master["DATA_07_3"].notna().sum()) == FILLED
    assert int((master["SOURCE_COMPLETE_07_3"] == "N").sum()) == INCOMPLETE
    assert master.loc[master["DATA_07_3"].notna(), "SortKey"].str[:3].nunique() == COUNTRIES_WITH_VALUES


def test_sample_run_records_its_provenance(sample_run):
    path, output = sample_run
    assert f"SHA-256 {SAMPLE_SHA256}" in output
    provenance = read_provenance(path)
    assert len(provenance) == 1
    row = provenance.iloc[0]
    assert row["Source file"] == SAMPLE.name and row["Source SHA-256"] == SAMPLE_SHA256
    assert row["PUBLICATION_DATE"] == PUBLICATION_DATE and row["cofog-panel version"] == __version__
    assert row["Columns created"] == "DATA_07_3, SOURCE_TIER_07_3, SOURCE_SECTORS_07_3, SOURCE_COMPLETE_07_3"
    assert row["Command"].startswith("cofog-panel run") and "--cofog 07.3" in row["Options"]


def test_build_panel_on_the_sample_returns_the_values_of_the_master(sample_run):
    master = pd.read_excel(sample_run[0], sheet_name="MasterData")
    master = master[master["DATA_07_3"].notna()].reset_index(drop=True)
    panel = build_panel(SAMPLE, "07.3")
    assert len(panel) == FILLED
    assert (panel["iso3"] + panel["year"].astype(str)).tolist() == master["SortKey"].tolist()
    assert panel["value"].tolist() == master["DATA_07_3"].tolist()
    assert panel["tier"].tolist() == master["SOURCE_TIER_07_3"].tolist()
    assert panel["sectors"].tolist() == master["SOURCE_SECTORS_07_3"].tolist()
    assert panel["complete"].tolist() == master["SOURCE_COMPLETE_07_3"].tolist()
    assert panel.attrs["provenance"][0]["Source SHA-256"] == SAMPLE_SHA256
