# PLAN.md — Phase 1: Repo Scaffolding & Config System

**Phase:** 1 of 19  
**Status:** Ready for execution  
**Depends on:** none  
**Blocks:** Phase 2, Phase 3 (all subsequent phases)  
**Estimated effort:** ~2–3 hours

---

## Objective

Create the foundational Python project skeleton — directory structure, typed config loader, logging infrastructure, test runner, CI stub, and initial git commit — that every subsequent phase builds on.

**Nothing in this phase makes LLM calls, does retrieval, or touches JEV.**

---

## Tracer Slice (end-to-end proof of life)

Before any expansion tasks, the following must work end-to-end:

```
uv sync → python -c "from jev_cot.config import load_config; cfg = load_config('configs/base.yaml'); print(cfg)" → pytest → exits 0
```

This is the acceptance signal for the tracer. Expansion tasks then fill out the full structure around it.

---

## Tasks

### T1 · Install uv
**Type:** setup  
**Files:** (none — system install)

```powershell
pip install uv
```

Verify: `uv --version` exits 0.

---

### T2 · Initialize project with uv
**Type:** setup  
**Files:** `pyproject.toml`, `uv.lock`  
**Depends on:** T1

```powershell
uv init --name jev-cot --python ">=3.11" --no-workspace
```

Then manually edit `pyproject.toml` to:
- Set `name = "jev-cot"`, `version = "0.1.0"`
- Add all Phase 1 dependencies (see T4)
- Add `[tool.pytest.ini_options]`, `[tool.ruff]`, `[tool.mypy]` sections

---

### T3 · Create full directory structure
**Type:** scaffold  
**Files:** all directories + `__init__.py` stubs  
**Depends on:** T2

Create the following directory tree (all empty `__init__.py` files make them importable Python packages):

```
data/
  raw/
  processed/
  train/
  validation/
  test/
retrieval/
  __init__.py
models/
  jev/
    labeling/
    checkpoints/
    __init__.py
  llm/
    __init__.py
controller/
  tools/
    __init__.py
  __init__.py
evaluation/
  grounding/
    __init__.py
  quality/
    __init__.py
  latency/
    __init__.py
  cost/
    __init__.py
  __init__.py
experiments/
  ablations/
    __init__.py
  __init__.py
configs/
  conditions/
analysis/
paper/
logs/
tests/
  __init__.py
src/
  jev_cot/
    __init__.py
.github/
  workflows/
```

The installable package lives under `src/jev_cot/` (src layout, standard for uv projects).

---

### T4 · Write pyproject.toml
**Type:** config  
**Files:** `pyproject.toml`  
**Depends on:** T2

Full content:

```toml
[project]
name = "jev-cot"
version = "0.1.0"
description = "JEV-Gated Adaptive Chain-of-Thought for Equity Research"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.7",
    "pyyaml>=6.0",
    "jsonlines>=4.0",
    "loguru>=0.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.6",
    "mypy>=1.10",
    "types-PyYAML",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jev_cot"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
```

After writing: `uv sync --extra dev` to install all dependencies and generate lockfile.

---

### T5 · Implement config loader — `src/jev_cot/config.py`
**Type:** tracer  
**Files:** `src/jev_cot/config.py`  
**Depends on:** T4  
**Requirement:** NFR-01 (determinism), NFR-03 (auditability), NFR-07 (portability)

This is the **heart of the tracer slice**. The config loader must:
1. Read a YAML file from a given path
2. Validate it against a pydantic model
3. Return a typed, immutable config object
4. Fail loudly (with a clear message) on invalid/missing fields

**Schema** — covers all PRD §6.6 fields:

```python
# src/jev_cot/config.py
from __future__ import annotations
from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class ToolLimitsConfig(BaseModel):
    model_config = {"frozen": True}
    max_retrievals: int = Field(ge=1, default=10)
    max_branches: int = Field(ge=1, default=3)
    max_compute_calls: int = Field(ge=1, default=5)


class ExperimentConfig(BaseModel):
    """Captures all fields required by PRD §6.6 for a single experiment run."""

    model_config = {"frozen": True}

    # Identity
    run_id: str | None = None  # auto-generated if not provided

    # LLM
    llm: str  # e.g. "gemini-1.5-pro-latest"
    temperature: float = Field(ge=0.0, le=2.0, default=0.0)
    max_tokens: int = Field(ge=1, default=4096)

    # Versioning (all required for auditability)
    jev_version: str = "none"  # "none" for Conditions A/B
    prompt_version: str
    retrieval_version: str
    dataset_version: str

    # Control limits
    max_steps: int = Field(ge=1, default=15)
    tool_limits: ToolLimitsConfig = Field(default_factory=ToolLimitsConfig)

    # Reproducibility
    random_seed: int = 42
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    # Condition
    condition: Literal["vanilla", "selfgate", "jevgate"] = "vanilla"

    # Safety — escalate fallback toggle
    enable_escalate_fallback: bool = False
    escalate_confidence_threshold: float = Field(ge=0.0, le=1.0, default=0.5)


def load_config(path: str | Path) -> ExperimentConfig:
    """Load and validate an experiment config from a YAML file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p.resolve()}")
    with p.open() as f:
        raw = yaml.safe_load(f)
    return ExperimentConfig.model_validate(raw)
```

---

### T6 · Write `configs/base.yaml` — example config
**Type:** config  
**Files:** `configs/base.yaml`  
**Depends on:** T5

```yaml
# configs/base.yaml — Example base experiment configuration
# All fields documented in src/jev_cot/config.py (ExperimentConfig)

llm: "gemini-1.5-pro-latest"
temperature: 0.0
max_tokens: 4096

prompt_version: "v0.1"
retrieval_version: "faiss-v0.1"
dataset_version: "phase1-seed-v0.1"
jev_version: "none"

condition: "vanilla"

max_steps: 15
tool_limits:
  max_retrievals: 10
  max_branches: 3
  max_compute_calls: 5

random_seed: 42

enable_escalate_fallback: false
escalate_confidence_threshold: 0.5
```

---

### T7 · Implement structured logging — `src/jev_cot/logging.py`
**Type:** infrastructure  
**Files:** `src/jev_cot/logging.py`  
**Depends on:** T4

```python
# src/jev_cot/logging.py
from __future__ import annotations
import sys
from pathlib import Path
from loguru import logger


def setup_logging(
    log_dir: str | Path = "logs",
    run_id: str = "default",
    level: str = "INFO",
) -> None:
    """
    Configure loguru for structured JSON output.

    - Console: human-readable (for dev)
    - File: JSON lines at logs/{run_id}.log.jsonl (for machine processing)
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Remove default handler
    logger.remove()

    # Console handler — human readable
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        colorize=True,
    )

    # File handler — JSON lines for machine processing
    logger.add(
        log_dir / f"{run_id}.log.jsonl",
        level=level,
        format="{message}",
        serialize=True,  # loguru serialize=True → JSON per line
        rotation="100 MB",
        retention="30 days",
        compression="gz",
    )


# Re-export so callers do: from jev_cot.logging import logger
__all__ = ["logger", "setup_logging"]
```

---

### T8 · Write initial test suite — `tests/test_config.py`
**Type:** tests  
**Files:** `tests/test_config.py`, `tests/conftest.py`  
**Depends on:** T5, T6

Tests must cover:
1. Valid config loads and returns typed object
2. Missing required field → `ValidationError` with clear message
3. Invalid field value (e.g., `temperature: 5.0`) → `ValidationError`
4. Non-existent file → `FileNotFoundError`
5. `base.yaml` round-trip: load file → object fields match expected values

```python
# tests/test_config.py
import pytest
from pathlib import Path
from pydantic import ValidationError
from jev_cot.config import load_config, ExperimentConfig


BASE_YAML = Path("configs/base.yaml")


class TestLoadConfig:
    def test_valid_base_yaml(self):
        cfg = load_config(BASE_YAML)
        assert cfg.llm == "gemini-1.5-pro-latest"
        assert cfg.condition == "vanilla"
        assert cfg.random_seed == 42
        assert cfg.temperature == 0.0

    def test_missing_required_field(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("temperature: 0.0\n")  # missing llm, prompt_version, etc.
        with pytest.raises(ValidationError):
            load_config(bad)

    def test_invalid_temperature(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "llm: gemini\ntemperature: 5.0\n"
            "prompt_version: v1\nretrieval_version: v1\ndataset_version: v1\n"
        )
        with pytest.raises(ValidationError):
            load_config(bad)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent/path/config.yaml")

    def test_tool_limits_defaults(self):
        cfg = load_config(BASE_YAML)
        assert cfg.tool_limits.max_retrievals == 10
        assert cfg.tool_limits.max_branches == 3
        assert cfg.tool_limits.max_compute_calls == 5

    def test_config_is_immutable(self):
        cfg = load_config(BASE_YAML)
        with pytest.raises(Exception):  # pydantic frozen=True raises
            cfg.llm = "something-else"  # type: ignore
```

---

### T9 · Write `.gitignore`
**Type:** config  
**Files:** `.gitignore`  
**Depends on:** T2

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.eggs/

# uv / venv
.venv/
.python-version

# Logs (keep structure, ignore content)
logs/*.jsonl
logs/*.log
logs/*.gz

# Model checkpoints (large files — track with DVC or LFS separately)
models/jev/checkpoints/*/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Test / coverage
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
coverage.xml

# Secrets / keys
.env
*.key
*.pem
```

---

### T10 · Write GitHub Actions CI stub
**Type:** ci  
**Files:** `.github/workflows/ci.yml`  
**Depends on:** T4

```yaml
name: CI

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Run ruff (lint + format check)
        run: uv run ruff check src/ tests/

      - name: Run mypy (type check)
        run: uv run mypy src/

      - name: Run pytest
        run: uv run pytest --cov=jev_cot --cov-report=term-missing
```

---

### T11 · Write README.md
**Type:** docs  
**Files:** `README.md`  
**Depends on:** T4

Content:
- Project title + one-paragraph description
- Prerequisites (Python ≥3.11, uv, git)
- Quick start: `pip install uv` → `uv sync --extra dev` → `pytest` → `python -m jev_cot.config`
- Repository structure (from PROJECT.md §8)
- Link to `.planning/ROADMAP.md` for phase status
- Link to `configs/base.yaml` for config reference
- Research questions (H1–H6, one line each)
- License placeholder

---

### T12 · Git init + initial commit
**Type:** version control  
**Files:** `.git/`  
**Depends on:** T1–T11

```powershell
git init
git add -A
git commit -m "feat: Phase 1 — repo scaffold, config loader, logging, CI stub

- Full directory structure (PRD §10)
- src/jev_cot/config.py: pydantic-validated ExperimentConfig (all PRD §6.6 fields)
- src/jev_cot/logging.py: loguru JSON + console dual-sink logging
- configs/base.yaml: example experiment config
- tests/test_config.py: 6 tests covering load, validation, immutability
- .github/workflows/ci.yml: uv + pytest + ruff + mypy CI pipeline
- pyproject.toml: uv-managed, src layout, dev extras
"
```

---

## Acceptance Criteria Verification

| Criterion | How verified |
|---|---|
| Loading sample config → typed object | `pytest tests/test_config.py::TestLoadConfig::test_valid_base_yaml` |
| Invalid config → loud failure | `pytest tests/test_config.py::TestLoadConfig::test_missing_required_field` |
| `pytest` passes on stub codebase | `uv run pytest` exits 0 |
| `uv sync` installs from lockfile | `uv sync --extra dev` exits 0 after lockfile generated |

---

## Non-Goals (enforced)

- ❌ No LLM calls anywhere in this phase
- ❌ No retrieval code
- ❌ No JEV model code
- ❌ No action enum (that's Phase 2)
- ❌ No benchmark schema (that's Phase 3)

---

## Rollback

If something goes wrong during this phase:
```powershell
# The repo isn't committed yet until T12 — so just delete and restart:
Remove-Item -Recurse -Force .git, src, tests, configs, .github
# Then re-run from T2
```

After T12 commit exists: `git revert HEAD` or `git reset --hard HEAD~1`.

