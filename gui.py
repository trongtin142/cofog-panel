import streamlit as st
import pandas as pd
import os
import shutil
import tempfile
from pathlib import Path
from cofog_panel.options import COFOG_LABELS, TRANSFORMATIONS, data_column_for, normalise_transformation
from cofog_panel.checks import verify_cofog_format, verify_country_format
from cofog_panel.master_seed import prepare_master, PACKAGED_LOOKUP, DEFAULT_FILE_NAME
from cofog_panel.etl import split_data
from cofog_panel.aggregate import run_aggregation

# --- Constants & Options ---
VALID_SECTORS = [
    "General government",
    "Central government including social security",
    "Budgetary central government",
    "Central government excluding social security",
    "Extrabudgetary central government",
    "Local Government",
    "Social security funds",
    "State Government",
]

COFOG_OPTIONS = [f"{code} - {label}" for code, label in COFOG_LABELS.items()]

st.set_page_config(
    page_title="COFOG-Panel GUI",
    page_icon="📊",
    layout="wide",
)

# --- Sidebar Configuration ---
st.sidebar.header("🛠️ Configuration")
st.sidebar.subheader("Pipeline Settings")

selected_cofog_full = st.sidebar.selectbox(
    "Select COFOG Function",
    options=COFOG_OPTIONS,
    index=COFOG_OPTIONS.index("05 - Environmental protection") if "05 - Environmental protection" in COFOG_OPTIONS else 0
)
selected_cofog_code = selected_cofog_full.split(" - ")[0]

selected_sector = st.sidebar.selectbox(
    "Aggregation Method (--sector)",
    options=VALID_SECTORS,
    index=VALID_SECTORS.index("General government")
)

selected_transformation = st.sidebar.selectbox(
    "Transformation Type (--filter-type)",
    options=TRANSFORMATIONS,
    index=TRANSFORMATIONS.index("Percent of GDP"),
)

st.sidebar.subheader("Year Range")
col1, col2 = st.sidebar.columns(2)
with col1:
    start_year = st.number_input("Start Year", value=1972, step=1)
with col2:
    end_year = st.number_input("End Year", value=2025, step=1)

overwrite_master = st.sidebar.checkbox("Overwrite Master File", value=False)

st.sidebar.divider()

# --- Main Area ---
st.title("📊 COFOG-Panel: Harmonise IMF GFS Data")
st.markdown("""
This tool builds a country-year panel for any COFOG division or group from a raw download (CSV or Excel) 
of the IMF Government Finance Statistics (GFS) dataset.
""")

# File Uploaders
col_file1, col_file2 = st.columns(2)

with col_file1:
    st.subheader("1. IMF GFS Data")
    uploaded_source = st.file_uploader("Upload IMF GFS CSV or Excel file", type=["csv", "xlsx"])

with col_file2:
    st.subheader("2. Country Lookup (Optional)")
    uploaded_lookup = st.file_uploader("Upload custom Country Codes Excel", type=["xlsx"])

# --- Execution Logic ---
if st.sidebar.button("🚀 Run Pipeline", type="primary", use_container_width=True):
    if not uploaded_source:
        st.error("❌ Please upload the IMF GFS data file first!")
    else:
        try:
            # Create a temporary directory for processing
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                input_dir = tmp_path / "input"
                output_dir = tmp_path / "output"
                split_dir = tmp_path / "splits"
                input_dir.mkdir()
                output_dir.mkdir()
                split_dir.mkdir()

                # Save uploaded IMF source
                source_path = input_dir / uploaded_source.name
                with open(source_path, "wb") as f:
                    f.write(uploaded_source.getbuffer())

                # Handle Lookup file
                lookup_path = PACKAGED_LOOKUP
                if uploaded_lookup:
                    lookup_path = input_dir / uploaded_lookup.name
                    with open(lookup_path, "wb") as f:
                        f.write(uploaded_lookup.getbuffer())

                # Prepare parameters
                transformation = normalise_transformation(selected_transformation)
                data_col = data_column_for(selected_cofog_code)

                # --- Pipeline Execution ---
                with st.status("⏳ Running COFOG Pipeline...", expanded=True) as status:
                    
                    st.write("🔍 [Stage 1/5] Checking COFOG Format...")
                    ok, msg = verify_cofog_format(source_path)
                    if not ok:
                        st.error(f"Format Check Failed: {msg}")
                        status.update(label="❌ Pipeline Failed at Stage 1", state="error")
                        st.stop()

                    st.write("🌍 [Stage 2/5] Checking Country Code Format...")
                    ok, msg = verify_country_format(lookup_path)
                    if not ok:
                        st.error(f"Country Lookup Check Failed: {msg}")
                        status.update(label="❌ Pipeline Failed at Stage 2", state="error")
                        st.stop()

                    st.write("🏗️ [Stage 3/5] Preparing Master XLSX...")
                    master_path, ok = prepare_master(
                        lookup_path, output_dir, DEFAULT_FILE_NAME, 
                        start_year, end_year, overwrite=overwrite_master
                    )
                    if not ok:
                        st.error("Failed to prepare Master file.")
                        status.update(label="❌ Pipeline Failed at Stage 3", state="error")
                        st.stop()

                    st.write("🔪 [Stage 4/5] Splitting Data per Country...")
                    folder, ok = split_data(source_path, transformation, {selected_cofog_code}, split_dir)
                    if not ok:
                        st.error("Failed to split data.")
                        status.update(label="❌ Pipeline Failed at Stage 4", state="error")
                        st.stop()

                    st.write("📊 [Stage 5/5] Running Tiered Aggregation...")
                    if not run_aggregation(master_path, folder, data_col, selected_sector, None, False, None, None):
                        st.error("Aggregation failed.")
                        status.update(label="❌ Pipeline Failed at Stage 5", state="error")
                        st.stop()

                    status.update(label="🎉 Pipeline Completed Successfully!", state="complete")

                # --- Result Display & Download ---
                st.success(f"✅ Processing complete! COFOG {selected_cofog_code} harmonised using '{selected_sector}' method.")
                
                with open(master_path, "rb") as f:
                    st.download_button(
                        label="📥 Download Resulting Master File",
                        data=f,
                        file_name="COFOG_MASTER_SCHEMA.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                # Preview (Optional)
                try:
                    df_preview = pd.read_excel(master_path, sheet_name="MasterData")
                    st.subheader("👀 Preview (First 10 rows)")
                    st.dataframe(df_preview.head(10), use_container_width=True)
                except:
                    st.warning("Could not generate preview, but the file is ready for download.")

        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            if st.checkbox("Show full error details"):
                st.exception(e)

st.divider()
with st.expander("📖 How to download IMF data?"):
    st.markdown("""
    1. Open the [IMF GFS COFOG dataset page](https://data.imf.org/en/datasets/IMF.STA:GFS_COFOG).
    2. Click **DOWNLOAD** (top right).
    3. Keep defaults: **Download full dataset** ON, **File Format: CSV**, **Data format: Timeseries per row**.
    4. Click **DOWNLOAD** in the window and upload the resulting file here.
    """)
