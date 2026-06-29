"""Database connection layer (local-first).

The prototype targets DuckDB — a single-file, in-process analytical engine. Your data
never leaves the machine. The :class:`DuckDBBackend` exposes the small surface the rest
of relpath needs (list tables, read columns, load frames, count distinct values), so a
Postgres / MySQL backend can be slotted in later behind the same interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class ColumnInfo:
    name: str
    sql_type: str


class DuckDBBackend:
    """Thin wrapper over a DuckDB connection."""

    def __init__(self, path: str | Path = ":memory:", read_only: bool = True):
        import duckdb

        self.path = str(path)
        # read_only is ignored for :memory:
        if self.path == ":memory:":
            self.con = duckdb.connect(self.path)
        else:
            self.con = duckdb.connect(self.path, read_only=read_only)

    # -- introspection -------------------------------------------------
    def tables(self) -> list[str]:
        rows = self.con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        return [r[0] for r in rows]

    def columns(self, table: str) -> list[ColumnInfo]:
        rows = self.con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [table],
        ).fetchall()
        return [ColumnInfo(name=r[0], sql_type=r[1]) for r in rows]

    def row_count(self, table: str) -> int:
        return int(self.con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])

    def distinct_count(self, table: str, column: str) -> tuple[int, int]:
        """Return (n_rows, n_distinct_non_null) for a column."""
        n, d = self.con.execute(
            f'SELECT COUNT("{column}"), COUNT(DISTINCT "{column}") FROM "{table}"'
        ).fetchone()
        return int(n), int(d)

    # -- data ----------------------------------------------------------
    def load(self, table: str) -> pd.DataFrame:
        return self.con.execute(f'SELECT * FROM "{table}"').df()

    def query(self, sql: str, params: list | None = None) -> pd.DataFrame:
        return self.con.execute(sql, params or []).df()

    def close(self) -> None:
        try:
            self.con.close()
        except Exception:
            pass


class PostgresBackend:
    """Read access to a PostgreSQL database (same surface as :class:`DuckDBBackend`).

    relpath generates SQL with ``?`` placeholders (DuckDB style) and double-quoted
    identifiers; this backend translates ``?`` -> psycopg's ``%s`` and connects read-only.
    Requires the optional ``relpath[postgres]`` extra (``psycopg``).
    """

    def __init__(self, dsn: str, schema: str = "public"):
        try:
            import psycopg
        except Exception as e:  # pragma: no cover - clear guidance
            raise ImportError(
                "Postgres support needs psycopg: pip install 'relpath[postgres]'"
            ) from e
        self.dsn = dsn
        self.schema = schema
        self.con = psycopg.connect(dsn)
        self.con.autocommit = True
        try:
            self.con.read_only = True
        except Exception:
            pass

    # -- introspection -------------------------------------------------
    def tables(self) -> list[str]:
        rows = self._fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s ORDER BY table_name",
            [self.schema],
        )
        return [r[0] for r in rows]

    def columns(self, table: str) -> list[ColumnInfo]:
        rows = self._fetch(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            [self.schema, table],
        )
        return [ColumnInfo(name=r[0], sql_type=r[1]) for r in rows]

    def row_count(self, table: str) -> int:
        return int(self._fetch(f'SELECT COUNT(*) FROM "{table}"')[0][0])

    def distinct_count(self, table: str, column: str) -> tuple[int, int]:
        n, d = self._fetch(
            f'SELECT COUNT("{column}"), COUNT(DISTINCT "{column}") FROM "{table}"'
        )[0]
        return int(n), int(d)

    # -- data ----------------------------------------------------------
    def load(self, table: str) -> pd.DataFrame:
        return self.query(f'SELECT * FROM "{table}"')

    def query(self, sql: str, params: list | None = None) -> pd.DataFrame:
        sql = sql.replace("?", "%s")  # DuckDB '?' -> psycopg '%s'
        with self.con.cursor() as cur:
            cur.execute(sql, params or [])
            cols = [d.name for d in cur.description]
            data = cur.fetchall()
        return pd.DataFrame(data, columns=cols)

    def _fetch(self, sql: str, params: list | None = None):
        with self.con.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()

    def close(self) -> None:
        try:
            self.con.close()
        except Exception:
            pass


def open_backend(source: str | Path):
    """Open a database source.

    * ``postgresql://`` / ``postgres://`` URL -> :class:`PostgresBackend` (needs the
      ``postgres`` extra).
    * a ``.duckdb``/``.db`` path or ``:memory:`` -> :class:`DuckDBBackend`.
    * a bare path -> DuckDB. Other URL schemes (mysql, etc.) are a Phase-2 roadmap item.
    """
    s = str(source)
    if s.startswith(("postgresql://", "postgres://")):
        return PostgresBackend(s)
    if s == ":memory:" or s.endswith((".duckdb", ".db", ".ddb")):
        return DuckDBBackend(s, read_only=(s != ":memory:"))
    if "://" in s:
        raise NotImplementedError(
            f"Connector for '{s.split('://')[0]}://' is on the Phase-2 roadmap. "
            "Use a DuckDB file or a postgresql:// URL for now."
        )
    # bare path — assume DuckDB
    return DuckDBBackend(s, read_only=True)
