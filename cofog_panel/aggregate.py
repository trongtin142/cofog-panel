import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from decimal import Decimal, InvalidOperation, getcontext

# Configure Decimal precision
getcontext().prec = 50

# --- SECTOR NAMES (normalised to lower case, as they appear in IMF GFS COFOG) ---
GG = 'general government'
CGSS = 'central government including social security'
CGXSS = 'central government excluding social security'
BCG = 'budgetary central government'
EBCG = 'extrabudgetary central government'
SSF = 'social security funds'
SG = 'state government'
LG = 'local government'

# Sectors used by each fallback tier of the General government method
T2_SECTORS = [CGSS, SG, LG]
T3_SECTORS = [BCG, EBCG, SSF, SG, LG]
# Sectors used by the fallback of the Central government method
C2_SECTORS = [BCG, EBCG, SSF]
# Levels whose omission makes a fallback sum incomplete (see is_complete)
COVERAGE_LEVELS = [EBCG, SSF, SG, LG]


def _central_core(values: Dict[str, Optional[Decimal]]) -> List[str]:
    """
    Central government excluding social security funds: the consolidated series if reported,
    otherwise its budgetary and extrabudgetary components (unconsolidated).
    """
    return [CGXSS] if values.get(CGXSS) is not None else [BCG, EBCG]

DIRECT_SECTORS = [
    "Budgetary central government", "Extrabudgetary central government",
    "Local Government", "Social security funds", "State Government",
    "Central government excluding social security",
]

# Transformations whose values can be added across subsectors.
# Shares of total outlays have subsector-specific denominators and cannot be summed.
SUMMABLE_TRANSFORMATIONS = {"Percent of GDP", "Domestic currency"}

# Short labels for the SOURCE_SECTORS column
SECTOR_ABBR = {GG: "GG", CGSS: "CGSS", CGXSS: "CGXSS", BCG: "BCG", EBCG: "EBCG", SSF: "SSF",
               SG: "SG", LG: "LG"}

# IMF country codes that differ from ISO 3166 alpha-3
IMF_TO_ISO = {"KOS": "XKX", "WBG": "PSE"}

DEFAULT_TIER_COL = "SOURCE_TIER"
DEFAULT_SECTORS_COL = "SOURCE_SECTORS"
DEFAULT_COMPLETE_COL = "SOURCE_COMPLETE"

# --- HELPER FUNCTIONS ---

def _to_decimal_safe(val: Any) -> Optional[Decimal]:
    """Safely convert a value to Decimal."""
    if val is None or pd.isna(val):
        return None

    s = str(val).strip()
    if not s:
        return None

    # Strict check for NaN/None strings
    if s.upper() in ('NAN', 'NONE', ''):
        return None

    try:
        return Decimal(s)
    except InvalidOperation:
        # If conversion fails (e.g., invalid string), return None
        return None


def _is_reported(val: Optional[Decimal], zero_as_missing: bool) -> bool:
    """A value is reported when present; zero counts as reported unless zero_as_missing."""
    if val is None:
        return False
    if zero_as_missing and val == Decimal(0):
        return False
    return True


def _sum_reported(values: Dict[str, Optional[Decimal]], sectors: List[str]) -> Tuple[Optional[Decimal], List[str]]:
    """Sum the sectors that are present; (None, []) if none of them is present."""
    present = [s for s in sectors if values.get(s) is not None]
    if not present:
        return None, []
    return sum((values[s] for s in present), Decimal(0)), present


def resolve_value(
    values: Dict[str, Optional[Decimal]],
    sector_override: str = "General government",
    zero_as_missing: bool = False,
    summable: bool = True,
) -> Tuple[Optional[Decimal], str, List[str]]:
    """
    Select one value for a country-year from its subsector values.

    `values` maps normalised (lower-case) sector names to Decimal or None.
    Returns (value, tier, sectors) where sectors lists the sectors that entered
    the value and tier is one of:
      T1 = General government reported
      T2 = Central gov. incl. social security + State + Local (unconsolidated sum)
      T3 = Central gov. excl. social security (or, if not reported, Budgetary + Extrabudgetary)
           + Social security funds + State + Local (unconsolidated sum)
      C1 = Central gov. incl. social security reported
      C2 = Central gov. excl. social security (or Budgetary + Extrabudgetary)
           + Social security funds (unconsolidated sum)
      D  = value of the directly requested sector
      "" = no value
    """
    if zero_as_missing:
        # A reported zero often means "not separately identified": drop zeros everywhere
        values = {k: (None if v is not None and v == Decimal(0) else v) for k, v in values.items()}

    if sector_override == "General government":
        if _is_reported(values.get(GG), zero_as_missing):
            return values[GG], "T1", [GG]
        if not summable:
            return None, "", []
        if _is_reported(values.get(CGSS), zero_as_missing):
            total, used = _sum_reported(values, T2_SECTORS)
            return total, "T2", used
        total, used = _sum_reported(values, _central_core(values) + [SSF, SG, LG])
        if total is not None:
            return total, "T3", used
        return None, "", []

    if sector_override == "Central government including social security":
        if _is_reported(values.get(CGSS), zero_as_missing):
            return values[CGSS], "C1", [CGSS]
        if not summable:
            return None, "", []
        total, used = _sum_reported(values, _central_core(values) + [SSF])
        if total is not None:
            return total, "C2", used
        return None, "", []

    if sector_override in DIRECT_SECTORS:
        val = values.get(sector_override.lower())
        if val is not None:
            return val, "D", [sector_override.lower()]
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
    subnational = [s for s in (SG, LG) if s in reported]

    def central_ok() -> bool:
        if CGXSS in used:
            core = True
        else:
            core = BCG in used and (EBCG in used or EBCG not in reported)
        return core and (SSF in used or SSF not in reported)

    if tier == "T1":
        if values is not None and values.get(CGSS) is not None and values.get(GG) is not None:
            sub_positive = any((values.get(s) or Decimal(0)) > 0 for s in (SG, LG))
            if sub_positive and values[GG] == values[CGSS]:
                return False
        return True
    if tier in ("C1", "D"):
        return True
    if tier == "T2":
        return all(s in used for s in subnational)
    if tier == "T3":
        return central_ok() and all(s in used for s in subnational)
    if tier == "C2":
        return central_ok()
    return None


def _format_decimal(val: Decimal) -> str:
    """Plain (non-scientific) string for a Decimal, without trailing zeros."""
    s = format(val, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s if s not in ('', '-0') else '0'

# --- MAIN FUNCTION FOR aggregate COMMAND ---

def run_aggregation(
    master_file_path: Path,
    source_folder_path: Path,
    data_col_out: str,
    sector_override: Optional[str] = "General government",
    tier_col_out: str = DEFAULT_TIER_COL,
    zero_as_missing: bool = False,
    sectors_col_out: str = DEFAULT_SECTORS_COL,
    complete_col_out: str = DEFAULT_COMPLETE_COL,
) -> bool:

    MASTER_TAB_NAME = "MasterData"
    print(f"\n--- AGGREGATE STAGE: Processing files in {source_folder_path.name} ---")

    # --- STEP 1: LOAD MASTER XLSX INTO MEMORY ---
    try:
        df_master = pd.read_excel(master_file_path, sheet_name=MASTER_TAB_NAME, dtype=str, keep_default_na=False)

        if 'SortKey' not in df_master.columns:
            print("❌ Initialization Error: Master XLSX missing 'SortKey' column.")
            return False

        print(f"✅ Master XLSX loaded: {len(df_master)} rows.")
    except Exception as e:
        print(f"❌ Initialization Error reading Master XLSX: {e}")
        return False

    # --- STEP 2: SCAN AND PROCESS EACH COUNTRY FILE ---
    updates_map: Dict[str, Tuple[str, str, str, str]] = {}  # { 'SortKey': (ValueString, Tier, Sectors, Complete) }
    master_countries = set(df_master['SortKey'].astype(str).str[:3])
    unmatched: List[str] = []

    from .etl import COUNTRY_FILE_PATTERN
    country_files = sorted(f for f in source_folder_path.glob("*.xlsx") if COUNTRY_FILE_PATTERN.match(f.name))
    failed: List[str] = []
    print(f"📂 Found {len(country_files)} intermediate country XLSX files in {source_folder_path}.")

    for idx, file_path in enumerate(country_files):
        country_code = file_path.stem  # Filename (without extension) is the 3-digit country code
        country_code = IMF_TO_ISO.get(country_code, country_code)
        if country_code not in master_countries:
            unmatched.append(country_code)

        print(f"[{idx+1}/{len(country_files)}] Processing {country_code}", end=" ")

        try:
            df = pd.read_excel(file_path, dtype=str)

            # Normalize Sector
            col_sector = 'SECTOR' if 'SECTOR' in df.columns else df.columns[4]
            df['SECTOR_NORM'] = df[col_sector].astype(str).str.lower().str.strip()
            # Keep the first row per sector (one series per sector after the split filter)
            df = df.drop_duplicates(subset='SECTOR_NORM', keep='first').set_index('SECTOR_NORM')

            # Shares of total outlays must not be summed across subsectors
            summable = True
            if 'TYPE_OF_TRANSFORMATION' in df.columns:
                types = set(df['TYPE_OF_TRANSFORMATION'].dropna().astype(str).str.strip())
                summable = types.issubset(SUMMABLE_TRANSFORMATIONS)

            year_cols = [c for c in df.columns if str(c).isdigit()]
            found_updates = 0

            # Levels reported in at least one year of this country's series
            def _reported(sec, y):
                d = _to_decimal_safe(df.at[sec, y])
                return d is not None and not (zero_as_missing and d == Decimal(0))
            levels_reported = [
                sec for sec in COVERAGE_LEVELS
                if sec in df.index and any(_reported(sec, y) for y in year_cols)
            ]

            for year_str in year_cols:
                sort_key = f"{country_code}{year_str}"
                values = {sec: _to_decimal_safe(df.at[sec, year_str]) for sec in df.index}

                dec_val, tier, used = resolve_value(values, sector_override, zero_as_missing, summable)

                # --- STORE RESULT ---
                if dec_val is not None:
                    # T1/C1/D keep the original reported string; sums are formatted from Decimal
                    if tier in ("T1", "C1", "D"):
                        sector_key = {"T1": GG, "C1": CGSS}.get(tier, str(sector_override).lower())
                        val_str = str(df.at[sector_key, year_str]).strip()
                    else:
                        val_str = _format_decimal(dec_val)
                    complete = is_complete(tier, used, levels_reported, values)
                    updates_map[sort_key] = (val_str, tier, "+".join(SECTOR_ABBR.get(u, u) for u in used),
                                             "Y" if complete else "N")
                    found_updates += 1

            print(f"-> OK ({found_updates} updates)")

        except Exception as e:
            print(f"❌ Processing Error: {e}")
            failed.append(country_code)

    # --- STEP 3: MAP RESULTS AND WRITE MASTER XLSX ---

    print("\n💾 Mapping results back to Master DataFrame and writing XLSX...")

    if unmatched:
        print(f"⚠️ Country files without a row in the Master file (check the lookup file): {unmatched}")

    keys = df_master['SortKey'].astype(str).str.strip()
    outside = sorted(set(updates_map) - set(keys))
    if outside:
        print(f"⚠️ {len(outside)} values have no row in the Master file (years or countries outside the panel) "
              f"and were not written, e.g. {outside[:5]}")

    empty = ("", "", "", "")
    df_master[data_col_out] = pd.to_numeric(pd.Series([updates_map.get(sk, empty)[0] for sk in keys],
                                                      index=df_master.index), errors="coerce")
    df_master[tier_col_out] = [updates_map.get(sk, empty)[1] for sk in keys]
    df_master[sectors_col_out] = [updates_map.get(sk, empty)[2] for sk in keys]
    df_master[complete_col_out] = [updates_map.get(sk, empty)[3] for sk in keys]
    update_count = int(df_master[data_col_out].notna().sum())

    try:
        # Keep every existing column (earlier indicators), with the panel keys first
        base = ['SortKey', 'Country', 'Year']
        df_to_write = df_master[base + [c for c in df_master.columns if c not in base]].copy()
        df_to_write['Year'] = pd.to_numeric(df_to_write['Year'], errors="coerce").astype("Int64")
        # Columns read back from the master are strings: restore numbers for earlier indicators
        for c in df_to_write.columns:
            if c in base or c == data_col_out:
                continue
            col = df_to_write[c].astype(str).replace({'nan': '', 'None': ''})
            as_num = pd.to_numeric(col.replace('', None), errors="coerce")
            looks_numeric = as_num.notna().any() and as_num.notna().sum() == (col != '').sum()
            df_to_write[c] = as_num if looks_numeric else col

        with pd.ExcelWriter(master_file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_to_write.to_excel(writer, sheet_name=MASTER_TAB_NAME, index=False)

        tier_counts = df_master[tier_col_out].replace('', pd.NA).dropna().value_counts().to_dict()
        print(f"✅ SUCCESS! Filled {update_count} of {len(df_master)} records in Master XLSX file.")
        print(f"   Tier breakdown: {tier_counts}")
        n_incomplete = int((df_master[complete_col_out] == "N").sum())
        if n_incomplete:
            print(f"   ⚠️ {n_incomplete} values are flagged incomplete ({complete_col_out} = N).")
        if failed:
            print(f"❌ {len(failed)} country files could not be processed: {failed}")
            return False
        return True

    except Exception as e:
        print(f"❌ FAILED TO WRITE TO MASTER XLSX FILE: {e}")
        return False
