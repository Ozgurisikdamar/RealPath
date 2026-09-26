"""Streamlit demo smoke tests: English by default, Turkish on request, a full predict round trip.

Runs the real app script headlessly with Streamlit's AppTest (no browser, no server).
Skipped when the ``demo`` extra (streamlit) is not installed.
"""
from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

APP = str(Path(__file__).resolve().parent.parent / "realpath" / "demo_app.py")
CHURN_PQL = "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id"


def _open(sample_db: str, lang: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=300)
    if lang:
        at.query_params["lang"] = lang
    at.run()
    at.sidebar.text_input[0].set_value(sample_db).run()  # point the app at the test database
    assert not at.exception
    return at


def _button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def _subheaders(at: AppTest) -> list[str]:
    return [s.value for s in at.subheader]


def test_english_is_the_default(sample_db):
    at = _open(sample_db)
    assert at.segmented_control[0].value == "en"
    assert at.query_params["lang"] == ["en"]
    assert at.sidebar.subheader[0].value == "Schema & FK graph"
    assert "1) Ask a predictive question" in _subheaders(at)
    assert _button(at, "Predict").label == "Predict"


def test_turkish_via_query_param(sample_db):
    at = _open(sample_db, lang="tr")
    assert at.segmented_control[0].value == "tr"
    assert at.sidebar.subheader[0].value == "Şema & FK grafiği"
    assert "1) Bir tahmin sorun" in _subheaders(at)
    assert _button(at, "Tahmin et").label == "Tahmin et"


def test_unknown_language_falls_back_to_english(sample_db):
    at = _open(sample_db, lang="de")
    assert at.segmented_control[0].value == "en"
    assert at.query_params["lang"] == ["en"]


def test_predict_then_switch_language_keeps_the_result(sample_db):
    at = _open(sample_db)
    at.text_area[0].set_value(CHURN_PQL).run()
    _button(at, "Predict").click().run()
    assert not at.exception

    assert "2) Result" in _subheaders(at)
    assert any(CHURN_PQL in c.value for c in at.code)
    labels = {m.label for m in at.metric}
    assert {"ROC-AUC", "Accuracy"} <= labels
    assert any("contribution" in c.value for c in at.code)  # the explanation card

    at.segmented_control[0].set_value("tr").run()
    assert "2) Sonuç" in _subheaders(at)
    assert {"ROC-AUC", "Doğruluk"} <= {m.label for m in at.metric}
    assert any("katki" in c.value for c in at.code)
    assert at.query_params["lang"] == ["tr"]
