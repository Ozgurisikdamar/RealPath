"""PQL compiler: PredictiveTask -> temporally-clean training/scoring splits.

Two jobs:

1. **Join inference** — find the FK path from the entity table to the target table so the
   user never writes a JOIN (``RelationalSchema.join_path``).
2. **Temporal decomposition** — for an *anchor timestamp* ``t*``, build the label from the
   future window ``(t*+start, t*+end]`` while features (built later by Featuretools with
   ``cutoff_time = t*``) only ever see ``t <= t*``. The two windows never overlap, so future
   information cannot leak into training. (See §6 of the spec.)
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..connect import DuckDBBackend
from ..schema import ForeignKey, RelationalSchema
from .ast import Filter, PredictiveTask


class PQLCompileError(ValueError):
    pass


@dataclass
class Split:
    anchor: pd.Timestamp
    entity_key: str
    cutoff: pd.DataFrame          # columns: [entity_key, 'time'] for Featuretools
    labels: pd.Series             # indexed by entity id; int (clf) or float (reg)
    target_value: pd.Series       # raw aggregation value (pre-comparison)


_SQL_OP = {"==": "=", "!=": "<>", ">": ">", ">=": ">=", "<": "<", "<=": "<="}


def _filter_sql(f: Filter, default_table: str) -> str:
    table = f.table or default_table
    col = f'"{table}"."{f.column}"'
    op = _SQL_OP.get(f.op, f.op)
    val = f"'{f.value}'" if isinstance(f.value, str) else str(f.value)
    return f"{col} {op} {val}"


class CompiledTask:
    def __init__(self, task: PredictiveTask, schema: RelationalSchema, backend: DuckDBBackend):
        self.task = task
        self.schema = schema
        self.backend = backend
        self._validate()
        self.path: list[ForeignKey] = schema.join_path(task.entity_table, task.target.table)
        if self.path is None:
            raise PQLCompileError(
                f"No foreign-key path connects {task.entity_table!r} to "
                f"{task.target.table!r}. Check the schema / FK inference."
            )

    # -- validation ----------------------------------------------------
    def _validate(self) -> None:
        t = self.task
        for tbl in (t.entity_table, t.target.table):
            if tbl not in self.schema.tables:
                raise PQLCompileError(f"Unknown table {tbl!r}")
        ent = self.schema.tables[t.entity_table]
        if ent.column(t.entity_key) is None:
            raise PQLCompileError(f"Unknown column {t.entity_table}.{t.entity_key}")
        if ent.primary_key and t.entity_key != ent.primary_key:
            raise PQLCompileError(
                f"FOR EACH key must be the primary key of {t.entity_table} "
                f"(expected {ent.primary_key}, got {t.entity_key})"
            )
        tt = self.schema.tables[t.target.table]
        if tt.time_index is None:
            raise PQLCompileError(
                f"Target table {t.target.table!r} has no time column; cannot define a "
                "future window."
            )
        if t.target.column and tt.column(t.target.column) is None:
            raise PQLCompileError(f"Unknown column {t.target.table}.{t.target.column}")

    # -- join chain ----------------------------------------------------
    def _join_sql(self) -> str:
        current = self.task.entity_table
        clauses = []
        for fk in self.path:
            if fk.child_table == current:
                nxt = fk.parent_table
                left = f'"{fk.child_table}"."{fk.child_column}"'
                right = f'"{fk.parent_table}"."{fk.parent_column}"'
            else:  # fk.parent_table == current
                nxt = fk.child_table
                left = f'"{fk.parent_table}"."{fk.parent_column}"'
                right = f'"{fk.child_table}"."{fk.child_column}"'
            clauses.append(f'JOIN "{nxt}" ON {left} = {right}')
            current = nxt
        return "\n        ".join(clauses)

    # -- anchors -------------------------------------------------------
    def data_range(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        tt = self.schema.tables[self.task.target.table]
        lo, hi = self.backend.query(
            f'SELECT MIN("{tt.time_index}"), MAX("{tt.time_index}") FROM "{tt.name}"'
        ).iloc[0]
        return pd.Timestamp(lo), pd.Timestamp(hi)

    def default_anchors(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        lo, hi = self.data_range()
        horizon = pd.Timedelta(days=self.task.target.window.horizon_days)
        test_anchor = hi - horizon
        train_anchor = test_anchor - horizon
        if train_anchor <= lo:
            # data is short; fall back to thirds
            span = (hi - lo) / 3
            train_anchor, test_anchor = lo + span, lo + 2 * span
        return train_anchor.normalize(), test_anchor.normalize()

    # -- split builder -------------------------------------------------
    def build_split(self, anchor: pd.Timestamp) -> Split:
        t = self.task
        ent = self.schema.tables[t.entity_table]
        tt = self.schema.tables[t.target.table]
        lo, hi = t.target.window.bounds(anchor)

        agg_arg = "*" if t.target.column is None else f'"{tt.name}"."{t.target.column}"'
        agg_expr = f"{t.target.func}({agg_arg})"

        # universe: entities that exist at the anchor (+ ASSUMING)
        existence = []
        params_universe = []
        if ent.time_index:
            existence.append(f'"{ent.name}"."{ent.time_index}" <= ?')
            params_universe.append(anchor.to_pydatetime())
        for f in t.assuming:
            existence.append(_filter_sql(f, ent.name))
        universe_where = ("WHERE " + " AND ".join(existence)) if existence else ""

        # events: target rows inside the future window (+ WHERE)
        event_where = [
            f'"{tt.name}"."{tt.time_index}" > ?',
            f'"{tt.name}"."{tt.time_index}" <= ?',
        ]
        params_events = [lo, hi]
        for f in t.where:
            event_where.append(_filter_sql(f, tt.name))

        sql = f"""
        WITH universe AS (
            SELECT "{ent.name}"."{t.entity_key}" AS _eid
            FROM "{ent.name}"
            {universe_where}
        ),
        events AS (
            SELECT "{ent.name}"."{t.entity_key}" AS _eid, {agg_expr} AS _val
            FROM "{ent.name}"
            {self._join_sql()}
            WHERE {" AND ".join(event_where)}
            GROUP BY "{ent.name}"."{t.entity_key}"
        )
        SELECT u._eid AS entity_id, COALESCE(e._val, 0) AS agg_value
        FROM universe u
        LEFT JOIN events e ON u._eid = e._eid
        ORDER BY u._eid
        """
        df = self.backend.query(sql, params_universe + params_events)
        target_value = pd.Series(
            df["agg_value"].to_numpy(), index=df["entity_id"], name="target_value"
        )

        if t.comparison is not None:
            labels = _apply_comparison(target_value, t.comparison.op, t.comparison.value).astype(int)
        else:
            labels = target_value.astype(float)
        labels.name = "label"

        cutoff = pd.DataFrame(
            {t.entity_key: df["entity_id"].to_numpy(), "time": anchor.to_pydatetime()}
        )
        return Split(anchor=anchor, entity_key=t.entity_key, cutoff=cutoff,
                     labels=labels, target_value=target_value)


def _apply_comparison(s: pd.Series, op: str, value: float) -> pd.Series:
    import operator
    fn = {"==": operator.eq, "!=": operator.ne, ">": operator.gt,
          ">=": operator.ge, "<": operator.lt, "<=": operator.le}[op]
    return fn(s, value)


def compile_task(task: PredictiveTask, schema: RelationalSchema, backend: DuckDBBackend) -> CompiledTask:
    return CompiledTask(task, schema, backend)
