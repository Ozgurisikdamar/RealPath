"""Explainability — *which join path drove this prediction*.

Because DFS feature names already encode the relational provenance
(``SUM(transactions.amount)`` ⇒ table ``transactions``, aggregation ``SUM``), we can turn
model importance into a human-readable account — globally (what matters in general) and
locally per entity (why *this* row). This is the structural edge over embedding-based
models, whose attributions are not human-readable join paths (§7 of the spec).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .model import TrainedModel

_AGG_RE = re.compile(r"^([A-Z_]+)\(")
_TABLE_RE = re.compile(r"([A-Za-z_]\w*)\.")


@dataclass
class Contribution:
    feature: str
    value: object
    weight: float          # gain (global) or shap (local)
    tables: list[str]
    agg: str | None


def provenance(name: str) -> tuple[list[str], str | None]:
    """Extract (tables, top-level aggregation) referenced by a DFS feature name."""
    agg_m = _AGG_RE.match(name)
    agg = agg_m.group(1) if agg_m else None
    tables = list(dict.fromkeys(_TABLE_RE.findall(name)))
    return tables, agg


def prettify(name: str) -> str:
    tables, agg = provenance(name)
    if agg and tables:
        return f"{agg} over {', '.join(tables)}  ·  {name}"
    return name


def global_importance(model: TrainedModel, top_n: int = 10) -> pd.DataFrame:
    imp = model.importance()
    if imp.empty:
        return pd.DataFrame(columns=["feature", "gain", "tables", "agg"])
    rows = []
    for feat, gain in imp.head(top_n).items():
        tables, agg = provenance(feat)
        rows.append({"feature": feat, "gain": float(gain), "tables": tables, "agg": agg})
    return pd.DataFrame(rows)


def explain_entity(
    model: TrainedModel,
    X: pd.DataFrame,
    entity_id,
    top_n: int = 5,
) -> list[Contribution]:
    """Top local contributions for one entity (SHAP if available, else gain-weighted)."""
    if entity_id not in X.index:
        return []
    row = X.loc[[entity_id]]
    Xt = model.preprocessor.transform(row)

    shap_vals = _shap_row(model, Xt)
    contribs: list[Contribution] = []
    if shap_vals is not None:
        order = np.argsort(-np.abs(shap_vals))[:top_n]
        for j in order:
            feat = model.feature_names[j]
            tables, agg = provenance(feat)
            contribs.append(Contribution(feat, _scalar(Xt.iloc[0, j]), float(shap_vals[j]), tables, agg))
        return contribs

    # fallback: global gain weighting (no per-row attribution available)
    imp = model.importance().head(top_n)
    for feat, gain in imp.items():
        tables, agg = provenance(feat)
        val = _scalar(Xt.iloc[0][feat]) if feat in Xt.columns else None
        contribs.append(Contribution(feat, val, float(gain), tables, agg))
    return contribs


def _shap_row(model: TrainedModel, Xt: pd.DataFrame):
    if model.constant is not None or model.estimator is None:
        return None
    try:
        import shap
    except Exception:
        return None
    try:
        explainer = shap.TreeExplainer(model.estimator)
        vals = explainer.shap_values(Xt)
        if isinstance(vals, list):  # older shap: list per class
            vals = vals[-1]
        vals = np.asarray(vals)
        if vals.ndim == 3:          # (n, features, classes)
            vals = vals[:, :, -1]
        return vals[0]
    except Exception:
        return None


def _scalar(v):
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return round(float(v), 4)
    return v


def format_card(entity_id, score: float, contribs: list[Contribution], task_type: str) -> str:
    head = "probability" if task_type == "classification" else "predicted value"
    lines = [f"entity {entity_id} -- {head} {score:.3f}"]
    for i, c in enumerate(contribs):
        branch = "`-" if i == len(contribs) - 1 else "|-"
        path = " -> ".join(c.tables) if c.tables else c.feature
        sign = "+" if c.weight >= 0 else "-"
        lines.append(
            f"  {branch} {path}: {c.agg or ''} = {c.value}   "
            f"katki {sign}{abs(c.weight):.3f}"
        )
    return "\n".join(lines)
