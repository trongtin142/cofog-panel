"""
Command-line interface: `cofog-panel <command>`, one command per stage plus `run` for all five,
two look-up commands (`list-cofog`, `list-sectors`) and `gui` for the browser interface.

Options are validated before any file is read. Every error prints one line on what went wrong
and one line on how to fix it; tracebacks are shown only with `cofog-panel --debug <command>`.
Exit codes: 0 success, 1 data or option error, 2 command-line usage error.
"""
import functools
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated, List, Mapping, Optional

import typer

# Status lines use symbols that a legacy Windows console encoding cannot print
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

from cofog_panel import __version__  # noqa: E402
from cofog_panel.aggregate import DEFAULT_DATA_COL, DIRECT_SECTORS, run_aggregation  # noqa: E402
from cofog_panel.checks import verify_cofog_format, verify_country_format  # noqa: E402
from cofog_panel.etl import list_cofog, read_split_marker, split_data  # noqa: E402
from cofog_panel.master_seed import (  # noqa: E402
    DEFAULT_END_YEAR, DEFAULT_FILE_NAME, DEFAULT_START_YEAR, PACKAGED_LOOKUP, prepare_master, seed_master,
)
from cofog_panel.messages import DOWNLOAD_HINT, hint_for_write_error, print_error  # noqa: E402
from cofog_panel.source import default_source  # noqa: E402
from cofog_panel.options import (  # noqa: E402
    COFOG_LABELS, OptionError, TRANSFORMATIONS, VALID_SECTORS, check_cofog, data_column_for, normalise_sector,
    normalise_transformation,
)
from cofog_panel.provenance import (  # noqa: E402
    PROVENANCE_SHEET, format_options, function_row, output_columns, record_run, sha256_of,
)

app = typer.Typer(help="COFOG-Panel: Tool for harmonizing IMF GFS COFOG data into reproducible panel datasets.",
                  pretty_exceptions_enable=False)

DEFAULT_MASTER_FILE_NAME = DEFAULT_FILE_NAME
DEFAULT_OUTPUT_DIR = Path("./output")
DEFAULT_SPLIT_DIR = Path("./intermediate_splits")
DEFAULT_TRANSFORMATION = "Percent of GDP"
# The browser interface, a Streamlit script inside the package (started by `cofog-panel gui`)
GUI_SCRIPT = Path(__file__).resolve().parent / "gui.py"
GUI_MAX_UPLOAD_MB = 1000  # the CSV download is about 530 MB; Streamlit's default limit is 200 MB

# VALID_SECTORS (options.py): single sectors, plus the two aggregation methods ("General government" is
# the three-tier rule T1/T2/T3)
SECTOR_METHODS = {
    "General government": "three-tier rule: T1 GG, T2 CGSS + state + local, T3 central components + SSF + state + local",
    "Central government including social security": "C1 CGSS, C2 central core + social security funds",
}

_state = {"debug": False}

# Exceptions that carry Typer's own control flow (exit codes, usage errors) and must pass through
# _guarded unchanged. Older Typer versions raise click's classes; Typer 0.27 and later bundle their own
# copy of click (base class TyperException). Both are found from the class hierarchy of typer.BadParameter.
_TYPER_EXCEPTIONS = (typer.Exit, typer.Abort) + tuple(
    cls for cls in typer.BadParameter.__mro__ if cls.__name__ in ("ClickException", "TyperException"))

# --- Shared option types ---
SourceFile = Annotated[Optional[Path], typer.Option(
    "--source-file", help="IMF.STA:GFS_COFOG download, CSV or Excel. "
                          "Default: data/gfs_raw_data.xlsx, or data/gfs_raw_data.csv if there is no .xlsx.")]
LookupFile = Annotated[Path, typer.Option(
    "--lookup-file", help="Country lookup file. Default: the lookup bundled with the package.")]
Cofog = Annotated[str, typer.Option(
    "--cofog", help="COFOG code (e.g. '05', '07.3') or COFOG label, letter case ignored "
                    "(e.g. 'Environmental protection'). 'cofog-panel list-cofog' lists them.")]
FilterType = Annotated[str, typer.Option(
    "--filter-type", help=f"Transformation type, letter case ignored: {', '.join(TRANSFORMATIONS)}.")]
Sector = Annotated[str, typer.Option(
    "--sector", help="Aggregation method: 'General government' (three-tier), "
                     "'Central government including social security', or a single sector name "
                     "('cofog-panel list-sectors').")]
DataCol = Annotated[Optional[str], typer.Option(
    "--data-col", "--output-cols", help="Data column in the master. Default: DATA_<COFOG code>, "
                                        "e.g. DATA_05 or DATA_07_3.")]
TierCol = Annotated[Optional[str], typer.Option(
    "--tier-col", help="Column recording the tier of each value. Default: SOURCE_TIER_<suffix of --data-col> "
                       "(SOURCE_TIER for DATA_NEW).")]
SectorsCol = Annotated[Optional[str], typer.Option(
    "--sectors-col", help="Column recording the contributing sectors. Default: SOURCE_SECTORS_<suffix of --data-col> "
                          "(SOURCE_SECTORS for DATA_NEW).")]
CompleteCol = Annotated[Optional[str], typer.Option(
    "--complete-col", help="Column recording completeness (Y/N). Default: SOURCE_COMPLETE_<suffix of --data-col> "
                           "(SOURCE_COMPLETE for DATA_NEW).")]
ZeroAsMissing = Annotated[bool, typer.Option(
    "--zero-as-missing", help="Treat reported zeros as not reported, in every sector "
                              "(zeros often mean 'not separately identified').")]
CheckRanges = Annotated[bool, typer.Option(
    "--check-ranges", help="List selected values that are negative, or above 100 for percentages (values are kept).")]
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
        except _TYPER_EXCEPTIONS:
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
    """Returns the --sector value as spelt in VALID_SECTORS, letter case ignored, as for --filter-type."""
    try:
        return normalise_sector(sector)
    except OptionError as exc:
        _stop(exc.what, exc.hint)


def _require_source(source_file: Path) -> None:
    if not source_file.exists():
        _stop(f"Source file not found: {source_file}", DOWNLOAD_HINT)


def _quote(arg: str) -> str:
    """An argument as it would be typed: in double quotes when it is empty or holds a space or quote."""
    return f'"{arg}"' if not arg or any(c in arg for c in " \t'\"&|<>;") else arg


def _command_line(command: str, options: Mapping[str, object]) -> str:
    """
    The command as typed when the process is the cofog-panel program, for the Provenance sheet;
    otherwise (tests, other callers) the command with every option value.
    """
    if Path(sys.argv[0]).stem.lower() in ("cofog-panel", "cofog_panel") and len(sys.argv) > 1:
        return " ".join(["cofog-panel", *(_quote(arg) for arg in sys.argv[1:])])
    return f"cofog-panel {command} {format_options(options)}"


# --- Look-up commands ---

@app.command("list-sectors")
@_guarded
def list_sectors() -> None:
    """Lists the accepted values of --sector and --filter-type."""
    typer.echo("--sector (aggregation method, letter case ignored):")
    for name in VALID_SECTORS:
        method = SECTOR_METHODS.get(name, "this sector only (tier D)" if name in DIRECT_SECTORS else "")
        typer.echo(f"  {name:<46} {method}")
    typer.echo("\n--filter-type (letter case ignored; shares of total outlays are never summed):")
    for name in TRANSFORMATIONS:
        typer.echo(f"  {name}")


@app.command("list-cofog")
@_guarded
def list_cofog_command(source_file: SourceFile = None) -> None:
    """
    Lists the COFOG codes and labels in the extract, with two counts of countries (reads the whole file).

    Countries: the countries with at least one value for the code, in any sector, transformation and year.
    Listed: the countries with a series for the code, with or without values.
    """
    source_file = source_file or default_source()
    _require_source(source_file)
    typer.echo(f"Reading {source_file.name} (seconds for a CSV file, about a minute for an Excel file)...")
    try:
        functions = list_cofog(source_file)
    except KeyError as exc:
        _stop(f"The extract has no column {exc.args[0]}.",
              "Use the Excel download of IMF.STA:GFS_COFOG without changes; 'cofog-panel check-format' checks it.")
    typer.echo(f"\n{'Code':<7} {'Countries':>9} {'Listed':>6}  Label")
    for code, label, n_with_values, n_listed in functions:
        indent = "" if "." not in code else "  "
        typer.echo(f"{code:<7} {n_with_values:>9} {n_listed:>6}  {indent}{label or COFOG_LABELS.get(code, '')}")
    typer.echo(f"\n{len(functions)} COFOG functions. Countries: countries with at least one value for the code. "
               "Listed: countries with a series for it, with or without values.")
    typer.echo("Use the code or the label (letter case ignored) with --cofog.")


# --- Stages 1 and 2 ---

@app.command("check-format")
@_guarded
def check_format(source_file: SourceFile = None) -> None:
    """Verifies the header structure of the raw COFOG input file."""
    if not verify_cofog_format(source_file or default_source())[0]:
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
    source_file: SourceFile = None,
    lookup_file: LookupFile = PACKAGED_LOOKUP,
    filter_type: FilterType = DEFAULT_TRANSFORMATION,
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Directory to save intermediate country CSV files.")] = DEFAULT_SPLIT_DIR,
) -> None:
    """Filters raw data and saves one CSV file per country."""
    source_file = source_file or default_source()
    transformation = normalise_transformation(filter_type)
    selector = check_cofog(cofog, source_file)
    _require_source(source_file)
    path, ok = split_data(source_file, transformation, {selector}, output_dir, lookup_file)
    if not ok:
        raise typer.Exit(code=1)
    typer.echo(f"::SPLIT_PATH::{path}")


# --- Stage 5 ---

def _warn_if_other_function(data_col: str, recorded: str) -> None:
    """Warn when a DATA_<code> column name names another COFOG function than the split recorded."""
    if not recorded or "," in recorded or not re.fullmatch(r"DATA_\d{2}(_\d+)?", data_col.upper()):
        return
    expected = data_column_for(recorded)
    if data_col.upper() != expected:
        print(f"⚠️ --data-col {data_col} does not match the COFOG function of the split ({recorded}, "
              f"which would be {expected}). Check that --folder-path and --data-col belong together.")

@app.command("aggregate")
@_guarded
def aggregate(
    master_file: Annotated[Path, typer.Option("--master-file", help="Path to the Master XLSX file to update.")],
    folder_path: Annotated[Path, typer.Option("--folder-path", help="Local path where intermediate country files are stored.")],
    data_col: Annotated[Optional[str], typer.Option(
        "--data-col", help="Data column in the master. Default: DATA_<COFOG code> of the split in --folder-path "
                           "(DATA_NEW if it is not recorded).")] = None,
    tier_col: TierCol = None,
    sectors_col: SectorsCol = None,
    complete_col: CompleteCol = None,
    sector: Sector = "General government",
    zero_as_missing: ZeroAsMissing = False,
    check_ranges: CheckRanges = False,
) -> None:
    """Applies the tiered selection rule and writes values and provenance to the Master file."""
    sector = _valid_sector(sector)
    if data_col is None:
        recorded = read_split_marker(folder_path).get("cofog", "")
        data_col = data_column_for(recorded) if recorded and "," not in recorded else DEFAULT_DATA_COL
    else:
        _warn_if_other_function(data_col, read_split_marker(folder_path).get("cofog", ""))
    if not run_aggregation(master_file, folder_path, data_col, sector, tier_col, zero_as_missing,
                           sectors_col, complete_col, check_ranges):
        raise typer.Exit(code=1)
    typer.echo("::AGGREGATE_SUCCESS::COMPLETED")


# --- All stages ---

@app.command("run")
@_guarded
def run(
    cofog: Annotated[List[str], typer.Option("--cofog", help="COFOG code (e.g. '05') or COFOG label, letter case "
                                                             "ignored ('cofog-panel list-cofog' lists them). Repeat the "
                                                             "option for several functions in one master.")],
    source_file: SourceFile = None,
    lookup_file: LookupFile = PACKAGED_LOOKUP,
    filter_type: FilterType = DEFAULT_TRANSFORMATION,
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Directory for Master XLSX.")] = DEFAULT_OUTPUT_DIR,
    split_dir: Annotated[Path, typer.Option("--split-dir", help="Directory to save intermediate country CSV splits.")] = DEFAULT_SPLIT_DIR,
    data_col: DataCol = None,
    tier_col: TierCol = None,
    sectors_col: SectorsCol = None,
    complete_col: CompleteCol = None,
    sector: Annotated[str, typer.Option("--sector", help="Aggregation method used in the final step.")] = "General government",
    zero_as_missing: ZeroAsMissing = False,
    check_ranges: CheckRanges = False,
    start_year: StartYear = DEFAULT_START_YEAR,
    end_year: EndYear = DEFAULT_END_YEAR,
    overwrite_master: Annotated[bool, typer.Option(
        "--overwrite-master", help="Rebuild the master from the lookup file, deleting its indicator columns. "
                                   "By default an existing master is kept and the new indicator is added to it.")] = False,
) -> None:
    """
    Runs the full pipeline sequentially (stages 1 -> 5) using local files.

    The master also gets a sheet 'Provenance' (version, source file and its SHA-256, PUBLICATION_DATE,
    command and options, time in UTC, columns created); its sheet MasterData is as in earlier versions.
    """
    source_file = source_file or default_source()
    sector = _valid_sector(sector)
    transformation = normalise_transformation(filter_type)
    selectors = [check_cofog(value, source_file) for value in cofog]
    several = len(selectors) > 1
    if several and any((data_col, tier_col, sectors_col, complete_col)):
        raise OptionError("--data-col, --tier-col, --sectors-col and --complete-col cannot be used with several --cofog values.",
                          "Each function gets DATA_<code> and its own provenance columns; run once per function to name them yourself.")
    data_cols = [data_col or data_column_for(selector) for selector in selectors]
    for column in set(data_cols):
        if data_cols.count(column) > 1:
            raise OptionError(f"Several --cofog values give the same data column {column}.", "Give each COFOG function once.")
    _require_source(source_file)
    options = {
        "--cofog": selectors, "--source-file": source_file,
        "--lookup-file": "(bundled country_codes.xlsx)" if lookup_file == PACKAGED_LOOKUP else lookup_file,
        "--filter-type": transformation, "--sector": sector, "--output-dir": output_dir, "--split-dir": split_dir,
        **{name: value for name, value in (("--data-col", data_col), ("--tier-col", tier_col),
                                           ("--sectors-col", sectors_col), ("--complete-col", complete_col)) if value},
        "--zero-as-missing": zero_as_missing, "--check-ranges": check_ranges,
        "--start-year": start_year, "--end-year": end_year, "--overwrite-master": overwrite_master,
    }

    typer.echo("--- Starting FULL LOCAL COFOG Pipeline Orchestration ---")
    source_sha256 = sha256_of(source_file)
    typer.echo(f"Source file {source_file.name}, SHA-256 {source_sha256}")
    for selector, column in zip(selectors, data_cols):
        typer.echo(f"COFOG {selector}, {transformation}, method '{sector}', data column {column}")
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

    functions = []
    for selector, column in zip(selectors, data_cols):
        # one split directory per function, so that each aggregation reads only its own country files
        target = split_dir / column.removeprefix("DATA_") if several else split_dir
        label = f" (COFOG {selector})" if several else ""
        typer.echo(f"\n[Stage 4/5] Splitting Data per Country (to Local CSV){label}...")
        folder, ok = split_data(source_file, transformation, {selector}, target, lookup_file)
        if not ok:
            raise typer.Exit(code=1)

        typer.echo(f"\n[Stage 5/5] Running Tiered Aggregation{label}...")
        if not run_aggregation(master_path, folder, column, sector, tier_col, zero_as_missing,
                               sectors_col, complete_col, check_ranges):
            raise typer.Exit(code=1)
        functions.append(function_row(selector, transformation, sector,
                                      output_columns(column, tier_col, sectors_col, complete_col),
                                      read_split_marker(folder).get("publication_date", "")))
    try:
        record_run(master_path, source_file, source_sha256, _command_line("run", options), options, functions)
    except Exception as exc:
        _stop(f"Cannot write the sheet '{PROVENANCE_SHEET}' of {master_path} ({exc}).", hint_for_write_error(exc))
    typer.echo(f"\nProvenance: {len(functions)} row(s) added to the sheet '{PROVENANCE_SHEET}' "
               f"(source SHA-256 {source_sha256}).")
    typer.echo("\n🎉 FULL PIPELINE COMPLETED SUCCESSFULLY! 🎉")
    typer.echo(f"Final Master XLSX available at: {master_path}")


# --- Browser interface ---

def _has_streamlit() -> bool:
    """True when the optional dependency of the browser interface (gui extra) is installed."""
    return importlib.util.find_spec("streamlit") is not None


@app.command("gui")
@_guarded
def gui(
    port: Annotated[Optional[int], typer.Option("--port", help="Port of the local server (Streamlit's default, 8501, if not given).")] = None,
    headless: Annotated[bool, typer.Option("--headless", help="Start the server without opening a browser window.")] = False,
) -> None:
    """Starts the browser interface in the default browser (needs the gui extra: pip install "cofog-panel[gui]")."""
    if not _has_streamlit():
        _stop("Streamlit is not installed, so the browser interface cannot start.",
              'Install the gui extra: pip install "cofog-panel[gui]" (in a clone: pip install -e ".[gui]").')
    command = [sys.executable, "-m", "streamlit", "run", str(GUI_SCRIPT),
               "--server.maxUploadSize", str(GUI_MAX_UPLOAD_MB)]
    if port is not None:
        command += ["--server.port", str(port)]
    if headless:
        command += ["--server.headless", "true"]
    typer.echo(f"Starting the browser interface ({GUI_SCRIPT.name}); press Ctrl+C here to stop it.")
    try:
        code = subprocess.call(command)
    except KeyboardInterrupt:
        code = 0
    raise typer.Exit(code=code)


if __name__ == "__main__":
    app()
