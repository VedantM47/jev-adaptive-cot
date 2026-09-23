---
last_mapped_commit: 237e58f437bc3e9685c2501dd1b012143667e3d4
last_mapped_at: 2026-09-23
---
# Testing Patterns

**Analysis Date:** 2026-09-23

## Test Framework

**Runner:**

- pytest 8.0+
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`

**Assertion Library:**

- pytest assertions (built-in)
- No custom assertion libraries; uses standard Python assert syntax
- Pydantic `ValidationError` caught with `pytest.raises()`

**Run Commands:**

```bash
pytest tests/                           # Run all tests
pytest tests/ -v                        # Verbose output (default in config)
pytest tests/ --tb=short                # Short traceback (default in config)
pytest tests/ --cov=src/jev_cot         # With coverage report
pytest tests/ --cov=src/jev_cot --cov-report=html  # HTML coverage report
pytest tests/test_config.py             # Run specific test file
pytest tests/test_config.py::TestLoadConfig::test_valid_base_yaml  # Run specific test
pytest tests/ -k "test_config"          # Run tests matching pattern
```

**Configuration in `pyproject.toml`:**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

## Test File Organization

**Location:**

- All tests in `tests/` directory at repository root
- Separate from source code (`src/jev_cot/`)

**Naming:**

- Test files: `test_<module>.py` (matches module being tested)
- Examples: `test_config.py`, `test_data_schema.py`, `test_data_split.py`, `test_phase2.py`
- Test classes: `Test<Subject>` (PascalCase): `TestLoadConfig`
- Test methods: `test_<scenario>()` (snake_case with descriptive names)

**Structure:**

```
tests/
├── __init__.py
├── conftest.py              # Shared pytest fixtures
├── test_config.py
├── test_data_schema.py
├── test_data_split.py
└── test_phase2.py
```

## Test Structure

**Suite Organization:**
Tests are organized into logical groups using test classes. Example from `tests/test_config.py`:

```python
class TestLoadConfig:
    # AC-1, AC-5 ──────────────────────────────────────────────────────────────
    def test_valid_base_yaml(self, base_yaml: Path) -> None:
        """Loading configs/base.yaml returns a correctly typed object."""
        cfg = load_config(base_yaml)
        assert isinstance(cfg, ExperimentConfig)
        assert cfg.llm == "gemini-1.5-pro-latest"
        
    # AC-2 ────────────────────────────────────────────────────────────────────
    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        """A YAML missing a required field raises ValidationError."""
        bad = tmp_path / "bad.yaml"
        bad.write_text("temperature: 0.0\n", encoding="utf-8")
        with pytest.raises(ValidationError) as exc_info:
            load_config(bad)
```

**Patterns:**

1. **Setup (Fixtures):** Use pytest fixtures (injected as function parameters)
   - Fixtures defined in `tests/conftest.py`
   - Scope: "session" for repo-wide resources, "function" (default) for per-test resources
   
2. **Execution:** Call the function/code under test directly
   - Assertions made immediately after execution
   - No separate setup/execute/verify sections within test functions
   
3. **Verification:** Use `assert` statements and `pytest.raises()` context manager
   - `assert condition, "message"` for positive assertions
   - `with pytest.raises(ExceptionType):` for exception testing
   - `with pytest.raises(ExceptionType, match="pattern"):` to verify exception message

**Example from `tests/test_config.py`:**

```python
def test_file_not_found_raises(self) -> None:
    """A non-existent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config("nonexistent/path/to/config.yaml")
```

## Mocking

**Framework:** unittest.mock (not explicitly used in codebase yet)

**Not Observed:**

- Current test suite does not use explicit mocking
- Tests work with real files and real data objects
- Fixtures create temporary files using pytest's `tmp_path` fixture

**When to Mock (if needed in future):**

- External API calls (would require `unittest.mock.patch()`)
- File I/O in unit tests (though current tests create real temp files)
- Expensive operations (database queries, network requests)

**What NOT to Mock:**

- Pydantic model validation (test the real validation)
- Configuration loading (test actual YAML parsing)
- Data structure transformations (test the real logic)

## Fixtures and Factories

**Test Data:**
All test data created using helper functions or pytest fixtures.

**Example Factory Function from `tests/test_data_split.py`:**

```python
def _create_dummy_data(
    tmp_path: Path, num_companies: int = 100, examples_per_company: int = 2
) -> Path:
    """Creates a temporary JSONL file with dummy benchmark examples."""
    p = tmp_path / "dummy.jsonl"
    with jsonlines.open(p, "w") as writer:
        for i in range(num_companies):
            comp = f"COMP_{i}"
            for j in range(examples_per_company):
                writer.write({
                    "id": f"{comp}_{j}",
                    "company": comp,
                    "period": "FY20",
                    "question": "Q",
                    "type": "factual_retrieval",
                    "documents": [],
                    "gold_claims": [],
                    "required_evidence": [],
                })
    return p
```

**Shared Fixtures in `tests/conftest.py`:**

```python
@pytest.fixture(scope="session")
def base_yaml() -> Path:
    """Absolute path to the base experiment config, resolved relative to repo root."""
    root = Path(__file__).parent.parent
    p = root / "configs" / "base.yaml"
    assert p.exists(), f"configs/base.yaml not found at {p}"
    return p
```

**Location:**

- Shared fixtures: `tests/conftest.py`
- Test-specific helpers (prefixed `_`): Within individual test files
- Example: `_minimal_yaml()` in `tests/test_config.py`, `_create_dummy_data()` in `tests/test_data_split.py`

**Using Fixtures:**

- Fixtures injected as function parameters: `def test_something(self, base_yaml: Path, tmp_path: Path) -> None:`
- Built-in pytest fixtures: `tmp_path` (temporary directory), `tmp_path_factory` (factory for multiple temps)
- Scope controls lifecycle: `scope="session"` for one-time setup, `scope="function"` (default) per test

## Coverage

**Requirements:** 

- Not enforced (no minimum coverage threshold configured)
- Coverage measurement available via pytest-cov

**View Coverage:**

```bash
pytest tests/ --cov=src/jev_cot --cov-report=term-missing
pytest tests/ --cov=src/jev_cot --cov-report=html  # generates htmlcov/index.html
```

**Current Coverage:**
Not explicitly tracked in configuration, but all critical paths are tested:

- Configuration loading and validation (AC 1-10 in `test_config.py`)
- Data schema validation (7 question types in `test_data_schema.py`)
- Dataset splitting logic and determinism (`test_data_split.py`)
- Action enum and metrics registry stubs (`test_phase2.py`)

## Test Types

**Unit Tests:**

- **Scope:** Individual functions and classes
- **Approach:** Test pure logic, validation, and error handling
- **Location:** Organized by module (e.g., `test_config.py` tests `config.py`)
- **Examples:**
  - `test_valid_base_yaml()` — Tests config loading and deserialization
  - `test_company_hash_is_deterministic()` — Tests pure function determinism
  - `test_config_is_immutable()` — Tests Pydantic frozen model behavior

**Integration Tests:**

- **Scope:** Multiple components working together
- **Approach:** Test workflows involving file I/O and data transformations
- **Location:** Same test files but may use real files or larger datasets
- **Examples:**
  - `test_split_no_overlap()` — Tests full dataset split workflow
  - `test_sample_dataset_validates()` — Tests schema validation on real data file

**End-to-End Tests:**

- **Not present:** E2E tests not implemented yet
- **Future scope:** Would test full pipeline execution (controller + all components)

## Common Patterns

**Async Testing:**
Not applicable. This is a synchronous Python project; no async/await patterns used.

**Error Testing:**

```python
def test_missing_required_field_raises(self, tmp_path: Path) -> None:
    """A YAML missing a required field raises ValidationError."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("temperature: 0.0\n", encoding="utf-8")
    with pytest.raises(ValidationError) as exc_info:
        load_config(bad)
    # Optionally verify error message:
    assert "llm" in str(exc_info.value) or "prompt_version" in str(exc_info.value)
```

**Parametrized Tests:**
Not explicitly used in current test suite, but pytest supports via `@pytest.mark.parametrize`:

```python
@pytest.mark.parametrize("condition", ["vanilla", "selfgate", "jevgate"])
def test_valid_conditions_accepted(self, tmp_path: Path, condition: str) -> None:
    p = _minimal_yaml(tmp_path, extra=f"condition: {condition}\n")
    cfg = load_config(p)
    assert cfg.condition == condition
```

**Determinism Testing:**
Tests verify reproducibility with fixed seeds:

```python
def test_split_is_deterministic(tmp_path: Path):
    """Verify that running the split twice with the same seed yields identical files."""
    input_file = _create_dummy_data(tmp_path)
    out_dir1 = tmp_path / "splits1"
    out_dir2 = tmp_path / "splits2"

    split_dataset(input_file, out_dir1, seed=99)
    split_dataset(input_file, out_dir2, seed=99)

    assert (out_dir1 / "train.jsonl").read_text() == (out_dir2 / "train.jsonl").read_text()
```

**Boundary Testing:**
Tests verify constraints and edge cases:

```python
def test_temperature_out_of_range_raises(self, tmp_path: Path) -> None:
    """temperature > 2.0 raises ValidationError."""
    p = _minimal_yaml(tmp_path, extra="temperature: 5.0\n")
    with pytest.raises(ValidationError):
        load_config(p)

def test_negative_max_steps_raises(self, tmp_path: Path) -> None:
    """max_steps < 1 raises ValidationError."""
    p = _minimal_yaml(tmp_path, extra="max_steps: 0\n")
    with pytest.raises(ValidationError):
        load_config(p)
```

**File I/O Testing:**
Uses `tmp_path` fixture (provided by pytest) for isolated temporary directories:

```python
def test_file_not_found_raises(self) -> None:
    """A non-existent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config("nonexistent/path/to/config.yaml")
```

**Collection Testing:**
Verifies data structure contents and properties:

```python
def test_split_no_overlap(tmp_path: Path):
    """Verify zero company overlap between train, val, and test splits."""
    # ... setup ...
    train_comps = get_companies(out_dir / "train.jsonl")
    val_comps = get_companies(out_dir / "val.jsonl")
    test_comps = get_companies(out_dir / "test.jsonl")

    assert len(train_comps.intersection(val_comps)) == 0
    assert len(train_comps.intersection(test_comps)) == 0
    assert len(val_comps.intersection(test_comps)) == 0
```

## Special Testing Conventions

**Acceptance Criteria Tracking:**

- Test methods are grouped by AC (Acceptance Criteria) number
- Comments mark which ACs a test covers: `# AC-1, AC-5 ──────────────────────────────────────────────`
- Test docstrings name the acceptance criterion being verified

**Example from `tests/test_config.py`:**

```python

# ── Test suite ────────────────────────────────────────────────────────────────

class TestLoadConfig:
    # AC-1, AC-5 ──────────────────────────────────────────────────────────────
    def test_valid_base_yaml(self, base_yaml: Path) -> None:
        """Loading configs/base.yaml returns a correctly typed object."""
        # ... test code ...
```

**Test Docstrings:**

- Every test has a docstring
- Docstring is a single sentence describing what is being tested
- Format: "<Condition/verb> <action> → <expected result>"
- Examples:
  - `"Loading a valid YAML → typed ExperimentConfig object."`
  - `"A YAML missing a required field raises ValidationError."`
  - `"Frozen pydantic model — mutation raises an exception."`

---

*Testing analysis: 2026-09-23*
