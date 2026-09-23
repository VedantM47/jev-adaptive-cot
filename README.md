# JEV-Gated Adaptive Chain-of-Thought for Equity Research

> **Research system** measuring whether a compact, calibrated classifier (JEV) can safely replace LLM self-gating in an Adaptive Chain-of-Thought pipeline — reducing cost and latency without degrading evidence grounding or answer quality.

---

## Research Questions

| # | Hypothesis |
|---|---|
| H1 | JEV uses fewer unnecessary operations than LLM self-gating |
| H2 | JEV lowers end-to-end latency (including JEV overhead) |
| H3 | JEV lowers cost per completed query |
| H4 | Grounding quality doesn't materially degrade |
| H5 | Answer quality stays comparable |
| H6 | JEV's confidence is calibrated |

Primary comparison: **Condition B (LLM self-gate) vs Condition C (JEV gate)** — same LLM, same retrieval, same tools, same synthesis. The gate is the **only** variable.

---

## Prerequisites

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) — `pip install uv`
- git

---

## Quick Start

```powershell
# 1. Clone and enter the project
git clone <repo-url>
cd jev-cot

# 2. Install all dependencies (runtime + dev)
uv sync --extra dev

# 3. Verify the config system works
python -c "from jev_cot.config import load_config; cfg = load_config('configs/base.yaml'); print(cfg.llm, cfg.condition)"

# 4. Run the test suite
uv run pytest

# 5. Run linting + type checking
uv run ruff check src/ tests/
uv run mypy src/
```

---

## Repository Structure

```
jev-cot/
├── .planning/            ← GSD planning artifacts (ROADMAP, REQUIREMENTS, STATE)
├── src/jev_cot/          ← Installable Python package
│   ├── config.py         ← Typed experiment config loader (start here)
│   └── logging.py        ← Loguru dual-sink logging setup
├── data/
│   ├── raw/              ← Seed benchmark examples
│   ├── processed/        ← Trajectories, JEV training pairs
│   ├── train/            ← Labeled JEV training data
│   ├── validation/
│   └── test/
├── retrieval/            ← Retrieval interface + FAISS backend
├── models/
│   ├── jev/              ← JEV classifier, training, calibration
│   └── llm/              ← LLM client wrapper, self-gate
├── controller/           ← Controller loop, actions, state extractor, limits
├── evaluation/           ← Grounding, quality, latency, cost, calibration metrics
├── experiments/          ← Run scripts: vanilla / selfgate / jevgate / matrix
├── configs/              ← YAML experiment configs
│   ├── base.yaml         ← Base config (all fields documented)
│   └── conditions/       ← Condition A/B/C presets (Phase 2)
├── logs/                 ← Per-run JSON-lines trajectory logs
├── analysis/             ← Statistical analysis, plots, error taxonomy
├── paper/                ← Results summary and figures
└── tests/                ← pytest test suite
```

---

## Configuration

All experiment parameters live in YAML files under `configs/`. The base config is [`configs/base.yaml`](configs/base.yaml).

Key fields (all required for auditability — PRD §6.6):

| Field | Description |
|---|---|
| `llm` | Model name, e.g. `gemini-1.5-pro-latest` |
| `condition` | `vanilla` / `selfgate` / `jevgate` |
| `prompt_version` | Version tag for all prompts |
| `retrieval_version` | Version tag for the retrieval index |
| `dataset_version` | Version tag for the benchmark dataset |
| `jev_version` | JEV checkpoint version (`none` for Conditions A/B) |
| `random_seed` | Reproducibility seed |
| `max_steps` | Hard step-count cap per trajectory |

```python
from jev_cot.config import load_config
cfg = load_config("configs/base.yaml")
print(cfg.llm)          # gemini-1.5-pro-latest
print(cfg.condition)    # vanilla
```

---

## Phase Status

See [`.planning/ROADMAP.md`](.planning/ROADMAP.md) for the full 19-phase implementation plan and current status.

| Phase | Description | Status |
|---|---|---|
| 1 | Repo scaffolding & config system | ✅ done |
| 2 | Action enum + condition presets | pending |
| 3 | Benchmark schema + loader | pending |
| 4 | Retrieval layer (FAISS) | pending |
| 5 | Vanilla LLM baseline (Condition A) | pending |
| … | … | … |

---

## Development

```powershell
# Run tests with coverage
uv run pytest --cov=jev_cot --cov-report=term-missing

# Auto-fix lint issues
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/

# Type check
uv run mypy src/
```

---

## License

*License TBD — research system, not yet publicly licensed.*

