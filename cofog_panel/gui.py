"""
Browser interface (Streamlit): the five stages of `cofog-panel run` for one COFOG function.

Start it with `cofog-panel gui` (gui extra: pip install "cofog-panel[gui]"), with
`streamlit run gui.py` in a clone, or with the launchers run_gui.sh and run_gui.bat.
Streamlit runs this file as a script; importing it does not draw the page.
"""
import io
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pandas as pd
import streamlit as st

from cofog_panel.aggregate import run_aggregation
from cofog_panel.checks import verify_cofog_format, verify_country_format
from cofog_panel.etl import read_split_marker, split_data
from cofog_panel.master_seed import DEFAULT_FILE_NAME, PACKAGED_LOOKUP, prepare_master
from cofog_panel.options import COFOG_LABELS, DIRECT_SECTORS, TRANSFORMATIONS, data_column_for, normalise_transformation
from cofog_panel.provenance import function_row, output_columns, record_run, sha256_of

# --- Constants & Options ---
VALID_SECTORS = ["General government", "Central government including social security", *DIRECT_SECTORS]

COFOG_OPTIONS = [f"{code} - {label}" for code, label in COFOG_LABELS.items()]


def main() -> None:
    """Draw the page and run the pipeline when the button is clicked (Streamlit calls the script on every interaction)."""
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
    if st.sidebar.button("🚀 Run Pipeline", type="primary", width="stretch"):
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
                    source_path = input_dir / Path(uploaded_source.name).name
                    with open(source_path, "wb") as f:
                        f.write(uploaded_source.getbuffer())

                    # Handle Lookup file
                    lookup_path = PACKAGED_LOOKUP
                    if uploaded_lookup:
                        lookup_path = input_dir / Path(uploaded_lookup.name).name
                        with open(lookup_path, "wb") as f:
                            f.write(uploaded_lookup.getbuffer())

                    # Prepare parameters
                    transformation = normalise_transformation(selected_transformation)
                    data_col = data_column_for(selected_cofog_code)

                    # The stages print their reports, warnings and two-line errors; show them on the page
                    log = io.StringIO()

                    def fail(status, stage, what):
                        st.error(what)
                        st.code(log.getvalue() or "(no details)", language=None)
                        status.update(label=f"❌ Pipeline Failed at Stage {stage}", state="error")
                        st.stop()

                    # --- Pipeline Execution ---
                    with st.status("⏳ Running COFOG Pipeline...", expanded=True) as status, \
                            redirect_stdout(log), redirect_stderr(log):

                        st.write("🔍 [Stage 1/5] Checking COFOG Format...")
                        ok, _details = verify_cofog_format(source_path)
                        if not ok:
                            fail(status, 1, "Format check failed. Use the unchanged IMF download (details below).")

                        st.write("🌍 [Stage 2/5] Checking Country Code Format...")
                        ok, _details = verify_country_format(lookup_path)
                        if not ok:
                            fail(status, 2, "Country lookup check failed (details below).")

                        st.write("🏗️ [Stage 3/5] Preparing Master XLSX...")
                        # output_dir is new for every run, so there is never a master to keep or overwrite
                        master_path, ok = prepare_master(
                            lookup_path, output_dir, DEFAULT_FILE_NAME,
                            start_year, end_year
                        )
                        if not ok:
                            fail(status, 3, "Failed to prepare the master file (details below).")

                        st.write("🔪 [Stage 4/5] Splitting Data per Country...")
                        folder, ok = split_data(source_path, transformation, {selected_cofog_code}, split_dir, lookup_path)
                        if not ok:
                            fail(status, 4, "Failed to split the data (details below).")

                        st.write("📊 [Stage 5/5] Running Tiered Aggregation...")
                        if not run_aggregation(master_path, folder, data_col, selected_sector, None, False, None, None):
                            fail(status, 5, "Aggregation failed (details below).")

                        # File-level provenance, as written by `cofog-panel run`
                        options = {"--cofog": selected_cofog_code, "--source-file": source_path.name,
                                   "--lookup-file": "(bundled country_codes.xlsx)" if lookup_path == PACKAGED_LOOKUP
                                   else lookup_path.name,
                                   "--filter-type": transformation, "--sector": selected_sector,
                                   "--start-year": int(start_year), "--end-year": int(end_year)}
                        source_sha256 = sha256_of(source_path)
                        record_run(master_path, source_path, source_sha256, "cofog-panel gui (browser interface)", options,
                                   [function_row(selected_cofog_code, transformation, selected_sector,
                                                 output_columns(data_col),
                                                 read_split_marker(folder).get("publication_date", ""))])
                        print(f"Source file {source_path.name}, SHA-256 {source_sha256} (sheet 'Provenance' of the master).")

                        status.update(label="🎉 Pipeline Completed Successfully!", state="complete")

                    # --- Result Display & Download ---
                    with st.expander("Run log (warnings and checks)"):
                        st.code(log.getvalue(), language=None)
                    st.success(f"✅ Processing complete! COFOG {selected_cofog_code} harmonised using '{selected_sector}' method.")

                    with open(master_path, "rb") as f:
                        st.download_button(
                            label="📥 Download Resulting Master File",
                            data=f,
                            file_name="COFOG_MASTER_SCHEMA.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            width="stretch"
                        )

                    # Preview (Optional)
                    try:
                        df_preview = pd.read_excel(master_path, sheet_name="MasterData")
                        st.subheader("👀 Preview (first 10 rows with a value)")
                        st.dataframe(df_preview[df_preview[data_col].notna()].head(10), width="stretch")
                    except Exception:
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


if __name__ == "__main__":
    main()
