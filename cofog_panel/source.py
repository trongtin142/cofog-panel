"""
Reading the GFS extract as downloaded from the IMF portal, in CSV (the portal's default)
or Excel (.xlsx) format. Both downloads have the same columns; the CSV is read much faster.
"""
import csv
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

import openpyxl

# Descriptive fields of the IMF CSV can exceed the default limit of the csv module
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

DEFAULT_SOURCES = (Path("data/gfs_raw_data.xlsx"), Path("data/gfs_raw_data.csv"))


def is_csv(path: Path) -> bool:
    return Path(path).suffix.lower() == ".csv"


def default_source() -> Path:
    """data/gfs_raw_data.xlsx if it exists, otherwise data/gfs_raw_data.csv (the first name if neither exists)."""
    for candidate in DEFAULT_SOURCES:
        if candidate.exists():
            return candidate
    return DEFAULT_SOURCES[0]


@contextmanager
def open_rows(path: Path) -> Iterator[Iterator[Sequence[Optional[Any]]]]:
    """
    Rows of the extract, header row first. Empty cells are None, as openpyxl returns them,
    so that both formats are processed in the same way.
    """
    if is_csv(path):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            yield ([cell if cell != "" else None for cell in row] for row in csv.reader(handle))
    else:
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            yield book.active.iter_rows(values_only=True)
        finally:
            book.close()
