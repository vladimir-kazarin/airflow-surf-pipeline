"""Smoke test: run the real app headless against the bundled snapshot (no AWS, no network)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"
SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample"
TIMEOUT_S = 60


@pytest.fixture
def app(monkeypatch) -> AppTest:
    monkeypatch.setenv("SURF_DATA_DIR", str(SAMPLE_DIR))
    return AppTest.from_file(str(APP), default_timeout=TIMEOUT_S).run()


def test_app_renders_without_errors(app):
    assert not app.exception
    assert app.title[0].value == "🌊 Surf Window"


def test_app_shows_a_tile_per_spot(app):
    assert len(app.metric) == 4


def test_changing_spot_rerenders(app):
    app.segmented_control(key="focus").set_value("Rockaway").run()
    assert not app.exception
    assert any("Rockaway vs. the other spots" in m.value for m in app.markdown)
