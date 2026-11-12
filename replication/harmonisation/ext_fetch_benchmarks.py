"""
Download the external benchmarks of evaluate_extensions_r6.py and build one filtered table from them.

    python -I ext_fetch_benchmarks.py --dl DIR --out FILE [--manifest FILE] [--offline]

Step 1 (network, skipped with --offline) writes each World Bank WDI bulk CSV (zip) unchanged into --dl
and records its URL, size, SHA-256, retrieval time and the "Last Updated Date" stated in the file in
--manifest. Step 2 reads only those files and writes --out, one row per country (ISO 3166-1 alpha-3)
and year 1990-2023:

  GHED_GG_HEALTH   SH.XPD.GHED.GD.ZS: domestic general government health expenditure, % of GDP
                   (WHO Global Health Expenditure Database)
  UIS_GOV_EDU      SE.XPD.TOTL.GD.ZS: government expenditure on education, total, % of GDP
                   (UNESCO Institute for Statistics)

Requests carry a generic user agent and no other headers.
"""
import argparse
import csv
import hashlib
import time
import urllib.request
import zipfile
from pathlib import Path

MAX_BYTES = 100 * 1024 * 1024
UA = {"User-Agent": "research-replication-script/1.0"}
WB = "https://api.worldbank.org/v2/en/indicator/{ind}?downloadformat=csv"
WB_SERIES = [("GHED_GG_HEALTH", "SH.XPD.GHED.GD.ZS"), ("UIS_GOV_EDU", "SE.XPD.TOTL.GD.ZS")]
YEARS = range(1990, 2024)


def _get(url: str, tries: int = 4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=300) as r:
                body, hdr = r.read(MAX_BYTES + 1), r.headers
            if len(body) > MAX_BYTES:
                raise SystemExit(f"{url}: download exceeds 100 MB, stopped")
            return body, hdr
        except (TimeoutError, OSError) as e:
            if k == tries - 1:
                raise
            print(f"retry {k + 1} after {type(e).__name__}: {url}")
            time.sleep(5 * (k + 1))


def _read_zip(path: Path):
    """(lines of the API_*.csv data file, lines of the Metadata_Indicator_*.csv file) of a WDI bulk zip."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        data = next(n for n in names if n.startswith("API_") and n.endswith(".csv"))
        meta = next((n for n in names if n.startswith("Metadata_Indicator") and n.endswith(".csv")), None)
        dl = z.read(data).decode("utf-8-sig").splitlines()
        ml = z.read(meta).decode("utf-8-sig").splitlines() if meta else []
    return dl, ml


def last_updated(lines) -> str:
    for ln in lines[:6]:
        if ln.startswith('"Last Updated Date"'):
            return next(csv.reader([ln]))[1]
    return ""


def fetch(dl: Path, manifest: Path):
    dl.mkdir(parents=True, exist_ok=True)
    rows = []
    for col, ind in WB_SERIES:
        url = WB.format(ind=ind)
        body, hdr = _get(url)
        name = f"wb_{ind}.zip"
        (dl / name).write_bytes(body)
        lines, meta = _read_zip(dl / name)
        src = ""
        if meta:
            r = next(csv.DictReader(meta))
            src = r.get("SOURCE_ORGANIZATION", "")
        rows.append({"File": name, "Indicator": ind, "Column": col, "URL": url, "Bytes": len(body),
                     "SHA-256": hashlib.sha256(body).hexdigest(),
                     "Retrieved (server Date header)": hdr.get("Date", ""),
                     "Last-Modified header": hdr.get("Last-Modified", ""),
                     "Last Updated Date (in file)": last_updated(lines),
                     "Source organization (metadata)": src})
        time.sleep(0.5)
    with manifest.open("w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def wb_series(dl: Path, ind: str) -> dict:
    lines, _ = _read_zip(dl / f"wb_{ind}.zip")
    head = next(i for i, ln in enumerate(lines) if ln.startswith('"Country Name"'))
    out = {}
    for r in csv.DictReader(lines[head:]):
        for y in YEARS:
            v = r.get(str(y), "")
            if v not in ("", None):
                out[(r["Country Code"], y)] = float(v)
    return out


def build(dl: Path, out: Path):
    s = {col: wb_series(dl, ind) for col, ind in WB_SERIES}
    keys = sorted(set().union(*[set(v) for v in s.values()]))
    rows = [{"ISO": k[0], "YEAR": k[1], **{col: s[col].get(k) for col, _ in WB_SERIES}} for k in keys]
    with out.open("w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{out.name}: {len(rows)} country-years, SHA-256 {hashlib.sha256(out.read_bytes()).hexdigest()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0].strip())
    ap.add_argument("--dl", type=Path, required=True, help="empty folder for the downloads")
    ap.add_argument("--out", type=Path, required=True, help="filtered table (CSV)")
    ap.add_argument("--manifest", type=Path, help="download manifest (CSV); required unless --offline")
    ap.add_argument("--offline", action="store_true", help="skip the downloads and rebuild --out from --dl")
    a = ap.parse_args()
    if not a.offline:
        if a.manifest is None:
            raise SystemExit("--manifest is required for a download")
        fetch(a.dl, a.manifest)
    build(a.dl, a.out)


if __name__ == "__main__":
    main()
