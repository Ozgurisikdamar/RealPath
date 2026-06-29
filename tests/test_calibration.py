"""Probability-calibration tests (opt-in isotonic calibration).

Calibration is monotonic, so ROC-AUC is preserved while probabilities become better
calibrated (lower Brier / ECE). Verified on a deterministic synthetic dataset and
end-to-end through the engine.
"""
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.metrics import brier_score_loss, roc_auc_score

from realpath.model import fit_model, reliability


def _split():
    X, y = make_classification(
        n_samples=3000, n_features=20, n_informative=8, weights=[0.7, 0.3], random_state=0
    )
    X = pd.DataFrame(X, columns=[f"f{i}" for i in range(20)])
    y = pd.Series(y)
    return X.iloc[:2000], y.iloc[:2000], X.iloc[2000:], y.iloc[2000:]


def test_calibration_preserves_auc_and_improves_ece():
    Xtr, ytr, Xte, yte = _split()
    m0 = fit_model(Xtr, ytr, "classification", calibrate=False)
    m1 = fit_model(Xtr, ytr, "classification", calibrate=True)
    assert m1.calibrator is not None

    p0, p1 = m0.predict(Xte), m1.predict(Xte)
    assert p1.min() >= 0.0 and p1.max() <= 1.0

    auc0, auc1 = roc_auc_score(yte, p0), roc_auc_score(yte, p1)
    assert auc1 > auc0 - 0.02                      # ranking essentially preserved

    # calibration should improve (or at least not worsen) Brier and ECE
    assert brier_score_loss(yte, p1) <= brier_score_loss(yte, p0) + 1e-3
    assert reliability(yte, p1)["ece"] < reliability(yte, p0)["ece"]


def test_reliability_helper_bounds():
    r = reliability([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
    assert 0.0 <= r["brier"] <= 1.0
    assert 0.0 <= r["ece"] <= 1.0
    # a perfectly confident, correct predictor has ~zero Brier
    perfect = reliability([0, 1], [0.0, 1.0])
    assert perfect["brier"] == 0.0


def test_engine_calibrate_end_to_end(engine):
    r = engine.churn(entity="customers", event="transactions", horizon_days=30, calibrate=True)
    assert r.model.calibrator is not None
    scores = r.predictions["score"].to_numpy()
    assert scores.min() >= 0.0 and scores.max() <= 1.0
    rel = r.reliability()
    assert "brier" in rel and "ece" in rel
    assert np.isfinite(rel["brier"]) and np.isfinite(rel["ece"])
