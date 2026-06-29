"""Automatic schema + foreign-key graph inference.

Most real databases dumped into a warehouse (or a CSV-built DuckDB) carry *no declared*
primary/foreign keys. relpath recovers the relational topology heuristically:

* **Primary key** — a `*_id` / `id` column whose values are unique within the table.
* **Foreign key** — a non-PK `*_id` column whose name matches another table's primary key.
* **Time index** — the first TIMESTAMP/DATE column (when a row "became visible").

The recovered :class:`RelationalSchema` is both the FK graph used for *join-path inference*
(see ``pql.compile``) and the blueprint for the Featuretools ``EntitySet``.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .connect import DuckDBBackend

# SQL type prefixes we treat as numeric / temporal (DuckDB, Postgres, MySQL).
_NUMERIC = ("BIGINT", "INTEGER", "INT", "MEDIUMINT", "SMALLINT", "TINYINT", "HUGEINT",
            "UBIGINT", "UINTEGER", "DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC")
_TEMPORAL = ("TIMESTAMP", "DATETIME", "DATE", "TIME")
_CATEGORICAL_MAX_RATIO = 0.5  # distinct/rows below this → categorical


@dataclass
class Column:
    name: str
    sql_type: str
    role: str  # 'pk' | 'fk' | 'time' | 'numeric' | 'categorical' | 'text'

    @property
    def is_id(self) -> bool:
        return self.role in ("pk", "fk")


@dataclass
class ForeignKey:
    child_table: str
    child_column: str
    parent_table: str
    parent_column: str

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.child_table}.{self.child_column} -> {self.parent_table}.{self.parent_column}"


@dataclass
class Table:
    name: str
    columns: list[Column]
    primary_key: str | None = None
    time_index: str | None = None

    def column(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name == name), None)

    @property
    def feature_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.role in ("numeric", "categorical")]


@dataclass
class RelationalSchema:
    tables: dict[str, Table] = field(default_factory=dict)
    foreign_keys: list[ForeignKey] = field(default_factory=list)

    # -- graph helpers -------------------------------------------------
    def neighbors(self, table: str) -> list[tuple[str, ForeignKey]]:
        out = []
        for fk in self.foreign_keys:
            if fk.child_table == table:
                out.append((fk.parent_table, fk))
            elif fk.parent_table == table:
                out.append((fk.child_table, fk))
        return out

    def join_path(self, src: str, dst: str) -> list[ForeignKey] | None:
        """Shortest FK path connecting two tables (BFS over the undirected FK graph)."""
        if src == dst:
            return []
        seen = {src}
        queue: deque[tuple[str, list[ForeignKey]]] = deque([(src, [])])
        while queue:
            node, path = queue.popleft()
            for nxt, fk in self.neighbors(node):
                if nxt in seen:
                    continue
                new_path = path + [fk]
                if nxt == dst:
                    return new_path
                seen.add(nxt)
                queue.append((nxt, new_path))
        return None

    def describe(self) -> str:
        lines = ["Tables:"]
        for t in self.tables.values():
            cols = ", ".join(f"{c.name}:{c.role}" for c in t.columns)
            lines.append(f"  {t.name} (pk={t.primary_key}, time={t.time_index}) [{cols}]")
        lines.append("Foreign keys:")
        for fk in self.foreign_keys:
            lines.append(f"  {fk}")
        return "\n".join(lines)


def _singular(name: str) -> str:
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith("ses"):
        return name[:-2]
    if name.endswith("s"):
        return name[:-1]
    return name


def _classify_type(sql_type: str) -> str:
    t = sql_type.upper()
    if any(t.startswith(p) for p in _TEMPORAL):
        return "time"
    if any(t.startswith(p) for p in _NUMERIC):
        return "numeric"
    return "string"


def infer_schema(backend: DuckDBBackend) -> RelationalSchema:
    schema = RelationalSchema()
    table_names = backend.tables()

    # First pass: classify columns, find primary keys and time indices.
    for tname in table_names:
        raw_cols = backend.columns(tname)
        n_rows = backend.row_count(tname)
        cols: list[Column] = []
        unique_ids: list[str] = []
        time_candidates: list[str] = []

        for ci in raw_cols:
            base = _classify_type(ci.sql_type)
            name = ci.name
            is_idish = name == "id" or name.endswith("_id")
            if base == "time":
                role = "time"
                time_candidates.append(name)
            elif is_idish:
                role = "id"  # provisional; pk/fk decided below
                n, d = backend.distinct_count(tname, name)
                if n_rows > 0 and n == n_rows and d == n_rows:
                    unique_ids.append(name)
            elif base == "numeric":
                role = "numeric"
            else:
                n, d = backend.distinct_count(tname, name)
                ratio = (d / n) if n else 1.0
                role = "categorical" if ratio <= _CATEGORICAL_MAX_RATIO else "text"
            cols.append(Column(name=name, sql_type=ci.sql_type, role=role))

        # primary key: prefer the name that matches the (singular) table name
        pk = None
        preferred = {f"{_singular(tname)}_id", f"{tname}_id", "id"}
        for cand in unique_ids:
            if cand in preferred:
                pk = cand
                break
        if pk is None and unique_ids:
            pk = unique_ids[0]

        time_index = time_candidates[0] if time_candidates else None
        schema.tables[tname] = Table(
            name=tname, columns=cols, primary_key=pk, time_index=time_index
        )

    # Mark the PK column role.
    pk_owner: dict[str, str] = {}  # pk_column_name -> table
    for t in schema.tables.values():
        if t.primary_key:
            t.column(t.primary_key).role = "pk"
            pk_owner.setdefault(t.primary_key, t.name)

    # Second pass: foreign keys. A non-PK '*_id' column whose name is some other
    # table's primary key becomes an FK to that table.
    for t in schema.tables.values():
        for c in t.columns:
            if c.role != "id":
                continue
            parent = pk_owner.get(c.name)
            if parent and parent != t.name:
                c.role = "fk"
                schema.foreign_keys.append(
                    ForeignKey(t.name, c.name, parent, c.name)
                )
            else:
                # an id-like column we couldn't resolve — leave out of features
                c.role = "text"

    return schema


def _normalize_dtypes(df):
    """Coerce DuckDB output into dtypes woodwork understands (datetime64[ns], object)."""
    import pandas as pd

    for c in df.columns:
        dt = df[c].dtype
        if pd.api.types.is_datetime64_any_dtype(dt):
            df[c] = df[c].astype("datetime64[ns]")
        elif pd.api.types.is_object_dtype(dt) or "str" in str(dt).lower() or "string" in str(dt).lower():
            df[c] = df[c].astype(object)
    return df


def build_entityset(backend: DuckDBBackend, schema: RelationalSchema, name: str = "db"):
    """Materialise the schema as a Featuretools EntitySet (entities + relationships)."""
    import featuretools as ft
    import pandas as pd

    es = ft.EntitySet(id=name)

    for t in schema.tables.values():
        df = _normalize_dtypes(backend.load(t.name))
        # ensure time index is real datetime
        if t.time_index and t.time_index in df.columns:
            df[t.time_index] = pd.to_datetime(df[t.time_index])

        logical_types = {}
        for c in t.columns:
            if c.role == "categorical":
                logical_types[c.name] = "Categorical"
            elif c.role == "time":
                logical_types[c.name] = "Datetime"

        kwargs = dict(dataframe_name=t.name, dataframe=df, logical_types=logical_types)
        if t.primary_key:
            kwargs["index"] = t.primary_key
        else:
            kwargs["make_index"] = True
            kwargs["index"] = f"{t.name}_idx"
        if t.time_index:
            kwargs["time_index"] = t.time_index
        es.add_dataframe(**kwargs)

    for fk in schema.foreign_keys:
        es.add_relationship(
            fk.parent_table, fk.parent_column, fk.child_table, fk.child_column
        )
    return es
