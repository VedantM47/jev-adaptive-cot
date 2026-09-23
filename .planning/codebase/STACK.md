---
last_mapped_commit: 237e58f437bc3e9685c2501dd1b012143667e3d4
last_mapped_at: 2026-09-23
---
# Technology Stack

**Analysis Date:** 2026-09-23

## Languages

**Primary:**

- Python 3.11+ - All codebase (required by `pyproject.toml`)

## Runtime

**Environment:**

- Python / CPython 3.11+ (`requires-python = ">=3.11"` in `pyproject.toml`)

**Package Manager:**

- uv - Python package management with lockfile (`uv.lock` present)
- Lockfile: present (`uv.lock` with pinned versions)

## Frameworks

**Core:**

- Pydantic 2.13.5 - Configuration validation and typed data structures (`src/jev_cot/config.py`, `src/jev_cot/data/schema.py`)
- PyYAML 6.0 - YAML config file parsing (`src/jev_cot/config.py`)

**Testing:**

- pytest 8.0 - Test runner (`pyproject.toml` specifies `pytest>=8.0`)
- pytest-cov 5.0 - Code coverage measurement
- Types-PyYAML - Type stubs for PyYAML

**Build/Dev:**

- Hatchling - Build backend (`pyproject.toml` build-system)
- Ruff 0.6 - Linting and formatting (configured in `pyproject.toml` with line-length=100, target-version="py311")
- mypy 2.3.1 - Static type checking (`mypy` configured in `pyproject.toml` with strict=true)

## Key Dependencies

**Critical:**

- Pydantic 2.13.5 - Enables typed, validated configuration system (`src/jev_cot/config.py`). All experiment parameters flow through frozen ExperimentConfig instances.
- loguru 0.7.3 - Structured logging with dual-sink output (console + JSON-lines file). Provides trajectory logging for experiment auditing (`src/jev_cot/logging.py`).
- jsonlines 4.0.0 - JSON-lines format for machine-readable logs and trajectory data (`src/jev_cot/data/split.py`, `src/jev_cot/data/validator.py`)

**Infrastructure:**

- PyYAML 6.0 - Parses experiment configs from YAML files (`configs/base.yaml`, `configs/conditions/*.yaml`)

## Configuration

**Environment:**

- YAML-based configuration files (`configs/base.yaml` as reference, overridable via condition presets in `configs/conditions/`)
- All required fields documented in `src/jev_cot/config.py:ExperimentConfig` for auditability (PRD §6.6)
- Environment variables for secrets (`.env` file ignored in `.gitignore`)

**Build:**

- `pyproject.toml` - project metadata, dependencies, tool configuration
- `uv.lock` - dependency lock file for reproducibility
- Ruff configuration: line-length=100, select rules E/F/I/N/W/UP
- mypy configuration: python_version=3.11, strict=true

## Platform Requirements

**Development:**

- Python 3.11+
- uv package manager
- Git (for version control)
- POSIX shell or PowerShell (for running test/lint scripts)

**Production:**

- Python 3.11+ runtime
- Local filesystem (for logs, models, data directories)

---

*Stack analysis: 2026-09-23*
