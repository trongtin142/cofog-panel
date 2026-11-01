"""
Downloads the third-party data of the environmental-spending replication that the repository does not
distribute, checks each file against the SHA-256 of the copy used in the study, and checks the third-party
files that the repository includes. Run from any folder:
    python replication/eeps/fetch_data.py            # download what is missing, then check every file
    python replication/eeps/fetch_data.py --check    # check only, download nothing
Files are written below replication/eeps/data_ext/lab/. When a download fails, the script prints the URL and
the place to save the file by hand. A file that differs from the checksum gives a warning: the provider may
have revised it, and results can then differ from those of the study. Sources and licences:
replication/eeps/data_ext/SOURCES.md.
"""
import argparse
import hashlib
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE / "data_ext" / "lab"
CACHE = LAB / "_downloads"
UA = {"User-Agent": "cofog-panel replication script (https://github.com/trongtin142/cofog-panel)"}
CEDS = "CEDS_v_2025_03_18_aggregate"

# Not distributed: downloaded from the original source. A zip entry lists (member, target, SHA-256 of target).
DOWNLOAD = [
    {"name": "Regional Authority Index, country file, April 2021",
     "url": "https://garymarks.web.unc.edu/wp-content/uploads/sites/13018/2021/04/RAI_country-april-2021.xlsx",
     "file": "RAI_country-april-2021.xlsx",
     "sha256": "4ae1860a62b23ee0f0adaf5f33beb648d878642a7c5829a1d0a04203ed60c610"},
    {"name": "Terrain ruggedness (Nunn and Puga 2012)",
     "url": "https://diegopuga.org/data/rugged/rugged_data.zip",
     "file": "_downloads/rugged_data.zip",
     "sha256": "3696fc1bd592cad7e75393b5988f797b234ce1797b92a1db037da7e9c657ed1f",
     "extract": [("rugged_data.csv", "rugged/rugged_data.csv",
                  "feaeaf89a8dd7981a80666ae0599660ae4f0dc3b5540fc4e1b48b17a3b09b551")]},
    {"name": "CEDS v_2025_03_18, aggregate data (Zenodo record 15059443)",
     "url": "https://zenodo.org/records/15059443/files/CEDS_v_2025_03_18_aggregate.zip?download=1",
     "file": f"_downloads/{CEDS}.zip",
     "sha256": "b55f0dddb4eb8e14435b13d835f99497b789cb3378eee391d1c78af58c5e8095",
     "extract": [(f"{CEDS}/BC_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
                  "ceds/BC_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
                  "c80b876b41518d4e2ae06682c13b6f46d811650c74110d8d8542ea19077efe1d"),
                 (f"{CEDS}/OC_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
                  "ceds/OC_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
                  "22ccfcd973cb00b4f99450d025b75f12e117f087514a06cbad0a31a47ecade33"),
                 (f"{CEDS}/SO2_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
                  "r3c/ceds/SO2_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
                  "ab4e0eefeb16badf5d8e5a02b03e2d364d38f95b591cba00fa769a86bb2c6998"),
                 (f"{CEDS}/NOx_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
                  "r3c/ceds/NOx_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
                  "39ef971597cd76068137ed85898ccf8af7b88e3cb138b364aa47b5231046dfa9"),
                 (f"{CEDS}/NH3_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
                  "r3c/ceds/NH3_CEDS_estimates_by_country_sector_v_2025_03_18.csv",
                  "4b2a33f4202ef54a74cd2f2ab23d23b69edc6ab6dbfbdb71895c47454806021a")]},
    {"name": "OECD SNG-WOFI, subnational government functional expenditure (COFOG)",
     "url": "https://sdmx.oecd.org/public/rest/data/OECD.CFE.RDG,DSD_SNG_WOFI@DF_COFOG,1.0/all"
            "?format=csvfilewithlabels",
     "file": "sngwofi/oecd_sng_wofi_cofog.csv",
     "sha256": "7d8ba29439d7927bbb26b903b574c4afb646f90d981bd8dddcc934864a6bb750"},
]
# Distributed with the repository (CC BY 4.0 or CC0): checked only.
INCLUDED = [
    ("what_a_waste_country_level_data.csv", "ea41e5b5f577b29df94a963519e70bd82e17efea4cfec3a33b0e9a6bd881cc04"),
    ("HIEF_data.csv", "273f31955e24154f63b8e831008558d8531dfc3775e72067f0782fcc949e77fe"),
    ("gbdmaps/41467_2021_23853_MOESM4_ESM.xlsx", "81a563fe2662bb81931efa0bcab204c7818410a80cd3c41f3e65c3b5ab7aed13"),
    ("r3c/wb_EG.CFT.ACCS.ZS.json", "04fada5fe68dbaefc4cd3ed9b4fcf29692ec737cbea8b977a9fb1d75d36e2743"),
    ("r3c/wb_EG.ELC.COAL.ZS.json", "0cd116de60c04b94fbff71084939fb61e9d82f0506170ce2ed8ade0eec4acdbc"),
    ("r3c/cckp_tas_cru408.json", "3fc826239259ef827271320965ebfade8153bbce9578783b6eb9cdee94dc5ff5"),
    ("r3c/cckp_pr_cru408.json", "bf067095784ffad87d884cd4987e8e9057f14c96616474b5b9015a0e39067a1d"),
    ("r3c/owid_burnt.csv", "040991afbf3a929ac26029bc6ae440f7929a9b30878daa664692cf060b1aaee7"),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check(p: Path, expected: str) -> bool:
    if not p.exists():
        print(f"  MISSING  {p.relative_to(HERE)}")
        return False
    if sha(p) != expected:
        print(f"  WARNING  {p.relative_to(HERE)} differs from the file used in the study "
              f"(SHA-256 {sha(p)[:12]}..., expected {expected[:12]}...)")
        return False
    print(f"  ok       {p.relative_to(HERE)}")
    return True


def download(src: dict) -> bool:
    target = LAB / src["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {src['name']} ...")
    tmp = target.with_name(target.name + ".part")
    try:
        with urllib.request.urlopen(urllib.request.Request(src["url"], headers=UA), timeout=600) as r:
            tmp.write_bytes(r.read())
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        print(f"  Download failed ({err}). Save the file by hand from\n    {src['url']}\n  as\n    {target}")
        return False
    tmp.replace(target)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--check", action="store_true", help="check the files only, download nothing")
    a = ap.parse_args()
    ok = True
    for src in DOWNLOAD:
        members = src.get("extract", [])
        have = all((LAB / t).exists() for _, t, _ in members) if members else (LAB / src["file"]).exists()
        if not have and not a.check:
            if not (LAB / src["file"]).exists() and not download(src):
                ok = False
                continue
            if members:
                check(LAB / src["file"], src["sha256"])
                with zipfile.ZipFile(LAB / src["file"]) as z:
                    for m, t, _ in members:
                        (LAB / t).parent.mkdir(parents=True, exist_ok=True)
                        (LAB / t).write_bytes(z.read(m))
    print("Downloaded files:")
    for src in DOWNLOAD:
        for _, t, h in src.get("extract", []) or [(None, src["file"], src["sha256"])]:
            ok = check(LAB / t, h) and ok
    print("Files included in the repository:")
    for f, h in INCLUDED:
        ok = check(LAB / f, h) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
