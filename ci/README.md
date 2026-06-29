# CI workflows (staging)

These are GitHub Actions workflows kept here (a plain `ci/` dir) because pushing under
`.github/workflows/` requires a token with the **`workflow`** scope, which the current setup
lacks. To activate them:

```bash
gh auth refresh -h github.com -s workflow      # grant the scope (interactive)
mkdir -p .github/workflows && git mv ci/ci.yml ci/gnn-eval.yml .github/workflows/
git commit -m "Activate CI workflows" && git push
```

- **`ci.yml`** — runs `ruff` + `pytest` on every push/PR (Python 3.10 & 3.11). The core suite is
  torch-free, so this is fast. (Locally validated: clean-room `pip install -e ".[dev]"` → 25/25.)
- **`gnn-eval.yml`** — manual (`workflow_dispatch`) heavy job: installs torch + PyG + **`pyg-lib`**
  (Linux-only) and runs the **fair, leakage-safe temporal GNN** on a RelBench task, alongside the
  DFS baseline. This is the proper venue for the GNN temporal benchmark (a clean Linux runner with
  disk space) — see [docs/BENCHMARKS.md](../docs/BENCHMARKS.md) §6 and ADR-011.
