# RESEARCH.md — Phase 1: Repo Scaffolding & Config System

**Generated:** 2026-09-23  
**Phase:** 1 — Repo Scaffolding & Config System

---

## Environment Findings

| Item | Status | Notes |
|---|---|---|
| Python 3.13 | ✅ installed | Only version available; 3.11 not present |
| Python 3.11 | ❌ not installed | uv can manage it automatically via `requires-python` |
| uv | ❌ not installed | Must install first; available via `pip install uv` or PowerShell installer |
| git | ✅ v2.50.0 | Configured (user: VedantM47, email: imvedant47@gmail.com) |

## Python Version Strategy

**Decision for this phase:** Target Python `>=3.11` in `pyproject.toml` rather than pinning to exactly 3.11. This lets uv use the installed 3.13 immediately while keeping the option to pin to 3.11 later if a dependency requires it. uv's managed Python feature (`uv python install 3.11`) can be invoked from the Makefile if strict 3.11 is needed for a specific dependency.

**Rationale:** All key dependencies (pydantic v2, pytest, PyYAML, jsonlines, loguru) support Python 3.11–3.13. XGBoost, LightGBM, FAISS, and sentence-transformers all publish 3.13-compatible wheels. No blocking incompatibility found.

## uv Installation Strategy

Install via pip (available everywhere Python is): `pip install uv`  
After install: `uv init` bootstraps `pyproject.toml` and `uv.lock`.

## Key Dependency Versions (latest stable, 2026-09)

| Package | Version | Purpose |
|---|---|---|
| pydantic | 2.x | Config validation + typed state schema |
| pyyaml | 6.x | YAML config parsing |
| jsonlines | 4.x | Streaming trajectory log writes |
| loguru | 0.7.x | Structured logging with JSON sink |
| pytest | 8.x | Test runner |
| pytest-cov | 5.x | Coverage reporting |
| ruff | 0.6.x | Linting + formatting |
| mypy | 1.x | Type checking |

## CI Choice

GitHub Actions (free, standard). `.github/workflows/ci.yml` with: install uv → uv sync → pytest → ruff check → mypy.

## Config Schema Fields (from PRD §6.6)

Fields required in every experiment run config:
- `llm` (model name + version)
- `jev_version`
- `prompt_version`
- `retrieval_version`
- `dataset_version`
- `temperature`
- `max_tokens`
- `max_steps`
- `tool_limits` (max_retrievals, max_branches, max_compute_calls)
- `random_seed`
- `timestamp` (auto-generated at run start)

## Structured Logging Design

Use `loguru` with a JSON sink for machine-readable logs. One log file per run, named `{run_id}_{timestamp}.jsonl`. The trajectory schema (Appendix B) is separate from the application log — trajectories are written by dedicated trajectory writers, not the logger.

## Directory Structure (confirmed from PRD §10)

```
project/
├── .planning/           (already exists — GSD artifacts)
├── data/{raw,processed,train,validation,test}/
├── retrieval/
├── models/{jev,llm}/
├── controller/
├── evaluation/{grounding,quality,latency,cost}/
├── experiments/
├── configs/{conditions}/
├── logs/
├── analysis/
└── paper/
```

Plus standard Python project files at root:
```
├── pyproject.toml
├── uv.lock
├── README.md
├── .gitignore
├── .github/workflows/ci.yml
└── tests/
    ├── __init__.py
    └── test_config.py   (initial test — loads sample config)
```

