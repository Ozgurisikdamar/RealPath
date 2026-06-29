"""Vertical-template tests: churn / forecast / fraud (return-risk) end-to-end on the sample DB.

Pins the documented metrics (sample DB, seed 42) with tolerant thresholds so the templates
stay protected against regressions — including the regression (forecast) and multi-hop
(customer return-risk) paths that were previously only smoke-checked by hand.
"""
import math

import pytest

from realpath.pql import parse_pql
from realpath.templates import churn_pql, forecast_pql, fraud_pql


# ---- PQL builders (fast, no DB) -------------------------------------
def test_template_builders_parse():
    churn = parse_pql(churn_pql("customers", "customer_id", "transactions", 30))
    assert churn.task_type == "classification"
    assert churn.target.func == "COUNT" and churn.target.window.end == 30

    fc = parse_pql(forecast_pql("products", "product_id", "transactions", "quantity", 3))
    assert fc.task_type == "regression"
    assert fc.target.func == "SUM" and fc.target.column == "quantity"

    fr = parse_pql(fraud_pql("customers", "customer_id", "returns", 30))
    assert fr.task_type == "classification" and fr.target.table == "returns"

    # ASSUMING segment is carried through
    fr2 = parse_pql(fraud_pql("transactions", "tx_id", "returns", 60, where="transactions.amount > 100"))
    assert any(f.column == "amount" and f.op == ">" for f in fr2.assuming)


# ---- engine template paths (full train+score) -----------------------
def test_churn_template(engine):
    r = engine.churn(entity="customers", event="transactions", horizon_days=30)
    assert r.task.task_type == "classification"
    assert len(r.predictions) > 1000
    assert "label" in r.predictions.columns          # evaluated against ground truth
    assert "accuracy" in r.metrics
    assert r.metrics["roc_auc"] > 0.70               # ~0.749 on the sample DB


def test_forecast_template_regression(engine):
    r = engine.forecast(entity="products", event="transactions", column="quantity", horizon_months=3)
    assert r.task.task_type == "regression"
    assert "mae" in r.metrics and "rmse" in r.metrics
    assert math.isfinite(r.metrics["mae"]) and r.metrics["mae"] > 0   # ~8.4


def test_fraud_return_risk_2hop(engine):
    # customer-level return risk exercises a 2-hop join: customers <- transactions <- returns
    path = engine.schema.join_path("customers", "returns")
    assert path is not None and len(path) == 2

    r = engine.fraud(entity="customers", event="returns", horizon_days=30)
    assert r.task.task_type == "classification"
    assert "roc_auc" in r.metrics
    assert r.metrics["roc_auc"] > 0.60               # ~0.689 on the sample DB


# ---- NL -> PQL offline routing (no API key) -------------------------
@pytest.mark.parametrize(
    "question,expect_entity,expect_target,expect_type",
    [
        ("gelecek 30 gunde islem yapmayacak musteriler", "customers", "transactions", "classification"),
        ("her urun icin onumuzdeki talebi tahmin et", "products", "transactions", "regression"),
        ("hangi musteriler iade yapacak", "customers", "returns", "classification"),
    ],
)
def test_nl_offline_routing(engine, question, expect_entity, expect_target, expect_type):
    nl = engine.ask(question)
    assert nl.source == "template"                   # no ANTHROPIC_API_KEY -> offline fallback
    task = parse_pql(nl.pql)                          # must be valid PQL
    assert task.entity_table == expect_entity
    assert task.target.table == expect_target
    assert task.task_type == expect_type


def test_predict_auto_detects_pql(engine):
    # a string starting with PREDICT is treated as PQL (not sent to the NL path)
    r = engine.predict(
        "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id",
        evaluate=False,
    )
    assert r.task.task_type == "classification"
    assert len(r.predictions) > 1000
