---
last_mapped_commit: 237e58f437bc3e9685c2501dd1b012143667e3d4
last_mapped_at: 2026-09-23
---
# Codebase Structure

**Analysis Date:** 2026-09-23

## Directory Layout

```
jev-adaptive-cot/
├── .planning/              # GSD planning artifacts (ROADMAP, REQUIREMENTS, STATE)
│   ├── codebase/           # (This file) Architecture & structure docs
│   ├── phases/             # Per-phase planning (Phase 1, 2, 3)
│   └── research/           # Research notes & references
├── src/jev_cot/            # Main installable Python package
│   ├── __init__.py         # Package entry point (main() function)
│   ├── config.py           # Typed experiment config loader (START HERE)
│   ├── logging.py          # Dual-sink structured logging (console + JSON-lines)
│   ├── controller/         # Action routing & control flow
│   │   ├── __init__.py     # Exports Action enum
│   │   └── actions.py      # 6-action enum (CONTINUE, RETRIEVE, COMPUTE, BRANCH, STOP, ESCALATE)
│   ├── data/               # Data layer (schema, validation, splitting)
│   │   ├── __init__.py
│   │   ├── schema.py       # BenchmarkExample Pydantic model (7 question types)
│   │   ├── validator.py    # CLI tool to validate JSONL datasets
│   │   └── split.py        # CLI tool to split dataset by company (zero overlap)
│   └── evaluation/         # Evaluation layer (metrics registry)
│       ├── __init__.py     # Exports METRICS & MetricDefinition
│       └── metrics_registry.py  # H1-H6 metric definitions (stubs)
├── configs/                # YAML experiment configurations
│   ├── base.yaml           # Base config (all required fields documented)
│   └── conditions/         # Condition presets (Phase 2)
│       ├── vanilla.yaml    # Condition A: single LLM pass (no adaptive control)
│       ├── selfgate.yaml   # Condition B: LLM self-gating
│       └── jevgate.yaml    # Condition C: JEV classifier gating
├── data/                   # Datasets
│   ├── raw/                # Seed benchmark examples
│   │   └── sample_examples.jsonl  # 7 examples covering all question types
│   ├── processed/          # Trajectories, JEV training pairs (future)
│   ├── train/              # Labeled training split (future)
│   ├── validation/         # Validation split (future)
│   └── test/               # Test split (future)
├── retrieval/              # Retrieval interface & backend (future: FAISS)
│   └── __init__.py         # (Placeholder)
├── models/                 # ML models
│   ├── jev/                # JEV classifier (future)
│   │   ├── __init__.py
│   │   └── labeling/       # Training data for JEV (future)
│   └── llm/                # LLM client wrapper & self-gate (future)
│       └── __init__.py
├── controller/             # Controller loop & tools (future)
│   ├── __init__.py
│   └── tools/              # Tool executors (RETRIEVE, COMPUTE, BRANCH)
│       └── __init__.py
├── evaluation/             # Evaluation metrics implementations (future)
│   ├── __init__.py
│   ├── cost/               # Cost calculation
│   ├── grounding/          # Grounding quality metrics
│   ├── latency/            # Latency measurement
│   └── quality/            # Answer quality metrics
├── experiments/            # Run scripts
│   ├── ablations/          # Ablation study scripts
│   └── (vanilla, selfgate, jevgate run scripts — future)
├── tests/                  # pytest test suite
│   ├── __init__.py
│   ├── conftest.py         # Fixtures (base_yaml)
│   ├── test_config.py      # Config loading & validation tests
│   ├── test_data_schema.py # Data schema validation tests
│   ├── test_data_split.py  # Data splitting logic tests
│   └── test_phase2.py      # Phase 2 deliverables (Action, presets, metrics)
├── logs/                   # Per-run JSON-lines trajectory logs (created at runtime)
│   └── {run_id}.log.jsonl  # Structured log for one run
├── analysis/               # Statistical analysis, plots, error taxonomy (future)
├── paper/                  # Results summary and figures (future)
├── pyproject.toml          # Python project metadata (uv, pytest, ruff, mypy)
├── uv.lock                 # Locked dependency versions
├── README.md               # Quick start & overview
└── .gitignore              # Git ignore rules
```

## Directory Purposes

**`.planning/`:**

- Purpose: GSD project planning and documentation
- Contains: ROADMAP, REQUIREMENTS, STATE, codebase analysis docs, per-phase plans
- Key files: `.planning/ROADMAP.md` (19-phase plan), `.planning/codebase/` (this analysis)

**`src/jev_cot/`:**

- Purpose: Main installable Python package (uv installs from here)
- Contains: Core pipeline code — config, logging, controller, data, evaluation
- Key files: `config.py` (START HERE), `logging.py`, `controller/actions.py`

**`configs/`:**

- Purpose: YAML experiment configurations (externalize all parameters)
- Contains: Base config + 3 condition presets (vanilla, selfgate, jevgate)
- Key files: `base.yaml` (template), `conditions/{vanilla|selfgate|jevgate}.yaml` (Phase 2 deliverables)

**`data/`:**

- Purpose: Datasets at all stages (raw, processed, train/val/test splits)
- Contains: Benchmark examples in JSONL format
- Key files: `raw/sample_examples.jsonl` (7 examples, all question types), future splits

**`retrieval/`:**

- Purpose: Retrieval interface and backend implementation (FAISS planned)
- Contains: Vector search, document indexing, caching (future)
- Key files: (Placeholder for now; implementations in Phase 4)

**`models/`:**

- Purpose: ML models: JEV classifier (Phase 7+) and LLM client (Phase 5+)
- Contains: Model training, inference, checkpoints
- Key files: `jev/`, `llm/` (both placeholders; Phase 5 adds LLM gate)

**`controller/`:**

- Purpose: Controller loop, action orchestration, tool execution
- Contains: Trajectory stepping, tool call dispatch, state management (future)
- Key files: (Placeholder; Phase 4+ adds loop and tool executors)

**`evaluation/`:**

- Purpose: Metrics computation and experimental analysis
- Contains: Cost calculation, grounding quality, latency, answer quality metrics
- Key files: `cost/`, `grounding/`, `latency/`, `quality/` (all Phase 13/14+)

**`experiments/`:**

- Purpose: Runnable experiment scripts (one per condition + ablations)
- Contains: Entrypoints that tie config, controller, data, evaluation together
- Key files: (Future; Phase 5+ adds run_vanilla.py, run_selfgate.py, run_jevgate.py)

**`tests/`:**

- Purpose: pytest test suite covering all modules
- Contains: Unit tests, integration tests, acceptance criteria validation
- Key files: `conftest.py` (fixtures), `test_config.py`, `test_data_schema.py`, `test_data_split.py`, `test_phase2.py`

**`logs/`:**

- Purpose: Runtime trajectory logs (one JSONL file per experiment run)
- Contains: Structured events emitted by controller loop (created at runtime)
- Key files: `{run_id}.log.jsonl` — machine-readable for replay and metrics computation

**`analysis/`:**

- Purpose: Statistical analysis, visualizations, error taxonomy (future)
- Contains: Jupyter notebooks, Python scripts, plots, tables
- Key files: (Phase 14+ adds analysis scripts)

**`paper/`:**

- Purpose: Results summary, tables, figures for publication (future)
- Contains: Markdown, images, data tables
- Key files: (Phase 19 final wrap-up)

## Key File Locations

**Entry Points:**

- `src/jev_cot/__init__.py`: Package entry point (placeholder main() function)
- `src/jev_cot/config.py:load_config()`: Config loading (all runs start here)
- `src/jev_cot/logging.py:setup_logging()`: Logger initialization
- Future: `experiments/run_{vanilla|selfgate|jevgate}.py`: Experiment runners

**Configuration:**

- `configs/base.yaml`: Base experiment config template (all fields documented)
- `configs/conditions/vanilla.yaml`: Condition A preset (no gate)
- `configs/conditions/selfgate.yaml`: Condition B preset (LLM gate)
- `configs/conditions/jevgate.yaml`: Condition C preset (JEV gate)

**Core Logic:**

- `src/jev_cot/config.py`: Pydantic config models (ExperimentConfig, ToolLimitsConfig)
- `src/jev_cot/controller/actions.py`: 6-action enum (CONTINUE, RETRIEVE, COMPUTE, BRANCH, STOP, ESCALATE)
- `src/jev_cot/data/schema.py`: BenchmarkExample Pydantic model (7 question types)
- `src/jev_cot/evaluation/metrics_registry.py`: H1-H6 metric definitions (stubs)
- `src/jev_cot/logging.py`: Loguru dual-sink setup

**Testing:**

- `tests/conftest.py`: Fixtures (base_yaml, future dataset fixtures)
- `tests/test_config.py`: Config loading, validation, immutability (10 ACs)
- `tests/test_data_schema.py`: Schema validation, sample dataset
- `tests/test_data_split.py`: Company-key zero-overlap splitting
- `tests/test_phase2.py`: Action enum, condition presets, metrics registry

## Naming Conventions

**Files:**

- Python modules: `snake_case.py` (e.g., `config.py`, `metrics_registry.py`)
- YAML configs: `snake_case.yaml` (e.g., `base.yaml`, `vanilla.yaml`)
- Test files: `test_{module}.py` (e.g., `test_config.py`, `test_data_schema.py`)
- Log files: `{run_id}.log.jsonl` (e.g., `run_20260923_abc123.log.jsonl`)

**Directories:**

- Package directories: `snake_case/` (e.g., `jev_cot/`, `data/`, `controller/`)
- Top-level directories: `snake_case/` (e.g., `configs/`, `models/`, `retrieval/`)
- Subdirectories: Purpose-named (e.g., `conditions/`, `tools/`, `labeling/`, `cost/`, `grounding/`)

**Python Identifiers:**

- Classes: `PascalCase` (e.g., `ExperimentConfig`, `BenchmarkExample`, `Action`)
- Functions: `snake_case` (e.g., `load_config()`, `setup_logging()`, `validate_file()`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `METRICS`, `Action.CONTINUE`)
- Private: Prefix with `_` (e.g., `_create_dummy_data()`, `_minimal_yaml()`)

**Configuration:**

- Field names in YAML: `snake_case` (e.g., `llm`, `max_steps`, `tool_limits.max_retrievals`)
- Enum values: `UPPER_SNAKE_CASE` in Action enum; lowercase string in config condition field
- Condition literals: `vanilla`, `selfgate`, `jevgate` (lowercase strings)
- Version strings: Format `{component}-v{major}.{minor}` (e.g., `faiss-v0.1`, `phase1-seed-v0.1`)

## Where to Add New Code

**New Feature (e.g., a new Action type):**

- Primary code: `src/jev_cot/controller/actions.py` — Add action to `Action` enum (StrEnum)
- Controller integration: Future `src/jev_cot/controller/` (Phase 6+) — Add dispatcher case
- Tests: `tests/test_phase2.py` or new `tests/test_actions.py` — Test enum presence and value

**New Data Validation Rule:**

- Schema update: `src/jev_cot/data/schema.py` — Add field to `BenchmarkExample` Pydantic model
- Validator update: `src/jev_cot/data/validator.py` — Add line-by-line check if needed
- Tests: `tests/test_data_schema.py` — Test valid + invalid cases

**New Metric Definition:**

- Add to registry: `src/jev_cot/evaluation/metrics_registry.py` — Append to `METRICS` dict with new `MetricDefinition(name, description, formula)`
- Implementation: Future `src/jev_cot/evaluation/{cost|grounding|latency|quality}/` (Phase 13/14)
- Tests: `tests/test_phase2.py` — Verify metric is in registry

**New Experiment Condition:**

- Config preset: `configs/conditions/{new_condition}.yaml` — Copy and modify vanilla/selfgate/jevgate preset
- Implementation: Dispatch in controller loop (future) based on `config.condition` value
- Tests: `tests/test_phase2.py:test_config_presets()` — Add load test for new preset

**New Tool Implementation (e.g., RETRIEVE executor):**

- Tool code: `controller/tools/retrieve.py` (future) or `src/jev_cot/controller/tools/retrieve.py`
- Integration: Update controller loop (Phase 6+) to dispatch `Action.RETRIEVE` → tool executor
- Tests: New `tests/test_retrieve_tool.py` (future)

**New Utility or Helper:**

- Shared utilities: `src/jev_cot/utils/` (create if not exists) or module-specific `src/jev_cot/{module}/_helpers.py`
- Private/internal: Prefix with `_` (e.g., `_normalize_text()`)
- Tests: `tests/test_utils.py` or `tests/test_{module}.py`

## Special Directories

**`.planning/`:**

- Purpose: GSD planning artifacts (not deployed, for project management)
- Generated: Partially (phase plans created by `/gsd-plan-phase`; codebase docs by `/gsd-map-codebase`)
- Committed: Yes — kept in git for historical reference

**`logs/`:**

- Purpose: Runtime trajectory logs (one file per experiment run)
- Generated: Yes — created by `setup_logging()` at runtime
- Committed: No — added to `.gitignore` (sensitive experiment data)

**`.github/workflows/`:**

- Purpose: CI/CD pipeline (stub, Phase 1 deliverable)
- Generated: No (manually maintained)
- Committed: Yes

**`data/raw/`:**

- Purpose: Seed benchmark examples (static, version-controlled)
- Generated: No (manually created by research team)
- Committed: Yes

**`data/{processed,train,validation,test}/`:**

- Purpose: Processed datasets and splits
- Generated: Yes — by `split_dataset()` and future preprocessing
- Committed: No (large files, add to `.gitignore` if not already)

**`models/jev/labeling/`:**

- Purpose: Training data for JEV classifier
- Generated: Yes — from benchmark trajectories (Phase 7+)
- Committed: No (generated data)

---

*Structure analysis: 2026-09-23*
