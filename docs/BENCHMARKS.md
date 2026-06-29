# relpath.dev — Benchmarks & Verified Results

All numbers below were **measured** (not vendor-claimed) on this codebase. Each row lists how to
reproduce it. Synthetic sample DB = `data/make_sample_db.py` (seed 42, deterministic).

> Test suite: **25 passed, 2 skipped** (the 2 skips are the opt-in Postgres/MySQL connector
> tests; run them with `RELPATH_TEST_PG` / `RELPATH_TEST_MYSQL`). `pytest tests/ -q`.

---

## 1. Backend parity — DuckDB = PostgreSQL = MySQL

The engine is **backend-agnostic**: the same churn task gives the **identical** result on all
three backends (same data, same pipeline).

| Backend | Churn ROC-AUC | How |
|---|---|---|
| DuckDB (default) | **0.7492** | `relpath predict "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id" --db data/shop.duckdb` |
| PostgreSQL (`postgres` extra) | **0.7492** | `data/load_postgres.py` → `connect("postgresql://...")` (Docker `postgres:16`) |
| MySQL (`mysql` extra) | **0.7492** | `data/load_mysql.py` → `connect("mysql://...")` (Docker `mysql:8`) |

---

## 2. Relational features beat a no-feature baseline

The core claim: cross-table feature synthesis (DFS) adds real signal vs entity-own columns only.

| Görev | Metrik | relpath (full relational) | Baseline (entity-only) | Δ |
|---|---|---|---|---|
| Churn (classification) | ROC-AUC | **0.7492** | 0.7043 | **+0.045** |

Reproduce: `python -m relpath.eval` → "relational features HELP".

---

## 3. Vertical templates (sample DB)

| Template | Type | Metric | Note |
|---|---|---|---|
| `churn` | classification | ROC-AUC **0.749** | acc 0.737 |
| `fraud` (customer return-risk, **2-hop join**) | classification | ROC-AUC **0.689** | 30d window (60d 0.699, 90d 0.690) |
| `forecast` (3-month `SUM(quantity)`) | regression | MAE **8.41** | rmse 10.1; *no relational lift on this synthetic data — churn is the headline* |

---

## 4. Probability calibration (opt-in)

Isotonic calibration on a held-out slice. ROC-AUC preserved (monotonic), probabilities improved.

| | ECE | Brier |
|---|---|---|
| uncalibrated | 0.0325 | 0.0411 |
| **calibrated** | **0.0144** | **0.0392** |

Reproduce: `relpath predict "..." --db data/shop.duckdb --calibrate` (prints Brier/ECE).

---

## 5. RelBench (our DFS+LightGBM via the adapter)

Our cheap baseline run through the RelBench harness (needs `relpath[eval]` + isolated venv).
Honest: a simple DFS+GBDT — **below** tuned RDL/GNN on these temporal F1 tasks (expected; that's
the Phase-2 GNN's job).

| Dataset / task | Type | Metric | (RelBench RDL baseline, ref.) |
|---|---|---|---|
| `rel-f1` / `driver-dnf` | classification | ROC-AUC **0.592** | ~0.72 |
| `rel-f1` / `driver-position` | regression | MAE **3.61** | — |

Reproduce: `python -m relpath.eval --dataset rel-f1 --task driver-dnf`.

---

## 6. GNN backend (relbench + PyG)

`relpath/gnn.py` — heterogeneous temporal GNN. **Code verified** (trains + predicts on rel-f1).
The **leakage-safe temporal** sampling needs `pyg-lib` (Linux); on Windows it falls back to
non-temporal sampling, which is **leaky** → not a fair benchmark, so no "beats baseline" number
is claimed here. Fair temporal eval is a Sprint 2 item (Linux/CI). See
[DECISIONS ADR-011](DECISIONS.md).

Reproduce (Linux, after `pip install pyg-lib`): `python -m relpath.eval --dataset rel-f1 --task driver-dnf --gnn`.

---

> Reproducing from scratch: `pip install -e ".[dev]"` → `python data/make_sample_db.py data/shop.duckdb`
> → `pytest tests/ -q` → `python -m relpath.eval`. Heavy paths (RelBench/GNN) use `pip install -e ".[eval]"`
> in an **isolated** venv (see [SKILLS.md](SKILLS.md)).
