---
last_mapped_commit: 237e58f437bc3e9685c2501dd1b012143667e3d4
last_mapped_at: 2026-09-23
---
<!-- refreshed: 2026-09-23 -->

# Architecture

**Analysis Date:** 2026-09-23

## System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                        Configuration Layer                          │
│                    `src/jev_cot/config.py`                          │
│          (Typed experiment config, validation, auditability)        │
└────────────────────┬─────────────────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────────────────┐
│                       Controller Layer                               │
│  `src/jev_cot/controller/` — Routes actions (CONTINUE, RETRIEVE,    │
│   COMPUTE, BRANCH, STOP, ESCALATE) based on condition gate         │
├──────────────────┬──────────────────┬───────────────────────────────┤
│   LLM Gate       │   JEV Gate       │   Controller Loop             │
│  (selfgate)      │  (jevgate)       │   (action orchestration)      │
│ `models/llm/`    │ `models/jev/`    │   `controller/`               │
└──────────────────┴──────────────────┴───────────────────────────────┘
         │                  │                      │
         ▼                  ▼                      ▼
┌────────────────────────────────────────────────────────────────────┐
│                       Tools Layer                                   │
│  `controller/tools/`, `retrieval/`                                  │
│  (Retrieval, Compute, Branch execution)                             │
└────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────┐
│                     Data & Evaluation Layer                         │
│  `src/jev_cot/data/` — Schema validation, splitting, loading       │
│  `src/jev_cot/evaluation/` — Metrics registry (H1-H6)              │
│  `data/` — Datasets (raw, processed, train/val/test splits)        │
└────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────┐
│                      Logging & Observability                        │
│                  `src/jev_cot/logging.py`                           │
│              (Dual-sink: console + JSON-lines file)                 │
└────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Configuration Manager | Load, validate, and audit experiment configs (PRD §6.6) | `src/jev_cot/config.py` |
| Action Enum | Define 6 routing actions: CONTINUE, RETRIEVE, COMPUTE, BRANCH, STOP, ESCALATE | `src/jev_cot/controller/actions.py` |
| LLM Gate | Self-gating gate for Condition B: uses LLM to decide next action | `models/llm/` |
| JEV Classifier | Compact classifier for Condition C: replaces LLM self-gating | `models/jev/` |
| Retrieval Engine | Vector search backend (FAISS), fetches relevant documents | `retrieval/` |
| Data Schema | Canonical benchmark example format (7 question types) | `src/jev_cot/data/schema.py` |
| Data Validator | Validates JSONL datasets against schema | `src/jev_cot/data/validator.py` |
| Data Splitter | Splits dataset by company (zero overlap) into train/val/test | `src/jev_cot/data/split.py` |
| Metrics Registry | Stub definitions of H1-H6 metric formulas | `src/jev_cot/evaluation/metrics_registry.py` |
| Logger | Structured logging to console and JSON-lines files | `src/jev_cot/logging.py` |

## Pattern Overview

**Overall:** Conditional gate architecture with pluggable routing logic.

**Key Characteristics:**

- **Configuration-driven**: All experiment parameters externalized to YAML; changes require no code edits (PRD §6.6)
- **Three-condition comparison**: Vanilla (baseline) vs. Selfgate (LLM) vs. Jevgate (compact classifier) — **only the gate differs**
- **Layered isolation**: Config → Controller → Tools → Data/Evaluation → Logging
- **Reproducibility**: All runs include config dump, random seed, versioned components, auto-timestamped (ISO-8601 UTC)
- **Auditability**: Every experiment must load config through `load_config()` before any pipeline code runs

## Layers

**Configuration Layer:**

- Purpose: Typed, frozen, validated experiment configuration
- Location: `src/jev_cot/config.py`
- Contains: `ExperimentConfig` (Pydantic BaseModel, frozen), `ToolLimitsConfig`, `load_config()` function
- Depends on: pydantic, PyYAML
- Used by: Every experiment script and test

**Controller Layer:**

- Purpose: Routes trajectories through 6 valid actions based on condition-specific gate
- Location: `src/jev_cot/controller/`
- Contains: `Action` enum (StrEnum with 6 values), future controller loop logic
- Depends on: Config layer
- Used by: Experiment scripts, gate implementations (`models/llm/`, `models/jev/`)

**Tools & Execution Layer:**

- Purpose: Implements tool calls (RETRIEVE, COMPUTE, BRANCH) and state management
- Location: `controller/tools/`, `retrieval/`
- Contains: Tool executors, retrieval interface, FAISS backend (future)
- Depends on: Controller layer (action routing)
- Used by: Controller loop during trajectory execution

**Data Layer:**

- Purpose: Defines, validates, and loads benchmark dataset
- Location: `src/jev_cot/data/`
- Contains: `BenchmarkExample` schema (7 question types), `validate_file()` CLI, `split_dataset()` CLI
- Depends on: pydantic, jsonlines
- Used by: Training, evaluation, experiment runners

**Evaluation Layer:**

- Purpose: Registers metrics for all 6 research hypotheses (H1-H6)
- Location: `src/jev_cot/evaluation/`
- Contains: `METRICS` dict with `MetricDefinition` objects (name, formula stubs)
- Depends on: None (pure data)
- Used by: Analysis scripts (future)

**Logging & Observability:**

- Purpose: Dual-sink structured logging (console + JSON-lines for replay)
- Location: `src/jev_cot/logging.py`
- Contains: `setup_logging()`, re-exported loguru logger
- Depends on: loguru
- Used by: All modules for instrumentation

## Data Flow

### Primary Request Path (Vanilla/Selfgate/Jevgate)

1. **Config Load** (`src/jev_cot/config.py:load_config()`)
   - Read YAML from `configs/base.yaml` or condition preset
   - Pydantic validates all required fields
   - Returns frozen `ExperimentConfig` object

2. **Logger Setup** (`src/jev_cot/logging.py:setup_logging()`)
   - Create console + JSON-lines sinks
   - Logs namespaced per run_id

3. **Dataset Load** (`src/jev_cot/data/schema.py`, `validator.py`)
   - Read JSONL from `data/train/`, `data/val/`, `data/test/`
   - Validate each line as `BenchmarkExample` instance
   - If invalid, halt with detailed pydantic error

4. **Trajectory Loop** (future: `src/jev_cot/controller/`)
   - For each benchmark example:
     a. **Initial retrieval**: Fetch documents via `retrieval/` backend
     b. **Gate decision**:
        - **Vanilla**: No gate, single LLM pass
        - **Selfgate**: LLM decides action (models/llm/)
        - **Jevgate**: JEV classifier decides action (models/jev/)
     c. **Action routing**: Controller dispatches action via `Action` enum
     d. **Tool execution**: Calls RETRIEVE, COMPUTE, or BRANCH
     e. **Step limit**: Stop if max_steps, max_latency_seconds, max_cost_usd exceeded
     f. **Log event**: Emit structured log record (action, cost, latency)

5. **Metrics Computation** (future: evaluation scripts)
   - Read trajectory logs from `logs/{run_id}.log.jsonl`
   - Compute H1-H6 metrics using formulas from `METRICS` registry
   - Export to analysis/

### Configuration Propagation

```
configs/base.yaml (or conditions/{vanilla|selfgate|jevgate}.yaml)
    ↓
load_config() → ExperimentConfig (frozen)
    ↓
Passed to experiment scripts & logged in run metadata
    ↓
Used by controller, logger, evaluation for versioning & reproducibility
```

**State Management:**

- **Experiment Config**: Immutable (Pydantic frozen=True) — ensures run parameters never mutate after load
- **Trajectory State**: Mutable list of (action, cost, latency, state_delta) tuples, appended each step
- **Global State**: None — all state passed explicitly through function arguments
- **Side Effects**: Logging (console + file), API calls (LLM, retrieval) — localized to executor functions

## Key Abstractions

**Action Routing:**

- Purpose: Encapsulates the 6 valid transitions in the Adaptive CoT state machine
- Examples: `controller/actions.py` defines `Action` enum
- Pattern: StrEnum for type safety; controller loop switches on action value

**Benchmark Example:**

- Purpose: Canonical data format for all 7 question types (factual retrieval, comparison, multi-doc synthesis, contradiction, calculation, causal, sufficiency)
- Examples: `BenchmarkExample` Pydantic model in `data/schema.py`
- Pattern: Flat JSONL lines, one example per object; company-keyed for split isolation

**Condition Preset:**

- Purpose: Pre-configured YAML that locks the gate and gate-specific parameters
- Examples: `configs/conditions/{vanilla|selfgate|jevgate}.yaml`
- Pattern: YAML with `condition: <literal>`, optionally `jev_version: <checkpoint>`

**Metrics Definition:**

- Purpose: Declarative registry of H1-H6 formulas (not yet implemented)
- Examples: `METRICS["ops_saved"]` → `MetricDefinition(name, description, formula)`
- Pattern: Dict-based registry; implementations added in Phase 13/14

## Entry Points

**Configuration Entry Point:**

- Location: `src/jev_cot/config.py:load_config()`
- Triggers: Every experiment run, test suite
- Responsibilities: Parse YAML, validate schema, return frozen config

**Logging Entry Point:**

- Location: `src/jev_cot/logging.py:setup_logging()`
- Triggers: Immediately after config load
- Responsibilities: Initialize dual sinks (console + JSON-lines)

**Data Validation Entry Point:**

- Location: `src/jev_cot/data/validator.py:main()`
- Triggers: CLI invocation or test suite
- Responsibilities: Validate JSONL file line-by-line

**Data Splitting Entry Point:**

- Location: `src/jev_cot/data/split.py:main()`
- Triggers: CLI invocation or preprocessing pipeline
- Responsibilities: Split input JSONL into train/val/test by company (zero overlap)

**Future Controller Entry Point:**

- Location: (future) `experiments/run_vanilla.py`, `experiments/run_selfgate.py`, `experiments/run_jevgate.py`
- Triggers: CLI: `python experiments/run_*.py --config configs/conditions/<preset>.yaml`
- Responsibilities: Orchestrate trajectory loop for one or more benchmark examples

## Architectural Constraints

- **Threading:** Single-threaded event loop (Python asyncio future), no worker threads. LLM and retrieval calls are blocking.
- **Global state:** None. All state passed explicitly. Logging is the only module-level mutable object (`loguru.logger`).
- **Circular imports:** None detected. Dependency graph is acyclic: config → controller → tools → data → logging.
- **Immutability:** Experiment config is frozen (Pydantic frozen=True); no mutation after load ensures reproducibility.
- **Reproducibility:** Random seed pinned in config; timestamps ISO-8601 UTC; all component versions logged.
- **Auditability:** Every run must load config through `load_config()` and log config fields (PRD §6.6).

## Anti-Patterns

### Hard-coded Parameters in Code

**What happens:** Tool limits, LLM parameters, or condition logic are embedded in Python modules instead of config YAML.
**Why it's wrong:** Requires code edits and re-deployment to change experiment parameters; violates PRD §6.6 auditability mandate.
**Do this instead:** All parameters live in YAML under `configs/` (base or conditions presets). Load via `load_config()`. Condition-specific logic is dispatched via the `condition` field in config.

### Missing Config Versions

**What happens:** Running an experiment without recording which prompt, retrieval index, or dataset version was used.
**Why it's wrong:** Makes results non-reproducible and non-auditable. Can't trace improvements or regressions.
**Do this instead:** Every config must include `prompt_version`, `retrieval_version`, `dataset_version`, `jev_version` fields. These are logged with every run.

### Mutable Trajectory State

**What happens:** Trajectory list or controller state mutated directly in nested functions without returning the updated state.
**Why it's wrong:** Makes debugging hard; makes it unclear which function owns state updates.
**Do this instead:** Trajectory state is immutable list of tuples; each step appends a new tuple and returns the updated list. Controller loop receives the new state.

## Error Handling

**Strategy:** Fail fast with detailed error messages; do not swallow exceptions.

**Patterns:**

- **Config validation errors**: Pydantic `ValidationError` with full field path and constraint details. Halt immediately.
- **Missing files**: `FileNotFoundError` with absolute path. Halt immediately.
- **Data schema violations**: Line-by-line validation in `validator.py` and `split_dataset()`. Log line number and error, continue to next line (collect all errors before failing).
- **Tool execution errors** (future): Caught in controller loop, logged with trajectory context, escalate to next action or STOP.

## Cross-Cutting Concerns

**Logging:** Dual-sink (console + JSON-lines). All significant events logged with context (run_id, step, action, cost, latency). Console is human-readable; file is machine-parseable for replay and analysis.

**Validation:** Schema validation via Pydantic at three points: config load, benchmark data, tool_limits. Validation errors include full context (line number, field path, constraint).

**Authentication:** None yet. Future LLM/retrieval calls will use env var tokens (e.g., `GEMINI_API_KEY`, `FAISS_INDEX_PATH`).

---

*Architecture analysis: 2026-09-23*
