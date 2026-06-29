"""realpath command-line interface.

    realpath make-sample                         # generate the bundled demo DB
    realpath schema  --db data/shop.duckdb
    realpath ask     "churn edecek musteriler"  --db data/shop.duckdb
    realpath predict "PREDICT COUNT(transactions.*, 0, 30, days) == 0 \
                     FOR EACH customers.customer_id" --db data/shop.duckdb --explain
    realpath eval                                # local relational-vs-baseline proof
"""
from __future__ import annotations

import argparse
import warnings

from ._io import sprint, use_utf8


def _cmd_make_sample(args):
    from .sample_data import build

    build(args.out)


def _cmd_schema(args):
    from .engine import connect

    eng = connect(args.db)
    sprint(eng.describe())


def _cmd_ask(args):
    from .engine import connect

    eng = connect(args.db)
    nl = eng.ask(args.question)
    sprint(f"[{nl.source}] {nl.pql}")
    if nl.note:
        sprint(f"  note: {nl.note}")


def _cmd_predict(args):
    from .engine import connect

    eng = connect(args.db)
    res = eng.predict(args.query, verbose=True, evaluate=not args.no_eval, calibrate=args.calibrate)
    if res.metrics:
        sprint("metrics:", "  ".join(f"{k}={v:.4f}" for k, v in res.metrics.items()))
    if args.calibrate:
        rel = res.reliability()
        if rel:
            sprint("calibration:", "  ".join(f"{k}={v:.4f}" for k, v in rel.items()))
    sprint("\ntop predictions:")
    sprint(res.top(args.top).to_string(index=False))
    if args.csv:
        res.to_csv(args.csv)
        sprint(f"\nwrote {args.csv}")
    if args.explain:
        sprint("")
        res.explain(top_n=args.top)
        if len(res.predictions):
            top_id = res.top(1).iloc[0][res.entity_key]
            sprint("")
            res.explain(entity_id=top_id, top_n=5)


def _cmd_eval(args):
    from .eval import evaluate_local, evaluate_relbench

    if args.dataset:
        evaluate_relbench(args.dataset, args.task)
    else:
        evaluate_local(args.db, args.pql)


def main(argv=None):
    use_utf8()
    warnings.filterwarnings("ignore")
    p = argparse.ArgumentParser(prog="realpath", description="The open-source relational prediction engine.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("make-sample", help="generate the bundled synthetic DuckDB")
    sp.add_argument("--out", default="data/shop.duckdb")
    sp.set_defaults(func=_cmd_make_sample)

    sp = sub.add_parser("schema", help="print the inferred schema + FK graph")
    sp.add_argument("--db", required=True)
    sp.set_defaults(func=_cmd_schema)

    sp = sub.add_parser("ask", help="translate a natural-language question to PQL")
    sp.add_argument("question")
    sp.add_argument("--db", required=True)
    sp.set_defaults(func=_cmd_ask)

    sp = sub.add_parser("predict", help="run a PQL or natural-language prediction")
    sp.add_argument("query", help="PQL string or plain-language question")
    sp.add_argument("--db", required=True)
    sp.add_argument("--top", type=int, default=10)
    sp.add_argument("--explain", action="store_true")
    sp.add_argument("--no-eval", action="store_true", help="skip metric computation")
    sp.add_argument("--calibrate", action="store_true",
                    help="isotonic probability calibration + Brier/ECE (classification)")
    sp.add_argument("--csv", default=None, help="write predictions to CSV")
    sp.set_defaults(func=_cmd_predict)

    sp = sub.add_parser("eval", help="evaluate (local relational-vs-baseline, or RelBench)")
    sp.add_argument("--db", default="data/shop.duckdb")
    sp.add_argument("--pql", default=None)
    sp.add_argument("--dataset", default=None, help="RelBench dataset (needs realpath[eval])")
    sp.add_argument("--task", default=None)
    sp.set_defaults(func=_cmd_eval)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
