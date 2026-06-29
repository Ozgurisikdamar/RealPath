"""Load the synthetic e-commerce sample into a MySQL database (for testing the MySQL
connector). Reads the tables from the local DuckDB sample so the data is identical.

Usage:
    python data/load_mysql.py "mysql://root:realpath@localhost:33060/shop"
"""
from __future__ import annotations

import sys
from urllib.parse import unquote, urlparse

import numpy as np
import pandas as pd

DDL = {
    "customers": "(customer_id BIGINT PRIMARY KEY, signup_date DATETIME, "
                 "country VARCHAR(255), segment VARCHAR(255))",
    "products": "(product_id BIGINT PRIMARY KEY, category VARCHAR(255), "
                "brand VARCHAR(255), price DOUBLE)",
    "transactions": "(tx_id BIGINT PRIMARY KEY, customer_id BIGINT, product_id BIGINT, "
                    "tx_time DATETIME, quantity INT, amount DOUBLE)",
    "returns": "(return_id BIGINT PRIMARY KEY, tx_id BIGINT, return_time DATETIME, "
               "reason VARCHAR(255))",
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
    import pymysql

    u = urlparse(dsn)
    src = duckdb.connect(duckdb_path, read_only=True)
    my = pymysql.connect(
        host=u.hostname or "localhost", port=u.port or 3306,
        user=unquote(u.username) if u.username else "root",
        password=unquote(u.password) if u.password else "",
        database=(u.path or "").lstrip("/"), autocommit=True,
    )
    cur = my.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for table, ddl in DDL.items():
        df = src.execute(f"SELECT * FROM {table}").df()
        cols = list(df.columns)
        cur.execute(f"DROP TABLE IF EXISTS `{table}`")
        cur.execute(f"CREATE TABLE `{table}` {ddl}")
        collist = ",".join(f"`{c}`" for c in cols)
        ph = ",".join(["%s"] * len(cols))
        rows = [tuple(_py(v) for v in rec) for rec in df.itertuples(index=False, name=None)]
        cur.executemany(f"INSERT INTO `{table}` ({collist}) VALUES ({ph})", rows)
        print(f"loaded {table}: {len(df)} rows")
    my.close()
    src.close()


if __name__ == "__main__":
    dsn = sys.argv[1] if len(sys.argv) > 1 else "mysql://root:realpath@localhost:33060/shop"
    load(dsn)
    print("done")
