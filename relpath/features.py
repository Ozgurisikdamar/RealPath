"""Automatic feature synthesis (leakage-safe).

We hand the relational ``EntitySet`` to Featuretools' Deep Feature Synthesis (DFS) with a
``cutoff_time`` per entity. That is the structural guarantee from §6 of the spec: DFS only
aggregates rows with ``time <= cutoff``, so no future information enters a feature.

The resulting feature *names* (e.g. ``SUM(transactions.amount)``) are human-readable join
paths — which is exactly what powers the explainability layer (``explain.py``).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .schema import RelationalSchema

# A deliberately small, fast primitive set — enough signal, bounded feature explosion.
AGG_PRIMITIVES = ["count", "sum", "mean", "max", "min", "std", "num_unique"]
TRANS_PRIMITIVES = ["month", "weekday"]


@dataclass
class FeatureMatrix:
    X: pd.DataFrame                  # indexed by entity id
    definitions: dict[str, str]      # feature name -> readable definition
    cutoff_time: pd.Timestamp | None


def _ignore_columns(schema: RelationalSchema) -> dict[str, list[str]]:
    """Keep ids and unresolved text out of the feature search (avoid id leakage)."""
    out: dict[str, list[str]] = {}
    for t in schema.tables.values():
        drop = [c.name for c in t.columns if c.role in ("pk", "fk", "text")]
        if drop:
            out[t.name] = drop
    return out


def synthesize(
    es,
    schema: RelationalSchema,
    target_table: str,
    cutoff: pd.DataFrame,
    max_depth: int = 2,
) -> FeatureMatrix:
    import featuretools as ft

    anchor = pd.Timestamp(cutoff["time"].iloc[0]) if len(cutoff) else None

    fm, fdefs = ft.dfs(
        entityset=es,
        target_dataframe_name=target_table,
        cutoff_time=cutoff,
        agg_primitives=AGG_PRIMITIVES,
        trans_primitives=TRANS_PRIMITIVES,
        ignore_columns=_ignore_columns(schema),
        max_depth=max_depth,
        verbose=False,
    )
    # DFS may return a (instance, time) MultiIndex — collapse to the entity id.
    if isinstance(fm.index, pd.MultiIndex):
        fm.index = fm.index.get_level_values(0)
    fm = fm.sort_index()
    definitions = {f.get_name(): f.get_name() for f in fdefs}
    return FeatureMatrix(X=fm, definitions=definitions, cutoff_time=anchor)


def align_xy(fm: FeatureMatrix, labels: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """Align a feature matrix and a label series on entity id (inner join)."""
    common = fm.X.index.intersection(labels.index)
    X = fm.X.loc[common]
    y = labels.loc[common]
    return X, y
