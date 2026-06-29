"""realpath.dev — the open-source, self-hostable relational prediction engine.

Connect a database, ask a predictive question in plain language (or PQL),
and get an *explained* answer — without moving your data anywhere.

Quick start
-----------
>>> import realpath as rp
>>> engine = rp.connect("data/shop.duckdb")
>>> result = engine.predict(
...     "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id"
... )
>>> result.predictions.head()
>>> result.explain()
"""

from .engine import Engine, connect
from .result import PredictionResult
from .pql import PredictiveTask, parse_pql

__version__ = "0.1.0"

__all__ = [
    "Engine",
    "connect",
    "PredictionResult",
    "PredictiveTask",
    "parse_pql",
    "__version__",
]
