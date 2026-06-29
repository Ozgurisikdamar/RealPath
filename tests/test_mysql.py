"""MySQL connector test — proves the engine is backend-agnostic (DuckDB/Postgres/MySQL).

Opt-in: set ``RELPATH_TEST_MYSQL`` to a ``mysql://`` DSN whose database has the sample schema
loaded (``python data/load_mysql.py <dsn>``). Skipped otherwise, so CI doesn't need MySQL.

    docker run -d --name relpath-mysql -e MYSQL_ROOT_PASSWORD=relpath -e MYSQL_DATABASE=shop \
        -p 33060:3306 mysql:8
    python data/load_mysql.py mysql://root:relpath@localhost:33060/shop
    set RELPATH_TEST_MYSQL=mysql://root:relpath@localhost:33060/shop
    pytest tests/test_mysql.py -q
"""
import os

import pytest

MY_DSN = os.environ.get("RELPATH_TEST_MYSQL")
pytestmark = pytest.mark.skipif(
    not MY_DSN, reason="set RELPATH_TEST_MYSQL to a mysql:// DSN (with sample data) to run"
)


def test_mysql_schema_inference_and_churn():
    import relpath as rp

    eng = rp.connect(MY_DSN)
    try:
        schema = eng.schema
        assert {"customers", "products", "transactions", "returns"} <= set(schema.tables)
        assert schema.tables["customers"].primary_key == "customer_id"
        assert schema.tables["transactions"].time_index == "tx_time"
        assert schema.join_path("customers", "returns") is not None  # 2-hop FK path

        r = eng.churn(entity="customers", event="transactions", horizon_days=30)
        assert r.task.task_type == "classification"
        assert r.metrics["roc_auc"] > 0.70
    finally:
        eng.close()
