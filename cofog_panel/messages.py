"""
Uniform error messages: one line on what went wrong, one line on how to fix it.

The command-line tool maps errors to exit codes: 0 success, 1 data or option error,
2 command-line usage error (unknown option, missing value), as raised by Typer itself.
"""

DOWNLOAD_HINT = ("Download IMF.STA:GFS_COFOG from https://data.imf.org (README, Quickstart) and save it as "
                 "data/gfs_raw_data.csv (or .xlsx), or give its path with --source-file.")
LOCKED_FILE_HINT = "Close the file if it is open in Excel, check that the directory is writable, and run the command again."


def print_error(what: str, hint: str = "") -> None:
    """Print the two-line error format used throughout the package."""
    print(f"❌ Error: {what}")
    if hint:
        print(f"   Hint: {hint}")


def hint_for_write_error(exc: Exception) -> str:
    """Hint for a failure to write an output workbook."""
    if isinstance(exc, PermissionError):
        return LOCKED_FILE_HINT
    return "Check the output path and the free disk space, then run the command again."
