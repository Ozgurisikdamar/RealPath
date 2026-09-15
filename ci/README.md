# CI workflows (staging)

> ⛔ **ÖNCE OKU (2026-09-15, ölçüldü): bunları etkinleştirmek BİR ŞEY ÜRETMEZ.**
> `Ozgurisikdamar` hesabında GitHub Actions hiç koşmadı — workflow'u olan iki depoda
> **55/55 koşum `startup_failure`**, sıfır başarı, `workflow_dispatch` dahil. Koşum
> workflow dosyasını okumaya hiç ulaşmıyor (`path: BuildFailed`), yani aşağıdaki
> reçete YAML açısından doğru ama **yeşil bir kapı vermez**. Sebep hesap düzeyinde
> (faturalandırma). Tek gerçek kapı yereldir: `python -m pytest tests/ -q`.
> ⚠️ Bu özellikle `gnn-eval.yml`'i vurur: "temiz Linux runner" diye bir mekân yok
> (`docs/DECISIONS.md` **ADR-015**, `docs/BENCHMARKS.md` §6).
> Ayrıca bu depoya **`schedule:` tetikleyicisi eklenmez.**

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
