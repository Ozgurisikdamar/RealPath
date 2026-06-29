"""PQL parser.

Grammar (case-insensitive keywords)::

    PREDICT  AGG( <table>.<col|*> , <start> , <end> , <unit> ) [ <op> <value> ]
    FOR EACH <entity_table>.<entity_key>
    [ WHERE    <filter expr> ]
    [ ASSUMING <filter expr> ]

The fixed top-level structure is parsed by hand; the boolean *filter expressions* in
WHERE / ASSUMING are parsed with **SQLGlot** so we accept real SQL predicates
(`amount > 1000 AND category = 'shoes'`) and validate them.
"""
from __future__ import annotations

import re

import sqlglot
import sqlglot.expressions as exp

from .ast import (
    AGGS,
    COMPARATORS,
    UNITS,
    Comparison,
    Filter,
    PredictiveTask,
    TargetAgg,
    TimeWindow,
)


class PQLSyntaxError(ValueError):
    """Raised when a PQL string cannot be parsed."""


_PREDICT_RE = re.compile(
    r"""^\s*PREDICT\s+(?P<target>.+?)
        \s+FOR\s+EACH\s+(?P<entity>[A-Za-z_][\w.]*)
        (?:\s+WHERE\s+(?P<where>.+?))?
        (?:\s+ASSUMING\s+(?P<assuming>.+?))?
        \s*$""",
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

# AGG( table.col , start , end , unit )  [ op value ]
_AGG_RE = re.compile(
    r"""^\s*(?P<func>[A-Za-z_]+)\s*\(\s*
        (?P<table>[A-Za-z_]\w*)\.(?P<col>\*|[A-Za-z_]\w*)\s*,\s*
        (?P<start>-?\d+)\s*,\s*(?P<end>-?\d+)\s*,\s*(?P<unit>[A-Za-z]+)\s*\)
        (?:\s*(?P<op>==|!=|>=|<=|>|<)\s*(?P<value>-?\d+(?:\.\d+)?))?\s*$""",
    re.IGNORECASE | re.VERBOSE,
)


def _parse_filters(text: str | None) -> list[Filter]:
    if not text or not text.strip():
        return []
    try:
        tree = sqlglot.parse_one(text, read="duckdb")
    except Exception as e:  # pragma: no cover - defensive
        raise PQLSyntaxError(f"Could not parse filter expression {text!r}: {e}") from e

    filters: list[Filter] = []
    op_map = {
        exp.EQ: "==", exp.NEQ: "!=", exp.GT: ">", exp.GTE: ">=",
        exp.LT: "<", exp.LTE: "<=",
    }
    for node in tree.find_all(*op_map.keys()):
        left, right = node.this, node.expression
        if not isinstance(left, exp.Column):
            continue
        table = left.table or None
        column = left.name
        if isinstance(right, exp.Literal):
            value = float(right.name) if right.is_number else right.name
        elif isinstance(right, exp.Boolean):
            value = right.this
        else:
            value = right.sql()
        filters.append(Filter(table=table, column=column, op=op_map[type(node)], value=value))
    if not filters:
        raise PQLSyntaxError(f"No usable comparison found in filter: {text!r}")
    return filters


def _parse_target(text: str) -> tuple[TargetAgg, Comparison | None]:
    m = _AGG_RE.match(text)
    if not m:
        raise PQLSyntaxError(
            f"Could not parse target aggregation {text!r}. "
            "Expected e.g. COUNT(transactions.*, 0, 30, days) == 0"
        )
    func = m["func"].upper()
    if func == "MEAN":
        func = "AVG"
    if func not in AGGS:
        raise PQLSyntaxError(f"Unsupported aggregation {func!r}; supported: {sorted(AGGS)}")
    unit = m["unit"].lower()
    if unit not in UNITS:
        raise PQLSyntaxError(f"Unsupported time unit {unit!r}; supported: {sorted(UNITS)}")
    col = None if m["col"] == "*" else m["col"]
    if func != "COUNT" and col is None:
        raise PQLSyntaxError(f"{func} needs a column, not '*'")
    window = TimeWindow(start=int(m["start"]), end=int(m["end"]), unit=unit)
    target = TargetAgg(func=func, table=m["table"], column=col, window=window)

    comparison = None
    if m["op"]:
        if m["op"] not in COMPARATORS:
            raise PQLSyntaxError(f"Unsupported comparator {m['op']!r}")
        comparison = Comparison(op=m["op"], value=float(m["value"]))
    return target, comparison


def parse_pql(text: str) -> PredictiveTask:
    """Parse a PQL string into a :class:`PredictiveTask`."""
    if not text or not text.strip():
        raise PQLSyntaxError("Empty PQL string")
    m = _PREDICT_RE.match(text.strip())
    if not m:
        raise PQLSyntaxError(
            "PQL must look like: PREDICT <agg> FOR EACH <table>.<key> [WHERE ...] [ASSUMING ...]"
        )
    entity = m["entity"]
    if "." not in entity:
        raise PQLSyntaxError(f"FOR EACH needs <table>.<key>, got {entity!r}")
    entity_table, entity_key = entity.split(".", 1)

    target, comparison = _parse_target(m["target"])
    return PredictiveTask(
        target=target,
        entity_table=entity_table,
        entity_key=entity_key,
        comparison=comparison,
        where=_parse_filters(m["where"]),
        assuming=_parse_filters(m["assuming"]),
        raw=text.strip(),
    )
