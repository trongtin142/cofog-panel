"""
Rebuild the sample extract in this folder from the full IMF download.

    python data/sample/make_sample.py PATH/TO/gfs_raw_data.xlsx

Keeps the rows of the Excel download of IMF.STA:GFS_COFOG 11.0.0 published on 3 February 2026
(SHA-256 91e3db1b...) whose series code names COFOG group 07.3 (hospital services) and whose
TYPE_OF_TRANSFORMATION is "Percent of GDP": every country and sector, all 105 columns. It writes them
in the layout of the portal's CSV download (UTF-8 with BOM, every field quoted, LF line ends). Cells
are written as cofog-panel reads them from the Excel file (numbers in Python's shortest exact form), so
`cofog-panel run --cofog 07.3` gives the same master from the sample as from the full download.
"""
import csv
import hashlib
import sys
from pathlib import Path

import openpyxl

FULL_SHA256 = "91e3db1bdb838f322dcbe648b133f511f3efe1921e50c8bc0d7621f512668cfe"
OUT = Path(__file__).resolve().parent / "gfs_cofog_073_sample.csv"


def is_group_073(series_code) -> bool:
    """'NPL.S13.G2MF.GF073_T.POGDP_PT.A' -> True (the fourth field is GF073 or GF0730 before '_')."""
    fields = series_code.split(".") if isinstance(series_code, str) else []
    return len(fields) >= 4 and fields[3].split("_")[0].rstrip("0") == "GF073"


def main() -> None:
    source = Path(sys.argv[1])
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != FULL_SHA256:
        sys.exit(f"{source.name} is not the download of 3 February 2026 (SHA-256 {digest[:12]}...).")
    book = openpyxl.load_workbook(source, read_only=True, data_only=True)
    rows = book.active.iter_rows(values_only=True)
    header = ["" if cell is None else str(cell).strip() for cell in next(rows)]
    at_series, at_type = header.index("SERIES_CODE"), header.index("TYPE_OF_TRANSFORMATION")
    kept = [["" if cell is None else str(cell) for cell in row] for row in rows
            if row[at_type] == "Percent of GDP" and is_group_073(row[at_series])]
    book.close()
    with OUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(kept)
    print(f"{OUT.name}: {len(kept)} rows, SHA-256 {hashlib.sha256(OUT.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
