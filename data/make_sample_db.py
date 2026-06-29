"""Back-compat wrapper — the generator now lives in the installed package
(`relpath.sample_data`) so `relpath make-sample` works for pip-installed users too.

Kept so `python data/make_sample_db.py [output_path]` and `from data.make_sample_db import build`
(used by tests/conftest.py and data/load_*.py) keep working from a source checkout.
"""
from __future__ import annotations

import sys

from relpath.sample_data import build  # re-export

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "data/shop.duckdb")
