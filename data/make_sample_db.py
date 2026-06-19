"""Generate a small, fully synthetic e-commerce database as a local DuckDB file.

Zero external downloads — this is what makes the relpath demo *local-first*: you can
run the whole engine end-to-end with nothing but this generated file.

Schema (a classic multi-table relational shape):

    customers(customer_id PK, signup_date, country, segment)
        |                                   ^
        | (customer_id FK)                  |
        v                                   |
    transactions(tx_id PK, customer_id FK, product_id FK, tx_time, quantity, amount)
        ^                                   |
        | (tx_id FK)                        | (product_id FK)
        |                                   v
    returns(return_id PK, tx_id FK,     products(product_id PK, category, brand, price)
            return_time, reason)

The data has *learnable temporal structure* on purpose: a customer's recent activity
(spend, frequency, returns) genuinely predicts whether they churn — so a feature-aware
model should beat a no-feature baseline, which is the point we want to demonstrate.

Usage:
    python data/make_sample_db.py [output_path]
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START = datetime(2024, 1, 1)
DAYS = 545  # ~18 months of history
N_CUSTOMERS = 1200
N_PRODUCTS = 220


def _make_customers(rng: np.random.Generator) -> pd.DataFrame:
    countries = np.array(["TR", "DE", "US", "GB", "NL"])
    segments = np.array(["new", "casual", "loyal", "vip"])
    signup_offset = rng.integers(0, DAYS - 90, size=N_CUSTOMERS)
    return pd.DataFrame(
        {
            "customer_id": np.arange(1, N_CUSTOMERS + 1),
            "signup_date": [START + timedelta(days=int(o)) for o in signup_offset],
            "country": rng.choice(countries, size=N_CUSTOMERS, p=[0.4, 0.2, 0.2, 0.1, 0.1]),
            "segment": rng.choice(segments, size=N_CUSTOMERS, p=[0.35, 0.35, 0.2, 0.1]),
        }
    )


def _make_products(rng: np.random.Generator) -> pd.DataFrame:
    categories = np.array(["apparel", "shoes", "accessories", "home", "beauty"])
    brands = np.array([f"brand_{i}" for i in range(1, 16)])
    return pd.DataFrame(
        {
            "product_id": np.arange(1, N_PRODUCTS + 1),
            "category": rng.choice(categories, size=N_PRODUCTS),
            "brand": rng.choice(brands, size=N_PRODUCTS),
            "price": np.round(rng.gamma(shape=2.0, scale=25.0, size=N_PRODUCTS) + 5, 2),
        }
    )


def _make_transactions(rng, customers, products):
    """Each customer has a latent 'engagement' that decays over time; high-engagement
    customers transact more often and later (i.e. they don't churn)."""
    rows = []
    tx_id = 1
    base_rate = {"new": 0.6, "casual": 1.0, "loyal": 2.2, "vip": 4.0}
    prod_ids = products["product_id"].to_numpy()
    prod_price = dict(zip(products["product_id"], products["price"]))

    for _, c in customers.iterrows():
        cid = int(c["customer_id"])
        signup = c["signup_date"]
        # latent engagement and a churn point: after t_churn the customer goes quiet
        engagement = base_rate[c["segment"]] * rng.uniform(0.5, 1.5)
        active_days = (START + timedelta(days=DAYS) - signup).days
        # ~45% of customers "churn" at some random point; the rest stay active
        if rng.random() < 0.45:
            churn_day = rng.integers(30, max(31, active_days))
        else:
            churn_day = active_days + 1  # never churns within window
        # number of transactions ~ Poisson over active period
        expected = engagement * (min(churn_day, active_days) / 30.0)
        n_tx = rng.poisson(max(0.2, expected))
        for _ in range(int(n_tx)):
            day = rng.integers(0, max(1, min(churn_day, active_days)))
            tx_time = signup + timedelta(days=int(day), hours=int(rng.integers(0, 24)))
            pid = int(rng.choice(prod_ids))
            qty = int(rng.integers(1, 4))
            unit = prod_price[pid] * rng.uniform(0.9, 1.1)
            rows.append(
                {
                    "tx_id": tx_id,
                    "customer_id": cid,
                    "product_id": pid,
                    "tx_time": tx_time,
                    "quantity": qty,
                    "amount": round(unit * qty, 2),
                }
            )
            tx_id += 1
    tx = pd.DataFrame(rows)
    tx = tx.sort_values("tx_time").reset_index(drop=True)
    return tx


def _make_returns(rng, transactions, cust_propensity):
    """Returns carry a *learnable* per-customer signal: every customer has a hidden
    'return propensity', so a customer who returned a lot in the past keeps returning —
    which makes future return-risk predictable from history. Higher-amount transactions
    are also slightly more return-prone."""
    reasons = np.array(["size", "defective", "changed_mind", "late"])
    n = len(transactions)
    amount_factor = transactions["amount"].to_numpy() / transactions["amount"].max() * 0.15
    prop = transactions["customer_id"].map(cust_propensity).to_numpy()
    prob = np.clip(0.02 + 0.55 * prop + amount_factor, 0, 0.85)
    mask = rng.random(n) < prob
    sub = transactions[mask]
    delay = rng.integers(1, 21, size=len(sub))
    return pd.DataFrame(
        {
            "return_id": np.arange(1, len(sub) + 1),
            "tx_id": sub["tx_id"].to_numpy(),
            "return_time": [t + timedelta(days=int(d)) for t, d in zip(sub["tx_time"], delay)],
            "reason": rng.choice(reasons, size=len(sub)),
        }
    )


def build(output_path: str | Path = "data/shop.duckdb") -> Path:
    import duckdb

    rng = np.random.default_rng(SEED)
    customers = _make_customers(rng)
    products = _make_products(rng)
    transactions = _make_transactions(rng, customers, products)
    # hidden per-customer "return propensity" (a latent trait, not stored as a column)
    cust_propensity = dict(
        zip(customers["customer_id"], rng.beta(1.4, 6.0, size=len(customers)))
    )
    returns = _make_returns(rng, transactions, cust_propensity)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    con = duckdb.connect(str(output_path))
    for name, df in [
        ("customers", customers),
        ("products", products),
        ("transactions", transactions),
        ("returns", returns),
    ]:
        con.register("df_tmp", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df_tmp")
        con.unregister("df_tmp")
    con.close()

    print(f"Wrote {output_path}")
    print(
        f"  customers={len(customers)}  products={len(products)}  "
        f"transactions={len(transactions)}  returns={len(returns)}"
    )
    return output_path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "data/shop.duckdb"
    build(out)
