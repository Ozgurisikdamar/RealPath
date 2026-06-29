"""PQL abstract syntax — the structured form of a predictive question."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

UNITS = {"days", "weeks", "months"}
AGGS = {"COUNT", "SUM", "AVG", "MEAN", "MIN", "MAX"}
COMPARATORS = {"==", "!=", ">", ">=", "<", "<="}


def shift(anchor, n: int, unit: str):
    """Return ``anchor`` shifted by ``n`` units (days/weeks/months)."""
    ts = pd.Timestamp(anchor)
    if unit == "days":
        return (ts + pd.Timedelta(days=n)).to_pydatetime()
    if unit == "weeks":
        return (ts + pd.Timedelta(weeks=n)).to_pydatetime()
    if unit == "months":
        return (ts + pd.DateOffset(months=n)).to_pydatetime()
    raise ValueError(f"Unknown time unit: {unit!r} (expected one of {sorted(UNITS)})")


@dataclass
class TimeWindow:
    start: int
    end: int
    unit: str

    def bounds(self, anchor):
        """Half-open (lo, hi] datetime bounds of this window relative to ``anchor``."""
        return shift(anchor, self.start, self.unit), shift(anchor, self.end, self.unit)

    @property
    def horizon_days(self) -> int:
        per = {"days": 1, "weeks": 7, "months": 30}[self.unit]
        return abs(self.end) * per


@dataclass
class TargetAgg:
    func: str               # COUNT|SUM|AVG|MIN|MAX
    table: str
    column: str | None      # None ==> COUNT(*)
    window: TimeWindow


@dataclass
class Comparison:
    op: str
    value: float


@dataclass
class Filter:
    table: str | None
    column: str
    op: str
    value: object

    def sql(self) -> str:
        col = f'"{self.table}"."{self.column}"' if self.table else f'"{self.column}"'
        val = repr(self.value) if isinstance(self.value, str) else str(self.value)
        return f"{col} {self.op} {val}"


@dataclass
class PredictiveTask:
    target: TargetAgg
    entity_table: str
    entity_key: str
    comparison: Comparison | None = None      # present ==> classification
    where: list[Filter] = field(default_factory=list)        # filters on target rows
    assuming: list[Filter] = field(default_factory=list)     # restrict entity universe
    raw: str = ""

    @property
    def task_type(self) -> str:
        return "classification" if self.comparison is not None else "regression"

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        c = self.column_label()
        cmp = f" {self.comparison.op} {self.comparison.value}" if self.comparison else ""
        return (
            f"PredictiveTask[{self.task_type}]: PREDICT {c}{cmp} "
            f"FOR EACH {self.entity_table}.{self.entity_key}"
        )

    def column_label(self) -> str:
        w = self.target.window
        arg = f"{self.target.table}.{self.target.column or '*'}"
        return f"{self.target.func}({arg}, {w.start}, {w.end}, {w.unit})"
