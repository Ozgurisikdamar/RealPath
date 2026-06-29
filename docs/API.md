# realpath.dev — API Reference

Public Python API, CLI, PQL, and connector reference for **realpath 0.1.0**.
Conceptual background: [`ARCHITECTURE.md`](ARCHITECTURE.md) · decisions: [`DECISIONS.md`](DECISIONS.md).

---

## Install

```bash
pip install -e .                       # core (DuckDB, Featuretools, LightGBM, sqlglot)
pip install -e ".[nlp]"                # NL→PQL via Claude (anthropic)
pip install -e ".[explain]"            # SHAP local explanations
pip install -e ".[postgres]"           # PostgreSQL connector (psycopg)
pip install -e ".[mysql]"              # MySQL connector (pymysql)
pip install -e ".[demo]"               # Streamlit demo
pip install -e ".[eval]"               # RelBench/GNN (torch, relbench, pytorch-frame, PyG) — heavy, isolate
```
> **pandas is pinned `>=2.0,<2.3`** (pandas 3.0 breaks woodwork — ADR-001). On Windows use `PYTHONUTF8=1`.

---

## 1. `connect(source, name="db") -> Engine`

Open a database and infer its relational schema. Local-first: nothing leaves the machine.

```python
import realpath as rp
engine = rp.connect("data/shop.duckdb")                              # DuckDB file
engine = rp.connect("postgresql://user:pw@host:5432/db")            # Postgres ([postgres] extra)
engine = rp.connect("mysql://root:pw@localhost:3306/db")            # MySQL ([mysql] extra)
```

**Sources:** `*.duckdb`/`*.db`/`:memory:` → DuckDB · `postgresql://`/`postgres://` → Postgres ·
`mysql://` → MySQL · other URLs → `NotImplementedError` (Phase-2). All three backends produce
**identical** results (backend-agnostic).

---

## 2. `Engine`

| Method | Description |
|---|---|
| `predict(query, max_depth=2, evaluate=True, verbose=False, calibrate=False)` | Run a PQL **or** natural-language prediction → `PredictionResult`. |
| `churn(entity, event, horizon_days=30, **kw)` | Template: entities with no activity in the window. |
| `forecast(entity, event, column, horizon_months=3, **kw)` | Template: future SUM of a column (regression). |
| `fraud(entity, event, horizon_days=60, where=None, **kw)` | Template: probability of a flagged event. |
| `ask(question) -> NLResult` | Translate NL → PQL (no execution). |
| `describe() -> str` | Human-readable schema + FK graph. |
| `schema` | The inferred `RelationalSchema` (tables, FKs, `join_path(a, b)`). |
| `close()` | Close the backend connection. |

```python
result = engine.predict(
    "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id"
)
result = engine.predict("gelecek 30 günde işlem yapmayacak müşteriler")   # NL (auto-detected)
result = engine.churn(entity="customers", event="transactions", horizon_days=30, calibrate=True)
```

`predict` auto-detects: a string starting with `PREDICT` is parsed as PQL; otherwise it's sent
through `ask()` (NL→PQL). `calibrate=True` applies isotonic probability calibration (classification).

---

## 3. `PredictionResult`

| Attribute / method | Description |
|---|---|
| `predictions` | `DataFrame[<entity_key>, score]` (+ `label` if evaluated). |
| `metrics` | `{roc_auc, accuracy}` (clf) or `{mae, rmse}` (reg). |
| `global_importance(top_n=10)` | DataFrame of top features (gain) + provenance (tables, agg). |
| `explain(entity_id=None, top_n=5)` | Global drivers (no id) or a per-entity **join-path card** (with id). |
| `reliability(n_bins=10)` | `{brier, ece}` calibration quality (classification, evaluated). |
| `top(n=10, ascending=False)` / `head(n=5)` | Sorted / first predictions. |
| `to_csv(path)` | Write predictions to CSV. |
| `task`, `model`, `X`, `entity_key` | The compiled task, trained model, scored feature matrix, id column. |

```python
result.metrics                 # {'roc_auc': 0.749, 'accuracy': 0.737}
result.explain()               # global drivers
result.explain(entity_id=9)    # why THIS customer (join-path card)
result.reliability()           # {'brier': 0.20, 'ece': 0.085}  (with calibrate=True)
result.top(10)                 # highest-risk entities
```

---

## 4. PQL — Predictive Query Language

```
PREDICT  AGG(<table>.<col|*>, <start>, <end>, <unit>) [<op> <value>]
FOR EACH <entity_table>.<primary_key>
[WHERE    <filter>]      -- filters which target rows count toward the label
[ASSUMING <filter>]      -- restricts which entities are scored
```
`AGG ∈ {COUNT, SUM, AVG, MIN, MAX}` (also `MEAN`→`AVG`) · `unit ∈ {days, weeks, months}` ·
`op ∈ {==, !=, >, >=, <, <=}`. **Comparison present ⇒ classification, absent ⇒ regression.**

```python
from realpath import parse_pql
task = parse_pql("PREDICT SUM(transactions.quantity, 0, 3, months) FOR EACH products.product_id")
task.task_type        # 'regression'
task.entity_table     # 'products'
task.column_label()   # 'SUM(transactions.quantity, 0, 3, months)'
```

**Templates** (`realpath.templates`) build PQL strings:
```python
from realpath.templates import churn_pql, forecast_pql, fraud_pql
churn_pql("customers", "customer_id", "transactions", 30)
forecast_pql("products", "product_id", "transactions", "quantity", 3)
fraud_pql("transactions", "tx_id", "returns", 60, where="transactions.amount > 1000")
```

---

## 5. NL → PQL (`realpath.nlp`)

```python
from realpath.nlp import nl_to_pql
nl = nl_to_pql("hangi müşteriler iade yapacak", engine.schema)
nl.pql        # generated PQL string
nl.source     # 'llm' (Claude) or 'template' (offline fallback)
```
Uses Claude when `ANTHROPIC_API_KEY` is set (model via `REALPATH_LLM_MODEL`, default
`claude-sonnet-4-6`); output is **re-parsed to validate**. Otherwise an offline keyword
template matcher (churn/forecast/fraud, TR+EN) — so local-first holds without a key.

---

## 6. Model layer (`realpath.model`)

```python
from realpath.model import fit_model, reliability
m = fit_model(X, y, task_type="classification", calibrate=True)   # isotonic on a held-out slice
proba = m.predict(X_new)                                          # class-1 probability
m.importance()                                                   # LightGBM gain (Series)
reliability(y_true, proba)                                       # {'brier':.., 'ece':..}
```
Default model = **LightGBM**; optional **TabPFN** for small classification (if installed).

---

## 7. CLI

```bash
realpath make-sample [--out data/shop.duckdb]
realpath schema  --db data/shop.duckdb
realpath ask     "..." --db data/shop.duckdb
realpath predict "<PQL or NL>" --db data/shop.duckdb [--explain] [--calibrate] [--top N] [--csv out.csv] [--no-eval]
realpath eval    [--db ...] [--pql ...]                       # local: relational vs no-feature baseline
realpath eval    --dataset rel-f1 --task driver-dnf           # RelBench adapter (needs [eval] extra)
realpath eval    --dataset rel-f1 --task driver-dnf --gnn     # GNN backend (needs [eval] + PyG)
```
Entry point `realpath` ≡ `python -m realpath.cli`.

---

## 8. Evaluation & GNN (`realpath.eval`, `realpath.gnn`)

```python
from realpath.eval import evaluate_local, evaluate_relbench, evaluate_gnn
evaluate_local("data/shop.duckdb")                     # relational vs entity-only baseline
evaluate_relbench("rel-f1", "driver-dnf")              # our DFS+LGBM on a RelBench task ([eval])
evaluate_gnn("rel-f1", "driver-dnf")                   # HeteroGNN ([eval] + PyG + torch-sparse)
```
> The GNN's leakage-safe **temporal** sampling needs `pyg-lib` (Linux); on Windows it falls back to
> non-temporal sampling (**leaky — dev only**, not a fair benchmark). See ADR-011.

---

## 9. Schema objects (`realpath.schema`)

`infer_schema(backend) -> RelationalSchema`. A `RelationalSchema` has `.tables` (dict of `Table`
with `.primary_key`, `.time_index`, `.columns`), `.foreign_keys`, and `.join_path(src, dst)` (BFS
over the FK graph, multi-hop). `build_entityset(backend, schema)` materializes a Featuretools
`EntitySet`.

```python
engine.schema.tables["customers"].primary_key          # 'customer_id'
engine.schema.join_path("customers", "returns")         # 2-hop FK path
```
