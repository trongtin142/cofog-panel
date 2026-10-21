"""
Stages 1 and 2: structural checks of the GFS extract and of the country lookup file.

Both checks print a short report and return (ok, details) so that scripts can act on the result.
"""
from pathlib import Path
from typing import Any, Dict, List, Tuple

import openpyxl
import pandas as pd

# Metadata columns of an IMF GFS COFOG Excel download, in the order the IMF writes them
IMF_METADATA_COLUMNS = (
    "DATASET", "SERIES_CODE", "OBS_MEASURE", "COUNTRY", "SECTOR", "GFS_GRP",
    "INDICATOR", "TYPE_OF_TRANSFORMATION", "FREQUENCY", "SCALE", "DECIMALS_DISPLAYED",
    "INSTR_ASSET", "GFS_STO", "COFOG", "CURRENCY", "INT_TTC", "COUNTERPART_SECTOR",
    "GFS_DF", "ACCOUNTING_ENTRY", "FLOW_STOCK_ENTRY", "FI_MATURITY", "GFS_RB",
    "STATISTICAL_MEASURES", "GFS_COMPONENT", "TRANSFORMATION", "ACCOUNTS", "UNIT",
    "OVERLAP", "DOI", "FULL_DESCRIPTION", "AUTHOR", "PUBLISHER", "DEPARTMENT",
    "CONTACT_POINT", "TOPIC", "TOPIC_DATASET", "KEYWORDS", "KEYWORDS_DATASET",
    "LANGUAGE", "PUBLICATION_DATE", "UPDATE_DATE", "METHODOLOGY", "METHODOLOGY_NOTES",
    "ACCESS_SHARING_LEVEL", "ACCESS_SHARING_NOTES", "SECURITY_CLASSIFICATION",
    "SHORT_SOURCE_CITATION", "FULL_SOURCE_CITATION", "LICENSE", "SUGGESTED_CITATION",
    "KEY_INDICATOR", "SERIES_NAME",
)
FIXED_HEADERS_SAMPLE = list(IMF_METADATA_COLUMNS)  # earlier name, kept for scripts that import it

# Year columns start in 1972. Later releases append years, so only a minimum last year is required.
START_YEAR = 1972
END_YEAR = 2024

REQUIRED_COUNTRY_COLS = ["name", "alpha-2", "alpha-3", "country-code"]

_RULE = "=" * 40


def read_header(path: Path) -> List[str]:
    """First row of the active sheet, as stripped strings (empty cells dropped)."""
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        first_row = next(book.active.iter_rows(max_row=1, values_only=True), ())
    finally:
        book.close()
    return [str(cell).strip() for cell in first_row if cell is not None]


def read_lookup(path: Path) -> pd.DataFrame:
    """Read a country lookup table from .csv, .xlsx or .xls. Codes such as 'NA' stay text."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, keep_default_na=False)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path, keep_default_na=False)
    raise ValueError(f"Unsupported file format for lookup: {path.suffix}. Must be .csv or .xlsx.")


def _years_are_valid(years: List[int]) -> bool:
    if not years or years[-1] < END_YEAR:
        return False
    return years == list(range(START_YEAR, years[-1] + 1))


def _print_format_report(name: str, details: Dict[str, Any]) -> None:
    print(f"\n{_RULE}\nCOFOG FORMAT VERIFICATION REPORT ({name})\n{_RULE}")
    if details["Match"]:
        print("🎉 SUCCESS: File header structure matches the required template.")
    else:
        print("❌ WARNING: Header structure mismatch detected.")
        missing, extra = details["Missing_Headers"], details["Extra_Headers"]
        if missing:
            print(f"   -> MISSING Fixed Headers ({len(missing)}): {missing}")
        if extra:
            print(f"   -> UNKNOWN Extra Headers ({len(extra)}): {extra}")
        if details["Year_Mismatch"]:
            print(f"   -> Year columns must run contiguously from {START_YEAR} to at least {END_YEAR}.")
    print(_RULE)


def verify_cofog_format(file_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """
    Check the header row of a GFS COFOG extract: every IMF metadata column, year columns
    running without gaps from 1972 to at least 2024, and no other columns.

    Only the first row is read, so the check is fast on the full extract.
    """
    details: Dict[str, Any] = {
        "Match": False, "Missing_Headers": [], "Extra_Headers": [],
        "Year_Mismatch": False, "Total_Columns": 0,
    }
    if not file_path.exists():
        print(f"❌ Error: File not found at {file_path}")
        return False, details
    try:
        headers = read_header(file_path)
    except Exception as exc:  # not a workbook, or damaged
        print(f"❌ Error reading Excel file structure: {exc}")
        return False, details

    years = sorted(int(h) for h in headers if len(h) == 4 and h.isdigit())
    known = set(IMF_METADATA_COLUMNS) | {str(y) for y in years}
    details["Total_Columns"] = len(headers)
    details["Missing_Headers"] = [c for c in IMF_METADATA_COLUMNS if c not in headers]
    details["Extra_Headers"] = [h for h in headers if h not in known]
    details["Year_Mismatch"] = not _years_are_valid(years)
    details["Match"] = not (details["Missing_Headers"] or details["Extra_Headers"] or details["Year_Mismatch"])

    _print_format_report(file_path.name, details)
    return details["Match"], details


def verify_country_format(file_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """Check that the lookup file has the ISO columns and no repeated alpha-3 code."""
    details: Dict[str, Any] = {"Valid": False, "Missing_Columns": [], "Duplicate_Alpha3": False, "Total_Rows": 0}
    if not file_path.exists():
        print(f"❌ Error: File not found at {file_path}")
        return False, details
    try:
        table = read_lookup(file_path)
    except ValueError as exc:
        print(f"❌ Error: {exc}")
        return False, details
    except Exception as exc:
        print(f"❌ Error processing lookup file {file_path}: {exc}")
        return False, details

    columns = list(table.columns)
    details["Total_Rows"] = len(table)
    details["Missing_Columns"] = [c for c in REQUIRED_COUNTRY_COLS if c not in columns]
    details["Duplicate_Alpha3"] = "alpha-3" in columns and bool(table["alpha-3"].duplicated().any())
    details["Valid"] = not (details["Missing_Columns"] or details["Duplicate_Alpha3"])

    if not details["Valid"]:
        print(f"❌ Mismatch detected in {file_path.name}.")
        if details["Missing_Columns"]:
            print(f"   -> Missing required columns: {details['Missing_Columns']}")
        if details["Duplicate_Alpha3"]:
            print("   -> Duplicate 'alpha-3' codes found.")
        print(f"   -> Columns found: {columns}")
        return False, details

    print("✅ SUCCESS: Country lookup file structure is VALID.")
    print(f"   -> Total Rows: {len(table)}")
    print(f"   -> Columns: {columns}")
    return True, details
