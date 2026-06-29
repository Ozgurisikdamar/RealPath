# realpath.dev — OSS Launch Checklist

Pre-launch checklist for the public GitHub / Show HN release. (Repo is currently **private**.)

## Repo hygiene
- [x] `LICENSE` (MIT) at root.
- [x] `README.md` (bilingual) with quickstart + CI badge.
- [x] `CONTRIBUTING.md` (setup, tests, guardrails).
- [x] CI green (GitHub Actions: ruff + pytest on push/PR). *(workflow commit needs a token with
      `workflow` scope to push — see HANDOVER.)*
- [x] `docs/` complete: ARCHITECTURE, API, DECISIONS, SPRINTS, BENCHMARKS, PITCH, SKILLS, INDEX, SPEC.
- [ ] `CODE_OF_CONDUCT.md` (Contributor Covenant) — optional, add before going public.
- [ ] GitHub repo **topics**: `relational-deep-learning`, `predictive-query`, `automl`,
      `feature-engineering`, `duckdb`, `local-first`, `explainable-ai`.
- [ ] Repo **description** + website set (already on the GitHub repo).
- [ ] Decide visibility → **make public** (currently private; open-core thesis ⇒ public core).

## Proof & messaging
- [x] [BENCHMARKS.md](BENCHMARKS.md) — verified numbers + reproduction.
- [x] [PITCH.md](PITCH.md) — one-page positioning.
- [x] [`examples/quickstart.ipynb`](../examples/quickstart.ipynb) — runnable in 60 seconds.
- [ ] Short demo GIF / asciinema of `realpath predict … --explain`.

## Distribution
- [x] PyPI build dry-run green (`python -m build` + `twine check` PASSED; wheel installs clean).
- [ ] Publish to PyPI (`twine upload`) — **when ready to go public** (needs PyPI account/token).
- [ ] NL→PQL interactive web demo (Streamlit Cloud / HF Spaces) — lead magnet (Sprint 4).

## Announce (drafts)
- [ ] **Show HN** draft: *"Show HN: realpath – open-source, local-first alternative to Kumo.AI
      (predict over your relational DB in plain English)"*. Body: problem (feature-engineering
      hell) → 4 moats → benchmarks → `pip install realpath`.
- [ ] r/MachineLearning / r/dataengineering post.
- [ ] Vertical SEO posts: "open-source churn prediction", "self-hosted demand forecasting",
      "relational deep learning without GPUs".

> Tracking: this is the Sprint 1 closing checklist; remaining `[ ]` items roll into Sprint 4
> (Product Surface & GTM) and the public-launch decision.
