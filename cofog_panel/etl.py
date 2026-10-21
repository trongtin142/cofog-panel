"""
Stage 4: filter the GFS extract on one transformation and one COFOG function, and write the
matching series to one workbook per country (AAA.xlsx) in a directory owned by this stage.
"""
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from .messages import DOWNLOAD_HINT, hint_for_write_error, print_error
from .options import OptionError, normalise_transformation
from .source import open_rows

COUNTRY_FILE_PATTERN = re.compile(r"^[A-Z]{3}\.xlsx$")
# Marker file: country files are only ever deleted from directories that carry it
SPLIT_MARKER = ".cofog_panel_split"
_MARKER_TEXT = "Created by cofog-panel split. Country files here are replaced on each run.\n"

_FILTER_COLUMNS = ("SERIES_CODE", "TYPE_OF_TRANSFORMATION", "COFOG")
_FUNCTION_FIELD = re.compile(r"GF(\d{2})(\d*)(?:_.*)?")
_PROGRESS_EVERY = 50_000


def _cofog_code_from_series(series_code: Any) -> Optional[str]:
    """
    COFOG code in an IMF series code, read from its fourth field:
    'ARM.S13.G2MF.GF0510_T.POGDP_PT.A' -> '05.1', '...GF05_T...' -> '05'.
    Groups carry trailing zeros in GFS (GF0510, GF07120), which are dropped.
    """
    if not isinstance(series_code, str):
        return None
    fields = series_code.split(".")
    if len(fields) < 4:
        return None
    match = _FUNCTION_FIELD.fullmatch(fields[3])
    if match is None:
        return None
    division, group = match.group(1), match.group(2).rstrip("0")
    return f"{division}.{group}" if group else division


def _country_of(series_code: Any) -> Optional[str]:
    """IMF country code: the first three characters of the series code."""
    if isinstance(series_code, str) and len(series_code) >= 3:
        return series_code[:3].upper()
    return None


def _directory_usable(path: Path) -> bool:
    """A split may write into a new or empty directory, or into one it created before."""
    if not path.exists() or (path / SPLIT_MARKER).exists():
        return True
    return not any(path.iterdir())


def _scan(source: Path, transformation: str, selectors: set) -> Tuple[List[str], Dict[str, List[List[str]]], int]:
    """
    Stream the extract once and keep the rows of the requested transformation and function.
    Returns (header, rows by country, number of rows read). Cells are kept as text.
    """
    with open_rows(source) as rows:
        header = ["" if cell is None else str(cell).strip() for cell in next(rows, ())]
        missing = [c for c in _FILTER_COLUMNS if c not in header]
        if missing:
            raise KeyError(missing)
        at_series, at_type, at_cofog = (header.index(c) for c in _FILTER_COLUMNS)

        kept: Dict[str, List[List[str]]] = {}
        n_kept = 0
        n_read = 1
        for n_read, row in enumerate(rows, start=2):
            if n_read % _PROGRESS_EVERY == 0:
                print(f"   ... Processed {n_read} rows. Found {n_kept} valid rows so far.")
            if row[at_type] != transformation:
                continue
            label = row[at_cofog]
            keys = {_cofog_code_from_series(row[at_series])}
            if label is not None:
                keys.add(str(label).strip())
            if not keys & selectors:
                continue
            country = _country_of(row[at_series])
            if country is None:
                continue
            kept.setdefault(country, []).append(["" if cell is None else str(cell) for cell in row])
            n_kept += 1
    return header, kept, n_read


def split_data(
    source_file_path: Path,
    filter_type: str,
    cofog_filter_set: Iterable[str],
    output_dir: Path,
) -> Tuple[Path, bool]:
    """
    Write the series of one transformation (e.g. 'Percent of GDP', any letter case) and one
    COFOG function (code such as '05' or '07.3', or the exact label) to output_dir/AAA.xlsx.

    Country files from a previous split in the same directory are replaced. Returns (output_dir, success).
    """
    selectors = {cofog_filter_set} if isinstance(cofog_filter_set, str) else set(cofog_filter_set)
    selectors = {str(s).strip() for s in selectors}
    print(f"\n--- ETL & SPLIT: Processing {source_file_path.name} ---")

    try:
        transformation = normalise_transformation(filter_type)
    except OptionError as exc:
        print_error(exc.what, exc.hint)
        return output_dir, False
    if not source_file_path.exists():
        print_error(f"Source file not found: {source_file_path}", DOWNLOAD_HINT)
        return output_dir, False
    # Checked before the long scan, so that a wrong directory fails at once
    if not _directory_usable(output_dir):
        print_error(f"{output_dir} is not empty and was not created by 'cofog-panel split'.",
                    "Choose an empty or new --output-dir (the default is intermediate_splits).")
        return output_dir, False

    print(f"Filtering data by Transformation: {transformation} and COFOGs: {selectors}...")
    try:
        header, by_country, n_read = _scan(source_file_path, transformation, selectors)
    except KeyError as exc:
        print_error(f"Missing essential column for filtering: {exc.args[0]}.",
                    "Use the Excel download of IMF.STA:GFS_COFOG without changes; 'cofog-panel check-format' checks it.")
        return output_dir, False
    except Exception as exc:
        print_error(f"Cannot read {source_file_path.name} ({exc}).",
                    "Use the CSV or Excel download from the IMF portal and close the file if it is open in another program.")
        return output_dir, False

    n_kept = sum(len(rows) for rows in by_country.values())
    print(f"\n--- Filtering complete. Total Processed: {n_read}. Total Valid: {n_kept} ---")
    if n_kept == 0:
        print_error(f"No rows matched COFOG {sorted(selectors)} with transformation '{transformation}'.",
                    "Run 'cofog-panel list-cofog' to see the COFOG codes and labels in the file.")
        return output_dir, False

    output_dir.mkdir(parents=True, exist_ok=True)
    notes = f"cofog={','.join(sorted(selectors))}\ntransformation={transformation}\n"
    (output_dir / SPLIT_MARKER).write_text(_MARKER_TEXT + notes)
    previous = [f for f in output_dir.glob("*.xlsx") if COUNTRY_FILE_PATTERN.match(f.name)]
    if previous:
        print(f"🧹 Removing {len(previous)} country files from a previous split in {output_dir}.")
        for old_file in previous:
            old_file.unlink()

    ok = True
    for country, rows in by_country.items():
        try:
            pd.DataFrame(rows, columns=header).to_excel(output_dir / f"{country}.xlsx", index=False, sheet_name=country)
            print(f"Wrote {len(rows)} rows for {country}.")
        except Exception as exc:
            print_error(f"Cannot write {country}.xlsx ({exc}).", hint_for_write_error(exc))
            ok = False

    print("\n=== SPLIT STAGE COMPLETED ===")
    return output_dir, ok


def read_split_marker(directory: Path) -> Dict[str, str]:
    """Settings recorded by the last split in a directory, e.g. {'cofog': '05', 'transformation': ...}."""
    marker = directory / SPLIT_MARKER
    if not marker.exists():
        return {}
    pairs = (line.split("=", 1) for line in marker.read_text().splitlines() if "=" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def list_cofog(source_file_path: Path) -> List[Tuple[str, str, int]]:
    """
    COFOG functions in an extract: (code, label, number of countries), sorted by code.
    Reads the whole file once (seconds for the CSV download, about a minute for the Excel one).
    """
    with open_rows(source_file_path) as rows:
        header = ["" if cell is None else str(cell).strip() for cell in next(rows, ())]
        missing = [c for c in ("SERIES_CODE", "COFOG") if c not in header]
        if missing:
            raise KeyError(missing)
        at_series, at_cofog = header.index("SERIES_CODE"), header.index("COFOG")
        countries: Dict[Tuple[str, str], set] = {}
        for row in rows:
            code = _cofog_code_from_series(row[at_series])
            if code is None:
                continue
            label = "" if row[at_cofog] is None else str(row[at_cofog]).strip()
            countries.setdefault((code, label), set()).add(_country_of(row[at_series]))
    return sorted(((code, label, len(isos)) for (code, label), isos in countries.items()),
                  key=lambda item: ([int(part) for part in item[0].split(".")], item[1]))
