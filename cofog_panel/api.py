"""
Python interface: `build_panel` runs the five stages of `cofog-panel run` in a temporary folder and
returns the panel as a pandas DataFrame in tidy form, with the provenance of every value.
The values are those of the master that `run` writes for the same file and options.
"""
import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Optional, Sequence, Union

import pandas as pd

from .aggregate import MASTER_SHEET, run_aggregation
from .checks import verify_cofog_format, verify_country_format
from .etl import read_split_marker, split_data
from .master_seed import DEFAULT_END_YEAR, DEFAULT_FILE_NAME, DEFAULT_START_YEAR, PACKAGED_LOOKUP, seed_master
from .options import OptionError, check_cofog, data_column_for, normalise_sector, normalise_transformation
from .provenance import function_row, output_columns, read_provenance, record_run, sha256_of

PathLike = Union[str, Path]
TIDY_COLUMNS = ["iso3", "country", "year", "cofog", "value", "tier", "sectors", "complete"]


class PipelineError(RuntimeError):
    """A stage of the pipeline failed; `log` holds the reports and errors the stages printed."""

    def __init__(self, message: str, log: str = ""):
        super().__init__(message)
        self.log = log


def build_panel(
    source: PathLike,
    cofog: Union[str, Sequence[str]],
    *,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int = DEFAULT_END_YEAR,
    zero_as_missing: bool = False,
    filter_type: str = "Percent of GDP",
    sector: str = "General government",
    lookup_file: Optional[PathLike] = None,
    keep_empty: bool = False,
    verbose: bool = False,
) -> pd.DataFrame:
    """
    Country-year panel of one or more COFOG functions from an IMF GFS COFOG download (CSV or Excel).

    The arguments mean what the options of `cofog-panel run` mean: `cofog` is a code ('05', '07.3') or
    a label, or a list of them; `filter_type` the transformation; `sector` the method ('General
    government' is the three-tier rule); `lookup_file` the country lookup (default: the bundled one).

    Returns one row per country, year and function with a value (every panel row with
    keep_empty=True), in the order of the master: columns iso3, country, year, cofog, value, tier,
    sectors, complete. `value` is the number written to the master; tier, sectors and complete are its
    provenance (T1/T2/T3/C1/C2/D, e.g. 'CGSS+LG', 'Y'/'N'). `df.attrs["provenance"]` holds the rows of
    the master's Provenance sheet (version, source SHA-256, PUBLICATION_DATE, options), as dicts.

    Raises FileNotFoundError for a missing source file, cofog_panel.options.OptionError (a ValueError)
    for an invalid option, and PipelineError (with the stage log) when a stage fails. The stage reports
    are printed only with verbose=True.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")
    values = [cofog] if isinstance(cofog, str) else list(cofog)
    if not values:
        raise OptionError("No COFOG function given.", "Give a code such as '05' or '07.3', or a list of them.")
    transformation = normalise_transformation(filter_type)
    method = normalise_sector(sector)
    selectors = [check_cofog(str(value), source) for value in values]
    columns = [data_column_for(selector) for selector in selectors]
    if len(set(columns)) < len(columns):
        raise OptionError("Several cofog values give the same function.", "Give each COFOG function once.")
    lookup = Path(lookup_file) if lookup_file is not None else PACKAGED_LOOKUP

    log = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="cofog_panel_") as tmp, redirect_stdout(sys.stdout if verbose else log):
        folder_root = Path(tmp)

        def stage(ok: bool, what: str) -> None:
            if not ok:
                raise PipelineError(f"{what} failed for {source.name}; see the log (PipelineError.log) "
                                    f"or call build_panel(..., verbose=True).", log.getvalue())

        stage(verify_cofog_format(source)[0], "The format check of the extract")
        stage(verify_country_format(lookup)[0], "The check of the country lookup")
        master_path, ok = seed_master(lookup, folder_root, DEFAULT_FILE_NAME, start_year, end_year)
        stage(ok, "Creating the master")
        functions = []
        for selector, column in zip(selectors, columns):
            folder, ok = split_data(source, transformation, {selector}, folder_root / "splits" / column, lookup)
            stage(ok, f"The split of COFOG {selector}")
            stage(run_aggregation(master_path, folder, column, method, None, zero_as_missing, None, None),
                  f"The aggregation of COFOG {selector}")
            functions.append(function_row(selector, transformation, method, output_columns(column),
                                          read_split_marker(folder).get("publication_date", "")))
        options = {"cofog": selectors, "source": source.name,
                   "lookup_file": "(bundled country_codes.xlsx)" if lookup == PACKAGED_LOOKUP else lookup.name,
                   "filter_type": transformation, "sector": method, "zero_as_missing": zero_as_missing,
                   "start_year": start_year, "end_year": end_year}
        record_run(master_path, source, sha256_of(source), "build_panel (Python)", options, functions)
        master = pd.read_excel(master_path, sheet_name=MASTER_SHEET)
        provenance = read_provenance(master_path)

    parts = []
    for selector, column in zip(selectors, columns):
        data, tier, sectors, complete = output_columns(column)
        part = pd.DataFrame({
            "iso3": master["SortKey"].astype(str).str[:3], "country": master["Country"],
            "year": master["Year"].astype(int), "cofog": selector, "value": master[data],
            "tier": master[tier].fillna("").astype(str), "sectors": master[sectors].fillna("").astype(str),
            "complete": master[complete].fillna("").astype(str),
        })
        parts.append(part if keep_empty else part[part["value"].notna()])
    panel = pd.concat(parts, ignore_index=True)[TIDY_COLUMNS]
    panel.attrs["provenance"] = provenance.to_dict("records")
    return panel
