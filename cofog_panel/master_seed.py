import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any

# --- DEFAULT CONFIGURATION ---
DEFAULT_START_YEAR = 1972   # first year of the IMF GFS COFOG data
DEFAULT_END_YEAR = 2025
DEFAULT_FILE_NAME = 'COFOG_MASTER_SCHEMA.xlsx'  # Changed to XLSX

def seed_master(
    lookup_file_path: Path, 
    output_path: Path,  # New parameter: local output directory
    output_name: str = DEFAULT_FILE_NAME,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
) -> Tuple[Path, bool]:
    """
    Create a local Master XLSX file structure using the lookup file.

    Args:
        lookup_file_path: Path to Excel file containing 'name' and 'alpha-3'.
        output_path: Root directory where the Master XLSX file will be saved.
        output_name: Name of the new Master XLSX file.
        start_year, end_year: First and last year of the panel (inclusive).

    Returns:
        Tuple (master_file_path: Path, success: bool)
    """
    
    final_output_path = output_path / output_name
    print(f"\n--- SEEDING MASTER: Processing {lookup_file_path.name} ---")

    if not lookup_file_path.exists():
        print(f"❌ Error: Lookup file not found at {lookup_file_path}")
        return Path(""), False

    try:
        # Read lookup file
        if lookup_file_path.suffix == '.csv':
            df_source = pd.read_csv(lookup_file_path, keep_default_na=False)
        else:
            df_source = pd.read_excel(lookup_file_path, keep_default_na=False)

        if 'name' not in df_source.columns or 'alpha-3' not in df_source.columns:
            print("❌ Error: Lookup file must contain 'name' and 'alpha-3' columns.")
            return final_output_path, False

        output_rows = []
        for index, row in df_source.iterrows():
            country_name = str(row['name']).strip()
            alpha_3 = str(row['alpha-3']).strip()

            if not alpha_3 or alpha_3.upper() == 'NAN':
                continue

            for year in range(start_year, end_year + 1):
                sort_key = f"{alpha_3}{year}"
                output_rows.append({
                    'SortKey': sort_key,
                    'Country': country_name,
                    'Year': year,
                })

        df_final = pd.DataFrame(output_rows)
        # Panel keys only; indicators are added by the aggregate stage
        df_final = df_final[['SortKey', 'Country', 'Year']]

        # Write to local XLSX file
        output_path.mkdir(parents=True, exist_ok=True)
        df_final.to_excel(final_output_path, index=False, sheet_name="MasterData")
        
        print(f"✅ SUCCESS: Master XLSX file created successfully.")
        print(f"=> File Path: {final_output_path}")
        
        return final_output_path, True

    except Exception as e:
        print(f"❌ Error during master seeding: {e}")
        return final_output_path, False