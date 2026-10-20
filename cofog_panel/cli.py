import sys
import typer
from pathlib import Path

# Status messages use symbols that a legacy Windows console encoding cannot print
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

from cofog_panel.checks import verify_cofog_format, verify_country_format
from cofog_panel.master_seed import seed_master, DEFAULT_START_YEAR, DEFAULT_END_YEAR
from cofog_panel import __version__
from cofog_panel.etl import split_data
from cofog_panel.aggregate import run_aggregation, DEFAULT_TIER_COL


app = typer.Typer(help="COFOG-Panel: Tool for harmonizing IMF GFS COFOG data into reproducible panel datasets.")


DEFAULT_MASTER_FILE_NAME = "COFOG_MASTER_SCHEMA.xlsx"
DEFAULT_OUTPUT_COLS = "DATA_NEW"
DEFAULT_OUTPUT_DIR = Path("./output")
DEFAULT_SPLIT_DIR = Path("./intermediate_splits")
DEFAULT_TRANSFORMATION = "Percent of GDP"  # Set a reasonable default value

VALID_SECTORS = [
    "Budgetary central government",
    "Central government excluding social security",
    "Central government including social security",
    "Extrabudgetary central government",
    "General government",  # Three-tier method (T1/T2/T3)
    "Local Government",
    "Social security funds",
    "State Government"
]


def _version_callback(value: bool):
    if value:
        typer.echo(f"cofog-panel {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True,
                                 help="Show the version and exit."),
):
    """COFOG-Panel: harmonise IMF GFS COFOG data into reproducible panel datasets."""


def _check_sector(sector: str) -> None:
    if sector not in VALID_SECTORS:
        typer.echo(f"❌ Invalid --sector '{sector}'. Choose one of: {VALID_SECTORS}", err=True)
        raise typer.Exit(code=1)

# ==============================================================================
# 1. CHECK FORMATS
# ==============================================================================

@app.command("check-format")
def check_cofog(
    input_file: Path = typer.Option(..., "--source-file", help="Path to the raw COFOG Excel file.")
):
    """Verifies the header structure of the raw COFOG input file."""
    if not verify_cofog_format(input_file)[0]:
        raise typer.Exit(code=1)

@app.command("check-country-format")
def check_country(
    lookup_file: Path = typer.Option(..., "--lookup-file", help="Path to the Country Code lookup file.")
):
    """Verifies the structure of the required Country Code mapping file."""
    if not verify_country_format(lookup_file)[0]:
        raise typer.Exit(code=1)


# ==============================================================================
# 2. SEED MASTER
# ==============================================================================

@app.command("seed-master")
def seed(
    lookup_file: Path = typer.Option(..., "--lookup-file", help="Verified Country Code file path."),
    output_dir: Path = typer.Option(DEFAULT_OUTPUT_DIR, "--output-dir", help="Directory to save the Master XLSX file."),
    output_name: str = typer.Option(DEFAULT_MASTER_FILE_NAME, "--output-name", help="Name for the new Master XLSX file."),
    start_year: int = typer.Option(DEFAULT_START_YEAR, "--start-year", help="First year of the panel."),
    end_year: int = typer.Option(DEFAULT_END_YEAR, "--end-year", help="Last year of the panel."),
):
    """Creates the empty Master XLSX panel (SortKey, Country, Year)."""

    output_dir.mkdir(parents=True, exist_ok=True)

    master_path, success = seed_master(lookup_file, output_dir, output_name, start_year, end_year)

    if success:
        typer.echo(f"::MASTER_PATH::{master_path}")
    else:
        raise typer.Exit(code=1)

# ==============================================================================
# 3. SPLIT DATA
# ==============================================================================
@app.command("split")
def split(
    source_file: Path = typer.Option(..., "--source-file", help="Path to the raw COFOG source file."),
    filter_type: str = typer.Option(DEFAULT_TRANSFORMATION, "--filter-type", help="Transformation type (Percent of GDP, Domestic currency, Percent of total outlays)."),
    cofog: str = typer.Option(..., "--cofog", help="COFOG code (e.g. '05', '07.3') or exact COFOG label (e.g. 'Environmental protection')."),
    output_dir: Path = typer.Option(DEFAULT_SPLIT_DIR, "--output-dir", help="Directory to save intermediate country XLSX files.")
):
    """Filters raw data and saves one XLSX file per country."""

    folder_path, success = split_data(
        source_file,
        filter_type,
        {cofog},
        output_dir
    )

    if success:
        typer.echo(f"::SPLIT_PATH::{folder_path}")
    else:
        raise typer.Exit(code=1)

# ==============================================================================
# 4. AGGREGATE
# ==============================================================================
@app.command("aggregate")
def aggregate(
    master_file_path: Path = typer.Option(..., "--master-file", help="Path to the Master XLSX file to update."),
    folder_path: Path = typer.Option(..., "--folder-path", help="Local path where intermediate country XLSX files are stored."),
    data_col: str = typer.Option(DEFAULT_OUTPUT_COLS, "--data-col", help="Target column name in Master file for final data."),
    tier_col: str = typer.Option(DEFAULT_TIER_COL, "--tier-col", help="Column recording the tier used for each value."),
    sector: str = typer.Option(
        "General government",
        "--sector",
        help="Aggregation method: 'General government' (three-tier), 'Central government including social security', or a single sector name."
    ),
    zero_as_missing: bool = typer.Option(False, "--zero-as-missing", help="Treat reported zeros as not reported, in every sector (zeros often mean 'not separately identified')."),
):
    """Applies the tiered selection rule and writes values and tiers to the Master file."""
    _check_sector(sector)

    success = run_aggregation(
        master_file_path,
        folder_path,
        data_col,
        sector,
        tier_col,
        zero_as_missing,
    )
    if success:
        typer.echo("::AGGREGATE_SUCCESS::COMPLETED")
    else:
        raise typer.Exit(code=1)


# ==============================================================================
# 5. RUN ORCHESTRATOR
# ==============================================================================
@app.command("run")
def run_pipeline(
    source_file: Path = typer.Option(..., "--source-file", help="Path to the raw COFOG source file."),
    lookup_file: Path = typer.Option(..., "--lookup-file", help="Path to the Country Code lookup file."),
    cofog: str = typer.Option(..., "--cofog", help="COFOG code (e.g. '05') or exact COFOG label."),
    filter_type: str = typer.Option(DEFAULT_TRANSFORMATION, "--filter-type", help="Transformation type (e.g., Percent of GDP, Domestic currency)."),
    output_dir: Path = typer.Option(DEFAULT_OUTPUT_DIR, "--output-dir", help="Directory for Master XLSX."),
    split_dir: Path = typer.Option(DEFAULT_SPLIT_DIR, "--split-dir", help="Directory to save intermediate country XLSX splits."),
    data_col: str = typer.Option(DEFAULT_OUTPUT_COLS, "--data-col", "--output-cols", help="Target data column name (e.g., DATA_ENV)."),
    tier_col: str = typer.Option(DEFAULT_TIER_COL, "--tier-col", help="Column recording the tier used for each value."),
    sector: str = typer.Option(
        "General government",
        "--sector",
        help="Aggregation method used in the final step."
    ),
    zero_as_missing: bool = typer.Option(False, "--zero-as-missing", help="Treat reported zeros as not reported, in every sector (zeros often mean 'not separately identified')."),
    start_year: int = typer.Option(DEFAULT_START_YEAR, "--start-year", help="First year of the panel."),
    end_year: int = typer.Option(DEFAULT_END_YEAR, "--end-year", help="Last year of the panel."),
):
    """Runs the full pipeline sequentially (stages 1 -> 5) using local files."""
    _check_sector(sector)

    typer.echo("--- Starting FULL LOCAL COFOG Pipeline Orchestration ---")

    typer.echo("\n[Stage 1/5] Checking COFOG Format...")
    if not verify_cofog_format(source_file)[0]: raise typer.Exit(code=1)

    typer.echo("\n[Stage 2/5] Checking Country Code Format...")
    if not verify_country_format(lookup_file)[0]: raise typer.Exit(code=1)

    typer.echo("\n[Stage 3/5] Seeding Master XLSX...")
    master_path, success = seed_master(lookup_file, output_dir, DEFAULT_MASTER_FILE_NAME, start_year, end_year)
    if not success: raise typer.Exit(code=1)

    typer.echo(f"Master Path Established: {master_path}")

    typer.echo("\n[Stage 4/5] Splitting Data per Country (to Local XLSX)...")
    folder_path, success = split_data(
        source_file, filter_type, {cofog}, split_dir
    )
    if not success: raise typer.Exit(code=1)

    typer.echo("\n[Stage 5/5] Running Tiered Aggregation...")
    success = run_aggregation(
        master_path,
        folder_path,
        data_col,
        sector,
        tier_col,
        zero_as_missing,
    )

    if success:
        typer.echo("\n🎉 FULL PIPELINE COMPLETED SUCCESSFULLY! 🎉")
        typer.echo(f"Final Master XLSX available at: {master_path}")
    else:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
