import pandas as pd
import openpyxl
from typing import List, Dict, Any, Tuple
from pathlib import Path

# --- STANDARD HEADER TEMPLATE CONFIGURATION (defined as constants) ---
FIXED_HEADERS_SAMPLE = [
   'DATASET', 'SERIES_CODE', 'OBS_MEASURE', 'COUNTRY', 'SECTOR', 'GFS_GRP',
   'INDICATOR', 'TYPE_OF_TRANSFORMATION', 'FREQUENCY', 'SCALE', 'DECIMALS_DISPLAYED',
   'INSTR_ASSET', 'GFS_STO', 'COFOG', 'CURRENCY', 'INT_TTC', 'COUNTERPART_SECTOR',
   'GFS_DF', 'ACCOUNTING_ENTRY', 'FLOW_STOCK_ENTRY', 'FI_MATURITY', 'GFS_RB',
   'STATISTICAL_MEASURES', 'GFS_COMPONENT', 'TRANSFORMATION', 'ACCOUNTS', 'UNIT',
   'OVERLAP', 'DOI', 'FULL_DESCRIPTION', 'AUTHOR', 'PUBLISHER', 'DEPARTMENT',
   'CONTACT_POINT', 'TOPIC', 'TOPIC_DATASET', 'KEYWORDS', 'KEYWORDS_DATASET',
   'LANGUAGE', 'PUBLICATION_DATE', 'UPDATE_DATE', 'METHODOLOGY', 'METHODOLOGY_NOTES',
   'ACCESS_SHARING_LEVEL', 'ACCESS_SHARING_NOTES', 'SECURITY_CLASSIFICATION',
   'SHORT_SOURCE_CITATION', 'FULL_SOURCE_CITATION', 'LICENSE', 'SUGGESTED_CITATION',
   'KEY_INDICATOR', 'SERIES_NAME'
]

START_YEAR = 1972
END_YEAR = 2024
YEAR_COLUMNS_SAMPLE = [str(y) for y in range(START_YEAR, END_YEAR + 1)]
# FULL_HEADER_SAMPLE is not required for validation, only fixed and year columns are needed.

# --- MAIN FUNCTION FOR CLI ---

def verify_cofog_format(file_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate the header structure of an input COFOG Excel file by streaming the first row.

    Args:
        file_path: Path to the source Excel file.

    Returns:
        Tuple (is_match: bool, details: dict)
    """
    verification_status = {
        "Match": True,
        "Missing_Headers": [],
        "Extra_Headers": [],
        "Year_Mismatch": False,
        "Total_Columns": 0
    }

    if not file_path.exists():
        print(f"❌ Error: File not found at {file_path}")
        verification_status["Match"] = False
        return False, verification_status

    try:
        # USE OPENPYXL WITH read_only=True (memory optimized)
        wb = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
        ws = wb.active
        
        # Read only the first row (header)
        header_row_tuple = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        wb.close()
        
        # Convert all headers to strings immediately
        uploaded_headers = [str(col).strip() for col in header_row_tuple if col is not None]
        verification_status["Total_Columns"] = len(uploaded_headers)
        
    except Exception as e:
        print(f"❌ Error reading Excel file structure: {e}")
        verification_status["Match"] = False
        return False, verification_status

    # --- STEP 2: VALIDATION ---

    # 1. Check for missing fixed headers
    missing = [h for h in FIXED_HEADERS_SAMPLE if h not in uploaded_headers]
    if missing:
        verification_status["Match"] = False
        verification_status["Missing_Headers"] = missing

    # 2. Check if all year columns exist
    # Later IMF releases append new years, so any contiguous run starting at START_YEAR is accepted
    uploaded_years = sorted(int(h) for h in uploaded_headers if h.isdigit() and len(h) == 4)
    expected_run = list(range(START_YEAR, (uploaded_years[-1] if uploaded_years else START_YEAR) + 1))

    if not uploaded_years or uploaded_years != expected_run or uploaded_years[-1] < END_YEAR:
        verification_status["Year_Mismatch"] = True
        verification_status["Match"] = False

    # 3. Check for headers that are neither fixed nor year columns
    fixed_set = set(FIXED_HEADERS_SAMPLE)
    year_set = {str(y) for y in uploaded_years}
    
    # Headers present but not part of fixed or year columns
    extra = [h for h in uploaded_headers if h not in fixed_set and h not in year_set]

    if extra:
        verification_status["Match"] = False
        verification_status["Extra_Headers"] = extra

    is_match = verification_status["Match"]
    
    # Print detailed report (user-facing output)
    print("\n" + "="*40)
    print(f"COFOG FORMAT VERIFICATION REPORT ({file_path.name})")
    print("="*40)

    if is_match:
        print("🎉 SUCCESS: File header structure matches the required template.")
    else:
        print("❌ WARNING: Header structure mismatch detected.")
        if verification_status["Missing_Headers"]:
            print(f"   -> MISSING Fixed Headers ({len(verification_status['Missing_Headers'])}): {verification_status['Missing_Headers']}")
        if verification_status["Extra_Headers"]:
            print(f"   -> UNKNOWN Extra Headers ({len(verification_status['Extra_Headers'])}): {verification_status['Extra_Headers']}")
        if verification_status["Year_Mismatch"]:
            print(f"   -> Year columns must run contiguously from {START_YEAR} to at least {END_YEAR}.")
    
    print("="*40)
    
    return is_match, verification_status


# --- CONSTANTS FOR COUNTRY CODE VALIDATION ---
REQUIRED_COUNTRY_COLS = ['name', 'alpha-2', 'alpha-3', 'country-code']

# --- FUNCTION FOR check-country-format COMMAND ---

def verify_country_format(file_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate the structure of a country lookup (mapping) file.

    Args:
        file_path: Path to the Excel/CSV lookup file.

    Returns:
        Tuple (is_valid: bool, details: dict)
    """
    verification_status = {
        "Valid": True,
        "Missing_Columns": [],
        "Duplicate_Alpha3": False,
        "Total_Rows": 0
    }

    if not file_path.exists():
        print(f"❌ Error: File not found at {file_path}")
        verification_status["Valid"] = False
        return False, verification_status

    try:
        # Auto-detect file format
        if file_path.suffix == '.csv':
            df = pd.read_csv(file_path, keep_default_na=False)
        elif file_path.suffix in ('.xlsx', '.xls'):
            df = pd.read_excel(file_path, keep_default_na=False)
        else:
            print(f"❌ Error: Unsupported file format for lookup: {file_path.suffix}. Must be .csv or .xlsx.")
            verification_status["Valid"] = False
            return False, verification_status

        verification_status["Total_Rows"] = len(df)

        # 1. Check required identifier columns
        missing_cols = [col for col in REQUIRED_COUNTRY_COLS if col not in df.columns]
        
        if missing_cols:
            verification_status["Valid"] = False
            verification_status["Missing_Columns"] = missing_cols

        # 2. Check duplicate alpha-3 codes
        if 'alpha-3' in df.columns and df['alpha-3'].duplicated().any():
            verification_status["Duplicate_Alpha3"] = True
            verification_status["Valid"] = False
            
        # Handle invalid cases but still print available columns
        if not verification_status["Valid"]:
             print(f"❌ Mismatch detected in {file_path.name}.")
             if verification_status["Missing_Columns"]:
                 print(f"   -> Missing required columns: {verification_status['Missing_Columns']}")
             if verification_status["Duplicate_Alpha3"]:
                 print("   -> Duplicate 'alpha-3' codes found.")
             print(f"   -> Columns found: {list(df.columns)}")
             return False, verification_status

        print(f"✅ SUCCESS: Country lookup file structure is VALID.")
        print(f"   -> Total Rows: {len(df)}")
        print(f"   -> Columns: {list(df.columns)}")
        return True, verification_status

    except Exception as e:
        print(f"❌ Error processing lookup file {file_path}: {str(e)}")
        verification_status["Valid"] = False
        return False, verification_status

# Helper function for standalone execution (local environment)
if __name__ == '__main__':
    # Simulate CLI execution here,
    # e.g., assume a test file 'test_data.xlsx' exists
    
    # To run this, place a sample Excel file in the root directory
    TEST_FILE = Path("test_data_cofog.xlsx") 
    
    if TEST_FILE.exists():
        print(f"Running self-test on {TEST_FILE}...")
        success, _ = verify_cofog_format(TEST_FILE)
        if success:
            print("\nSelf-test passed.")
        else:
            print("\nSelf-test failed.")
    else:
        print("Setup complete. To test locally, create 'test_data_cofog.xlsx' and run this script.")