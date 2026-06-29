"""Model layer: a strong, cheap baseline.

LightGBM (gradient boosting) is the workhorse — §2.4 of the spec shows it matches or beats
GNN/RDL on many relational tabular tasks at a fraction of the cost. Task type (classification
vs regression) is taken straight from the PQL (a comparison ⇒ classification). TabPFN is an
optional small-data path.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class _Preprocessor:
    cat_columns: list[str] = field(default_factory=list)
    categories: dict[str, pd.Index] = field(default_factory=dict)
    columns: list[str] = field(default_factory=list)

    def fit(self, X: pd.DataFrame) -> "_Preprocessor":
        X = _clean(X)
        self.columns = list(X.columns)
        for c in X.columns:
            if X[c].dtype == object or str(X[c].dtype) == "category":
                cat = X[c].astype("category")
                self.cat_columns.append(c)
                self.categories[c] = cat.cat.categories
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        X = _clean(X).reindex(columns=self.columns)
        for c in self.cat_columns:
            X[c] = pd.Categorical(X[c], categories=self.categories[c])
        return X


def _clean(X: pd.DataFrame) -> pd.DataFrame:
    X = X.copy()
    X = X.replace([np.inf, -np.inf], np.nan)
    # drop columns that are entirely null (no signal, upsets some learners)
    all_null = [c for c in X.columns if X[c].isna().all()]
    return X.drop(columns=all_null)


@dataclass
class TrainedModel:
    estimator: object
    task_type: str
    preprocessor: _Preprocessor
    feature_names: list[str]
    classes_: np.ndarray | None = None
    constant: float | None = None      # set when the target was degenerate
    calibrator: object | None = None   # isotonic map raw->calibrated proba (classification)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Class-1 probability (classification) or value (regression)."""
        if self.constant is not None:
            return np.full(len(X), self.constant, dtype=float)
        Xt = self.preprocessor.transform(X)
        if self.task_type == "classification":
            raw = self.estimator.predict_proba(Xt)[:, 1]
            return self.calibrator.predict(raw) if self.calibrator is not None else raw
        return self.estimator.predict(Xt)

    def importance(self) -> pd.Series:
        if self.constant is not None or not hasattr(self.estimator, "booster_"):
            return pd.Series(dtype=float)
        gain = self.estimator.booster_.feature_importance(importance_type="gain")
        return pd.Series(gain, index=self.feature_names).sort_values(ascending=False)


def fit_model(
    X: pd.DataFrame,
    y: pd.Series,
    task_type: str,
    backend: str = "auto",
    calibrate: bool = False,
) -> TrainedModel:
    """Train a model. ``calibrate=True`` adds isotonic probability calibration for
    classification (fit on a held-out slice). Isotonic is monotonic, so ranking — and
    therefore ROC-AUC — is preserved while probabilities become better calibrated."""
    pre = _Preprocessor().fit(X)
    Xt = pre.transform(X)
    feat = list(Xt.columns)

    # degenerate target guard
    if task_type == "classification" and y.nunique() < 2:
        const = float(y.iloc[0]) if len(y) else 0.0
        return TrainedModel(None, task_type, pre, feat, constant=const)

    if backend == "tabpfn" or (backend == "auto" and _should_use_tabpfn(Xt, y, task_type)):
        est = _fit_tabpfn(Xt, y, task_type)
        if est is not None:
            classes = getattr(est, "classes_", None)
            return TrainedModel(est, task_type, pre, feat, classes_=classes)

    import lightgbm as lgb

    params = dict(n_estimators=300, learning_rate=0.05, num_leaves=31,
                  subsample=0.8, colsample_bytree=0.8, min_child_samples=20,
                  n_jobs=-1, verbosity=-1)
    if task_type == "classification":
        est = lgb.LGBMClassifier(**params)
        calibrator = _fit_with_calibration(est, Xt, y) if calibrate else None
        if calibrator is None:
            est.fit(Xt, y)
        return TrainedModel(est, task_type, pre, feat, classes_=est.classes_, calibrator=calibrator)
    est = lgb.LGBMRegressor(**params)
    est.fit(Xt, y)
    return TrainedModel(est, task_type, pre, feat)


def _fit_with_calibration(est, Xt: pd.DataFrame, y: pd.Series):
    """Fit ``est`` on a train slice and an isotonic calibrator on a held-out slice.
    Returns the calibrator, or None if calibration isn't applicable (``est`` is then
    left to be fit on the full data by the caller)."""
    if y.nunique() < 2 or len(Xt) < 50:
        return None
    try:
        from sklearn.isotonic import IsotonicRegression
        from sklearn.model_selection import train_test_split

        Xf, Xc, yf, yc = train_test_split(Xt, y, test_size=0.25, stratify=y, random_state=42)
        est.fit(Xf, yf)
        raw = est.predict_proba(Xc)[:, 1]
        return IsotonicRegression(out_of_bounds="clip").fit(raw, yc.to_numpy())
    except Exception:
        return None


def reliability(y_true, proba, n_bins: int = 10) -> dict:
    """Calibration quality: Brier score and Expected Calibration Error (lower is better)."""
    y_true = np.asarray(y_true, dtype=float)
    proba = np.asarray(proba, dtype=float)
    brier = float(np.mean((proba - y_true) ** 2))
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(proba, edges[1:-1]), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        ece += (m.sum() / len(proba)) * abs(proba[m].mean() - y_true[m].mean())
    return {"brier": brier, "ece": float(ece)}


def _should_use_tabpfn(X: pd.DataFrame, y: pd.Series, task_type: str) -> bool:
    # TabPFN shines on small numeric tabular data; keep auto-selection conservative.
    return task_type == "classification" and len(X) <= 1000 and X.shape[1] <= 100 and _has_tabpfn()


def _has_tabpfn() -> bool:
    try:
        import tabpfn  # noqa: F401
        return True
    except Exception:
        return False


def _fit_tabpfn(X: pd.DataFrame, y: pd.Series, task_type: str):
    try:
        from tabpfn import TabPFNClassifier
    except Exception:
        return None
    if task_type != "classification":
        return None
    Xn = X.select_dtypes(include=[np.number]).fillna(0.0)
    clf = TabPFNClassifier()
    clf.fit(Xn.to_numpy(), y.to_numpy())
    return clf
