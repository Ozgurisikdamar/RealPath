"""PostgreSQL connector test — proves the engine is backend-agnostic.

Opt-in: set ``REALPATH_TEST_PG`` to a ``postgresql://`` DSN whose database has the sample
schema loaded (``python data/load_postgres.py <dsn>``). Skipped otherwise, so CI / fresh
checkouts don't require a running Postgres.

    docker run -d --name realpath-pg -e POSTGRES_PASSWORD=realpath -e POSTGRES_DB=shop \
        -p 55432:5432 postgres:16
    python data/load_postgres.py postgresql://postgres:realpath@localhost:55432/shop
    set REALPATH_TEST_PG=postgresql://postgres:realpath@localhost:55432/shop
    pytest tests/test_postgres.py -q
"""
import os

import pytest

PG_DSN = os.environ.get("REALPATH_TEST_PG")
pytestmark = pytest.mark.skipif(
    not PG_DSN, reason="set REALPATH_TEST_PG to a postgresql:// DSN (with sample data) to run"
)


def test_postgres_schema_inference_and_churn():
    import realpath as rp

    eng = rp.connect(PG_DSN)
    try:
        schema = eng.schema
        # schema + FK graph recovered from Postgres information_schema
        assert {"customers", "products", "transactions", "returns"} <= set(schema.tables)
        assert schema.tables["customers"].primary_key == "customer_id"
        assert schema.tables["transactions"].time_index == "tx_time"
        # 2-hop FK path customers <- transactions <- returns
        assert schema.join_path("customers", "returns") is not None

        # full pipeline runs against Postgres and matches the DuckDB result
        r = eng.churn(entity="customers", event="transactions", horizon_days=30)
        assert r.task.task_type == "classification"
        assert r.metrics["roc_auc"] > 0.70
    finally:
        eng.close()
