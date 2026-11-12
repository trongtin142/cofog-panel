"""Runs the browser interface (cofog_panel/gui.py, and the gui.py shim of a clone) with Streamlit's test harness.
Skipped when the optional extra `gui` is not installed."""
import hashlib
import io
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("streamlit")
import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from cofog_panel.checks import FIXED_HEADERS_SAMPLE  # noqa: E402
from tests.test_cli import YEARS, _series  # noqa: E402

REPO = Path(__file__).parent.parent
GUI = REPO / "cofog_panel" / "gui.py"
SHIM = REPO / "gui.py"


class _Upload(io.BytesIO):
    """What st.file_uploader returns: a name and getbuffer()."""

    def __init__(self, name, data):
        super().__init__(data)
        self.name = name

    def getbuffer(self):
        return memoryview(self.getvalue())


def _run_gui(monkeypatch, name, data, script=GUI):
    monkeypatch.setattr(st, "file_uploader", lambda label, **kw: _Upload(name, data) if "IMF" in label else None)
    app = AppTest.from_file(str(script), default_timeout=120).run()
    app.sidebar.button[0].click().run()
    return app


def _two_countries() -> bytes:
    rows = [_series("USA", "United States", "General government", "05", "Environmental protection", {2000: 1.0}),
            _series("DEU", "Germany", "Local Government", "05", "Environmental protection", {2000: 0.2})]
    return pd.DataFrame(rows, columns=FIXED_HEADERS_SAMPLE + YEARS).to_csv(index=False).encode()


@pytest.mark.parametrize("script", [GUI, SHIM], ids=["package", "shim"])
def test_gui_runs_the_pipeline_and_shows_filled_rows(monkeypatch, script):
    data = _two_countries()
    app = _run_gui(monkeypatch, "data.csv", data, script)
    assert not app.exception and not app.error
    assert "Processing complete" in app.success[0].value
    preview = app.dataframe[0].value
    assert set(preview["SortKey"]) == {"DEU2000", "USA2000"} and preview["DATA_05"].notna().all()
    assert "Run log" in [e.label for e in app.expander][0]
    # the run log names the SHA-256 that the Provenance sheet of the downloaded master records
    assert f"SHA-256 {hashlib.sha256(data).hexdigest()}" in app.code[0].value


def test_gui_shows_the_reason_when_a_stage_fails(monkeypatch):
    app = _run_gui(monkeypatch, "bad.csv", b"A,B\n1,2\n")
    assert not app.exception
    assert "Format check failed" in app.error[0].value
    assert "FORMAT VERIFICATION REPORT (bad.csv)" in app.code[0].value
