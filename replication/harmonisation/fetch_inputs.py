"""
Download the external inputs of dist_exhibit.py and build one filtered table from them.

    python -I fetch_inputs.py --dl DIR --out FILE [--manifest FILE] [--offline]

Step 1 (network, skipped with --offline) writes each source file unchanged into --dl and records its
URL, size, SHA-256 and retrieval time in --manifest. Step 2 reads only those files and writes --out,
one row per country (ISO 3166-1 alpha-3) and year 1990-2023:

  GINI_PRE        Gini of pre-tax national income per equal-split adult (WID, with WID
                  interpolations and extrapolations)
  S50_PRE         share of the bottom 50% in the same income (sum of deciles 1-5), per cent
  GINI_PRE_OBS    GINI_PRE where WID reports an estimate that is neither interpolated nor
                  extrapolated, otherwise empty
  S50_PRE_OBS     same for S50_PRE
  NNI_GDP         net national income / GDP = (GNI - consumption of fixed capital) / GDP (WDI,
                  current US$); this converts a ratio to GDP into a ratio to national income

WID series are taken from the Our World in Data indicator API (WID dataset version 2026-06-18, WID
accessed 2026-07-07, CC BY 4.0), which extracts them with WID's own `wid` Stata command: variables
gptinc992j and sptinc992j (deciles p0p10 ... p40p50), without and with the `exclude` option.
WDI series come from the World Bank API v2 bulk CSV download (CC BY 4.0). No personal information is sent: requests
carry a generic user agent and no other headers.
"""
import argparse
import csv
import hashlib
import json
import time
import urllib.request
import zipfile
from pathlib import Path

MAX_BYTES = 100 * 1024 * 1024
UA = {"User-Agent": "research-replication-script/1.0"}
OWID = "https://api.ourworldindata.org/v1/indicators/{id}.{kind}.json"
# (column, OWID indicator id, OWID short name)
OWID_SERIES = [
    ("GINI_PRE", 1290168, "gini__welfare_type_before_tax__extrapolated_yes"),
    ("GINI_PRE_OBS", 1290172, "gini__welfare_type_before_tax__extrapolated_no"),
    ("D1", 1290068, "share__welfare_type_before_tax__quantile_1__extrapolated_yes"),
    ("D2", 1290072, "share__welfare_type_before_tax__quantile_2__extrapolated_yes"),
    ("D3", 1290071, "share__welfare_type_before_tax__quantile_3__extrapolated_yes"),
    ("D4", 1290073, "share__welfare_type_before_tax__quantile_4__extrapolated_yes"),
    ("D5", 1290074, "share__welfare_type_before_tax__quantile_5__extrapolated_yes"),
    ("D1_OBS", 1290125, "share__welfare_type_before_tax__quantile_1__extrapolated_no"),
    ("D2_OBS", 1290127, "share__welfare_type_before_tax__quantile_2__extrapolated_no"),
    ("D3_OBS", 1290128, "share__welfare_type_before_tax__quantile_3__extrapolated_no"),
    ("D4_OBS", 1290129, "share__welfare_type_before_tax__quantile_4__extrapolated_no"),
    ("D5_OBS", 1290130, "share__welfare_type_before_tax__quantile_5__extrapolated_no"),
]
WB = "https://api.worldbank.org/v2/en/indicator/{ind}?downloadformat=csv"
WB_SERIES = [("GDP", "NY.GDP.MKTP.CD"), ("GNI", "NY.GNP.MKTP.CD"), ("CFC", "NY.ADJ.DKAP.CD")]
YEARS = range(1990, 2024)


def files():
    """(local file name, URL, description) of every download."""
    out = []
    for col, i, short in OWID_SERIES:
        for kind in ("data", "metadata"):
            out.append((f"owid_{i}.{kind}.json", OWID.format(id=i, kind=kind), f"WID via OWID: {short} ({kind})"))
    for col, ind in WB_SERIES:
        out.append((f"wb_{ind}.zip", WB.format(ind=ind), f"World Bank WDI: {ind} (bulk CSV, zip)"))
    return out


def _get(url: str, tries: int = 4):
    """Body and response headers of a GET request, with retries; stops above 100 MB."""
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


def fetch(dl: Path, manifest: Path):
    """Download every file into --dl and record it in --manifest (retrieval time = server Date header)."""
    dl.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, url, desc in files():
        body, hdr = _get(url)
        (dl / name).write_bytes(body)
        rows.append({"File": name, "Source": desc, "URL": url, "Bytes": len(body),
                     "SHA-256": hashlib.sha256(body).hexdigest(),
                     "Retrieved (server Date header)": hdr.get("Date", ""),
                     "Last-Modified header": hdr.get("Last-Modified", "")})
        time.sleep(0.5)
    with manifest.open("w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def owid_series(dl: Path, i: int) -> dict:
    """{(ISO3, year): value} from an OWID indicator; entities without an ISO3 code are dropped."""
    data = json.loads((dl / f"owid_{i}.data.json").read_text(encoding="utf8"))
    meta = json.loads((dl / f"owid_{i}.metadata.json").read_text(encoding="utf8"))
    code = {e["id"]: e.get("code") for e in meta["dimensions"]["entities"]["values"]}
    out = {}
    for v, y, e in zip(data["values"], data["years"], data["entities"]):
        iso = code.get(e)
        if iso and len(iso) == 3 and not iso.startswith("OWID") and y in YEARS:
            out[(iso, int(y))] = float(v)
    return out


def wb_series(dl: Path, ind: str) -> dict:
    """{(ISO3, year): value} from a WDI bulk CSV (zip with one API_<indicator>_*.csv data file)."""
    with zipfile.ZipFile(dl / f"wb_{ind}.zip") as z:
        name = next(n for n in z.namelist() if n.startswith("API_") and n.endswith(".csv"))
        lines = z.read(name).decode("utf-8-sig").splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith('"Country Name"'))
    out = {}
    for r in csv.DictReader(lines[head:]):
        for y in YEARS:
            v = r.get(str(y), "")
            if v not in ("", None):
                out[(r["Country Code"], y)] = float(v)
    return out


def build(dl: Path, out: Path):
    s = {col: owid_series(dl, i) for col, i, _ in OWID_SERIES}
    wb = {col: wb_series(dl, ind) for col, ind in WB_SERIES}
    keys = sorted(set(s["GINI_PRE"]) | set(wb["GDP"]))
    rows = []
    for k in keys:
        def dsum(sfx):
            vals = [s[f"D{j}{sfx}"].get(k) for j in range(1, 6)]
            return None if any(v is None for v in vals) else round(sum(vals), 6)
        gdp, gni, cfc = (wb[c].get(k) for c in ("GDP", "GNI", "CFC"))
        nni = None if None in (gdp, gni, cfc) or gdp <= 0 else round((gni - cfc) / gdp, 6)
        row = {"ISO": k[0], "YEAR": k[1], "GINI_PRE": s["GINI_PRE"].get(k), "S50_PRE": dsum(""),
               "GINI_PRE_OBS": s["GINI_PRE_OBS"].get(k), "S50_PRE_OBS": dsum("_OBS"), "NNI_GDP": nni}
        if any(row[c] is not None for c in ("GINI_PRE", "NNI_GDP")):
            rows.append(row)
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
