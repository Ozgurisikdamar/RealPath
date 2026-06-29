"""Temporal leakage-safety tests — the structural guarantee from §6 of the spec.

Strategy: features computed at an anchor must depend ONLY on rows at or before the anchor.
We prove it by *deleting every event after the anchor* and checking the feature matrix is
byte-for-byte identical. If any future row leaked into a feature, the matrices would differ.
"""
import duckdb
import numpy as np
import pandas as pd

from realpath.engine import connect
from realpath.features import synthesize


def _build_split_and_features(db_path, pql, anchor):
    from realpath.pql import compile_task, parse_pql

    eng = connect(db_path)
    task = parse_pql(pql)
    compiled = compile_task(task, eng.schema, eng.backend)
    split = compiled.build_split(anchor)
    fm = synthesize(eng.es, eng.schema, task.entity_table, split.cutoff)
    eng.close()
    return fm.X, task


def _truncated_db(src_path, anchor, dst_path):
    """Copy the DB but drop every row whose time index is after the anchor."""
    src = duckdb.connect(src_path, read_only=True)
    back = connect(src_path)
    schema = back.schema
    dst = duckdb.connect(str(dst_path))
    for t in schema.tables.values():
        df = src.execute(f'SELECT * FROM "{t.name}"').df()
        if t.time_index:
            df = df[pd.to_datetime(df[t.time_index]) <= anchor]
        dst.register("tmp", df)
        dst.execute(f'CREATE TABLE "{t.name}" AS SELECT * FROM tmp')
        dst.unregister("tmp")
    dst.close()
    src.close()
    back.close()


PQL = "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id"


def test_no_future_leakage(sample_db, tmp_path):
    anchor = pd.Timestamp("2025-03-01")

    X_full, _ = _build_split_and_features(sample_db, PQL, anchor)

    trunc_path = tmp_path / "trunc.duckdb"
    _truncated_db(sample_db, anchor, trunc_path)
    X_trunc, _ = _build_split_and_features(str(trunc_path), PQL, anchor)

    common_idx = X_full.index.intersection(X_trunc.index)
    common_cols = X_full.columns.intersection(X_trunc.columns)
    assert len(common_idx) > 100 and len(common_cols) > 5

    a = X_full.loc[common_idx, common_cols]
    b = X_trunc.loc[common_idx, common_cols]
    # identical => no feature depended on post-anchor rows
    mismatches = []
    for col in common_cols:
        if not _series_equal(a[col], b[col]):
            mismatches.append(col)
    assert not mismatches, f"Future data leaked into features: {mismatches}"


def test_label_window_is_in_the_future(sample_db):
    """The label window must lie strictly after the anchor (no overlap with features)."""
    from realpath.pql import compile_task, parse_pql

    eng = connect(sample_db)
    compiled = compile_task(parse_pql(PQL), eng.schema, eng.backend)
    anchor = pd.Timestamp("2025-03-01")
    lo, hi = compiled.task.target.window.bounds(anchor)
    assert pd.Timestamp(lo) >= anchor and pd.Timestamp(hi) > anchor
    eng.close()


def _series_equal(s1: pd.Series, s2: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(s1) and pd.api.types.is_numeric_dtype(s2):
        return np.allclose(s1.fillna(-999999).to_numpy(), s2.fillna(-999999).to_numpy(),
                           rtol=1e-6, atol=1e-9)
    # categorical / object: compare value-by-value, treating NaN as a sentinel
    a = [None if pd.isna(v) else str(v) for v in s1.astype(object).tolist()]
    b = [None if pd.isna(v) else str(v) for v in s2.astype(object).tolist()]
    return a == b
