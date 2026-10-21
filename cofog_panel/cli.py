"""
Command-line interface: `cofog-panel <command>`, one command per stage plus `run` for all five.

Options are validated before any file is read, so that a wrong --filter-type, --cofog or
--sector is reported at once rather than after the scan of the GFS extract.
"""
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

# Status lines use symbols that a legacy Windows console encoding cannot print
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

from cofog_panel import __version__  # noqa: E402
from cofog_panel.aggregate import DEFAULT_DATA_COL, DEFAULT_TIER_COL, run_aggregation  # noqa: E402
from cofog_panel.checks import verify_cofog_format, verify_country_format  # noqa: E402
from cofog_panel.etl import split_data  # noqa: E402
from cofog_panel.master_seed import (  # noqa: E402
    DEFAULT_END_YEAR, DEFAULT_FILE_NAME, DEFAULT_START_YEAR, prepare_master, seed_master,
)
from cofog_panel.options import OptionError, TRANSFORMATIONS, check_cofog, normalise_transformation  # noqa: E402

app = typer.Typer(help="COFOG-Panel: Tool for harmonizing IMF GFS COFOG data into reproducible panel datasets.")

DEFAULT_MASTER_FILE_NAME = DEFAULT_FILE_NAME
DEFAULT_OUTPUT_DIR = Path("./output")
DEFAULT_SPLIT_DIR = Path("./intermediate_splits")
DEFAULT_TRANSFORMATION = "Percent of GDP"

VALID_SECTORS = [
    "Budgetary central government",
    "Central government excluding social security",
    "Central government including social security",
    "Extrabudgetary central government",
    "General government",  # three-tier rule (T1/T2/T3)
    "Local Government",
    "Social security funds",
    "State Government",
]

# --- Shared option types ---
SourceFile = Annotated[Path, typer.Option("--source-file", help="Path to the raw COFOG Excel file.")]
LookupFile = Annotated[Path, typer.Option("--lookup-file", help="Path to the Country Code lookup file.")]
Cofog = Annotated[str, typer.Option(
    "--cofog", help="COFOG code (e.g. '05', '07.3') or exact COFOG label (e.g. 'Environmental protection').")]
FilterType = Annotated[str, typer.Option(
    "--filter-type", help=f"Transformation type, letter case ignored: {', '.join(TRANSFORMATIONS)}.")]
Sector = Annotated[str, typer.Option(
    "--sector", help="Aggregation method: 'General government' (three-tier), "
                     "'Central government including social security', or a single sector name.")]
TierCol = Annotated[str, typer.Option("--tier-col", help="Column recording the tier used for each value.")]
SectorsCol = Annotated[Optional[str], typer.Option(
    "--sectors-col", help="Column recording the contributing sectors. Default: SOURCE_SECTORS_<suffix of --data-col> "
                          "(SOURCE_SECTORS for the default DATA_NEW).")]
CompleteCol = Annotated[Optional[str], typer.Option(
    "--complete-col", help="Column recording completeness (Y/N). Default: SOURCE_COMPLETE_<suffix of --data-col> "
                           "(SOURCE_COMPLETE for the default DATA_NEW).")]
ZeroAsMissing = Annotated[bool, typer.Option(
    "--zero-as-missing", help="Treat reported zeros as not reported, in every sector "
                              "(zeros often mean 'not separately identified').")]
StartYear = Annotated[int, typer.Option("--start-year", help="First year of the panel.")]
EndYear = Annotated[int, typer.Option("--end-year", help="Last year of the panel.")]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"cofog-panel {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[bool, typer.Option("--version", callback=_version_callback, is_eager=True,
                                          help="Show the version and exit.")] = False,
) -> None:
    """COFOG-Panel: harmonise IMF GFS COFOG data into reproducible panel datasets."""


def _fail(message: str) -> None:
    typer.echo(f"❌ {message}", err=True)
    raise typer.Exit(code=2)


def _valid_sector(sector: str) -> str:
    if sector not in VALID_SECTORS:
        typer.echo(f"❌ Invalid --sector '{sector}'. Choose one of: {VALID_SECTORS}", err=True)
        raise typer.Exit(code=1)
    return sector


def _valid_transformation(value: str) -> str:
    try:
        return normalise_transformation(value)
    except OptionError as exc:
        _fail(str(exc))


def _valid_cofog(value: str, source_file: Path) -> str:
    try:
        return check_cofog(value, source_file)
    except OptionError as exc:
        _fail(str(exc))


# --- Stages 1 and 2 ---

@app.command("check-format")
def check_format(source_file: SourceFile) -> None:
    """Verifies the header structure of the raw COFOG input file."""
    if not verify_cofog_format(source_file)[0]:
        raise typer.Exit(code=1)


@app.command("check-country-format")
def check_country_format(lookup_file: LookupFile) -> None:
    """Verifies the structure of the required Country Code mapping file."""
    if not verify_country_format(lookup_file)[0]:
        raise typer.Exit(code=1)


# --- Stage 3 ---

@app.command("seed-master")
def seed(
    lookup_file: LookupFile,
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Directory to save the Master XLSX file.")] = DEFAULT_OUTPUT_DIR,
    output_name: Annotated[str, typer.Option("--output-name", help="Name for the new Master XLSX file.")] = DEFAULT_MASTER_FILE_NAME,
    start_year: StartYear = DEFAULT_START_YEAR,
    end_year: EndYear = DEFAULT_END_YEAR,
) -> None:
    """Creates the empty Master XLSX panel (SortKey, Country, Year). An existing file is replaced."""
    path, ok = seed_master(lookup_file, output_dir, output_name, start_year, end_year)
    if not ok:
        raise typer.Exit(code=1)
    typer.echo(f"::MASTER_PATH::{path}")


# --- Stage 4 ---

@app.command("split")
def split(
    source_file: SourceFile,
    cofog: Cofog,
    filter_type: FilterType = DEFAULT_TRANSFORMATION,
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Directory to save intermediate country XLSX files.")] = DEFAULT_SPLIT_DIR,
) -> None:
    """Filters raw data and saves one XLSX file per country."""
    transformation = _valid_transformation(filter_type)
    selector = _valid_cofog(cofog, source_file)
    path, ok = split_data(source_file, transformation, {selector}, output_dir)
    if not ok:
        raise typer.Exit(code=1)
    typer.echo(f"::SPLIT_PATH::{path}")


# --- Stage 5 ---

@app.command("aggregate")
def aggregate(
    master_file: Annotated[Path, typer.Option("--master-file", help="Path to the Master XLSX file to update.")],
    folder_path: Annotated[Path, typer.Option("--folder-path", help="Local path where intermediate country XLSX files are stored.")],
    data_col: Annotated[str, typer.Option("--data-col", help="Target column name in Master file for final data.")] = DEFAULT_DATA_COL,
    tier_col: TierCol = DEFAULT_TIER_COL,
    sectors_col: SectorsCol = None,
    complete_col: CompleteCol = None,
    sector: Sector = "General government",
    zero_as_missing: ZeroAsMissing = False,
) -> None:
    """Applies the tiered selection rule and writes values and provenance to the Master file."""
    _valid_sector(sector)
    if not run_aggregation(master_file, folder_path, data_col, sector, tier_col, zero_as_missing,
                           sectors_col, complete_col):
        raise typer.Exit(code=1)
    typer.echo("::AGGREGATE_SUCCESS::COMPLETED")


# --- All stages ---

@app.command("run")
def run(
    source_file: SourceFile,
    lookup_file: LookupFile,
    cofog: Annotated[str, typer.Option("--cofog", help="COFOG code (e.g. '05') or exact COFOG label.")],
    filter_type: FilterType = DEFAULT_TRANSFORMATION,
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Directory for Master XLSX.")] = DEFAULT_OUTPUT_DIR,
    split_dir: Annotated[Path, typer.Option("--split-dir", help="Directory to save intermediate country XLSX splits.")] = DEFAULT_SPLIT_DIR,
    data_col: Annotated[str, typer.Option("--data-col", "--output-cols", help="Target data column name (e.g., DATA_ENV).")] = DEFAULT_DATA_COL,
    tier_col: TierCol = DEFAULT_TIER_COL,
    sectors_col: SectorsCol = None,
    complete_col: CompleteCol = None,
    sector: Annotated[str, typer.Option("--sector", help="Aggregation method used in the final step.")] = "General government",
    zero_as_missing: ZeroAsMissing = False,
    start_year: StartYear = DEFAULT_START_YEAR,
    end_year: EndYear = DEFAULT_END_YEAR,
    overwrite_master: Annotated[bool, typer.Option(
        "--overwrite-master", help="Rebuild the master from the lookup file, deleting its indicator columns. "
                                   "By default an existing master is kept and the new indicator is added to it.")] = False,
) -> None:
    """Runs the full pipeline sequentially (stages 1 -> 5) using local files."""
    _valid_sector(sector)
    transformation = _valid_transformation(filter_type)
    selector = _valid_cofog(cofog, source_file)

    typer.echo("--- Starting FULL LOCAL COFOG Pipeline Orchestration ---")
    typer.echo("\n[Stage 1/5] Checking COFOG Format...")
    if not verify_cofog_format(source_file)[0]:
        raise typer.Exit(code=1)
    typer.echo("\n[Stage 2/5] Checking Country Code Format...")
    if not verify_country_format(lookup_file)[0]:
        raise typer.Exit(code=1)

    typer.echo("\n[Stage 3/5] Preparing Master XLSX...")
    master_path, ok = prepare_master(lookup_file, output_dir, DEFAULT_MASTER_FILE_NAME, start_year, end_year,
                                     overwrite=overwrite_master)
    if not ok:
        raise typer.Exit(code=1)
    typer.echo(f"Master Path Established: {master_path}")

    typer.echo("\n[Stage 4/5] Splitting Data per Country (to Local XLSX)...")
    folder, ok = split_data(source_file, transformation, {selector}, split_dir)
    if not ok:
        raise typer.Exit(code=1)

    typer.echo("\n[Stage 5/5] Running Tiered Aggregation...")
    if not run_aggregation(master_path, folder, data_col, sector, tier_col, zero_as_missing,
                           sectors_col, complete_col):
        raise typer.Exit(code=1)
    typer.echo("\n🎉 FULL PIPELINE COMPLETED SUCCESSFULLY! 🎉")
    typer.echo(f"Final Master XLSX available at: {master_path}")


if __name__ == "__main__":
    app()
