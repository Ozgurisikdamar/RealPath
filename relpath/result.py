"""The object returned by ``Engine.predict`` — predictions plus explanation handles."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import explain as _explain
from ._io import sprint
from .model import TrainedModel
from .pql import PredictiveTask


@dataclass
class PredictionResult:
    task: PredictiveTask
    predictions: pd.DataFrame          # [entity_id, score] (+ 'label' if evaluated)
    model: TrainedModel
    X: pd.DataFrame                    # scored feature matrix (indexed by entity id)
    metrics: dict = field(default_factory=dict)
    entity_key: str = "entity_id"

    # -- explainability ------------------------------------------------
    def global_importance(self, top_n: int = 10) -> pd.DataFrame:
        return _explain.global_importance(self.model, top_n=top_n)

    def explain(self, entity_id=None, top_n: int = 5):
        """Global driver table (no id) or a per-entity 'join-path card' (with id)."""
        if entity_id is None:
            imp = self.global_importance(top_n=top_n)
            sprint(f"En etkili {len(imp)} surucu (global, gain):")
            for _, r in imp.iterrows():
                path = " -> ".join(r["tables"]) if r["tables"] else r["feature"]
                sprint(f"  * {r['agg'] or ''} {path:<28} {_explain.prettify(r['feature'])}")
            return imp
        score = float(self.predictions.set_index(self.entity_key).loc[entity_id, "score"])
        contribs = _explain.explain_entity(self.model, self.X, entity_id, top_n=top_n)
        sprint(_explain.format_card(entity_id, score, contribs, self.task.task_type))
        return contribs

    def reliability(self, n_bins: int = 10) -> dict:
        """Calibration quality (Brier + ECE) for classification with known labels."""
        if self.task.task_type != "classification" or "label" not in self.predictions.columns:
            return {}
        from .model import reliability as _rel

        df = self.predictions.dropna(subset=["label"])
        if df.empty:
            return {}
        return _rel(df["label"].to_numpy(), df["score"].to_numpy(), n_bins=n_bins)

    # -- convenience ---------------------------------------------------
    def top(self, n: int = 10, ascending: bool = False) -> pd.DataFrame:
        return self.predictions.sort_values("score", ascending=ascending).head(n)

    def head(self, n: int = 5) -> pd.DataFrame:
        return self.predictions.head(n)

    def to_csv(self, path: str) -> None:
        self.predictions.to_csv(path, index=False)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        m = "  ".join(f"{k}={v:.4f}" for k, v in self.metrics.items())
        return (
            f"PredictionResult({self.task.task_type}, n={len(self.predictions)}"
            + (f", {m}" if m else "")
            + ")"
        )
