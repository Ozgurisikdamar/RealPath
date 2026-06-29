"""The high-level engine — ties connect → schema → PQL → features → model → explain.

    import relpath as rp
    engine = rp.connect("data/shop.duckdb")
    result = engine.predict("PREDICT COUNT(transactions.*, 0, 30, days) == 0 "
                            "FOR EACH customers.customer_id")
    result.explain()                 # global drivers
    result.explain(entity_id=4471)   # why this customer
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import features as _features
from . import nlp as _nlp
from .connect import DuckDBBackend, open_backend
from .model import fit_model
from .pql import PredictiveTask, compile_task, parse_pql
from .result import PredictionResult
from .schema import RelationalSchema, build_entityset, infer_schema


class Engine:
    def __init__(self, backend: DuckDBBackend, schema: RelationalSchema, name: str = "db"):
        self.backend = backend
        self.schema = schema
        self.name = name
        self._es = None

    # lazily build the EntitySet (loads tables into memory)
    @property
    def es(self):
        if self._es is None:
            self._es = build_entityset(self.backend, self.schema, name=self.name)
        return self._es

    # -- introspection -------------------------------------------------
    def describe(self) -> str:
        return self.schema.describe()

    def ask(self, question: str) -> _nlp.NLResult:
        """Translate a natural-language question to PQL (no execution)."""
        return _nlp.nl_to_pql(question, self.schema)

    # -- prediction ----------------------------------------------------
    def predict(
        self,
        query: str | PredictiveTask,
        max_depth: int = 2,
        evaluate: bool = True,
        verbose: bool = False,
        calibrate: bool = False,
    ) -> PredictionResult:
        task = self._to_task(query)
        compiled = compile_task(task, self.schema, self.backend)
        train_anchor, test_anchor = compiled.default_anchors()
        if verbose:
            print(f"[relpath] {task}")
            print(f"[relpath] anchors: train={train_anchor.date()} test={test_anchor.date()}")

        # TRAIN: features (cutoff <= train_anchor) + labels (future window)
        train_split = compiled.build_split(train_anchor)
        train_fm = _features.synthesize(self.es, self.schema, task.entity_table,
                                        train_split.cutoff, max_depth=max_depth)
        Xtr, ytr = _features.align_xy(train_fm, train_split.labels)
        if verbose:
            print(f"[relpath] train: {Xtr.shape[0]} rows × {Xtr.shape[1]} features")
        model = fit_model(Xtr, ytr, task.task_type, calibrate=calibrate)

        # SCORE: features at test_anchor → predictions (+ eval vs ground truth)
        test_split = compiled.build_split(test_anchor)
        test_fm = _features.synthesize(self.es, self.schema, task.entity_table,
                                       test_split.cutoff, max_depth=max_depth)
        Xte = test_fm.X.reindex(columns=Xtr.columns)
        scores = model.predict(Xte)

        preds = pd.DataFrame({task.entity_key: Xte.index.to_numpy(), "score": scores})
        metrics = {}
        if evaluate:
            common = Xte.index.intersection(test_split.labels.index)
            y_true = test_split.labels.loc[common]
            y_pred = pd.Series(scores, index=Xte.index).loc[common]
            label_df = test_split.labels.rename("label")
            label_df.index.name = task.entity_key
            preds = preds.merge(label_df.reset_index(), on=task.entity_key, how="left")
            metrics = _metrics(task.task_type, y_true.to_numpy(), y_pred.to_numpy())

        return PredictionResult(
            task=task, predictions=preds, model=model, X=Xte,
            metrics=metrics, entity_key=task.entity_key,
        )

    # -- vertical templates -------------------------------------------
    def churn(self, entity: str, event: str, horizon_days: int = 30, **kw) -> PredictionResult:
        pk = self.schema.tables[entity].primary_key
        pql = f"PREDICT COUNT({event}.*, 0, {horizon_days}, days) == 0 FOR EACH {entity}.{pk}"
        return self.predict(pql, **kw)

    def forecast(self, entity: str, event: str, column: str, horizon_months: int = 3, **kw) -> PredictionResult:
        pk = self.schema.tables[entity].primary_key
        pql = f"PREDICT SUM({event}.{column}, 0, {horizon_months}, months) FOR EACH {entity}.{pk}"
        return self.predict(pql, **kw)

    def fraud(self, entity: str, event: str, horizon_days: int = 60, where: str | None = None, **kw) -> PredictionResult:
        pk = self.schema.tables[entity].primary_key
        pql = f"PREDICT COUNT({event}.*, 0, {horizon_days}, days) > 0 FOR EACH {entity}.{pk}"
        if where:
            pql += f" ASSUMING {where}"
        return self.predict(pql, **kw)

    # -- helpers -------------------------------------------------------
    def _to_task(self, query: str | PredictiveTask) -> PredictiveTask:
        if isinstance(query, PredictiveTask):
            return query
        text = query.strip()
        if text.upper().startswith("PREDICT"):
            return parse_pql(text)
        # natural language
        nl = self.ask(text)
        task = parse_pql(nl.pql)
        task.raw = f"{text}  ⟶  {nl.pql}  [{nl.source}]"
        return task

    def close(self) -> None:
        self.backend.close()


def connect(source: str, name: str = "db") -> Engine:
    """Open a database and infer its relational schema. Local-first: nothing leaves the box."""
    backend = open_backend(source)
    schema = infer_schema(backend)
    return Engine(backend, schema, name=name)


# -- metrics -----------------------------------------------------------
def _metrics(task_type: str, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    from sklearn.metrics import (
        accuracy_score,
        mean_absolute_error,
        mean_squared_error,
        roc_auc_score,
    )

    if task_type == "classification":
        out = {}
        if len(np.unique(y_true)) > 1:
            out["roc_auc"] = float(roc_auc_score(y_true, y_pred))
        out["accuracy"] = float(accuracy_score(y_true, (y_pred >= 0.5).astype(int)))
        return out
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    return {"mae": float(mean_absolute_error(y_true, y_pred)), "rmse": rmse}
