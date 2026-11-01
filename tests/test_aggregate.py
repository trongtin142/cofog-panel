from decimal import Decimal

import pandas as pd
import pytest

from cofog_panel.aggregate import (
    _as_decimal, resolve_value, run_aggregation, is_complete,
    GG, CGSS, CGXSS, BCG, EBCG, SSF, SG, LG,
)
from cofog_panel.etl import _cofog_code_from_series, _country_of, country_files, list_cofog, read_split_marker, split_data
from cofog_panel.master_seed import seed_master
from cofog_panel.checks import verify_cofog_format, verify_country_format, FIXED_HEADERS_SAMPLE


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
    assert sorted(f.name for f in split_dir.glob("*.csv")) == ["AAA.csv"]

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
    a = pd.read_csv(d1 / "AAA.csv", dtype=str)
    b = pd.read_csv(d2 / "AAA.csv", dtype=str)
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
    assert ok and sorted(f.name for f in d.glob("*.csv")) == ["AAA.csv"]


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
    (split_dir / "BBB.csv").write_text("corrupt")
    assert not run_aggregation(master_path, split_dir, "DATA_ENV")


def test_seed_master_year_range(workspace):
    tmp, _, lookup_path = workspace
    master_path, ok = seed_master(lookup_path, tmp, start_year=2000, end_year=2002)
    out = pd.read_excel(master_path, sheet_name="MasterData")
    assert ok and sorted(out["Year"].unique()) == [2000, 2001, 2002]
    assert list(out.columns) == ["SortKey", "Country", "Year"]


# --- Several series for one sector ---

def _duplicate_workspace(tmp_path, second_value):
    rows = _raw_rows("AAA", "Alpha", {"General government": {2000: 1.0}})
    rows += _raw_rows("AAA", "Alpha", {"General government": {2000: second_value}})
    raw_path = tmp_path / "dup.xlsx"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(raw_path, index=False)
    lookup_path = tmp_path / "countries.xlsx"
    pd.DataFrame({"name": ["Alpha"], "alpha-2": ["AA"], "alpha-3": ["AAA"], "country-code": [1]}).to_excel(
        lookup_path, index=False)
    master_path, _ = seed_master(lookup_path, tmp_path)
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp_path / "splits")
    return master_path, split_dir


def test_conflicting_series_for_one_sector_warn_and_use_the_first(tmp_path, capsys):
    master_path, split_dir = _duplicate_workspace(tmp_path, 2.0)
    assert run_aggregation(master_path, split_dir, "DATA_ENV")
    assert "several series with different values for ['general government']" in capsys.readouterr().out
    out = pd.read_excel(master_path, sheet_name="MasterData").set_index("SortKey")
    assert out.at["AAA2000", "DATA_ENV"] == 1.0


def test_identical_repeated_series_do_not_warn(tmp_path, capsys):
    master_path, split_dir = _duplicate_workspace(tmp_path, 1.0)
    assert run_aggregation(master_path, split_dir, "DATA_ENV")
    assert "several series" not in capsys.readouterr().out


# --- Header check: extra columns warn, missing columns fail ---

def _extract_with_columns(path, extra=(), drop=()):
    columns = [c for c in FIXED_HEADERS_SAMPLE if c not in drop] + list(extra) + YEARS
    pd.DataFrame([dict.fromkeys(columns, "")], columns=columns).to_excel(path, index=False)
    return path


def test_format_check_warns_about_extra_columns_but_passes(tmp_path, capsys):
    ok, details = verify_cofog_format(_extract_with_columns(tmp_path / "x.xlsx", extra=["NEW_IMF_FIELD"]))
    out = capsys.readouterr().out
    assert ok and details["Extra_Headers"] == ["NEW_IMF_FIELD"]
    assert "SUCCESS" in out and "Unknown extra columns" in out


def test_format_check_still_fails_on_missing_column(tmp_path):
    path = _extract_with_columns(tmp_path / "x.xlsx", extra=["NEW_IMF_FIELD"], drop=["SECTOR"])
    ok, details = verify_cofog_format(path)
    assert not ok and details["Missing_Headers"] == ["SECTOR"]


# --- Completeness and selection: edge cases ---

def test_completeness_central_core_needs_budgetary_when_extrabudgetary_is_reported():
    assert is_complete("T3", [EBCG, LG], [EBCG, LG]) is False      # BCG missing
    assert is_complete("T3", [BCG, EBCG, LG], [EBCG, LG]) is True
    assert is_complete("T3", [BCG, LG], [LG]) is True               # EBCG never reported


def test_selected_sectors_are_always_reported_ones():
    """Exhaustive over which sectors are reported: sectors used are reported, and tier matches the rule."""
    import itertools
    sectors = [GG, CGSS, CGXSS, BCG, EBCG, SSF, SG, LG]
    for present in itertools.product([False, True], repeat=len(sectors)):
        values = {s: (D(1) if p else None) for s, p in zip(sectors, present)}
        reported = {s for s, p in zip(sectors, present) if p}
        for method in ("General government", "Central government including social security",
                       "Budgetary central government"):
            value, tier, used = resolve_value(values, method)
            assert set(used) <= reported
            assert (value is None) == (tier == "") == (used == [])
            if value is not None:
                assert value == len(used)   # every reported value is 1


# --- Country files: CSV, with older .xlsx splits still readable ---

def _master_after_aggregate(workspace, split_dir, master_name):
    tmp, _, lookup_path = workspace
    master_path, _ = seed_master(lookup_path, tmp, master_name)
    assert run_aggregation(master_path, split_dir, "DATA_ENV")
    return pd.read_excel(master_path, sheet_name="MasterData", dtype=str).fillna("")


def test_older_xlsx_split_gives_the_same_master(workspace):
    tmp, raw_path, _ = workspace
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "splits")
    from_csv = _master_after_aggregate(workspace, split_dir, "csv.xlsx")
    for path in split_dir.glob("*.csv"):
        pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig").to_excel(
            path.with_suffix(".xlsx"), index=False)
        path.unlink()
    assert [f.suffix for f in country_files(split_dir)] == [".xlsx"]
    from_xlsx = _master_after_aggregate(workspace, split_dir, "xlsx.xlsx")
    pd.testing.assert_frame_equal(from_csv, from_xlsx)


def test_csv_is_preferred_and_resplit_removes_older_xlsx(workspace):
    tmp, raw_path, _ = workspace
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "splits")
    (split_dir / "AAA.xlsx").write_text("older split")
    assert [f.name for f in country_files(split_dir)] == ["AAA.csv"]
    split_data(raw_path, "Percent of GDP", {"05"}, split_dir)
    assert sorted(f.name for f in split_dir.glob("[A-Z]*")) == ["AAA.csv"]


def test_country_file_keeps_text_exactly(workspace):
    tmp, raw_path, _ = workspace
    rows = _raw_rows("AAA", "Alpha", {"General government": {2000: 0.1}})
    rows[0]["FULL_DESCRIPTION"] = 'Ünïcode, "quoted"\nsecond line'
    path = tmp / "special.xlsx"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(path, index=False)
    split_dir, ok = split_data(path, "Percent of GDP", {"05"}, tmp / "special_split")
    assert ok
    back = pd.read_csv(split_dir / "AAA.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    assert back.at[0, "FULL_DESCRIPTION"] == 'Ünïcode, "quoted"\nsecond line'
    assert back.at[0, "2000"] == "0.1" and back.at[0, "2001"] == ""


# --- Input validation: unreadable cells, country codes, lookup, year range, master ---

@pytest.mark.parametrize("text", ["Infinity", "-inf", "NaN", "1,5", "..", "n/a", "5%", "1 000", ""])
def test_cell_texts_that_are_not_finite_numbers_are_missing(text):
    assert _as_decimal(text) is None


def test_unreadable_cells_are_reported_and_read_as_missing(workspace, capsys):
    tmp, _, lookup_path = workspace
    rows = _raw_rows("AAA", "Alpha", {"General government": {2000: "1,5", 2001: "Infinity", 2002: 1.0},
                                      "Local Government": {2000: "..", 2003: 0.5}})
    path = tmp / "bad_cells.xlsx"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(path, index=False)
    master_path, _ = seed_master(lookup_path, tmp)
    split_dir, _ = split_data(path, "Percent of GDP", {"05"}, tmp / "s")
    assert run_aggregation(master_path, split_dir, "DATA_ENV")
    assert "3 distinct cell texts are not numbers" in capsys.readouterr().out
    out = pd.read_excel(master_path, sheet_name="MasterData").set_index("SortKey")
    assert pd.isna(out.at["AAA2000", "DATA_ENV"]) and pd.isna(out.at["AAA2001", "DATA_ENV"])
    assert out.at["AAA2002", "DATA_ENV"] == 1.0 and out.at["AAA2003", "DATA_ENV"] == 0.5


@pytest.mark.parametrize("series, country", [
    ("ARM.S13.G2MF.GF05_T.POGDP_PT.A", "ARM"), ("usa.S13.X.GF05_T.A", "USA"),
    ("EU.S13.G2MF.GF05_T.POGDP_PT.A", "EU"), ("G20.S13.X", "G20"), ("ABCD.S13", "ABCD"), ("", None), (None, None),
])
def test_country_is_the_first_field_of_the_series_code(series, country):
    assert _country_of(series) == country


def test_series_of_codes_that_are_not_countries_are_reported_not_split(workspace, capsys):
    tmp, _, _ = workspace
    rows = (_raw_rows("AAA", "Alpha", {"General government": {2000: 1.0}})
            + _raw_rows("EU", "Euro area", {"General government": {2000: 2.0}})
            + _raw_rows("ABCD", "Four", {"General government": {2000: 3.0}}))
    path = tmp / "groups.xlsx"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(path, index=False)
    split_dir, ok = split_data(path, "Percent of GDP", {"05"}, tmp / "s")
    assert ok and [f.name for f in country_files(split_dir)] == ["AAA.csv"]
    assert "['ABCD', 'EU']" in capsys.readouterr().out
    assert [n for _, _, n in list_cofog(path)] == [1]


def _lookup(tmp_path, codes):
    path = tmp_path / "lookup.xlsx"
    pd.DataFrame({"name": [f"C{i}" for i in range(len(codes))], "alpha-2": "XX",
                  "alpha-3": codes, "country-code": range(len(codes))}).to_excel(path, index=False)
    return path


@pytest.mark.parametrize("codes, message", [
    (["AAA", "aaa"], "repeated codes ['AAA']"),
    (["AAA", "US1"], "not three letters ['US1']"),
    (["AAA", "AB"], "not three letters ['AB']"),
])
def test_seed_master_rejects_a_bad_lookup(tmp_path, capsys, codes, message):
    path = _lookup(tmp_path, codes)
    _, ok = seed_master(path, tmp_path / "out")
    assert not ok and message in capsys.readouterr().out
    assert not (tmp_path / "out").exists()
    assert not verify_country_format(path)[0]


def test_seed_master_writes_upper_case_keys_for_a_lower_case_lookup(tmp_path):
    path = _lookup(tmp_path, [" aaa", "BBB"])
    target, ok = seed_master(path, tmp_path / "out", start_year=2000, end_year=2000)
    assert ok and list(pd.read_excel(target)["SortKey"]) == ["AAA2000", "BBB2000"]


def test_seed_master_rejects_a_reversed_year_range(tmp_path, capsys):
    _, ok = seed_master(_lookup(tmp_path, ["AAA"]), tmp_path / "out", start_year=2030, end_year=2000)
    assert not ok and "--start-year 2030 is after --end-year 2000" in capsys.readouterr().out
    assert not (tmp_path / "out").exists()


def test_aggregate_refuses_a_master_with_repeated_sortkeys(workspace, capsys):
    tmp, raw_path, lookup_path = workspace
    master_path, _ = seed_master(lookup_path, tmp, start_year=2000, end_year=2001)
    master = pd.read_excel(master_path, sheet_name="MasterData")
    pd.concat([master, master.iloc[[0]]]).to_excel(master_path, index=False, sheet_name="MasterData")
    before = master_path.read_bytes()
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "s")
    assert not run_aggregation(master_path, split_dir, "DATA_ENV")
    assert "repeated SortKey values, e.g. ['AAA2000']" in capsys.readouterr().out
    assert master_path.read_bytes() == before


def test_aggregate_leaves_the_master_unchanged_when_a_value_cannot_be_written(workspace, monkeypatch, capsys):
    import cofog_panel.aggregate as aggregate
    tmp, raw_path, lookup_path = workspace
    master_path, _ = seed_master(lookup_path, tmp)
    before = master_path.read_bytes()
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "s")
    monkeypatch.setattr(aggregate, "_select_for_country",
                        lambda *a, **k: {"AAA2000": ("not a number", "T1", "GG", "Y")})
    assert not run_aggregation(master_path, split_dir, "DATA_ENV")
    assert "could not be written as numbers" in capsys.readouterr().out
    assert master_path.read_bytes() == before


# --- Countries without a lookup row are listed by split ---

def _split_with_lookup(tmp_path, series_rows, lookup_codes, name="s"):
    raw = tmp_path / f"{name}.xlsx"
    pd.DataFrame(series_rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(raw, index=False)
    return split_data(raw, "Percent of GDP", {"05"}, tmp_path / f"{name}_out", _lookup(tmp_path, lookup_codes))


def test_split_lists_countries_missing_from_the_lookup(tmp_path, capsys):
    rows = (_raw_rows("AAA", "Alpha", {"General government": {2000: 1.0}})
            + _raw_rows("ZZZ", "Zeta", {"General government": {2000: 2.0}}))
    split_dir, ok = _split_with_lookup(tmp_path, rows, ["AAA"])
    out = capsys.readouterr().out
    assert ok and "1 countries in the extract have no row in the lookup file" in out and "ZZZ (Zeta)" in out
    assert "AAA (" not in out
    assert [f.name for f in country_files(split_dir)] == ["AAA.csv", "ZZZ.csv"]   # the files are still written


def test_split_maps_imf_codes_before_comparing_with_the_lookup(tmp_path, capsys):
    rows = (_raw_rows("KOS", "Kosovo", {"General government": {2000: 1.0}})
            + _raw_rows("WBG", "West Bank and Gaza", {"General government": {2000: 1.0}}))
    _, ok = _split_with_lookup(tmp_path, rows, ["XKX", "PSE"])
    assert ok and "no row in the lookup file" not in capsys.readouterr().out


def test_split_without_a_usable_lookup_does_not_warn(tmp_path, capsys):
    rows = _raw_rows("ZZZ", "Zeta", {"General government": {2000: 2.0}})
    raw = tmp_path / "raw.xlsx"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(raw, index=False)
    (tmp_path / "broken.xlsx").write_text("not a workbook")
    for lookup in (None, tmp_path / "broken.xlsx", tmp_path / "absent.xlsx"):
        _, ok = split_data(raw, "Percent of GDP", {"05"}, tmp_path / "out", lookup)
        assert ok
    assert "no row in the lookup file" not in capsys.readouterr().out


# --- Values in domestic currency are not added when the series have different units ---

def _currency_rows(scale_central="Millions", scale_local="Millions", currency_local="Euro"):
    rows = _raw_rows("AAA", "Alpha", {"Central government including social security": {2000: 10.0},
                                      "Local Government": {2000: 5.0}}, transformation="Domestic currency")
    rows[0].update({"SCALE": scale_central, "CURRENCY": "Euro"})
    rows[1].update({"SCALE": scale_local, "CURRENCY": currency_local})
    return rows


def _aggregate_currency(tmp_path, rows):
    raw = tmp_path / "currency.xlsx"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(raw, index=False)
    master_path, _ = seed_master(_lookup(tmp_path, ["AAA"]), tmp_path / "m", start_year=2000, end_year=2000)
    split_dir, _ = split_data(raw, "Domestic currency", {"05"}, tmp_path / "currency_split")
    assert run_aggregation(master_path, split_dir, "DATA_ENV")
    return pd.read_excel(master_path, sheet_name="MasterData", dtype=str).fillna("").set_index("SortKey")


def test_domestic_currency_with_one_unit_is_added(tmp_path, capsys):
    out = _aggregate_currency(tmp_path, _currency_rows())
    assert (out.at["AAA2000", "DATA_ENV"], out.at["AAA2000", "SOURCE_TIER_ENV"]) == ("15", "T2")
    assert "differ in" not in capsys.readouterr().out


@pytest.mark.parametrize("kwargs, column", [
    ({"scale_local": "Billions"}, "SCALE: 'Billions', 'Millions'"),
    ({"currency_local": "Dollar"}, "CURRENCY: 'Dollar', 'Euro'"),
])
def test_domestic_currency_with_different_units_is_not_added(tmp_path, capsys, kwargs, column):
    out = _aggregate_currency(tmp_path, _currency_rows(**kwargs))
    assert out.at["AAA2000", "DATA_ENV"] == "" and out.at["AAA2000", "SOURCE_TIER_ENV"] == ""
    assert f"AAA: series in domestic currency differ in {column}" in capsys.readouterr().out


def test_domestic_currency_unit_check_ignores_letter_case_and_still_returns_reported_values(tmp_path):
    out = _aggregate_currency(tmp_path, _currency_rows(scale_local="millions"))
    assert out.at["AAA2000", "SOURCE_TIER_ENV"] == "T2"
    rows = _currency_rows(scale_local="Billions")
    rows += _raw_rows("AAA", "Alpha", {"General government": {2000: 99.0}}, transformation="Domestic currency")
    rows[-1].update({"SCALE": "Millions", "CURRENCY": "Euro"})
    (tmp_path / "t1").mkdir()
    out = _aggregate_currency(tmp_path / "t1", rows)
    assert (out.at["AAA2000", "DATA_ENV"], out.at["AAA2000", "SOURCE_TIER_ENV"]) == ("99", "T1")


def test_percent_of_gdp_is_added_whatever_the_scale_column_says(tmp_path):
    rows = _raw_rows("AAA", "Alpha", {"Central government including social security": {2000: 1.0},
                                      "Local Government": {2000: 0.5}})
    rows[0]["SCALE"], rows[1]["SCALE"] = "Units", "Millions"
    raw = tmp_path / "gdp.xlsx"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(raw, index=False)
    master_path, _ = seed_master(_lookup(tmp_path, ["AAA"]), tmp_path / "m", start_year=2000, end_year=2000)
    split_dir, _ = split_data(raw, "Percent of GDP", {"05"}, tmp_path / "gdp_split")
    assert run_aggregation(master_path, split_dir, "DATA_ENV")
    out = pd.read_excel(master_path, sheet_name="MasterData").set_index("SortKey")
    assert (out.at["AAA2000", "DATA_ENV"], out.at["AAA2000", "SOURCE_TIER_ENV"]) == (1.5, "T2")


def test_split_counts_rows_without_a_cofog_function(workspace, tmp_path, capsys):
    _, raw_path, _ = workspace
    frame = pd.read_excel(raw_path)
    odd = frame.iloc[[0]].copy()
    odd["SERIES_CODE"] = "AAA.S13.G2MF"
    pd.concat([frame, odd]).to_excel(raw_path, index=False)
    _, ok = split_data(raw_path, "Percent of GDP", {"05"}, tmp_path / "s")
    assert ok and "1 rows of this transformation have no COFOG function" in capsys.readouterr().out


def test_split_is_silent_when_every_row_has_a_function(workspace, tmp_path, capsys):
    _, raw_path, _ = workspace
    split_data(raw_path, "Percent of GDP", {"05"}, tmp_path / "s")
    assert "no COFOG function" not in capsys.readouterr().out


@pytest.mark.parametrize("series, label, warned", [
    ("AAA.S13.G2MF.TOA_T.POGDP_PT.A", None, False),        # total outlays, in every IMF extract
    ("AAA.S1311.G2MF.TOTOUT_T.POGDP_PT.A", None, False),
    ("AAA.S13.G2MF.F6N_G33_L_T.POGDP_PT.A", None, False),  # a liability series
    ("AAA.S13.G2MF.TOA_T.POGDP_PT.A", "Health", True),     # labelled with a function its code does not give
    ("AAA.S13.G2MF.GF0X_T.POGDP_PT.A", None, True),        # a GF code that cannot be read
])
def test_split_does_not_count_series_of_other_indicators(workspace, tmp_path, capsys, series, label, warned):
    _, raw_path, _ = workspace
    frame = pd.read_excel(raw_path)
    other = frame.iloc[[0]].copy()
    other["SERIES_CODE"], other["COFOG"] = series, label
    pd.concat([frame, other]).to_excel(raw_path, index=False)
    _, ok = split_data(raw_path, "Percent of GDP", {"05"}, tmp_path / "s")
    assert ok and ("1 rows of this transformation have no COFOG function" in capsys.readouterr().out) == warned


def _with_publication_dates(raw_path, dates):
    frame = pd.read_excel(raw_path, dtype=str, keep_default_na=False)
    frame.loc[frame["COFOG"] == "Environmental protection", "PUBLICATION_DATE"] = (
        [dates[i % len(dates)] for i in range(int((frame["COFOG"] == "Environmental protection").sum()))])
    frame.to_excel(raw_path, index=False)


def test_split_records_one_publication_date_and_the_year_span(workspace, tmp_path, capsys):
    _, raw_path, _ = workspace
    _with_publication_dates(raw_path, ["2026-10-21"])
    split_dir, ok = split_data(raw_path, "Percent of GDP", {"05"}, tmp_path / "s")
    marker = read_split_marker(split_dir)
    assert ok and marker["publication_date"] == "2026-10-21" and marker["years"] == "1972-2024"
    assert "PUBLICATION_DATE values" not in capsys.readouterr().out


def test_split_warns_when_publication_dates_differ(workspace, tmp_path, capsys):
    _, raw_path, _ = workspace
    _with_publication_dates(raw_path, ["2026-10-21", "2025-04-01"])
    split_dir, ok = split_data(raw_path, "Percent of GDP", {"05"}, tmp_path / "s")
    assert ok and "2 different PUBLICATION_DATE values (2025-04-01, 2026-10-21)" in capsys.readouterr().out
    assert read_split_marker(split_dir)["publication_date"] == "2025-04-01,2026-10-21"


def test_publication_dates_of_other_functions_are_ignored(workspace, tmp_path):
    _, raw_path, _ = workspace
    _with_publication_dates(raw_path, ["2026-10-21"])
    frame = pd.read_excel(raw_path, dtype=str, keep_default_na=False)
    frame.loc[frame["COFOG"] == "Defence", "PUBLICATION_DATE"] = "1999-01-01"
    frame.to_excel(raw_path, index=False)
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp_path / "s")
    assert read_split_marker(split_dir)["publication_date"] == "2026-10-21"


def test_aggregate_reports_the_publication_date(workspace, tmp_path, capsys):
    tmp, raw_path, lookup_path = workspace
    _with_publication_dates(raw_path, ["2026-10-21"])
    master_path, _ = seed_master(lookup_path, tmp, start_year=1972, end_year=2024)
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "s")
    assert run_aggregation(master_path, split_dir, "DATA_ENV")
    out = capsys.readouterr().out
    assert "Source PUBLICATION_DATE: 2026-10-21" in out and "master covers" not in out and "extract has years" not in out


@pytest.mark.parametrize("start, end, message", [
    (1972, 2030, "The master covers 1972-2030 but the extract has years 1972-2024: master rows outside 1972-2024 stay empty."),
    (1990, 2024, "The extract has years 1972-2024 but the master covers 1990-2024: values outside the master's years are not written."),
])
def test_aggregate_compares_master_years_with_the_extract(workspace, tmp_path, capsys, start, end, message):
    tmp, raw_path, lookup_path = workspace
    master_path, _ = seed_master(lookup_path, tmp, start_year=start, end_year=end)
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "s")
    assert run_aggregation(master_path, split_dir, "DATA_ENV")
    assert message in capsys.readouterr().out


def test_aggregate_without_marker_skips_the_year_comparison(workspace, tmp_path, capsys):
    tmp, raw_path, lookup_path = workspace
    master_path, _ = seed_master(lookup_path, tmp, start_year=1990, end_year=2030)
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "s")
    (split_dir / ".cofog_panel_split").unlink()
    assert run_aggregation(master_path, split_dir, "DATA_ENV")
    assert "extract has years" not in capsys.readouterr().out


def test_split_warns_when_a_label_covers_several_functions(tmp_path, capsys):
    rows = (_raw_rows("AAA", "Alpha", {"General government": {2000: 1.0}}, cofog_label="Shared", cofog_code="05")
            + _raw_rows("AAA", "Alpha", {"General government": {2000: 2.0}}, cofog_label="Shared", cofog_code="051"))
    path = tmp_path / "labels.xlsx"
    pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_excel(path, index=False)
    _, ok = split_data(path, "Percent of GDP", {"Shared"}, tmp_path / "s")
    assert ok and "The label 'Shared' covers several COFOG functions (05, 05.1)" in capsys.readouterr().out
    split_data(path, "Percent of GDP", {"05"}, tmp_path / "t")
    assert "covers several" not in capsys.readouterr().out


def test_split_is_silent_for_a_label_with_one_function(workspace, tmp_path, capsys):
    _, raw_path, _ = workspace
    split_data(raw_path, "Percent of GDP", {"Environmental protection"}, tmp_path / "s")
    assert "covers several" not in capsys.readouterr().out


@pytest.mark.parametrize("values, warned", [(["Annual", "Annual"], False), (["Annual", "Quarterly"], True)])
def test_split_warns_about_mixed_frequencies(workspace, tmp_path, capsys, values, warned):
    _, raw_path, _ = workspace
    frame = pd.read_excel(raw_path, dtype=str, keep_default_na=False)
    chosen = frame["COFOG"] == "Environmental protection"
    frame.loc[chosen, "FREQUENCY"] = [values[i % 2] for i in range(int(chosen.sum()))]
    frame.loc[frame["COFOG"] == "Defence", "FREQUENCY"] = "Monthly"  # other function: ignored
    frame.to_excel(raw_path, index=False)
    split_data(raw_path, "Percent of GDP", {"05"}, tmp_path / "s")
    out = capsys.readouterr().out
    assert ("different FREQUENCY values (Annual, Quarterly)" in out) is warned
    assert "Monthly" not in out


def _selected(value, transformation):
    return {"AAA2000": (value, "T1", "GG", "Y")}, transformation


@pytest.mark.parametrize("value, transformation, message", [
    ("-0.5", "Percent of GDP", "1 selected values are negative, e.g. ['AAA2000=-0.5']"),
    ("120", "Percent of GDP", "above 100 (Percent of GDP)"),
    ("120", "Percent of total outlays", "above 100 (Percent of total outlays)"),
    ("-5", "Domestic currency", "negative"),
    ("120", "Domestic currency", "no negative values"),
    ("100", "Percent of GDP", "no negative values"),
    ("3", "Percent of GDP", "no negative values"),
])
def test_range_report(capsys, value, transformation, message):
    from cofog_panel.aggregate import _report_ranges
    _report_ranges(*_selected(value, transformation))
    assert message in capsys.readouterr().out


def test_aggregate_range_check_is_opt_in(workspace, tmp_path, capsys):
    tmp, raw_path, lookup_path = workspace
    frame = pd.read_excel(raw_path)
    frame.loc[(frame["SECTOR"] == "General government") & (frame["COFOG"] == "Environmental protection"), "2000"] = -1.0
    frame.to_excel(raw_path, index=False)
    master_path, _ = seed_master(lookup_path, tmp, start_year=2000, end_year=2001)
    split_dir, _ = split_data(raw_path, "Percent of GDP", {"05"}, tmp / "s")
    assert run_aggregation(master_path, split_dir, "DATA_ENV")
    quiet = capsys.readouterr().out
    assert "Range check" not in quiet and "negative" not in quiet
    assert run_aggregation(master_path, split_dir, "DATA_ENV", check_ranges=True)
    out = capsys.readouterr().out
    assert "selected values are negative, e.g. ['AAA2000=-1" in out
    assert pd.read_excel(master_path)["DATA_ENV"].min() == -1.0


def test_imf_country_codes_come_from_the_data_file(tmp_path):
    from cofog_panel.etl import IMF_CODES_FILE, IMF_TO_ISO, _read_imf_codes
    assert IMF_CODES_FILE.exists() and IMF_TO_ISO == {"KOS": "XKX", "WBG": "PSE"}
    path = tmp_path / "codes.csv"
    path.write_text("imf,iso\n kos ,xkx\nAAA,BBB\n", encoding="utf-8")
    assert _read_imf_codes(path) == {"KOS": "XKX", "AAA": "BBB"}
