"""
File-level provenance of a master workbook: the sheet 'Provenance'.

`run`, the browser interface and `build_panel` add one row to it for every COFOG function they
write: the package version, the source file with the SHA-256 computed here, the IMF
PUBLICATION_DATE of the selected series, the command and all its option values, the time (UTC)
and the columns created. Rows of earlier runs on the same master are kept; a run number groups
the rows of one call. The sheet 'MasterData' is not changed.
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional

import pandas as pd

from . import __version__
from .aggregate import provenance_columns, tier_column

PROVENANCE_SHEET = "Provenance"
PROVENANCE_COLUMNS = [
    "Run", "Time (UTC)", "cofog-panel version", "Command", "Options",
    "Source file", "Source SHA-256", "Source size (bytes)", "PUBLICATION_DATE",
    "COFOG", "Transformation", "Method (--sector)", "Columns created",
]


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    """SHA-256 of a file, read in chunks (a few seconds for the 530 MB CSV download)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_timestamp() -> str:
    """The current time in UTC, ISO 8601 to the second: 2026-11-12T20:15:03Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_options(options: Mapping[str, object]) -> str:
    """Option values as one line, e.g. --cofog 07.3 --filter-type "Percent of GDP" --zero-as-missing false."""
    parts = []
    for name, value in options.items():
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            text = str(item).lower() if isinstance(item, bool) else str(item)
            parts.append(f'{name} "{text}"' if (" " in text or text == "") else f"{name} {text}")
    return " ".join(parts)


def output_columns(
    data_col: str, tier_col: Optional[str] = None, sectors_col: Optional[str] = None, complete_col: Optional[str] = None,
) -> List[str]:
    """The four columns that run_aggregation writes for a data column, with the same defaults."""
    sectors, complete = provenance_columns(data_col)
    return [data_col, tier_col or tier_column(data_col), sectors_col or sectors, complete_col or complete]


def function_row(
    cofog: str, transformation: str, method: str, columns: List[str], publication_date: str = "",
) -> Dict[str, str]:
    """The part of a provenance row that describes one COFOG function of a run."""
    return {"COFOG": cofog, "Transformation": transformation, "Method (--sector)": method,
            "PUBLICATION_DATE": publication_date, "Columns created": ", ".join(columns)}


def read_provenance(master_path: Path) -> pd.DataFrame:
    """The Provenance sheet of a master as text (an empty table with its columns if there is none)."""
    with pd.ExcelFile(master_path, engine="openpyxl") as book:
        if PROVENANCE_SHEET not in book.sheet_names:
            return pd.DataFrame(columns=PROVENANCE_COLUMNS)
        return pd.read_excel(book, sheet_name=PROVENANCE_SHEET, dtype=str, keep_default_na=False)


def record_run(
    master_path: Path,
    source_file: Path,
    source_sha256: str,
    command: str,
    options: Mapping[str, object],
    functions: List[Dict[str, str]],
    timestamp: Optional[str] = None,
) -> pd.DataFrame:
    """
    Append one row per entry of `functions` (see function_row) to the Provenance sheet of the
    master, with the run number, time, version, command, options and source file shared by them.
    Other sheets are kept as they are. Returns the rows written.
    """
    master_path, source_file = Path(master_path), Path(source_file)
    earlier = read_provenance(master_path)
    runs = pd.to_numeric(earlier["Run"], errors="coerce").dropna() if len(earlier) else pd.Series(dtype=float)
    shared = {
        "Run": str(int(runs.max()) + 1 if len(runs) else 1),
        "Time (UTC)": timestamp or utc_timestamp(),
        "cofog-panel version": __version__,
        "Command": command,
        "Options": format_options(options),
        "Source file": source_file.name,
        "Source SHA-256": source_sha256,
        "Source size (bytes)": str(source_file.stat().st_size) if source_file.exists() else "",
    }
    rows = pd.DataFrame([{**shared, **row} for row in functions], columns=PROVENANCE_COLUMNS)
    table = pd.concat([earlier.reindex(columns=PROVENANCE_COLUMNS), rows], ignore_index=True)
    for column in ("Run", "Source size (bytes)"):
        numbers = pd.to_numeric(table[column], errors="coerce")
        table[column] = numbers.astype("Int64") if numbers.notna().all() else table[column]
    with pd.ExcelWriter(master_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        table.to_excel(writer, sheet_name=PROVENANCE_SHEET, index=False)
    return rows
