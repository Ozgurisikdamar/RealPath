"""RelBench adapter (optional — requires ``relpath[eval]``).

Reuses relpath's own feature synthesis + model on Stanford RelBench tasks so we can compare
against published baselines on the *same* data. Kept in a separate module so importing the
core engine never pulls in torch/relbench.

Run via: ``python -m relpath.eval --dataset rel-f1 --task driver-dnf`` (needs the eval extra).
"""
from __future__ import annotations

import pandas as pd

from ._io import sprint


def _build_entityset(db, name: str = "relbench"):
    import featuretools as ft

    from .schema import _normalize_dtypes

    es = ft.EntitySet(id=name)
    for tname, table in db.table_dict.items():
        df = _normalize_dtypes(table.df.copy())
        if table.time_col and table.time_col in df.columns:
            df[table.time_col] = pd.to_datetime(df[table.time_col]).astype("datetime64[ns]")
        kwargs = dict(dataframe_name=tname, dataframe=df)
        if table.pkey_col:
            kwargs["index"] = table.pkey_col
        else:
            kwargs["make_index"] = True
            kwargs["index"] = f"{tname}__idx"
        if table.time_col:
            kwargs["time_index"] = table.time_col
        es.add_dataframe(**kwargs)
    for tname, table in db.table_dict.items():
        for fk_col, parent in table.fkey_col_to_pkey_table.items():
            parent_pk = db.table_dict[parent].pkey_col
            es.add_relationship(parent, parent_pk, tname, fk_col)
    return es


def _ignore_columns(db) -> dict:
    """Keep primary/foreign-key id columns out of the DFS search (avoid id leakage)."""
    out: dict[str, list[str]] = {}
    for tname, table in db.table_dict.items():
        drop = ([table.pkey_col] if table.pkey_col else []) + list(table.fkey_col_to_pkey_table)
        if drop:
            out[tname] = drop
    return out


def run_relbench_task(dataset_name: str, task_name: str, max_depth: int = 2) -> dict:
    import featuretools as ft
    from relbench.datasets import get_dataset
    from relbench.tasks import get_task

    from .engine import _metrics
    from .features import AGG_PRIMITIVES, TRANS_PRIMITIVES
    from .model import fit_model

    dataset = get_dataset(dataset_name, download=True)
    task = get_task(dataset_name, task_name, download=True)
    db = dataset.get_db()
    es = _build_entityset(db)
    ignore = _ignore_columns(db)

    entity_table = task.entity_table
    entity_col = task.entity_col
    time_col = task.time_col
    target_col = task.target_col
    ttype = str(getattr(task, "task_type", "")).lower()
    task_type = "regression" if "regress" in ttype else "classification"

    def featurize(split: str):
        tbl = task.get_table(split).df.copy()
        if target_col not in tbl.columns or tbl[target_col].isna().all():
            return None, None
        tbl[time_col] = pd.to_datetime(tbl[time_col]).astype("datetime64[ns]")
        # carry the label inside cutoff_time — Featuretools passes it through, so X and y
        # stay aligned regardless of how DFS orders rows.
        cutoff = tbl[[entity_col, time_col, target_col]].rename(columns={time_col: "time"})
        fm, _ = ft.dfs(
            entityset=es, target_dataframe_name=entity_table, cutoff_time=cutoff,
            agg_primitives=AGG_PRIMITIVES, trans_primitives=TRANS_PRIMITIVES,
            ignore_columns=ignore, max_depth=max_depth, verbose=False,
        )
        if isinstance(fm.index, pd.MultiIndex):
            fm.index = fm.index.get_level_values(0)
        y = fm[target_col]
        X = fm.drop(columns=[target_col])
        return X, y

    Xtr, ytr = featurize("train")
    Xte, yte = featurize("test")
    if Xte is None:  # test labels masked (leaderboard split) -> fall back to val
        sprint("[relpath] test labels unavailable; using 'val' split for evaluation")
        Xte, yte = featurize("val")

    Xte = Xte.reindex(columns=Xtr.columns)
    model = fit_model(Xtr, ytr, task_type)
    preds = model.predict(Xte)
    metrics = _metrics(task_type, yte.to_numpy(), preds)
    sprint(f"\nRelBench {dataset_name}/{task_name} [{task_type}]  "
           f"train={len(Xtr)} test={len(Xte)} feats={Xtr.shape[1]}  -> {metrics}\n")
    return metrics
