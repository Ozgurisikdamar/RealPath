# Contributing to realpath.dev

Thanks for your interest! realpath is an open-source, self-hostable, **local-first**
relational prediction engine. This guide gets you from clone to green tests.

> Deep dives: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (how it works),
> [`docs/SKILLS.md`](docs/SKILLS.md) (task recipes), [`docs/DECISIONS.md`](docs/DECISIONS.md)
> (why things are the way they are), [`docs/ROADMAP.md`](docs/ROADMAP.md) (what's next).

## Development setup

Requires Python **3.10+**.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  Unix:  source .venv/bin/activate
pip install -e ".[dev]"
```

> ⚠️ **pandas is pinned to `>=2.0,<2.3`.** pandas 3.0 breaks `woodwork`'s `.ww` accessor
> (the Featuretools EntitySet fails to build). Do not bump it — see
> [DECISIONS.md ADR-001](docs/DECISIONS.md). `pip install -e .` already enforces this.

Generate the bundled sample database (it's git-ignored — regenerate anywhere):

```bash
python data/make_sample_db.py data/shop.duckdb
```

## Running tests & lint

```bash
pytest tests/ -q          # expect: 25 passed, 1 skipped
ruff check realpath/ tests/ data/
```

On Windows, set `PYTHONUTF8=1` if you see encoding errors on Turkish output (the library
also prints encoding-safely via `realpath._io.sprint`).

### The Postgres test (opt-in)

`tests/test_postgres.py` is skipped unless you point it at a Postgres with the sample data:

```bash
docker run -d --name realpath-pg -e POSTGRES_PASSWORD=realpath -e POSTGRES_DB=shop \
    -p 55432:5432 postgres:16
python data/load_postgres.py postgresql://postgres:realpath@localhost:55432/shop
REALPATH_TEST_PG=postgresql://postgres:realpath@localhost:55432/shop pytest tests/test_postgres.py -q
```

## Guardrails (please respect these)

- **No future leakage.** Features must only use data at or before each entity's *anchor
  timestamp*. This is enforced structurally via Featuretools `cutoff_time` and proven by
  `tests/test_leakage.py` (it deletes all post-anchor rows and asserts the feature matrix is
  unchanged). If you touch feature synthesis, that test must stay green.
- **Local-first.** Nothing should *require* sending data to a third party. Keep DuckDB the
  default; new backends connect read-only.
- **Core stays permissively licensed** (MIT/BSD/Apache). `getML` (ELv2) and `TabPFN-2.5`
  (non-commercial) are quarantined as optional plugins, never core dependencies.
- **CI must pass.** `ruff` + `pytest` run on every push/PR (Python 3.10 & 3.11).

## Common contributions (recipes in [`docs/SKILLS.md`](docs/SKILLS.md))

- **New vertical template** → `realpath/templates.py` builder + `Engine` method + a test.
- **New DB connector** → implement the `DuckDBBackend` surface
  (`tables/columns/row_count/distinct_count/load/query/close`) and route it in
  `open_backend`. `PostgresBackend` is a worked example.
- **New PQL aggregation** → `pql/ast.py` (`AGGS`) + parser + `pql/compile.py` SQL mapping + a
  parser test.

## Pull requests

- Keep PRs focused; one logical change each.
- Commit messages: short, imperative, **English** (e.g. "Add MySQL connector").
- Make sure `ruff check` and `pytest` are clean locally before opening the PR.
- New behavior needs a test. New public surface needs a docstring.

## License

MIT (see `pyproject.toml`). By contributing you agree your contributions are licensed under MIT.
