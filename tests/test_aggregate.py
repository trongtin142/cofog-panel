from decimal import Decimal

import pandas as pd
import pytest

from cofog_panel.aggregate import (
    resolve_value, run_aggregation, is_complete,
    GG, CGSS, CGXSS, BCG, EBCG, SSF, SG, LG,
)
from cofog_panel.etl import _cofog_code_from_series, split_data
from cofog_panel.master_seed import seed_master
from cofog_panel.checks import verify_cofog_format, FIXED_HEADERS_SAMPLE


def D(x):
    return Decimal(str(x))


# --- resolve_value: General government three-tier method ---

def test_t1_general_government_reported():
    vals = {GG: D(1.2), CGSS: D(0.5), LG: D(0.7)}
    assert resolve_value(vals)[:2] == (D(1.2), "T1")


def test_t1_zero_is_a_valid_observation():
    vals = {GG: D(0), CGSS: D(0.3)}
    assert resolve_value(vals)[:2] == (D(0), "T1")


def test_zero_as_missing_skips_zero_general_government():
    vals = {GG: D(0), CGSS: D(0.3), LG: D(0.1)}
    assert resolve_value(vals, zero_as_missing=True)[:2] == (D("0.4"), "T2")


def test_zero_as_missing_drops_all_zero_series():
    vals = {GG: D(0), CGSS: D(0), BCG: D(0), LG: D(0)}
    assert resolve_value(vals)[:2] == (D(0), "T1")
    assert resolve_value(vals, zero_as_missing=True)[:2] == (None, "")


def test_t2_sums_central_state_local():
    vals = {GG: None, CGSS: D(0.5), SG: D(0.2), LG: D(0.3)}
    assert resolve_value(vals)[:2] == (D("1.0"), "T2")


def test_t2_missing_subnational_counts_as_zero():
    vals = {CGSS: D(0.5)}
    assert resolve_value(vals)[:2] == (D("0.5"), "T2")


def test_t3_sums_central_components_and_subnational():
    vals = {GG: None, CGSS: None, BCG: D(0.4), EBCG: D(0.1), LG: D(0.2)}
    assert resolve_value(vals)[:2] == (D("0.7"), "T3")


def test_no_data_returns_empty_tier():
    assert resolve_value({GG: None, CGSS: None})[:2] == (None, "")


def test_non_summable_transformation_only_uses_t1():
    vals = {GG: None, CGSS: D(10), LG: D(5)}
    assert resolve_value(vals, summable=False)[:2] == (None, "")
    assert resolve_value({GG: D(12)}, summable=False)[:2] == (D(12), "T1")


# --- resolve_value: other methods ---

def test_central_government_method():
    assert resolve_value({CGSS: D(2)}, "Central government including social security")[:2] == (D(2), "C1")
    vals = {CGSS: None, BCG: D(1), SSF: D(0.5)}
    assert resolve_value(vals, "Central government including social security")[:2] == (D("1.5"), "C2")


def test_direct_sector():
    assert resolve_value({LG: D(0.3)}, "Local Government")[:2] == (D("0.3"), "D")
    assert resolve_value({LG: None}, "Local Government")[:2] == (None, "")


def test_sectors_used_are_reported():
    vals = {GG: None, CGSS: None, BCG: D(0.1), LG: D(0.2)}
    assert resolve_value(vals)[2] == [BCG, LG]


def test_completeness_flag():
    assert is_complete("T1", [GG], [LG]) is True
    assert is_complete("T2", [CGSS, LG], [LG]) is True
    assert is_complete("T2", [CGSS], [LG]) is False          # local level reported in other years
    assert is_complete("T2", [CGSS], []) is True             # unitary country without local data
    assert is_complete("T3", [BCG, LG], [LG]) is True
    assert is_complete("T3", [SSF, LG], [LG]) is False       # no budgetary central government
    assert is_complete("", [], []) is None


def test_completeness_requires_reported_central_components():
    # SSF and EBCG reported in other years must be present in a T3 sum
    assert is_complete("T3", [BCG, EBCG, LG], [EBCG, SSF, LG]) is False
    assert is_complete("T3", [BCG, SSF, LG], [EBCG, SSF, LG]) is False
    assert is_complete("T3", [BCG, EBCG, SSF, LG], [EBCG, SSF, LG]) is True
    # the consolidated central core already contains EBCG
    assert is_complete("T3", [CGXSS, SSF, LG], [EBCG, SSF, LG]) is True
    assert is_complete("C2", [BCG], [SSF]) is False


def test_t1_flagged_when_gg_equals_central_with_subnational_spending():
    vals = {GG: D("1.2"), CGSS: D("1.2"), LG: D("0.3")}
    assert is_complete("T1", [GG], [LG], vals) is False
    vals = {GG: D("1.5"), CGSS: D("1.2"), LG: D("0.3")}
    assert is_complete("T1", [GG], [LG], vals) is True


def test_t3_prefers_consolidated_central_core():
    vals = {GG: None, CGSS: None, CGXSS: D("0.5"), BCG: D("0.4"), EBCG: D("0.2"), LG: D("0.1")}
    value, tier, used = resolve_value(vals)
    assert (value, tier, used) == (D("0.6"), "T3", [CGXSS, LG])
    vals = {GG: None, CGSS: None, BCG: D("0.4"), EBCG: D("0.2"), LG: D("0.1")}
    assert resolve_value(vals)[2] == [BCG, EBCG, LG]


def test_unknown_sector_raises():
    with pytest.raises(ValueError):
        resolve_value({}, "Federal government")


# --- COFOG code parsing ---

@pytest.mark.parametrize("series, code", [
    ("ARM.S1321.G2MF.GF02_T.POGDP_PT.A", "02"),
    ("GRC.S13112.G2MF.GF0810_T.POGDP_PT.A", "08.1"),
    ("X.S13.G2MF.GF0560_T.POGDP_PT.A", "05.6"),
    ("X.S13.G2MF.GF10_T.XDC.A", "10"),
    ("bad-code", None),
])
def test_cofog_code_from_series(series, code):
    assert _cofog_code_from_series(series) == code


# --- End-to-end on a synthetic GFS extract ---

YEARS = [str(y) for y in range(1972, 2025)]
SECTOR_CODES = {
    "General government": "S13",
    "Central government including social security": "S1321",
    "Budgetary central government": "S1311B",
    "Extrabudgetary central government": "S13112",
    "Social security funds": "S1314",
    "State Government": "S1312MIXED",
    "Local Government": "S1313MIXED",
}


def _raw_rows(iso, country, values, cofog_label="Environmental protection", cofog_code="05",
              transformation="Percent of GDP"):
    """values: {sector: {year: value}}"""
    rows = []
    for sector, by_year in values.items():
        row = {h: "" for h in FIXED_HEADERS_SAMPLE}
        row.update({
            "SERIES_CODE": f"{iso}.{SECTOR_CODES[sector]}.G2MF.GF{cofog_code}_T.POGDP_PT.A",
            "COUNTRY": country, "SECTOR": sector, "COFOG": cofog_label,
            "TYPE_OF_TRANSFORMATION": transformation,
        })
        row.update({y: by_year.get(int(y)) for y in YEARS})
        rows.append(row)
    return rows


@pytest.fixture
def workspace(tmp_path):
    rows = []
    # AAA: GG in 2000, GG=0 in 2001, only CGSS+LG in 2002, only BCG+LG in 2003
    rows += _raw_rows("AAA", "Alpha", {
        "General government": {2000: 1.0, 2001: 0.0},
        "Central government including social security": {2000: 0.6, 2001: 0.0, 2002: 0.5},
        "Budgetary central government": {2003: 0.4},
        "Local Government": {2000: 0.4, 2002: 0.25, 2003: 0.2},
    })
    # BBB: a different function and a different transformation, both must be filtered out
    rows += _raw_rows("BBB", "Beta", {"General government": {2000: 9.0}},
                      cofog_label="Defence", cofog_code="02")
    rows += _raw_rows("BBB", "Beta", {"General government": {2000: 7.0}},
                      transformation="Percent of total outlays")
    raw = pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS)
    raw_path = tmp_path / "raw.xlsx"
    raw.to_excel(raw_path, index=False)

    lookup = pd.DataFrame({"name": ["Alpha", "Beta"], "alpha-2": ["AA", "BB"],
                           "alpha-3": ["AAA", "BBB"], "country-code": [1, 2]})
    lookup_path = tmp_path / "countries.xlsx"
    lookup.to_excel(lookup_path, index=False)
    return tmp_path, raw_path, lookup_path


def test_format_check_accepts_synthetic_extract(workspace):
    _, raw_path, _ = workspace
    assert verify_cofog_format(raw_path)[0]


def test_pipeline_end_to_end(workspace):
    tmp, raw_path, lookup_path = workspace
    master_path, ok = seed_master(lookup_path, tmp)
    assert ok
    split_dir, ok = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "splits")
    assert ok
    assert sorted(f.name for f in split_dir.glob("*.xlsx")) == ["AAA.xlsx"]

    assert run_aggregation(master_path, split_dir, "DATA_ENV", "General government")
    out = pd.read_excel(master_path, sheet_name="MasterData", dtype=str).fillna("")
    out = out.set_index("SortKey")
    assert list(out.columns) == ["Country", "Year", "DATA_ENV", "SOURCE_TIER_ENV", "SOURCE_SECTORS_ENV", "SOURCE_COMPLETE_ENV"]
    assert out.at["AAA2002", "SOURCE_COMPLETE_ENV"] == "Y"
    assert out.at["AAA2002", "SOURCE_SECTORS_ENV"] == "CGSS+LG"
    assert out.at["AAA2003", "SOURCE_SECTORS_ENV"] == "BCG+LG"

    def cell(key):
        return float(out.at[key, "DATA_ENV"]), out.at[key, "SOURCE_TIER_ENV"]

    assert cell("AAA2000") == (1.0, "T1")
    assert cell("AAA2001") == (0.0, "T1")
    assert cell("AAA2002") == (0.75, "T2")
    assert cell("AAA2003") == (pytest.approx(0.6), "T3")
    assert out.at["AAA2004", "DATA_ENV"] == ""
    assert out.at["BBB2000", "DATA_ENV"] == ""


def test_split_by_label_matches_split_by_code(workspace):
    tmp, raw_path, _ = workspace
    d1, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "by_code")
    d2, _ = split_data(raw_path, "Percent of GDP", {"Environmental protection"}, tmp / "by_label")
    a = pd.read_excel(d1 / "AAA.xlsx")
    b = pd.read_excel(d2 / "AAA.xlsx")
    pd.testing.assert_frame_equal(a, b)


def test_split_without_matches_fails(workspace):
    tmp, raw_path, _ = workspace
    _, ok = split_data(raw_path, "Percent of GDP", {"99"}, tmp / "none")
    assert not ok


def test_split_refuses_foreign_directory(workspace):
    tmp, raw_path, _ = workspace
    user_dir = tmp / "user"
    user_dir.mkdir()
    (user_dir / "TAX.xlsx").write_text("not a split file")
    _, ok = split_data(raw_path, "Percent of GDP", {"05"}, user_dir)
    assert not ok
    assert (user_dir / "TAX.xlsx").exists()


def test_split_reruns_in_its_own_directory(workspace):
    tmp, raw_path, _ = workspace
    d, ok = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "s")
    assert ok
    d, ok = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "s")
    assert ok and sorted(f.name for f in d.glob("*.xlsx")) == ["AAA.xlsx"]


def test_second_indicator_keeps_first_and_values_are_numeric(workspace):
    tmp, raw_path, lookup_path = workspace
    master_path, _ = seed_master(lookup_path, tmp)
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "splits")
    assert run_aggregation(master_path, split_dir, "DATA_ENV", tier_col_out="ENV_TIER",
                           sectors_col_out="ENV_SECTORS", complete_col_out="ENV_COMPLETE")
    assert run_aggregation(master_path, split_dir, "DATA_ENV2")
    out = pd.read_excel(master_path, sheet_name="MasterData")
    assert {"DATA_ENV", "ENV_TIER", "DATA_ENV2", "SOURCE_TIER_ENV2"} <= set(out.columns)
    assert pd.api.types.is_numeric_dtype(out["DATA_ENV"])
    assert pd.api.types.is_numeric_dtype(out["DATA_ENV2"])
    assert pd.api.types.is_integer_dtype(out["Year"])


def test_corrupt_country_file_fails_the_stage(workspace):
    tmp, raw_path, lookup_path = workspace
    master_path, _ = seed_master(lookup_path, tmp)
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "splits")
    (split_dir / "BBB.xlsx").write_text("corrupt")
    assert not run_aggregation(master_path, split_dir, "DATA_ENV")


def test_seed_master_year_range(workspace):
    tmp, _, lookup_path = workspace
    master_path, ok = seed_master(lookup_path, tmp, start_year=2000, end_year=2002)
    out = pd.read_excel(master_path, sheet_name="MasterData")
    assert ok and sorted(out["Year"].unique()) == [2000, 2001, 2002]
    assert list(out.columns) == ["SortKey", "Country", "Year"]
