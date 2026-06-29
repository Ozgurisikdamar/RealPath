"""PQL parser unit tests."""
import pytest

from realpath.pql import PQLSyntaxError, parse_pql


def test_churn_classification():
    t = parse_pql("PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id")
    assert t.task_type == "classification"
    assert t.target.func == "COUNT"
    assert t.target.table == "transactions"
    assert t.target.column is None
    assert (t.target.window.start, t.target.window.end, t.target.window.unit) == (0, 30, "days")
    assert t.comparison.op == "==" and t.comparison.value == 0.0
    assert t.entity_table == "customers" and t.entity_key == "customer_id"


def test_forecast_regression():
    t = parse_pql("PREDICT SUM(transactions.quantity, 0, 3, months) FOR EACH products.product_id")
    assert t.task_type == "regression"
    assert t.target.func == "SUM" and t.target.column == "quantity"
    assert t.comparison is None
    assert t.target.window.unit == "months"


def test_mean_alias_and_where_assuming():
    t = parse_pql(
        "PREDICT COUNT(returns.*, 0, 60, days) > 0 FOR EACH transactions.tx_id "
        "WHERE returns.reason == 'defective' ASSUMING transactions.amount > 1000"
    )
    assert t.comparison.op == ">"
    assert any(f.column == "reason" and f.value == "defective" for f in t.where)
    assert any(f.column == "amount" and f.op == ">" and f.value == 1000 for f in t.assuming)


def test_window_horizon_days():
    t = parse_pql("PREDICT SUM(transactions.amount, 0, 2, months) FOR EACH customers.customer_id")
    assert t.target.window.horizon_days == 60


@pytest.mark.parametrize("bad", [
    "",
    "SELECT * FROM customers",
    "PREDICT COUNT(transactions.*, 0, 30, days)",          # missing FOR EACH
    "PREDICT FROOB(transactions.*, 0, 30, days) FOR EACH customers.customer_id",  # bad agg
    "PREDICT SUM(transactions.*, 0, 3, months) FOR EACH products.product_id",     # SUM needs a column
    "PREDICT COUNT(transactions.*, 0, 30, fortnights) FOR EACH customers.id",     # bad unit
])
def test_invalid_pql_raises(bad):
    with pytest.raises((PQLSyntaxError, ValueError)):
        parse_pql(bad)
