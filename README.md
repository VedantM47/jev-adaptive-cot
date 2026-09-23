# JEV-Gated Adaptive Chain-of-Thought for Equity Research

> **Research system** measuring whether a compact, calibrated classifier (JEV) can safely replace LLM self-gating in an Adaptive Chain-of-Thought pipeline — reducing cost and latency without degrading evidence grounding or answer quality.

**Docs:** [Introduction](docs/INTRO.md) · [Testing Guide](docs/TESTING-GUIDE.md) · [Full Technical Write-up](docs/PROJECT-OVERVIEW.md)

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

All real code lives under `src/jev_cot/` (the installable package) — that's
the one to read. The top-level `retrieval/`, `models/`, `controller/`,
`evaluation/`, `experiments/` folders are empty leftovers from the initial
scaffold, kept but unused (nothing imports them).

```
jev-cot/
├── app.py                ← Streamlit frontend (calls src/jev_cot/ directly)
├── docs/                 ← Intro, testing guide, full technical write-up
├── .planning/            ← GSD planning artifacts (ROADMAP, REQUIREMENTS, STATE)
├── src/jev_cot/          ← Installable Python package — ALL real code lives here
│   ├── config.py         ← Typed experiment config loader (start here)
│   ├── logging.py        ← Loguru dual-sink logging setup
│   ├── retrieval/        ← Retrieval interface + FAISS backend
│   ├── models/
│   │   ├── jev/          ← JEV classifier, training, calibration
│   │   └── llm/          ← LLM client wrapper, self-gate
│   ├── controller/       ← Controller loop, actions, state extractor, limits
│   ├── evaluation/       ← Grounding, quality, latency, cost, calibration metrics
│   ├── experiments/      ← Run scripts: vanilla / selfgate / jevgate / matrix
│   ├── analysis/         ← Statistical analysis, error taxonomy, report generator
│   └── data/             ← Benchmark schema, splitter, trajectory schema
├── data/
│   ├── raw/              ← Seed benchmark examples + documents
│   ├── processed/        ← Trajectories, JEV training pairs (generated)
│   └── train/            ← Labeled JEV training data (generated)
├── configs/              ← YAML experiment configs
│   ├── base.yaml         ← Base config (all fields documented)
│   └── conditions/       ← Condition A/B/C presets (Phase 2)
├── logs/                 ← Per-run JSON-lines trajectory logs (generated)
├── models/jev/checkpoints/ ← Trained JEV artifacts (generated)
├── paper/                ← Auto-generated results summary
└── tests/                ← pytest test suite (139 tests)
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
print(cfg.llm)  # gemini-1.5-pro-latest
print(cfg.condition)  # vanilla
```

---

## Running the Full Pipeline

**1. Get a Gemini API key** (free tier is plenty): https://aistudio.google.com/apikey

**2. Set it up:**
```powershell
cp .env.example .env
# then edit .env and paste your key after GEMINI_API_KEY=
```

**3. Run each stage, in order** (each is also runnable as `python -m jev_cot.<module>`):
```powershell
# Baselines
uv run python -m jev_cot.experiments.run_vanilla       # Condition A
uv run python -m jev_cot.experiments.run_selfgate      # Condition B

# Collect (state, action) pairs from Condition B, then train + calibrate + freeze JEV
uv run python -m jev_cot.experiments.collect_trajectories
uv run python -m jev_cot.models.jev.labeling.rules
uv run python -m jev_cot.models.jev.train
uv run python -m jev_cot.models.jev.calibrate

# Condition C, now that a frozen JEV checkpoint exists
uv run python -m jev_cot.experiments.run_jevgate

# Oracle upper bound
uv run python -m jev_cot.experiments.run_oracle

# Score any trajectories file for grounding + answer quality
uv run python -m jev_cot.experiments.evaluate_run --trajectories logs/<run>_trajectories.jsonl

# Full factorial matrix (the primary result) + auto-generated report
uv run python -m jev_cot.experiments.run_matrix
uv run python -m jev_cot.analysis.generate_report

# Ablations
uv run python -m jev_cot.experiments.ablations.size_ablation
uv run python -m jev_cot.experiments.ablations.feature_ablations
```

The FAISS index auto-builds on first use — no separate ingest step needed unless you want to rebuild it (`python -m jev_cot.retrieval.ingest`).

Everything above makes real Gemini API calls and costs real (tiny) money — the seed dataset is 9 examples, so a full pass through every command above is a handful of cents on the free/low tier, not more.

**Offline, no API key needed:** `uv run pytest` — the full test suite (139 tests) including `tests/test_pipeline_smoke.py`, which exercises the entire controller loop, JEV train/calibrate/save/load, and evaluation math end-to-end with a fake LLM client.

---

## Frontend

A small Streamlit UI (`app.py`) sits directly on top of the backend above — no separate API layer, it calls the same Python code the CLI scripts use.

```powershell
uv run streamlit run app.py
```

Opens at `http://localhost:8501`. Three tabs: **Run a Question** (pick a benchmark question + condition, run it live), **Results** (the factorial matrix table, once `run_matrix.py` has produced one), **About** (the problem statement). See `docs/TESTING-GUIDE.md` §3 for details.

---

## Phase Status

See [`.planning/ROADMAP.md`](.planning/ROADMAP.md) for the full 19-phase implementation plan and current status.

| Phase | Description | Status |
|---|---|---|
| 1 | Repo scaffolding & config system | ✅ done |
| 2 | Action enum + condition presets | ✅ done |
| 3 | Benchmark schema + loader | ✅ done |
| 4 | Retrieval layer (FAISS) | ✅ done |
| 5 | Vanilla LLM baseline (Condition A) | ✅ built (needs API key to run) |
| 6 | Structured state extractor | ✅ built |
| 7 | Self-gate + controller loop (Condition B) | ✅ built (needs API key to run) |
| 8 | Trajectory collection | ✅ built |
| 9 | JEV label generation (rule-based) | ✅ built |
| 10 | JEV model training (S/M/L) | ✅ built |
| 11 | JEV calibration + freeze | ✅ built |
| 12 | JEV integration (Condition C) | ✅ built (needs API key to run) |
| 13-14 | Evaluation suite (efficiency/latency/grounding/quality) | ✅ built |
| 15 | Full factorial experiment runner | ✅ built |
| 16 | Ablation suite (size + feature) | ✅ built |
| 17 | Oracle gate | ✅ built |
| 18 | Error taxonomy | ✅ built |
| 19 | Statistics + auto-generated report | ✅ built |

"Built" means the code is written, imports cleanly, passes mypy --strict and ruff, and is exercised by an offline smoke test — but anything touching Gemini needs your API key in `.env` to actually run and hasn't been live-tested against the real API yet.

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

