"""
Stage 4: filter the GFS extract on one transformation and one COFOG function, and write the
matching series to one CSV file per country (AAA.csv) in a directory owned by this stage.
"""
import csv
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .checks import read_lookup
from .messages import DOWNLOAD_HINT, hint_for_write_error, print_error
from .options import OptionError, normalise_transformation
from .source import header_row, open_rows

# Country files are CSV; .xlsx is what splits made by versions up to 1.0.5 contain
COUNTRY_FILE_PATTERN = re.compile(r"^[A-Z]{3}\.(csv|xlsx)$")
COUNTRY_FILE_ENCODING = "utf-8-sig"  # with a BOM, so that Excel opens non-ASCII text correctly
# Marker file: country files are only ever deleted from directories that carry it
SPLIT_MARKER = ".cofog_panel_split"
_MARKER_TEXT = "Created by cofog-panel split. Country files here are replaced on each run.\n"

# IMF country codes that differ from ISO 3166 alpha-3, read from data/imf_country_codes.csv (columns imf, iso)
IMF_CODES_FILE = Path(__file__).parent / "data" / "imf_country_codes.csv"


def _read_imf_codes(path: Path) -> Dict[str, str]:
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return {row["imf"].strip().upper(): row["iso"].strip().upper() for row in csv.DictReader(handle)}


IMF_TO_ISO = _read_imf_codes(IMF_CODES_FILE)

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


def _is_other_indicator(series_code: Any, label: Any) -> bool:
    """
    Series of another GFS indicator than a COFOG function, which the extract also carries: total
    outlays 'ARM.S13.G2MF.TOA_T.POGDP_PT.A' and '...TOTOUT_T...', or a liability series. The fourth
    field is not a GF code and the COFOG label is empty, so these rows cannot belong to a function.
    """
    fields = series_code.split(".") if isinstance(series_code, str) else []
    return len(fields) >= 4 and not fields[3].startswith("GF") and (label is None or not str(label).strip())


def _country_of(series_code: Any) -> Optional[str]:
    """IMF code of the first field of the series code (upper case): 'ARM.S13...' -> 'ARM', 'EU.S13...' -> 'EU'."""
    if isinstance(series_code, str) and series_code.split(".")[0].strip():
        return series_code.split(".")[0].strip().upper()
    return None


def _is_country_code(code: Optional[str]) -> bool:
    """Country files are named after three-letter codes; other codes (groups, areas) are not split."""
    return code is not None and re.fullmatch(r"[A-Z]{3}", code) is not None


def country_files(directory: Path) -> List[Path]:
    """Country files (AAA.csv, or AAA.xlsx from an older split) of a directory, one per country, CSV first."""
    found: Dict[str, Path] = {}
    for path in sorted(Path(directory).iterdir(), key=lambda p: p.suffix != ".csv"):
        if COUNTRY_FILE_PATTERN.match(path.name):
            found.setdefault(path.stem, path)
    return sorted(found.values())


def _missing_from_lookup(
    by_country: Dict[str, List[List[str]]], header: List[str], lookup_file: Path,
) -> List[str]:
    """'AAA (Name)' for the countries of a split that have no alpha-3 row in the lookup; [] if the lookup is unreadable."""
    try:
        table = read_lookup(lookup_file)
        known = set(table["alpha-3"].astype(str).str.strip().str.upper())
    except Exception:  # the lookup checks (check-country-format, seed-master) report this
        return []
    at_name = header.index("COUNTRY") if "COUNTRY" in header else None
    missing = []
    for code, rows in sorted(by_country.items()):
        if IMF_TO_ISO.get(code, code) not in known:
            name = rows[0][at_name].strip() if at_name is not None and rows[0][at_name].strip() else ""
            missing.append(f"{code} ({name})" if name else code)
    return missing


def _directory_usable(path: Path) -> bool:
    """A split may write into a new or empty directory, or into one it created before."""
    if not path.exists() or (path / SPLIT_MARKER).exists():
        return True
    return not any(path.iterdir())


def _date_text(cell: Any) -> str:
    """A PUBLICATION_DATE cell as text: dates from Excel as YYYY-MM-DD, anything else as it is."""
    return cell.date().isoformat() if hasattr(cell, "date") else str(cell).strip()


def _scan(
    source: Path, transformation: str, selectors: set,
) -> Tuple[List[str], Dict[str, List[List[str]]], int, List[str]]:
    """
    Stream the extract once and keep the rows of the requested transformation and function.
    Returns (header, rows by country, number of rows read, PUBLICATION_DATE values of the kept rows).
    Cells are kept as text.
    """
    with open_rows(source) as rows:
        header = header_row(rows)
        missing = [c for c in _FILTER_COLUMNS if c not in header]
        if missing:
            raise KeyError(missing)
        at_series, at_type, at_cofog = (header.index(c) for c in _FILTER_COLUMNS)
        at_published = header.index("PUBLICATION_DATE") if "PUBLICATION_DATE" in header else None
        published: set = set()
        at_frequency = header.index("FREQUENCY") if "FREQUENCY" in header else None
        frequencies: set = set()
        codes_of_label: Dict[str, set] = {}

        kept: Dict[str, List[List[str]]] = {}
        skipped: set = set()
        n_no_function = 0
        n_kept = 0
        n_read = 1
        for n_read, row in enumerate(rows, start=2):
            if n_read % _PROGRESS_EVERY == 0:
                print(f"   ... Processed {n_read} rows. Found {n_kept} valid rows so far.")
            if row[at_type] != transformation:
                continue
            label = row[at_cofog]
            code = _cofog_code_from_series(row[at_series])
            keys = {code}
            if label is not None:
                keys.add(str(label).strip())
            if not keys & selectors:
                if code is None and not _is_other_indicator(row[at_series], label):
                    n_no_function += 1
                continue
            country = _country_of(row[at_series])
            if not _is_country_code(country):
                skipped.add(country)
                continue
            kept.setdefault(country, []).append(["" if cell is None else str(cell) for cell in row])
            n_kept += 1
            if label is not None and str(label).strip() in selectors:
                codes_of_label.setdefault(str(label).strip(), set()).add(code)
            if at_frequency is not None and row[at_frequency] is not None and str(row[at_frequency]).strip():
                frequencies.add(str(row[at_frequency]).strip())
            if at_published is not None and row[at_published] is not None and str(row[at_published]).strip():
                published.add(_date_text(row[at_published]))
    if n_no_function:
        print(f"⚠️ {n_no_function} rows of this transformation have no COFOG function in their series code and were not "
              f"written (series that do not follow the 'country.sector.unit.function' pattern).")
    if skipped:
        print(f"⚠️ Series with a code that is not three letters were not written: {sorted(map(str, skipped))}")
    for label, codes in sorted(codes_of_label.items()):
        if len(codes) > 1:
            print(f"⚠️ The label '{label}' covers several COFOG functions ({', '.join(sorted(map(str, codes)))}); "
                  f"their series are mixed in the output. Select one code (e.g. --cofog 05) to avoid this.")
    if len(frequencies) > 1:
        print(f"⚠️ The selected series have different FREQUENCY values ({', '.join(sorted(frequencies))}); "
              f"the panel is yearly, so check that the extract holds annual data only.")
    return header, kept, n_read, sorted(published)


def split_data(
    source_file_path: Path,
    filter_type: str,
    cofog_filter_set: Iterable[str],
    output_dir: Path,
    lookup_file: Optional[Path] = None,
) -> Tuple[Path, bool]:
    """
    Write the series of one transformation (e.g. 'Percent of GDP', any letter case) and one
    COFOG function (code such as '05' or '07.3', or the exact label) to output_dir/AAA.csv.

    Country files from a previous split in the same directory are replaced. With a lookup_file,
    countries of the extract that have no row in it are listed (they would not reach the master).
    Returns (output_dir, success).
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
        header, by_country, n_read, published = _scan(source_file_path, transformation, selectors)
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

    if len(published) > 1:
        print(f"⚠️ The selected series carry {len(published)} different PUBLICATION_DATE values ({', '.join(published)}): "
              f"the extract mixes IMF releases. Download it again in one go if the values must be consistent.")
    missing = _missing_from_lookup(by_country, header, lookup_file) if lookup_file is not None else []
    if missing:
        print(f"⚠️ {len(missing)} countries in the extract have no row in the lookup file and will not reach the master "
              f"(add them to the lookup, or check the codes): {', '.join(missing)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    notes = f"cofog={','.join(sorted(selectors))}\ntransformation={transformation}\n"
    if published:
        notes += f"publication_date={','.join(published)}\n"
    years = sorted(int(h) for h in header if len(h) == 4 and h.isdigit())
    if years:
        notes += f"years={years[0]}-{years[-1]}\n"
    (output_dir / SPLIT_MARKER).write_text(_MARKER_TEXT + notes)
    previous = [f for f in output_dir.iterdir() if COUNTRY_FILE_PATTERN.match(f.name)]
    if previous:
        print(f"🧹 Removing {len(previous)} country files from a previous split in {output_dir}.")
        for old_file in previous:
            old_file.unlink()

    ok = True
    for country, rows in by_country.items():
        try:
            with open(output_dir / f"{country}.csv", "w", encoding=COUNTRY_FILE_ENCODING, newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerows(rows)
            print(f"Wrote {len(rows)} rows for {country}.")
        except Exception as exc:
            print_error(f"Cannot write {country}.csv ({exc}).", hint_for_write_error(exc))
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
        header = header_row(rows)
        missing = [c for c in ("SERIES_CODE", "COFOG") if c not in header]
        if missing:
            raise KeyError(missing)
        at_series, at_cofog = header.index("SERIES_CODE"), header.index("COFOG")
        countries: Dict[Tuple[str, str], set] = {}
        for row in rows:
            code = _cofog_code_from_series(row[at_series])
            country = _country_of(row[at_series])
            if code is None or not _is_country_code(country):
                continue
            label = "" if row[at_cofog] is None else str(row[at_cofog]).strip()
            countries.setdefault((code, label), set()).add(country)
    return sorted(((code, label, len(isos)) for (code, label), isos in countries.items()),
                  key=lambda item: ([int(part) for part in item[0].split(".")], item[1]))
