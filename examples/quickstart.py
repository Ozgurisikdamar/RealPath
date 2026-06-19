"""relpath quickstart — connect, ask, predict, explain. Local-first, ~10 lines.

Run:
    python data/make_sample_db.py          # once, to create data/shop.duckdb
    python examples/quickstart.py
"""
import warnings

warnings.filterwarnings("ignore")

import relpath as rp

# 1) Connect to a local database. Nothing leaves your machine.
engine = rp.connect("data/shop.duckdb")
print(engine.describe())

# 2) Ask in plain language -> PQL (uses Claude if ANTHROPIC_API_KEY is set, else offline templates)
nl = engine.ask("gelecek 30 günde işlem yapmayacak müşterileri bul")
print(f"\nNL -> PQL [{nl.source}]: {nl.pql}\n")

# 3) Predict (PQL or natural language both work)
result = engine.predict(nl.pql)
print("metrics:", result.metrics)
print(result.top(5).to_string(index=False))

# 4) Explain — globally and for one entity (the join paths that drove the score)
print("\n--- global drivers ---")
result.explain(top_n=5)

top_customer = result.top(1).iloc[0][result.entity_key]
print("\n--- why this customer? ---")
result.explain(entity_id=top_customer, top_n=5)

# 5) Templates: churn / forecast / fraud as one-liners
print("\n--- demand forecast (regression) ---")
fc = engine.forecast(entity="products", event="transactions", column="quantity", horizon_months=2)
print("metrics:", fc.metrics)
