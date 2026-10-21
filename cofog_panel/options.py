"""
Validation of command-line options before any data are read.

A wrong --filter-type or --cofog used to surface only after the whole GFS extract
(about 372,000 rows) had been scanned. The checks here run first and say what is accepted.
"""
import difflib
import re
import zipfile
from pathlib import Path
from typing import List, Optional, Set
from xml.etree import ElementTree

# Values of TYPE_OF_TRANSFORMATION in the IMF GFS COFOG extract
TRANSFORMATIONS = ("Percent of GDP", "Domestic currency", "Percent of total outlays")

# COFOG division and group labels of IMF.STA:GFS_COFOG 11.0.0 (February 2026),
# keyed by the code carried in SERIES_CODE (GF05 -> 05, GF0730 -> 07.3, GF07120 -> 07.12)
COFOG_LABELS = {
    "01": "General public services",
    "01.1": "Executive and legislative organs, financial and fiscal affairs, external affairs",
    "01.2": "Foreign economic aid",
    "01.3": "General services",
    "01.4": "Basic research (CS)",
    "01.5": "R&D General public services (CS)",
    "01.6": "General public services n.e.c. (CS)",
    "01.7": "Public debt transactions (CS)",
    "01.8": "Transfers of a general character between different levels of government (CS)",
    "02": "Defence",
    "02.1": "Military defence (CS)",
    "02.2": "Civil defence (CS)",
    "02.3": "Foreign military aid (CS)",
    "02.4": "R&D Defence (CS)",
    "02.5": "Defence n.e.c.",
    "03": "Public order and safety",
    "03.1": "Police services (CS)",
    "03.2": "Fire-protection services (CS)",
    "03.3": "Law courts (CS)",
    "03.4": "Prisons (CS)",
    "03.5": "R&D Public order and safety (CS)",
    "03.6": "Public order and safety n.e.c. (CS)",
    "04": "Economic affairs",
    "04.1": "General economic, commercial and labour affairs",
    "04.2": "Agriculture, forestry, fishing and hunting",
    "04.3": "Fuel and energy",
    "04.4": "Mining, manufacturing and construction",
    "04.5": "Transport",
    "04.6": "Communication (CS)",
    "04.7": "Other industries",
    "04.8": "R&D Economic affairs",
    "04.9": "Economic affairs n.e.c. (CS)",
    "05": "Environmental protection",
    "05.1": "Waste management (CS)",
    "05.2": "Waste water management (CS)",
    "05.3": "Pollution abatement (CS)",
    "05.4": "Protection of biodiversity and landscape (CS)",
    "05.5": "R&D Environmental protection (CS)",
    "05.6": "Environmental protection n.e.c. (CS)",
    "06": "Housing and community amenities",
    "06.1": "Housing development (CS)",
    "06.2": "Community development (CS)",
    "06.3": "Water supply (CS)",
    "06.4": "Street lighting (CS)",
    "06.5": "R&D Housing and community amenities (CS)",
    "06.6": "Housing and community amenities n.e.c. (CS)",
    "07": "Health",
    "07.12": "Other medical products (IS)",
    "07.2": "Outpatient services",
    "07.3": "Hospital services",
    "07.4": "Public health services (IS)",
    "07.5": "R&D Health",
    "07.6": "Health n.e.c. (CS)",
    "08": "Recreation, culture and religion",
    "08.1": "Recreational and sporting services (IS)",
    "08.2": "Cultural services (IS)",
    "08.3": "Broadcasting and publishing services (CS)",
    "08.4": "Religious and other community services (CS)",
    "08.5": "R&D Recreation, culture and religion (CS)",
    "08.6": "Recreation, culture and religion n.e.c. (CS)",
    "09": "Education",
    "09.1": "Pre-primary and primary education",
    "09.2": "Secondary education",
    "09.3": "Post-secondary non-tertiary education (IS)",
    "09.4": "Tertiary education",
    "09.5": "Education not definable by level (IS)",
    "09.6": "Subsidiary services to education (IS)",
    "09.7": "R&D Education (CS)",
    "09.8": "Education n.e.c. (CS)",
    "10": "Social protection",
    "10.1": "Sickness and disability",
    "10.2": "Old age (IS)",
    "10.3": "Survivors (IS)",
    "10.4": "Family and children (IS)",
    "10.5": "Unemployment (IS)",
    "10.6": "Housing (IS)",
    "10.7": "Social exclusion n.e.c. (IS)",
    "10.8": "R&D Social protection (CS)",
    "10.9": "Social protection n.e.c. (CS)",
}

# A division (01 to 10), optionally followed by a group: 05, 07.3, 07.12
CODE_PATTERN = re.compile(r"(0[1-9]|10)(\.[0-9]{1,2})?")


class OptionError(ValueError):
    """
    An option value that cannot be used: `what` says what is wrong, `hint` how to fix it.
    str() gives both, so the full message is available to scripts.
    """

    def __init__(self, what: str, hint: str = ""):
        super().__init__(f"{what} {hint}".strip())
        self.what = what
        self.hint = hint


def normalise_transformation(value: str) -> str:
    """Return the spelling used in the IMF file for a --filter-type given in any letter case."""
    wanted = value.strip().casefold()
    for name in TRANSFORMATIONS:
        if name.casefold() == wanted:
            return name
    accepted = ", ".join(f"'{name}'" for name in TRANSFORMATIONS)
    raise OptionError(f"Invalid --filter-type '{value}'.", f"Choose one of: {accepted} (letter case does not matter).")


def workbook_strings(path: Path) -> Optional[Set[str]]:
    """
    Distinct text values of an .xlsx workbook, read from its shared-strings part.

    This takes well under a second for the full IMF extract, against about a minute for
    reading every row. Returns None when the workbook has no readable shared-strings part.
    """
    found: Set[str] = set()
    try:
        with zipfile.ZipFile(path) as book, book.open("xl/sharedStrings.xml") as part:
            for _, element in ElementTree.iterparse(part):
                if element.tag.endswith("}t") and element.text:
                    found.add(element.text.strip())
                element.clear()
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
        return None
    return found


def labels_in_file(path: Path) -> Set[str]:
    """
    Text values that may be COFOG labels in an extract: the shared strings of an IMF workbook or,
    for CSV files and workbooks written with inline strings (e.g. by openpyxl), its COFOG column.
    """
    strings = workbook_strings(path)
    if strings is not None:
        return strings
    from .source import open_rows
    try:
        with open_rows(path) as rows:
            header = ["" if cell is None else str(cell).strip() for cell in next(rows, ())]
            if "COFOG" not in header:
                return set()
            at = header.index("COFOG")
            return {str(row[at]).strip() for row in rows if len(row) > at and row[at] is not None}
    except Exception:
        return set()


def _describe(code: str) -> str:
    return f"'{code}' ({COFOG_LABELS[code]})" if code in COFOG_LABELS else f"'{code}'"


def suggest_cofog(value: str, extra_labels: Optional[Set[str]] = None) -> List[str]:
    """Up to three codes or labels close to an unusable --cofog value, best first, one per code."""
    text = value.strip()
    code_of = {label: code for code, label in COFOG_LABELS.items()}
    labels = set(COFOG_LABELS.values()) | (extra_labels or set())
    hints: List[str] = []
    covered: Set[str] = set()

    def add(code: Optional[str], hint: str) -> None:
        if (code is None or code not in covered) and hint not in hints:
            hints.append(hint)
            if code is not None:
                covered.add(code)

    # Codes written without the leading zero: 5 -> 05, 7.3 -> 07.3
    padded = re.fullmatch(r"(\d)(\.\d{1,2})?", text)
    if padded:
        candidate = f"0{padded.group(1)}{padded.group(2) or ''}"
        if candidate in COFOG_LABELS:
            add(candidate, _describe(candidate))

    # Labels typed in another letter case
    by_case = {label.casefold(): label for label in labels}
    if text.casefold() in by_case:
        label = by_case[text.casefold()]
        add(code_of.get(label), f"'{label}' (code {code_of[label]})" if label in code_of else f"'{label}'")

    for match in difflib.get_close_matches(text, list(COFOG_LABELS) + sorted(labels), n=5, cutoff=0.6):
        code = match if match in COFOG_LABELS else code_of.get(match)
        add(code, _describe(code) if code is not None else f"'{match}'")
    return hints[:3]


def check_cofog(value: str, source_file: Optional[Path] = None) -> str:
    """
    Accept a COFOG code (01 to 10, optionally with a group such as 07.3) or an exact label.

    Labels are looked up in the built-in list of the February 2026 release and, when a source
    file is given, among the text values of that workbook (later releases may add labels).
    """
    text = value.strip()
    if CODE_PATTERN.fullmatch(text) or text in COFOG_LABELS.values():
        return text
    file_labels = labels_in_file(source_file) if source_file is not None and source_file.exists() else set()
    if text in file_labels:
        return text
    hints = suggest_cofog(text)
    hint = ("Did you mean: " + ", ".join(hints) + "? ") if hints else ""
    hint += ("Use a COFOG code (01 to 10, or a group such as 07.3) or the exact label used in the file; "
             "'cofog-panel list-cofog' lists them.")
    raise OptionError(f"Invalid --cofog '{value}'.", hint)


def data_column_for(selector: str) -> str:
    """
    Default data column for a COFOG selector: '05' -> DATA_05, '07.3' -> DATA_07_3,
    'Environmental protection' -> DATA_05, any other label -> DATA_<LABEL IN CAPITALS>.
    """
    text = selector.strip()
    if not CODE_PATTERN.fullmatch(text):
        code_of = {label: code for code, label in COFOG_LABELS.items()}
        if text not in code_of:
            return "DATA_" + (re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_").upper() or "NEW")
        text = code_of[text]
    return "DATA_" + text.replace(".", "_")
