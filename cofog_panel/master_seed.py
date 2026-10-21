"""
Stage 3: the master panel, one row per country and year, keyed by SortKey = ISO3 + year.

Indicator columns are added later by the aggregate stage.
"""
from pathlib import Path
from typing import Tuple

import pandas as pd

from .checks import read_lookup
from .messages import hint_for_write_error, print_error

# Lookup bundled with the package (ISO 3166 with Kosovo, XKX): the default --lookup-file
PACKAGED_LOOKUP = Path(__file__).resolve().parent / "data" / "country_codes.xlsx"

DEFAULT_START_YEAR = 1972  # first year of the IMF GFS COFOG data
DEFAULT_END_YEAR = 2025
DEFAULT_FILE_NAME = "COFOG_MASTER_SCHEMA.xlsx"
MASTER_SHEET = "MasterData"
PANEL_KEYS = ["SortKey", "Country", "Year"]


def build_panel(lookup: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    """Every country with an alpha-3 code crossed with every year, countries in lookup order."""
    iso = lookup["alpha-3"].astype(str).str.strip()
    usable = (iso != "") & (iso.str.upper() != "NAN")
    countries = pd.DataFrame({"Country": lookup.loc[usable, "name"].astype(str).str.strip(), "ISO": iso[usable]})
    years = pd.DataFrame({"Year": list(range(start_year, end_year + 1))})
    panel = countries.merge(years, how="cross")
    panel["SortKey"] = panel["ISO"] + panel["Year"].astype(str)
    return panel[PANEL_KEYS]


def seed_master(
    lookup_file_path: Path,
    output_path: Path,
    output_name: str = DEFAULT_FILE_NAME,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
) -> Tuple[Path, bool]:
    """
    Write a new master workbook (sheet 'MasterData') to output_path / output_name.

    An existing file of that name is replaced. Returns (path, success).
    """
    target = output_path / output_name
    print(f"\n--- SEEDING MASTER: Processing {lookup_file_path.name} ---")
    if not lookup_file_path.exists():
        print_error(f"Lookup file not found: {lookup_file_path}", "Omit --lookup-file to use the lookup bundled with the package, or give the path of your own file.")
        return Path(""), False

    try:
        lookup = read_lookup(lookup_file_path)
        if not {"name", "alpha-3"} <= set(lookup.columns):
            print_error("Lookup file must contain 'name' and 'alpha-3' columns.",
                        "Check the column names in the first row, or omit --lookup-file to use the bundled lookup.")
            return target, False
        panel = build_panel(lookup, start_year, end_year)
        if target.exists():
            print(f"⚠️ Replacing the existing master file {target}: its indicator columns are removed.")
        output_path.mkdir(parents=True, exist_ok=True)
        panel.to_excel(target, index=False, sheet_name=MASTER_SHEET)
    except Exception as exc:
        print_error(f"Cannot write the master file {target} ({exc}).", hint_for_write_error(exc))
        return target, False

    print(f"✅ SUCCESS: Master XLSX file created with {len(panel)} rows ({start_year}-{end_year}).")
    print(f"=> File Path: {target}")
    return target, True


def prepare_master(
    lookup_file_path: Path,
    output_path: Path,
    output_name: str = DEFAULT_FILE_NAME,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
    overwrite: bool = False,
) -> Tuple[Path, bool]:
    """
    Master file for the 'run' command: an existing master is kept, so that indicators from
    earlier runs survive and the new indicator is added as further columns. With overwrite=True
    the master is rebuilt from the lookup file and its indicator columns are lost.
    """
    target = output_path / output_name
    if target.exists() and not overwrite:
        print(f"\n--- MASTER: keeping the existing file {target} ---")
        print("   New columns are added to it; earlier indicator columns are kept.")
        print("   (--start-year/--end-year apply only when a master is created; use --overwrite-master to rebuild it.)")
        return target, True
    if target.exists():
        print(f"\n⚠️ WARNING: --overwrite-master is set. {target} is rebuilt and every indicator column in it is deleted.")
    return seed_master(lookup_file_path, output_path, output_name, start_year, end_year)
