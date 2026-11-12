"""
Grant flows within general government from the IMF GFS Statement of Operations (IMF.STA:GFS_SOO),
the input of the grant-flow tests in evaluate_extensions.py: reads the SDMX-ML download or the
filtered CSV made from it, and makes that CSV.

Run from the repository root, on an SDMX-ML (structure-specific) download of the query recorded in
data_ext/SOURCES.md:
    python replication/harmonisation/grants_sdmx.py DOWNLOAD.xml [--out FILE]

The CSV (default data_ext/gfs_soo_grants_pcgdp.csv) keeps every observation that has a value, in the
order of the download: one row per series and year, with the series key (COUNTRY, SECTOR, INDICATOR,
TYPE_OF_TRANSFORMATION, FREQUENCY), TIME_PERIOD and OBS_VALUE copied as text. Observations without a
value and the observation attributes (status flags) are left out. evaluate_extensions.py reads either
file and gives the same results. Standard library only.
"""
import argparse
import csv
import hashlib
import re
from pathlib import Path
from typing import Dict, Iterator

HERE = Path(__file__).resolve().parent
CSV_FILE = HERE / "data_ext" / "gfs_soo_grants_pcgdp.csv"
COLUMNS = ["COUNTRY", "SECTOR", "INDICATOR", "TYPE_OF_TRANSFORMATION", "FREQUENCY", "TIME_PERIOD", "OBS_VALUE"]
# SHA-256 of the SDMX-ML download (IMF.STA:GFS_SOO 12.0.0, published 2026-11-12) and of the CSV made from it
SHA256 = {"xml": "6315f830739cdbb2f9546bd1f553c314130feae156823acc27a69c3bf48cb18c",
          "csv": "b17d090c2cbe192eb45bfa1459bccd85b34cab1444308831723d55509f46a3af"}


def expected_sha256(path: Path) -> str:
    return SHA256["csv" if Path(path).suffix.lower() == ".csv" else "xml"]


def records(path: Path) -> Iterator[Dict[str, str]]:
    """Observations with a value, in file order, as {column of COLUMNS: text}."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf8", newline="") as handle:
            yield from csv.DictReader(handle)
        return
    text = path.read_text(encoding="utf8")
    for series in re.finditer(r"<Series ([^>]*)>(.*?)</Series>", text, re.S):
        key = dict(re.findall(r'(\w+)="([^"]*)"', series.group(1)))
        for obs in re.finditer(r"<Obs ([^>]*)/>", series.group(2)):
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', obs.group(1)))
            if attrs.get("OBS_VALUE") not in (None, "", "NaN"):
                yield {**{c: key.get(c, "") for c in COLUMNS[:5]},
                       "TIME_PERIOD": attrs["TIME_PERIOD"], "OBS_VALUE": attrs["OBS_VALUE"]}


def write_csv(source: Path, out: Path) -> int:
    """Write the observations of an SDMX-ML download to a CSV file (UTF-8, LF line ends); returns the row count."""
    n = 0
    with Path(out).open("w", encoding="utf8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in records(source):
            writer.writerow(row)
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0].strip())
    ap.add_argument("download", type=Path, help="SDMX-ML download of IMF.STA:GFS_SOO (see data_ext/SOURCES.md)")
    ap.add_argument("--out", type=Path, default=CSV_FILE, help="CSV file to write (default: %(default)s)")
    a = ap.parse_args()
    digest = hashlib.sha256(a.download.read_bytes()).hexdigest()
    if digest != SHA256["xml"]:
        print(f"WARNING: {a.download.name} differs from the download used for the study (SHA-256 {digest[:12]}...).")
    n = write_csv(a.download, a.out)
    print(f"{a.out.name}: {n} observations, SHA-256 {hashlib.sha256(a.out.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
