import re
import pandas as pd
import openpyxl
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# --- FIXED CONFIGURATION (only keep default Transformation Type) ---
DEFAULT_TARGET_TRANSFORMATION = "Percent of GDP"
DEFAULT_OUTPUT_SUBDIR = "intermediate_splits"
COUNTRY_FILE_PATTERN = re.compile(r"^[A-Z]{3}\.xlsx$")
# Marker written into split directories; country files are only ever deleted from marked directories
SPLIT_MARKER = ".cofog_panel_split"

# --- HELPER FUNCTIONS ---

def _cofog_code_from_series(series_code: Any) -> Optional[str]:
    """Extract the COFOG code from an IMF series code, e.g. 'ARM.S13.G2MF.GF0510_T.POGDP_PT.A' -> '05.1'."""
    if not isinstance(series_code, str):
        return None
    parts = series_code.split(".")
    if len(parts) < 4 or not parts[3].startswith("GF"):
        return None
    digits = parts[3][2:].split("_")[0]
    if not digits.isdigit():
        return None
    if len(digits) <= 2:
        return digits
    # Groups are coded with a trailing zero in GFS (GF0510 -> 05.1)
    return f"{digits[:2]}.{digits[2:].rstrip('0') or '0'}"


def _matches_cofog(val_cofog: Any, series_code: Any, cofog_filter_set: set) -> bool:
    """Match on the COFOG label (e.g. 'Environmental protection') or on the code (e.g. '05')."""
    if val_cofog is not None and str(val_cofog).strip() in cofog_filter_set:
        return True
    code = _cofog_code_from_series(series_code)
    return code is not None and code in cofog_filter_set

# --- MAIN FUNCTION FOR split COMMAND ---

def split_data(
    source_file_path: Path, 
    filter_type: str,  
    cofog_filter_set: set,  # RECEIVE COFOG FILTER SET FROM OUTSIDE
    output_dir: Path
) -> Tuple[Path, bool]:
    """
    Filter raw COFOG data and save into separate XLSX files by 3-digit country code.
    """
    print(f"\n--- ETL & SPLIT: Processing {source_file_path.name} ---")
    
    # ... (File validation and workbook loading remain unchanged) ...
    if not source_file_path.exists():
        print(f"❌ Error: Source file not found at {source_file_path}")
        return output_dir, False
        
    try:
        wb = openpyxl.load_workbook(str(source_file_path), read_only=True, data_only=True)
        ws = wb.active
    except Exception as e:
        print(f"❌ Error reading Excel workbook structure: {e}")
        return output_dir, False

    buffered_data: Dict[str, List[List[Any]]] = {}
    headers: List[str] = []
    col_mapping: Dict[str, int] = {}
    TARGET_TRANSFORMATION = filter_type 

    row_count = 0
    valid_count = 0
    
    print(f"Filtering data by Transformation: {TARGET_TRANSFORMATION} and COFOGs: {cofog_filter_set}...")

    for row in ws.iter_rows(values_only=True):
        row_count += 1
        if row_count % 50000 == 0:
            print(f"   ... Processed {row_count} rows. Found {valid_count} valid rows so far.")

        if row_count == 1:
            headers = [str(col).strip() if col is not None else "" for col in row]
            try:
                col_mapping["SERIES_CODE"] = headers.index("SERIES_CODE")
                col_mapping["TYPE_OF_TRANSFORMATION"] = headers.index("TYPE_OF_TRANSFORMATION")
                col_mapping["COFOG"] = headers.index("COFOG")
            except ValueError as e:
                print(f"❌ Header Error: Missing essential column for filtering: {e}")
                return output_dir, False
            continue

        val_series = row[col_mapping["SERIES_CODE"]]
        val_type = row[col_mapping["TYPE_OF_TRANSFORMATION"]]
        val_cofog = row[col_mapping["COFOG"]]
        
        # --- FILTER LOGIC (check if COFOG is in the provided SET) ---
        if val_type != TARGET_TRANSFORMATION: continue
        if not _matches_cofog(val_cofog, val_series, cofog_filter_set): continue

        # ... (Data routing and buffering logic remain unchanged) ...
        
        country_code = None
        if val_series and isinstance(val_series, str) and len(val_series) >= 3:
            country_code = val_series[:3].upper()
        
        if not country_code: continue

        valid_count += 1

        if country_code not in buffered_data:
            buffered_data[country_code] = []

        clean_row = [str(cell) if cell is not None else "" for cell in row]
        buffered_data[country_code].append(clean_row)

    wb.close()

    print(f"\n--- Filtering complete. Total Processed: {row_count}. Total Valid: {valid_count} ---")
    
    # --- STEP 4: WRITE LOCAL XLSX FILES ---
    success = True

    if valid_count == 0:
        print(f"❌ No rows matched COFOG {cofog_filter_set} with transformation '{TARGET_TRANSFORMATION}'.")
        return output_dir, False

    # Only write into an empty directory or one created by a previous split (never touch user files)
    if output_dir.exists() and any(output_dir.iterdir()) and not (output_dir / SPLIT_MARKER).exists():
        print(f"❌ {output_dir} is not empty and was not created by 'cofog-panel split'. "
              f"Choose an empty or new --output-dir.")
        return output_dir, False
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / SPLIT_MARKER).write_text("Created by cofog-panel split. Country files here are replaced on each run." + chr(10))

    # Remove country files from a previous run so that aggregation only sees this split
    stale = [f for f in output_dir.glob("*.xlsx") if COUNTRY_FILE_PATTERN.match(f.name)]
    if stale:
        print(f"🧹 Removing {len(stale)} country files from a previous split in {output_dir}.")
        for f in stale:
            f.unlink()
    
    for country, rows in buffered_data.items():
        file_name = f"{country}.xlsx"
        output_path = output_dir / file_name
        
        print(f"Writing {len(rows)} rows for country: {country}...")
        
        try:
            df_country = pd.DataFrame(rows, columns=headers)
            df_country.to_excel(output_path, index=False, sheet_name=country)
            print(f"-> Successfully wrote {country}.")

        except Exception as e:
            print(f"❌ Critical Error writing file {country}: {str(e)}")
            success = False
            
    print("\n=== SPLIT STAGE COMPLETED ===")
    return output_dir, success