"""RelBench adapter (optional — requires ``relpath[eval]``).

Reuses relpath's own feature synthesis + model on Stanford RelBench tasks so we can compare
against published baselines on the *same* data. Kept in a separate module so importing the
core engine never pulls in torch/relbench.

NOTE: this path requires the heavy extra (torch + relbench) and was *not* executed in the
prototype's build environment — treat the numbers as reproducible-by-you, not vendor-claimed.
The local harness (``relpath.eval`` without ``--dataset``) is the tested, always-runnable proof.
"""
from __future__ import annotations

import pandas as pd

from ._io import sprint


def _build_entityset(db, name="relbench"):
    import featuretools as ft

    es = ft.EntitySet(id=name)
    for tname, table in db.table_dict.items():
        df = table.df.copy()
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
    # relationships from declared foreign keys
    for tname, table in db.table_dict.items():
        for fk_col, parent in table.fkey_col_to_pkey_table.items():
            parent_pk = db.table_dict[parent].pkey_col
            es.add_relationship(parent, parent_pk, tname, fk_col)
    return es


def run_relbench_task(dataset_name: str, task_name: str, max_depth: int = 2) -> dict:
    from relbench.datasets import get_dataset
    from relbench.tasks import get_task

    from .features import AGG_PRIMITIVES, TRANS_PRIMITIVES
    from .model import fit_model
    from .engine import _metrics
    import featuretools as ft

    dataset = get_dataset(dataset_name, download=True)
    task = get_task(dataset_name, task_name, download=True)
    db = dataset.get_db()
    es = _build_entityset(db)

    entity_table = task.entity_table
    entity_col = task.entity_col
    time_col = task.time_col
    target_col = task.target_col
    ttype = str(getattr(task, "task_type", "")).lower()
    task_type = "regression" if "regress" in ttype else "classification"

    def featurize(table_df):
        cutoff = table_df[[entity_col, time_col]].rename(columns={time_col: "time"})
        fm, _ = ft.dfs(
            entityset=es, target_dataframe_name=entity_table, cutoff_time=cutoff,
            agg_primitives=AGG_PRIMITIVES, trans_primitives=TRANS_PRIMITIVES,
            max_depth=max_depth, verbose=False,
        )
        if isinstance(fm.index, pd.MultiIndex):
            fm.index = fm.index.get_level_values(0)
        return fm.reset_index(drop=True)

    train_t = task.get_table("train").df
    test_t = task.get_table("test").df
    Xtr, ytr = featurize(train_t), train_t[target_col].reset_index(drop=True)
    Xte, yte = featurize(test_t), test_t[target_col].reset_index(drop=True)
    Xte = Xte.reindex(columns=Xtr.columns)

    model = fit_model(Xtr, ytr, task_type)
    preds = model.predict(Xte)
    metrics = _metrics(task_type, yte.to_numpy(), preds)
    sprint(f"\nRelBench {dataset_name}/{task_name} [{task_type}] -> {metrics}\n")
    return metrics
