"""Vertical templates — pre-packaged predictive questions as parametrized PQL.

These turn a domain problem into a one-liner so users never start from a blank page.
The :class:`~realpath.engine.Engine` exposes them as ``engine.churn(...)`` etc.; here they
are also available as plain PQL builders for the CLI and for inspection.
"""
from __future__ import annotations

TEMPLATES = {
    "churn": {
        "desc": "Entities with no activity in the next window (e.g. customers who stop buying).",
        "params": ["entity", "key", "event", "horizon_days"],
    },
    "forecast": {
        "desc": "Total of a numeric column over a future window (e.g. demand per product).",
        "params": ["entity", "key", "event", "column", "horizon_months"],
    },
    "fraud": {
        "desc": "Probability an entity triggers a flagged event soon (e.g. returns/chargebacks).",
        "params": ["entity", "key", "event", "horizon_days", "where"],
    },
}


def churn_pql(entity: str, key: str, event: str, horizon_days: int = 30) -> str:
    return f"PREDICT COUNT({event}.*, 0, {horizon_days}, days) == 0 FOR EACH {entity}.{key}"


def forecast_pql(entity: str, key: str, event: str, column: str, horizon_months: int = 3) -> str:
    return f"PREDICT SUM({event}.{column}, 0, {horizon_months}, months) FOR EACH {entity}.{key}"


def fraud_pql(entity: str, key: str, event: str, horizon_days: int = 60, where: str | None = None) -> str:
    pql = f"PREDICT COUNT({event}.*, 0, {horizon_days}, days) > 0 FOR EACH {entity}.{key}"
    if where:
        pql += f" ASSUMING {where}"
    return pql
