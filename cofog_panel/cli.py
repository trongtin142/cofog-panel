"""
Command-line interface: `cofog-panel <command>`, one command per stage plus `run` for all five
and two look-up commands (`list-cofog`, `list-sectors`).

Options are validated before any file is read. Every error prints one line on what went wrong
and one line on how to fix it; tracebacks are shown only with `cofog-panel --debug <command>`.
Exit codes: 0 success, 1 data or option error, 2 command-line usage error.
"""
import functools
import sys
from pathlib import Path
from typing import Annotated, Optional

import click
import typer

# Status lines use symbols that a legacy Windows console encoding cannot print
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

from cofog_panel import __version__  # noqa: E402
from cofog_panel.aggregate import DEFAULT_DATA_COL, DEFAULT_TIER_COL, DIRECT_SECTORS, run_aggregation  # noqa: E402
from cofog_panel.checks import verify_cofog_format, verify_country_format  # noqa: E402
from cofog_panel.etl import list_cofog, read_split_marker, split_data  # noqa: E402
from cofog_panel.master_seed import (  # noqa: E402
    DEFAULT_END_YEAR, DEFAULT_FILE_NAME, DEFAULT_START_YEAR, PACKAGED_LOOKUP, prepare_master, seed_master,
)
from cofog_panel.messages import DOWNLOAD_HINT, print_error  # noqa: E402
from cofog_panel.options import (  # noqa: E402
    COFOG_LABELS, OptionError, TRANSFORMATIONS, check_cofog, data_column_for, normalise_transformation,
)

app = typer.Typer(help="COFOG-Panel: Tool for harmonizing IMF GFS COFOG data into reproducible panel datasets.",
                  pretty_exceptions_enable=False)

DEFAULT_MASTER_FILE_NAME = DEFAULT_FILE_NAME
DEFAULT_SOURCE_FILE = Path("data/gfs_raw_data.xlsx")
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
SECTOR_METHODS = {
    "General government": "three-tier rule: T1 GG, T2 CGSS + state + local, T3 central components + SSF + state + local",
    "Central government including social security": "C1 CGSS, C2 central core + social security funds",
}

_state = {"debug": False}

# --- Shared option types ---
SourceFile = Annotated[Path, typer.Option(
    "--source-file", help="Path to the raw COFOG Excel file (IMF.STA:GFS_COFOG download).")]
LookupFile = Annotated[Path, typer.Option(
    "--lookup-file", help="Country lookup file. Default: the lookup bundled with the package.")]
Cofog = Annotated[str, typer.Option(
    "--cofog", help="COFOG code (e.g. '05', '07.3') or exact COFOG label (e.g. 'Environmental protection'). "
                    "'cofog-panel list-cofog' lists them.")]
FilterType = Annotated[str, typer.Option(
    "--filter-type", help=f"Transformation type, letter case ignored: {', '.join(TRANSFORMATIONS)}.")]
Sector = Annotated[str, typer.Option(
    "--sector", help="Aggregation method: 'General government' (three-tier), "
                     "'Central government including social security', or a single sector name "
                     "('cofog-panel list-sectors').")]
DataCol = Annotated[Optional[str], typer.Option(
    "--data-col", "--output-cols", help="Data column in the master. Default: DATA_<COFOG code>, "
                                        "e.g. DATA_05 or DATA_07_3.")]
TierCol = Annotated[str, typer.Option("--tier-col", help="Column recording the tier used for each value.")]
SectorsCol = Annotated[Optional[str], typer.Option(
    "--sectors-col", help="Column recording the contributing sectors. Default: SOURCE_SECTORS_<suffix of --data-col> "
                          "(SOURCE_SECTORS for DATA_NEW).")]
CompleteCol = Annotated[Optional[str], typer.Option(
    "--complete-col", help="Column recording completeness (Y/N). Default: SOURCE_COMPLETE_<suffix of --data-col> "
                           "(SOURCE_COMPLETE for DATA_NEW).")]
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
    debug: Annotated[bool, typer.Option("--debug", help="Show the full traceback of unexpected errors.")] = False,
) -> None:
    """COFOG-Panel: harmonise IMF GFS COFOG data into reproducible panel datasets."""
    _state["debug"] = debug


def _stop(what: str, hint: str) -> None:
    """Report a data or option error and end the command with exit code 1."""
    print_error(what, hint)
    raise typer.Exit(code=1)


def _guarded(command):
    """Turn unexpected exceptions into the two-line error format (exit code 1), unless --debug is set."""
    @functools.wraps(command)
    def wrapper(*args, **kwargs):
        try:
            return command(*args, **kwargs)
        except (click.exceptions.Exit, click.exceptions.Abort, click.ClickException):
            raise
        except OptionError as exc:
            _stop(exc.what, exc.hint)
        except Exception as exc:
            if _state["debug"]:
                raise
            _stop(f"Unexpected {type(exc).__name__}: {exc}",
                  "Run the command again as 'cofog-panel --debug ...' to see the full traceback.")
    return wrapper


def _valid_sector(sector: str) -> str:
    if sector not in VALID_SECTORS:
        _stop(f"Invalid --sector '{sector}'. Choose one of: {VALID_SECTORS}",
              "Run 'cofog-panel list-sectors' for the accepted values (letter case matters).")
    return sector


def _require_source(source_file: Path) -> None:
    if not source_file.exists():
        _stop(f"Source file not found: {source_file}", DOWNLOAD_HINT)


# --- Look-up commands ---

@app.command("list-sectors")
@_guarded
def list_sectors() -> None:
    """Lists the accepted values of --sector and --filter-type."""
    typer.echo("--sector (aggregation method):")
    for name in VALID_SECTORS:
        method = SECTOR_METHODS.get(name, "this sector only (tier D)" if name in DIRECT_SECTORS else "")
        typer.echo(f"  {name:<46} {method}")
    typer.echo("\n--filter-type (letter case ignored; shares of total outlays are never summed):")
    for name in TRANSFORMATIONS:
        typer.echo(f"  {name}")


@app.command("list-cofog")
@_guarded
def list_cofog_command(source_file: SourceFile = DEFAULT_SOURCE_FILE) -> None:
    """Lists the COFOG codes and labels in the extract, with the number of countries (reads the whole file)."""
    _require_source(source_file)
    typer.echo(f"Reading {source_file.name} (about a minute for the full IMF extract)...")
    try:
        functions = list_cofog(source_file)
    except KeyError as exc:
        _stop(f"The extract has no column {exc.args[0]}.",
              "Use the Excel download of IMF.STA:GFS_COFOG without changes; 'cofog-panel check-format' checks it.")
    typer.echo(f"\n{'Code':<7} {'Countries':>9}  Label")
    for code, label, n_countries in functions:
        indent = "" if "." not in code else "  "
        typer.echo(f"{code:<7} {n_countries:>9}  {indent}{label or COFOG_LABELS.get(code, '')}")
    typer.echo(f"\n{len(functions)} COFOG functions. Use the code or the exact label with --cofog.")


# --- Stages 1 and 2 ---

@app.command("check-format")
@_guarded
def check_format(source_file: SourceFile = DEFAULT_SOURCE_FILE) -> None:
    """Verifies the header structure of the raw COFOG input file."""
    if not verify_cofog_format(source_file)[0]:
        raise typer.Exit(code=1)


@app.command("check-country-format")
@_guarded
def check_country_format(lookup_file: LookupFile = PACKAGED_LOOKUP) -> None:
    """Verifies the structure of the Country Code mapping file."""
    if not verify_country_format(lookup_file)[0]:
        raise typer.Exit(code=1)


# --- Stage 3 ---

@app.command("seed-master")
@_guarded
def seed(
    lookup_file: LookupFile = PACKAGED_LOOKUP,
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
@_guarded
def split(
    cofog: Cofog,
    source_file: SourceFile = DEFAULT_SOURCE_FILE,
    filter_type: FilterType = DEFAULT_TRANSFORMATION,
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Directory to save intermediate country XLSX files.")] = DEFAULT_SPLIT_DIR,
) -> None:
    """Filters raw data and saves one XLSX file per country."""
    transformation = normalise_transformation(filter_type)
    selector = check_cofog(cofog, source_file)
    _require_source(source_file)
    path, ok = split_data(source_file, transformation, {selector}, output_dir)
    if not ok:
        raise typer.Exit(code=1)
    typer.echo(f"::SPLIT_PATH::{path}")


# --- Stage 5 ---

@app.command("aggregate")
@_guarded
def aggregate(
    master_file: Annotated[Path, typer.Option("--master-file", help="Path to the Master XLSX file to update.")],
    folder_path: Annotated[Path, typer.Option("--folder-path", help="Local path where intermediate country XLSX files are stored.")],
    data_col: Annotated[Optional[str], typer.Option(
        "--data-col", help="Data column in the master. Default: DATA_<COFOG code> of the split in --folder-path "
                           "(DATA_NEW if it is not recorded).")] = None,
    tier_col: TierCol = DEFAULT_TIER_COL,
    sectors_col: SectorsCol = None,
    complete_col: CompleteCol = None,
    sector: Sector = "General government",
    zero_as_missing: ZeroAsMissing = False,
) -> None:
    """Applies the tiered selection rule and writes values and provenance to the Master file."""
    _valid_sector(sector)
    if data_col is None:
        recorded = read_split_marker(folder_path).get("cofog", "")
        data_col = data_column_for(recorded) if recorded and "," not in recorded else DEFAULT_DATA_COL
    if not run_aggregation(master_file, folder_path, data_col, sector, tier_col, zero_as_missing,
                           sectors_col, complete_col):
        raise typer.Exit(code=1)
    typer.echo("::AGGREGATE_SUCCESS::COMPLETED")


# --- All stages ---

@app.command("run")
@_guarded
def run(
    cofog: Annotated[str, typer.Option("--cofog", help="COFOG code (e.g. '05') or exact COFOG label "
                                                       "('cofog-panel list-cofog' lists them).")],
    source_file: SourceFile = DEFAULT_SOURCE_FILE,
    lookup_file: LookupFile = PACKAGED_LOOKUP,
    filter_type: FilterType = DEFAULT_TRANSFORMATION,
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Directory for Master XLSX.")] = DEFAULT_OUTPUT_DIR,
    split_dir: Annotated[Path, typer.Option("--split-dir", help="Directory to save intermediate country XLSX splits.")] = DEFAULT_SPLIT_DIR,
    data_col: DataCol = None,
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
    transformation = normalise_transformation(filter_type)
    selector = check_cofog(cofog, source_file)
    data_col = data_col or data_column_for(selector)
    _require_source(source_file)

    typer.echo("--- Starting FULL LOCAL COFOG Pipeline Orchestration ---")
    typer.echo(f"COFOG {selector}, {transformation}, method '{sector}', data column {data_col}")
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
