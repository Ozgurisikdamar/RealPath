"""Evaluation harness.

Two modes:

* **local** (default, no heavy deps): on any DuckDB, compares relpath's full relational
  features against a *no-relational-features* baseline (entity-own columns only). This
  demonstrates the core claim — cross-table feature synthesis adds real signal — and runs
  anywhere, instantly.
* **relbench** (``--dataset``): runs the same pipeline on a Stanford RelBench task to compare
  against published baselines. Requires the optional ``relpath[eval]`` extra (pulls in
  torch + relbench).

    python -m relpath.eval                       # local, on the sample DB
    python -m relpath.eval --pql "PREDICT ..."   # local, custom PQL
    python -m relpath.eval --dataset rel-hm --task user-churn   # RelBench (needs extra)
"""
from __future__ import annotations

import argparse

from ._io import sprint, use_utf8
from .explain import provenance


def _direct_columns(columns, entity_table: str) -> list[str]:
    """Columns that use *no* other table — the no-relational-features baseline."""
    out = []
    for col in columns:
        tables, _ = provenance(col)
        if not tables or set(tables) <= {entity_table}:
            out.append(col)
    return out


def evaluate_local(db: str, pql: str | None = None, max_depth: int = 2) -> dict:
    from .engine import _metrics, connect
    from .features import align_xy, synthesize
    from .model import fit_model
    from .pql import compile_task, parse_pql
    from .templates import churn_pql
    import pandas as pd

    eng = connect(db)
    if pql is None:
        # default: churn on the first customer-like entity, else first event's parent
        pql = churn_pql("customers", "customer_id", "transactions")
    task = parse_pql(pql)
    compiled = compile_task(task, eng.schema, eng.backend)
    train_anchor, test_anchor = compiled.default_anchors()

    trs, tes = compiled.build_split(train_anchor), compiled.build_split(test_anchor)
    trfm = synthesize(eng.es, eng.schema, task.entity_table, trs.cutoff, max_depth=max_depth)
    tefm = synthesize(eng.es, eng.schema, task.entity_table, tes.cutoff, max_depth=max_depth)
    Xtr, ytr = align_xy(trfm, trs.labels)
    Xte_full = tefm.X.reindex(columns=Xtr.columns)
    common = Xte_full.index.intersection(tes.labels.index)
    yte = tes.labels.loc[common]

    direct = _direct_columns(Xtr.columns, task.entity_table)

    def run(cols):
        m = fit_model(Xtr[cols], ytr, task.task_type)
        preds = pd.Series(m.predict(Xte_full[cols]), index=Xte_full.index).loc[common]
        return _metrics(task.task_type, yte.to_numpy(), preds.to_numpy())

    base = run(direct)
    full = run(list(Xtr.columns))

    sprint(f"\nrelpath local eval  —  {task}")
    sprint(f"  db={db}  anchors: train={train_anchor.date()} test={test_anchor.date()}")
    sprint(f"  features: {len(direct)} entity-only  vs  {len(Xtr.columns)} relational\n")
    key = "roc_auc" if task.task_type == "classification" else "mae"
    better = "higher=better" if task.task_type == "classification" else "lower=better"
    sprint(f"  {'metric':<10}{'baseline (no rel.)':>20}{'relpath (full)':>18}   ({better})")
    for k in sorted(set(base) | set(full)):
        bv, fv = base.get(k), full.get(k)
        sprint(f"  {k:<10}{bv:>20.4f}{fv:>18.4f}")
    delta = (full.get(key, 0) - base.get(key, 0))
    verdict = "relational features HELP" if (
        (task.task_type == "classification" and delta > 0)
        or (task.task_type == "regression" and delta < 0)
    ) else "no improvement"
    sprint(f"\n  => {key} delta = {delta:+.4f}  ({verdict})\n")
    return {"baseline": base, "relpath": full}


def evaluate_relbench(dataset: str, task: str) -> dict:  # pragma: no cover - needs extra
    try:
        import relbench  # noqa: F401
    except Exception:
        raise SystemExit(
            "RelBench eval needs the optional extra:\n"
            "  pip install 'relpath[eval]'\n"
            "(this pulls in torch + relbench)."
        )
    from .relbench_adapter import run_relbench_task  # lazy, isolated module
    return run_relbench_task(dataset, task)


def main(argv=None):
    use_utf8()
    ap = argparse.ArgumentParser(prog="relpath.eval", description="relpath evaluation harness")
    ap.add_argument("--db", default="data/shop.duckdb", help="DuckDB path for local eval")
    ap.add_argument("--pql", default=None, help="PQL to evaluate (local mode)")
    ap.add_argument("--dataset", default=None, help="RelBench dataset (needs extra)")
    ap.add_argument("--task", default=None, help="RelBench task name")
    ap.add_argument("--max-depth", type=int, default=2)
    args = ap.parse_args(argv)

    if args.dataset:
        evaluate_relbench(args.dataset, args.task)
    else:
        evaluate_local(args.db, args.pql, max_depth=args.max_depth)


if __name__ == "__main__":
    main()
