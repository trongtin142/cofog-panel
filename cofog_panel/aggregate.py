"""
Stage 5: apply the selection rule to every country file of a split and write the selected
values, with their provenance, as new columns of the master panel.

For each country-year the rule picks one value from the reported sectors (resolve_value) and
records the tier, the contributing sectors and whether the value covers every level of
government that the country reports in its series (is_complete).
"""
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .messages import hint_for_write_error, print_error

# --- Sector names, normalised to lower case as they appear in IMF GFS COFOG ---
GG = "general government"
CGSS = "central government including social security"
CGXSS = "central government excluding social security"
BCG = "budgetary central government"
EBCG = "extrabudgetary central government"
SSF = "social security funds"
SG = "state government"
LG = "local government"

# Sectors summed by each fallback tier
T2_SECTORS = [CGSS, SG, LG]
T3_SECTORS = [BCG, EBCG, SSF, SG, LG]  # with CGXSS in place of BCG + EBCG when it is reported
C2_SECTORS = [BCG, EBCG, SSF]
# Levels whose omission makes a fallback sum incomplete (see is_complete)
COVERAGE_LEVELS = [EBCG, SSF, SG, LG]

# Sector names accepted by --sector for a single-sector panel (tier D)
DIRECT_SECTORS = [
    "Budgetary central government", "Extrabudgetary central government",
    "Local Government", "Social security funds", "State Government",
    "Central government excluding social security",
]

# Transformations whose values can be added across subsectors. Shares of total outlays
# have a different denominator in each subsector and are never summed.
SUMMABLE_TRANSFORMATIONS = {"Percent of GDP", "Domestic currency"}

# Short labels written to the sectors column
SECTOR_ABBR = {GG: "GG", CGSS: "CGSS", CGXSS: "CGXSS", BCG: "BCG", EBCG: "EBCG", SSF: "SSF", SG: "SG", LG: "LG"}

# IMF country codes that differ from ISO 3166 alpha-3
IMF_TO_ISO = {"KOS": "XKX", "WBG": "PSE"}

DEFAULT_DATA_COL = "DATA_NEW"
DEFAULT_TIER_COL = "SOURCE_TIER"
DEFAULT_SECTORS_COL = "SOURCE_SECTORS"
DEFAULT_COMPLETE_COL = "SOURCE_COMPLETE"
MASTER_SHEET = "MasterData"
PANEL_KEYS = ["SortKey", "Country", "Year"]

# Precision for sums of reported values (well above the 15-17 digits of the source data)
_SUM_PRECISION = 50


# --- Selection rule ---

def _sum_present(values: Dict[str, Optional[Decimal]], sectors: List[str]) -> Tuple[Optional[Decimal], List[str]]:
    """Sum of the listed sectors that have a value, with the sectors used; (None, []) if none has one."""
    used = [s for s in sectors if values.get(s) is not None]
    if not used:
        return None, []
    with localcontext() as ctx:
        ctx.prec = _SUM_PRECISION
        return sum((values[s] for s in used), Decimal(0)), used


def _central_core(values: Dict[str, Optional[Decimal]]) -> List[str]:
    """Central government excluding social security: CGXSS if reported, otherwise BCG and EBCG."""
    return [CGXSS] if values.get(CGXSS) is not None else [BCG, EBCG]


def resolve_value(
    values: Dict[str, Optional[Decimal]],
    sector_override: str = "General government",
    zero_as_missing: bool = False,
    summable: bool = True,
) -> Tuple[Optional[Decimal], str, List[str]]:
    """
    Select one value for a country-year from its sector values.

    `values` maps lower-case sector names to Decimal or None. Returns (value, tier, sectors),
    where sectors lists the sectors that entered the value and tier is one of:
      T1 = General government reported
      T2 = Central gov. incl. social security + State + Local (unconsolidated sum)
      T3 = Central gov. excl. social security (or, if not reported, Budgetary + Extrabudgetary)
           + Social security funds + State + Local (unconsolidated sum)
      C1 = Central gov. incl. social security reported
      C2 = Central gov. excl. social security (or Budgetary + Extrabudgetary)
           + Social security funds (unconsolidated sum)
      D  = value of the directly requested sector
      "" = no value
    Reported zeros count as values unless zero_as_missing is set. When the values cannot be
    summed (summable=False), only T1, C1 and D can be returned.
    """
    if zero_as_missing:
        # A reported zero often means "not separately identified": drop zeros in every sector
        values = {k: (None if v is not None and v == 0 else v) for k, v in values.items()}

    if sector_override == "General government":
        if values.get(GG) is not None:
            return values[GG], "T1", [GG]
        if not summable:
            return None, "", []
        if values.get(CGSS) is not None:
            total, used = _sum_present(values, T2_SECTORS)
            return total, "T2", used
        total, used = _sum_present(values, _central_core(values) + [SSF, SG, LG])
        return (total, "T3", used) if total is not None else (None, "", [])

    if sector_override == "Central government including social security":
        if values.get(CGSS) is not None:
            return values[CGSS], "C1", [CGSS]
        if not summable:
            return None, "", []
        total, used = _sum_present(values, _central_core(values) + [SSF])
        return (total, "C2", used) if total is not None else (None, "", [])

    if sector_override in DIRECT_SECTORS:
        key = sector_override.lower()
        if values.get(key) is not None:
            return values[key], "D", [key]
        return None, "", []

    raise ValueError(f"Unknown sector option: {sector_override}")


def is_complete(
    tier: str,
    used: List[str],
    levels_reported: List[str],
    values: Optional[Dict[str, Optional[Decimal]]] = None,
) -> Optional[bool]:
    """
    Whether a value covers the whole of general government (or of central government for C2).

    levels_reported lists the levels among EBCG, SSF, SG and LG that the country reports in
    at least one year of the series. A fallback sum is complete when it includes:
      T2: every reported subnational level (SG, LG);
      T3: the central core (CGXSS, or BCG with EBCG if EBCG is reported), SSF if reported,
          and every reported subnational level;
      C2: the central core and SSF if reported.
    T1, C1 and D values are taken as reported, except that a T1 value is flagged when GG
    equals CGSS exactly while State or Local government report positive spending in the
    same year (passed in `values`), which suggests GG omits the subnational levels.
    Returns None when there is no value.
    """
    reported = set(levels_reported)
    included = set(used)

    def has_level(level: str) -> bool:
        return level in included or level not in reported

    def central_covered() -> bool:
        core = CGXSS in included or (BCG in included and has_level(EBCG))
        return core and has_level(SSF)

    subnational_covered = has_level(SG) and has_level(LG)

    if tier == "T1":
        if values is not None and values.get(GG) is not None and values.get(CGSS) is not None:
            subnational_spends = any((values.get(s) or Decimal(0)) > 0 for s in (SG, LG))
            if subnational_spends and values[GG] == values[CGSS]:
                return False
        return True
    if tier in ("C1", "D"):
        return True
    if tier == "T2":
        return subnational_covered
    if tier == "T3":
        return central_covered() and subnational_covered
    if tier == "C2":
        return central_covered()
    return None


# --- Reading country files ---

def _as_decimal(cell: Any) -> Optional[Decimal]:
    """Decimal value of a cell read as text; None for empty, NaN or non-numeric cells."""
    if cell is None:
        return None
    text = str(cell).strip()
    if text.upper() in ("", "NAN", "NONE"):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _plain(value: Decimal) -> str:
    """Fixed-point text of a Decimal without trailing zeros ('0' for zero)."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _read_country_file(path: Path) -> Tuple[pd.DataFrame, bool]:
    """
    Year columns of a split country file, indexed by lower-case sector name (first series
    per sector), and whether its transformation allows sums across sectors.
    """
    frame = pd.read_excel(path, dtype=str)
    sector_column = "SECTOR" if "SECTOR" in frame.columns else frame.columns[4]
    frame.index = frame[sector_column].astype(str).str.strip().str.lower()
    frame = frame[~frame.index.duplicated(keep="first")]
    summable = True
    if "TYPE_OF_TRANSFORMATION" in frame.columns:
        kinds = set(frame["TYPE_OF_TRANSFORMATION"].dropna().astype(str).str.strip())
        summable = kinds <= SUMMABLE_TRANSFORMATIONS
    year_columns = [c for c in frame.columns if str(c).isdigit()]
    return frame[year_columns], summable


def _levels_reported(cells: pd.DataFrame, zero_as_missing: bool) -> List[str]:
    """Coverage levels with at least one value in the series (non-zero if zeros count as missing)."""
    levels = []
    for level in COVERAGE_LEVELS:
        if level not in cells.index:
            continue
        numbers = [_as_decimal(v) for v in cells.loc[level]]
        if any(n is not None and not (zero_as_missing and n == 0) for n in numbers):
            levels.append(level)
    return levels


def _select_for_country(
    iso: str,
    cells: pd.DataFrame,
    summable: bool,
    sector_override: str,
    zero_as_missing: bool,
) -> Dict[str, Tuple[str, str, str, str]]:
    """{SortKey: (value text, tier, sectors, Y/N)} for the years of one country with a value."""
    levels = _levels_reported(cells, zero_as_missing)
    direct_key = {"T1": GG, "C1": CGSS, "D": str(sector_override).lower()}
    selected = {}
    for year in cells.columns:
        values = {sector: _as_decimal(cells.at[sector, year]) for sector in cells.index}
        value, tier, used = resolve_value(values, sector_override, zero_as_missing, summable)
        if value is None:
            continue
        # A reported value keeps its original text; a sum is written from the Decimal
        text = str(cells.at[direct_key[tier], year]).strip() if tier in direct_key else _plain(value)
        flag = "Y" if is_complete(tier, used, levels, values) else "N"
        selected[f"{iso}{year}"] = (text, tier, "+".join(SECTOR_ABBR.get(s, s) for s in used), flag)
    return selected


# --- Writing the master ---

def provenance_columns(data_col: str) -> Tuple[str, str]:
    """
    Default names of the sectors and completeness columns for a data column:
    DATA_ENV -> (SOURCE_SECTORS_ENV, SOURCE_COMPLETE_ENV), ENV -> (SOURCE_SECTORS_ENV, ...).
    The default data column DATA_NEW keeps the unsuffixed names SOURCE_SECTORS and SOURCE_COMPLETE.
    """
    if data_col == DEFAULT_DATA_COL:
        return DEFAULT_SECTORS_COL, DEFAULT_COMPLETE_COL
    suffix = data_col[5:] if data_col.upper().startswith("DATA_") and len(data_col) > 5 else data_col
    return f"{DEFAULT_SECTORS_COL}_{suffix}", f"{DEFAULT_COMPLETE_COL}_{suffix}"


def _restore_types(frame: pd.DataFrame, skip: List[str]) -> pd.DataFrame:
    """The master is read as text: turn back into numbers the columns whose filled cells are all numeric."""
    for column in frame.columns:
        if column in skip:
            continue
        text = frame[column].astype(str).replace({"nan": "", "None": ""})
        numbers = pd.to_numeric(text.mask(text == ""), errors="coerce")
        filled = int((text != "").sum())
        frame[column] = numbers if filled and int(numbers.notna().sum()) == filled else text
    return frame


def run_aggregation(
    master_file_path: Path,
    source_folder_path: Path,
    data_col_out: str,
    sector_override: Optional[str] = "General government",
    tier_col_out: str = DEFAULT_TIER_COL,
    zero_as_missing: bool = False,
    sectors_col_out: Optional[str] = None,
    complete_col_out: Optional[str] = None,
) -> bool:
    """
    Fill data_col_out, tier_col_out and the provenance columns of the master from the country
    files in source_folder_path. Other columns of the master (earlier indicators) are kept.

    sectors_col_out and complete_col_out default to names derived from data_col_out (see
    provenance_columns), so that two indicators in one master keep separate provenance.
    Returns False if the master cannot be read or written, or if any country file fails.
    """
    default_sectors, default_complete = provenance_columns(data_col_out)
    sectors_col_out = sectors_col_out or default_sectors
    complete_col_out = complete_col_out or default_complete
    print(f"\n--- AGGREGATE STAGE: Processing files in {source_folder_path.name} ---")

    if not Path(master_file_path).exists():
        print_error(f"Master file not found: {master_file_path}",
                    "Create it with 'cofog-panel seed-master', or use 'cofog-panel run', which creates it.")
        return False
    if not Path(source_folder_path).is_dir():
        print_error(f"Split directory not found: {source_folder_path}",
                    "Create the country files with 'cofog-panel split', or give the directory with --folder-path.")
        return False
    try:
        master = pd.read_excel(master_file_path, sheet_name=MASTER_SHEET, dtype=str, keep_default_na=False)
    except Exception as exc:
        print_error(f"Cannot read the sheet '{MASTER_SHEET}' of {master_file_path} ({exc}).",
                    "Use a master created by 'cofog-panel seed-master' and close it if it is open in Excel.")
        return False
    if "SortKey" not in master.columns:
        print_error("The master file has no 'SortKey' column.", "Use a master created by 'cofog-panel seed-master'.")
        return False
    print(f"✅ Master XLSX loaded: {len(master)} rows.")

    new_columns = [data_col_out, tier_col_out, sectors_col_out, complete_col_out]
    replaced = [c for c in new_columns if c in master.columns]
    if replaced:
        print(f"⚠️ Columns already in the master are replaced by this indicator: {replaced}. "
              f"Use other --data-col/--tier-col/--sectors-col/--complete-col names to keep them.")

    from .etl import COUNTRY_FILE_PATTERN
    files = sorted(f for f in source_folder_path.glob("*.xlsx") if COUNTRY_FILE_PATTERN.match(f.name))
    print(f"📂 Found {len(files)} intermediate country XLSX files in {source_folder_path}.")

    master_isos = set(master["SortKey"].astype(str).str[:3])
    selected: Dict[str, Tuple[str, str, str, str]] = {}
    unmatched: List[str] = []
    failed: List[str] = []
    for position, path in enumerate(files, start=1):
        iso = IMF_TO_ISO.get(path.stem, path.stem)
        if iso not in master_isos:
            unmatched.append(iso)
        print(f"[{position}/{len(files)}] Processing {iso}", end=" ")
        try:
            cells, summable = _read_country_file(path)
            found = _select_for_country(iso, cells, summable, sector_override, zero_as_missing)
        except Exception as exc:
            print(f"❌ Processing Error: {exc}")
            failed.append(iso)
            continue
        selected.update(found)
        print(f"-> OK ({len(found)} updates)")

    print("\n💾 Mapping results back to Master DataFrame and writing XLSX...")
    if unmatched:
        print(f"⚠️ Country files without a row in the Master file (check the lookup file): {unmatched}")
    keys = master["SortKey"].astype(str).str.strip()
    outside = sorted(set(selected) - set(keys))
    if outside:
        print(f"⚠️ {len(outside)} values have no row in the Master file (years or countries outside the panel) "
              f"and were not written, e.g. {outside[:5]}")

    rows = [selected.get(key, ("", "", "", "")) for key in keys]
    master[data_col_out] = pd.to_numeric(pd.Series([r[0] for r in rows], index=master.index), errors="coerce")
    for position, column in enumerate(new_columns[1:], start=1):
        master[column] = [r[position] for r in rows]

    out = master[PANEL_KEYS + [c for c in master.columns if c not in PANEL_KEYS]].copy()
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce").astype("Int64")
    out = _restore_types(out, skip=PANEL_KEYS + [data_col_out])
    try:
        with pd.ExcelWriter(master_file_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            out.to_excel(writer, sheet_name=MASTER_SHEET, index=False)
    except Exception as exc:
        print_error(f"Cannot write the master file {master_file_path} ({exc}).", hint_for_write_error(exc))
        return False

    tiers = master[tier_col_out].replace("", pd.NA).dropna().value_counts().to_dict()
    print(f"✅ SUCCESS! Filled {int(master[data_col_out].notna().sum())} of {len(master)} records in Master XLSX file.")
    print(f"   Tier breakdown: {tiers}")
    print(f"   Provenance columns: {tier_col_out}, {sectors_col_out}, {complete_col_out}")
    n_incomplete = int((master[complete_col_out] == "N").sum())
    if n_incomplete:
        print(f"   ⚠️ {n_incomplete} values are flagged incomplete ({complete_col_out} = N).")
    if failed:
        print_error(f"{len(failed)} country files could not be processed: {failed}",
                    "Run 'cofog-panel split' again to recreate the country files in this directory.")
        return False
    return True
