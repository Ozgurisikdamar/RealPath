"""Load the synthetic e-commerce sample into a PostgreSQL database (for testing the
Postgres connector). Reads the tables from the local DuckDB sample so the data is identical.

Usage:
    python data/load_postgres.py "postgresql://postgres:realpath@localhost:55432/shop"
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

DDL = {
    "customers": "(customer_id BIGINT PRIMARY KEY, signup_date TIMESTAMP, country VARCHAR, segment VARCHAR)",
    "products": "(product_id BIGINT PRIMARY KEY, category VARCHAR, brand VARCHAR, price DOUBLE PRECISION)",
    "transactions": "(tx_id BIGINT PRIMARY KEY, customer_id BIGINT, product_id BIGINT, "
                    "tx_time TIMESTAMP, quantity INTEGER, amount DOUBLE PRECISION)",
    "returns": "(return_id BIGINT PRIMARY KEY, tx_id BIGINT, return_time TIMESTAMP, reason VARCHAR)",
}


def _py(v):
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return None if np.isnan(v) else float(v)
    return v


def load(dsn: str, duckdb_path: str = "data/shop.duckdb") -> None:
    import duckdb
    import psycopg

    src = duckdb.connect(duckdb_path, read_only=True)
    pg = psycopg.connect(dsn)
    pg.autocommit = True
    cur = pg.cursor()
    for table, ddl in DDL.items():
        df = src.execute(f"SELECT * FROM {table}").df()
        cols = list(df.columns)
        collist = ",".join(f'"{c}"' for c in cols)
        cur.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
        cur.execute(f'CREATE TABLE "{table}" {ddl}')
        with cur.copy(f'COPY "{table}" ({collist}) FROM STDIN') as copy:
            for rec in df.itertuples(index=False, name=None):
                copy.write_row(tuple(_py(v) for v in rec))
        print(f"loaded {table}: {len(df)} rows")
    pg.close()
    src.close()


if __name__ == "__main__":
    dsn = sys.argv[1] if len(sys.argv) > 1 else "postgresql://postgres:realpath@localhost:55432/shop"
    load(dsn)
    print("done")
