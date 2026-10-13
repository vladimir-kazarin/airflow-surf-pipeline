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


def test_app_shows_one_card_per_spot(app):
    history_buttons = [b for b in app.button if b.key and b.key.startswith("history-")]
    assert len(history_buttons) == 4


def test_headline_names_a_spot(app):
    assert any("Best bet" in m.value or "least bad" in m.value for m in app.markdown)


def test_opening_history_dialog_renders(app):
    app.button(key="history-Bali").click().run()
    assert not app.exception
