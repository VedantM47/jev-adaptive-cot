---
last_mapped_commit: 237e58f437bc3e9685c2501dd1b012143667e3d4
last_mapped_at: 2026-09-23
---
# Coding Conventions

**Analysis Date:** 2026-09-23

## Naming Patterns

**Files:**

- Use lowercase with underscores: `config.py`, `metrics_registry.py`
- Modules named after their primary class or responsibility: `schema.py` for `BenchmarkExample`
- CLI tools follow the pattern `<domain>_<verb>.py`: `split.py`, `validator.py`
- Test files follow the pattern `test_<module>.py`: `test_config.py`, `test_data_schema.py`

**Functions:**

- Use lowercase with underscores (snake_case): `load_config()`, `get_company_hash()`, `split_dataset()`
- Private helper functions prefixed with single underscore: `_minimal_yaml()`, `_create_dummy_data()`
- Main entry point for CLI scripts: `main() -> None`
- Functions with side effects (CLI, I/O) explicitly documented in docstrings

**Variables:**

- Use lowercase with underscores: `run_id`, `log_dir`, `temp_count`
- Loop counters are short: `i`, `j`
- Boolean variables use positive assertions: `all_valid`, `is_frozen`
- Constants and enum values in UPPER_SNAKE_CASE: `CONTINUE`, `FACTUAL_RETRIEVAL`

**Types:**

- Use `StrEnum` for string-based enumerations: `QuestionType`, `Action` in `src/jev_cot/controller/actions.py`
- Pydantic `BaseModel` for data classes: `ExperimentConfig`, `BenchmarkExample`, `ToolLimitsConfig`
- Use type unions with pipe operator: `str | Path`, `str | None` (requires `from __future__ import annotations`)

**Classes:**

- Use PascalCase: `ExperimentConfig`, `BenchmarkExample`, `MetricDefinition`
- Data classes inherit from `pydantic.BaseModel`
- Enum classes inherit from `StrEnum` (Python 3.11+)
- Enum members in UPPER_SNAKE_CASE

## Code Style

**Formatting:**

- Tool: Ruff (configured in `pyproject.toml`)
- Line length: 100 characters
- Target Python: 3.11+
- Run formatter with: `ruff format src/ tests/`

**Linting:**

- Tool: Ruff
- Selected rule sets: E (pycodestyle errors), F (Pyflakes), I (isort), N (pep8 naming), W (warnings), UP (pyupgrade)
- Configuration in `pyproject.toml` under `[tool.ruff.lint]`
- Run linter with: `ruff check src/ tests/`

**Type Checking:**

- Tool: mypy
- Mode: strict (`strict = true`)
- Python version: 3.11
- Ignore missing imports when external stubs unavailable
- Run with: `mypy src/`

## Import Organization

**Order:**

1. `from __future__ import annotations` (at file start for forward references)
2. Standard library imports (datetime, pathlib, sys, argparse, etc.)
3. Third-party imports (pydantic, pyyaml, loguru, jsonlines)
4. Local imports from the `jev_cot` package

**Example from `src/jev_cot/config.py`:**

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
```

**Path Aliases:**

- No path aliases configured; use full relative imports from package root
- All imports reference the package name: `from jev_cot.config import load_config`

**Barrel Files:**

- Minimal use; `__init__.py` files document submodules but don't re-export
- Example in `src/jev_cot/__init__.py` — docstring describes submodules only

## Error Handling

**Patterns:**

- Explicit exception raising with descriptive messages: `FileNotFoundError(f"Config file not found: {p.resolve()}")`
- Pydantic handles validation errors through `model_validate()` — raises `ValidationError` on failure
- CLI tools use `sys.exit(1)` for error termination with messages to `sys.stderr`
- Exit code 0 for success, 1 for failure
- Print error messages directly to `sys.stderr` for CLI tools: `print(f"Error: {message}", file=sys.stderr)`

**Example from `src/jev_cot/data/validator.py`:**

```python
try:
    BenchmarkExample.model_validate(obj)
except ValidationError as e:
    print(f"Validation error on line {idx + 1}:", file=sys.stderr)
    print(e, file=sys.stderr)
    all_valid = False
```

**Example from `src/jev_cot/config.py`:**

```python
p = Path(path)
if not p.exists():
    raise FileNotFoundError(f"Config file not found: {p.resolve()}")
```

## Logging

**Framework:** loguru

**Setup:**

- Call `setup_logging()` once at pipeline start
- Dual-sink configuration: console (human-readable) + JSON-lines file (machine-processable)
- Configuration in `src/jev_cot/logging.py`

**Usage:**

```python
from jev_cot.logging import logger, setup_logging

setup_logging(log_dir="logs", run_id="run_abc123")
logger.info("Pipeline started", condition="vanilla")
```

**Patterns:**

- Log at appropriate level: `logger.info()`, `logger.debug()`, `logger.error()`
- Include contextual data as keyword arguments: `logger.info("Event", key=value)`
- Structured JSON output for production auditing
- Console output with timestamps and color for development

## Comments

**When to Comment:**

- Comments explain *why*, not what
- Non-obvious algorithmic decisions warrant explanation
- Complex business logic documented with references to PRD sections (e.g., "PRD §6.6")
- Input validation and safety constraints noted
- Comments precede the code they describe

**Examples:**

- `# AC-1, AC-5 ──────────────────────────────────────────────────────────────` — marks acceptance criteria
- `# We assume the validator has run, so 'company' exists` — explains assumption
- `diagnose=False,  # avoid leaking locals in production` — explains non-obvious parameter

**Module Docstrings:**

- Every module has a module-level docstring
- Format: title (underlined with equals), description, usage example
- Example from `src/jev_cot/config.py`:

```python
"""
jev_cot.config
==============
Typed, validated experiment configuration loader.

Every experiment run must load a config through this module so that
all fields required by PRD §6.6 are present and validated before
any pipeline code executes.

Usage::

    from jev_cot.config import load_config
    cfg = load_config("configs/base.yaml")
    print(cfg.llm, cfg.random_seed)
"""
```

## JSDoc/TSDoc

**Not applicable.** This is a Python project. Python uses docstrings instead.

**Docstring Format:**

- Google-style docstrings for functions and classes
- Include Args, Returns, Raises sections for public APIs
- Example from `src/jev_cot/config.py`:

```python
def load_config(path: str | Path) -> ExperimentConfig:
    """
    Load and validate an experiment config from a YAML file.

    Args:
        path: Path to a YAML config file.

    Returns:
        A frozen, validated :class:`ExperimentConfig` object.

    Raises:
        FileNotFoundError: If *path* does not exist.
        pydantic.ValidationError: If the YAML content fails schema validation.
    """
```

**Field Documentation in Pydantic:**

- Use `Field(description="...")` for all public fields
- Include units, ranges, and constraints: `Field(ge=0.0, le=1.0, description="...")`
- Example from `src/jev_cot/config.py`:

```python
max_retrievals: int = Field(
    ge=1, 
    default=10, 
    description="Max retrieval calls per trajectory"
)
```

## Function Design

**Size:** 

- Aim for functions under 30 lines
- Break complex logic into helper functions
- CLI tools follow a pattern: parse args → validate → call main logic → exit

**Parameters:**

- Use type hints for all parameters and return types
- Default values for optional parameters
- Use `|` for union types (requires `from __future__ import annotations`)
- Example: `def split_dataset(input_file: str | Path, output_dir: str | Path, seed: int = 42) -> None:`

**Return Values:**

- Always include return type annotation, even for `None`
- Explicit return statements required (no implicit None returns in Python, but be explicit)
- Example: `def main() -> None:` for CLI entry points

## Module Design

**Exports:**

- No explicit `__all__` lists unless module is a public API
- Example in `src/jev_cot/logging.py`:

```python
__all__ = ["logger", "setup_logging"]
```

**Barrel Files:**

- Minimal use — `__init__.py` typically contains only docstring and version
- Example `src/jev_cot/__init__.py`:

```python
__version__ = "0.1.0"
```

**Class Freezing:**

- Data classes marked with `model_config = {"frozen": True}` to enforce immutability
- Pydantic V2 syntax
- Example from `src/jev_cot/config.py`:

```python
class ExperimentConfig(BaseModel):
    model_config = {"frozen": True}
    # fields follow
```

## Special Conventions

**Section Headers in Code:**

- Use repeating characters for section separation
- Example: `# ── Identity ──────────────────────────────────────────────────────────────`
- Improves readability of large classes or modules

**Acceptance Criteria in Tests:**

- Test class methods marked with AC numbers: `# AC-1, AC-5 ──────────────────────────────────────────────`
- Test docstrings name the criteria: `"""Loading a valid YAML → typed ExperimentConfig object."""`
- Grouping improves traceability to requirements

**CLI Entry Points:**

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="...")
    parser.add_argument("...", type=str, help="...")
    args = parser.parse_args()
    # execute logic
    
if __name__ == "__main__":
    main()
```

---

*Convention analysis: 2026-09-23*
