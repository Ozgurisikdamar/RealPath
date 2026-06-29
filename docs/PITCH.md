# realpath.dev — One-Page Pitch

**The open-source, self-hostable, local-first relational prediction engine.**
Connect a database, ask a predictive question in plain language, get an *explained* answer —
without moving your data anywhere.

---

## The problem

The world's most valuable data is **relational** — spread across dozens of tables joined by
primary/foreign keys (customers, transactions, returns…). But mainstream ML tools (XGBoost,
LightGBM) only see **one flat table**. Closing that gap is months of hand-written SQL `JOIN` +
`GROUP BY` "feature engineering" — expensive, slow, repeated for every new question.

## The solution

realpath connects to your database, **auto-discovers the foreign-key graph**, compiles your
predictive question (plain language → **PQL**) into leakage-safe features, trains a model, and
explains **which join path drove the answer** — all locally.

```python
engine = realpath.connect("postgresql://…")     # or DuckDB / MySQL — same result
engine.predict("which customers will churn in the next 30 days").explain()
```

## Why us, not Kumo.AI (the category leader)

Kumo defined this category but is **closed, sales-led, warehouse-locked, opaque-priced, with no
on-prem/air-gap and only correlational explanations.** Those are structural gaps. Our four moats:

1. 🔓 **Open-source + self-host + local-first** — runs on your laptop (DuckDB), data never leaves.
2. 🗣️ **Natural language → PQL** — ask in plain English/Turkish, validated before it runs.
3. 🔎 **Explainability** — human-readable join-path provenance, not embedding black boxes.
4. 📦 **Vertical templates** — churn / forecast / fraud in one line.

## Who it's for

Data scientists & ML engineers (kill the feature-engineering tax) · indie/startup devs (cheap,
no GPU) · **regulated sectors** (healthcare, public, finance) that require self-host / privacy /
explainability.

## What's already real (not slideware)

Working PoC: **3 verified backends** (DuckDB/Postgres/MySQL, identical results) · churn ROC-AUC
**0.749** (+0.045 over baseline) · NL→PQL · calibration · explainability · RelBench harness ·
GNN backend (code-verified) · **25/25 tests**, CI, full docs. See [BENCHMARKS.md](BENCHMARKS.md).

## Business model (open-core)

MIT core forever (engine, connectors, CLI, demo). Commercial later: managed/hosted service,
warehouse **managed** connectors (Snowflake/BigQuery), team/governance, support. See
[DECISIONS.md](DECISIONS.md) BD-002.

## Call to action

⭐ Star the repo · try the **NL→PQL demo** · `pip install realpath` and predict on your own DB in
60 seconds. *"The end of feature-engineering hell — open-source, on your machine."*
