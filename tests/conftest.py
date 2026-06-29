"""Shared pytest fixtures."""
import sys
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def sample_db(tmp_path_factory) -> str:
    """Build the synthetic e-commerce DuckDB once per test session."""
    from data.make_sample_db import build

    out = tmp_path_factory.mktemp("realpath_data") / "shop.duckdb"
    build(out)
    return str(out)


@pytest.fixture(scope="session")
def engine(sample_db):
    """A connected Engine on the sample DB, shared across tests (EntitySet built once)."""
    import realpath as rp

    eng = rp.connect(sample_db)
    yield eng
    eng.close()
