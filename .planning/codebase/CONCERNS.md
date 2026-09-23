---
last_mapped_commit: 237e58f437bc3e9685c2501dd1b012143667e3d4
last_mapped_at: 2026-09-23
---
# Codebase Concerns

**Analysis Date:** 2026-09-23

## Tech Debt

**Stubbed Metrics Registry:**

- Issue: `src/jev_cot/evaluation/metrics_registry.py` defines metrics as placeholder formula strings with no actual implementations
- Files: `src/jev_cot/evaluation/metrics_registry.py` (lines 20-65)
- Impact: Cannot run evaluation pipeline; all metrics (ops_saved, latency_reduction, cost_ratio, grounding_precision, grounding_recall, answer_quality, ece, brier_score) return no numerical values. These are mandatory for Phase 4 onward but deferred to Phase 13-14.
- Fix approach: In Phase 13-14, replace formula strings with actual computation methods that operate on trajectory data from `src/jev_cot/logging.py` JSON-lines logs

**Empty Module Scaffolding:**

- Issue: Large portions of codebase are directory stubs with no implementations
- Files: 
  - `retrieval/` (empty, Phase 4)
  - `models/llm/` (empty, Phase 5)
  - `models/jev/` (empty, Phase 6)
  - `controller/tools/` (empty, Phase 3)
  - `evaluation/cost/`, `evaluation/grounding/`, `evaluation/latency/`, `evaluation/quality/` (empty, Phases 8-11)
  - `experiments/ablations/` (empty, Phase 15)
- Impact: Cannot execute the full pipeline; retrieval, LLM integration, JEV training, and evaluation all blocked on implementations deferred to later phases. System is non-functional until Phase 5 at earliest.
- Fix approach: These are planned per ROADMAP.md. Follow phase-by-phase implementation from Phase 4 forward.

**Validator Output Handling Fragility:**

- Issue: `src/jev_cot/data/split.py:49` contains a comment "We assume the validator has run" and calls `obj.get("company", "UNKNOWN")` without verification
- Files: `src/jev_cot/data/split.py` (line 49)
- Impact: If split is called on non-validated data, missing fields silently default to "UNKNOWN" and continue without error. No audit trail of which records were patched. Data quality issues propagate silently to train/val/test splits.
- Fix approach: (1) Make validator a required preprocessing step documented in CLI help; (2) Log when `obj.get()` falls back to default; (3) Consider raising an error if required fields are missing rather than silently defaulting

## Known Bugs

**Test Suite Fails to Run Without Installation:**

- Symptoms: Running `pytest tests/` from fresh checkout fails with `ModuleNotFoundError: No module named 'jev_cot'`
- Files: All test files (`tests/test_*.py`)
- Trigger: Run `pytest` without first running `uv sync --extra dev`
- Workaround: Always run `uv sync --extra dev` before running tests. This installs the package in development mode.
- Root cause: The `src/jev_cot` package is not automatically added to Python path. The README mentions running `uv sync --extra dev` but does not emphasize it is **required before testing**.

**Missing Fixtures in Conftest:**

- Symptoms: Test import errors if `configs/base.yaml` doesn't exist
- Files: `tests/conftest.py:15` (assertion that config file exists)
- Trigger: If config is renamed or deleted
- Workaround: None; test suite will fail. No graceful fallback.

## Test Coverage Gaps

**No Validator CLI Tests:**

- What's not tested: The CLI entry point in `src/jev_cot/data/validator.py:main()` is never exercised by the test suite
- Files: `src/jev_cot/data/validator.py`
- Risk: CLI behavior (argument parsing, stderr/stdout routing, exit codes) could regress without detection. Malformed JSONL handling is untested.
- Priority: High (validator is a critical data pipeline component)

**No Error Handling Tests for Validator:**

- What's not tested: File I/O errors (missing files, permission errors, encoding issues), malformed JSONL (truncated lines, invalid JSON), extremely large files
- Files: `src/jev_cot/data/validator.py`
- Risk: Validator may crash ungracefully on real data edge cases; error messages may not be actionable for users
- Priority: High

**No Logging Setup Tests:**

- What's not tested: The `setup_logging()` function in `src/jev_cot/logging.py` is never called by tests. Log file rotation, compression, retention policies, and JSON serialization are untested.
- Files: `src/jev_cot/logging.py`
- Risk: Log setup could fail in production (e.g., permission denied on log directory, disk full during rotation). Serialization format could be broken by a dependency update.
- Priority: Medium

**No Error Condition Tests in Split:**

- What's not tested: Missing required fields in records, corrupted JSONL lines during read/write, disk full scenarios, very large datasets
- Files: `src/jev_cot/data/split.py`
- Risk: Split can fail silently (defaulting to "UNKNOWN") or crash with an unhelpful error message if data is malformed
- Priority: Medium

**No Tests for Configuration Edge Cases:**

- What's not tested: YAML parsing errors (malformed YAML), environment variable expansion, config file permissions, extremely large numbers in config fields
- Files: `src/jev_cot/config.py`
- Risk: Low-likelihood edge cases could cause confusing failures at experiment startup
- Priority: Low

## Fragile Areas

**Data Pipeline Assumption Chain:**

- Files: `src/jev_cot/data/split.py`, `src/jev_cot/data/validator.py`
- Why fragile: Split assumes validator has been run. No programmatic way to enforce this order. A developer could call split on raw, unvalidated data and get silently-patched output with no warning.
- Safe modification: Add an optional `--strict` flag to split that requires all records to pass validation before splitting. Log a warning if fields are defaulted.
- Test coverage: Add test_split_with_invalid_company_field that verifies behavior when data lacks required fields.

**Logging Setup Timing:**

- Files: `src/jev_cot/logging.py`
- Why fragile: The function removes loguru's default handler and adds two new ones. If called multiple times, handlers stack. If called with a log_dir that has permission issues, it will fail silently (mkdir succeeds but file creation fails).
- Safe modification: Add idempotent handler removal; test mkdir failure scenarios.
- Test coverage: Add test_setup_logging_permission_denied.

**Config Immutability Enforcement:**

- Files: `src/jev_cot/config.py` (pydantic frozen model)
- Why fragile: Frozen model prevents mutation but provides a generic error message. If downstream code tries to modify config (a common mistake), the error is unclear.
- Safe modification: Document in docstring that config is immutable; provide an example of the error message users will see.
- Test coverage: Already has test_config_is_immutable; consider improving error message with a custom __setattr__.

## Missing Critical Features

**No Actual Metric Calculations:**

- Problem: All 8 metrics (H1-H6) are defined in `src/jev_cot/evaluation/metrics_registry.py` as formula strings, but none have implementations
- Blocks: Cannot evaluate any hypotheses (H1-H6) until Phase 13-14
- Impact: High (evaluation is core to the research project)

**No Retrieval Layer:**

- Problem: `retrieval/` directory is empty. No FAISS backend, no sentence-transformers integration, no ingestion pipeline.
- Blocks: Phase 5 (LLM baseline) cannot run without retrieval; Phases 6-11 all depend on it
- Impact: Critical (retrieval is required for all three conditions A/B/C)

**No LLM Integration:**

- Problem: `models/llm/` is empty. No LLM client, no prompt management, no token counting
- Blocks: Phase 5 (vanilla condition) cannot run
- Impact: Critical

**No JEV Classifier:**

- Problem: `models/jev/` is empty. No classifier training, calibration, or inference pipeline
- Blocks: Phase 6 (JEV training) and Phase 7 (JEV-gate condition) cannot run
- Impact: Critical (JEV is the main research contribution)

**No Controller Loop:**

- Problem: `controller/tools/` is empty. No action execution, tool handling, state extraction, or safety limits enforcement
- Blocks: All three pipeline conditions (A/B/C) cannot run
- Impact: Critical

## Performance Bottlenecks

**Serialization Overhead in Logging:**

- Problem: Every log call with `serialize=True` in `src/jev_cot/logging.py:68` serializes the entire record to JSON. For high-frequency logging (e.g., per-step in controller loop), this could be slow.
- Files: `src/jev_cot/logging.py` (line 68)
- Cause: loguru's full-record serialization includes all context variables, function name, line number, etc. For trajectories with 100+ steps, this multiplies.
- Improvement path: (1) Benchmark logging throughput; (2) If slow, use a custom serializer that only includes essential fields (step, state, decision, latency, cost); (3) Consider batch writing to reduce I/O syscalls

**Deterministic Hashing in Split:**

- Problem: `src/jev_cot/data/split.py:18` uses MD5 hashing on every company for every record. For large datasets (millions of records), this is CPU-bound.
- Files: `src/jev_cot/data/split.py` (line 18)
- Cause: No caching of company hash values; recomputed per record
- Improvement path: Cache company hash in a dictionary on first encounter; reuse for all subsequent records of that company

**Config YAML Parsing on Every Load:**

- Problem: `src/jev_cot/config.py:125` parses YAML and validates via pydantic on every `load_config()` call. No caching.
- Files: `src/jev_cot/config.py` (line 125)
- Cause: Small overhead, but unnecessary if config is loaded multiple times
- Improvement path: For now, not a bottleneck. If experiments load config multiple times, add memoization.

## Scaling Limits

**No Batch Processing in Validator:**

- Current capacity: Validator processes entire JSONL sequentially, one record at a time
- Limit: For datasets > 1M records, this is slow (no parallelization)
- Scaling path: Add optional `--workers N` flag to validator; use multiprocessing to validate chunks in parallel

**No Streaming in Split:**

- Current capacity: Split reads entire JSONL into memory (via jsonlines.open in streaming mode, but output written sequentially)
- Limit: For datasets > 1GB, memory usage could be high if records are large
- Scaling path: Already streaming-capable; no change needed for Phase 3 (seed data is small)

**Single-Machine Constraint:**

- Current capacity: All code assumes local filesystem and single-process execution
- Limit: Cannot scale to multiple machines or distributed processing
- Scaling path: Out of scope for Phase 3; Phase 4 onward should plan for distributed retrieval indexing

## Security Considerations

**No Input Validation on YAML Fields:**

- Risk: YAML config paths (e.g., `log_dir`) are used directly in `mkdir()` and file I/O without sanitization
- Files: `src/jev_cot/config.py` (line 80, `tool_limits`), `src/jev_cot/logging.py` (line 43, `log_path.mkdir()`)
- Current mitigation: Fields are string types; no path traversal validation
- Recommendations: (1) Add `validation.py` module with `validate_path()` function that rejects `..` and absolute paths; (2) Use `Path.resolve()` and verify it's under expected root; (3) Add test_config_path_traversal_rejection

**Hardcoded JSON Encoding in Logging:**

- Risk: No custom JSON encoder defined; if state objects contain non-serializable types, logging will crash silently or with unhelpful error
- Files: `src/jev_cot/logging.py` (line 68, `serialize=True`)
- Current mitigation: Currently only logging strings; risk increases when trajectory data is logged
- Recommendations: (1) Add a custom encoder to handle datetime, Decimal, numpy types; (2) Test logging with complex trajectory objects before Phase 8

**Config File Permissions:**

- Risk: `configs/base.yaml` (and future secrets) could contain sensitive API keys if developers aren't careful
- Files: `configs/`, `.gitignore`
- Current mitigation: No secrets are currently stored in configs; .gitignore does not exclude `*.yaml`
- Recommendations: (1) Add to `.gitignore`: `configs/*-secrets.yaml`, `configs/.env*`; (2) Document in README that API keys must never be in version control; (3) Consider adding a pre-commit hook to scan for patterns like `sk-` (OpenAI key prefix)

## Dependencies at Risk

**No Version Pinning for Development Tools:**

- Risk: `pytest >= 8.0`, `ruff >= 0.6`, `mypy >= 1.10` could introduce breaking changes in minor versions
- Impact: Future `uv sync` could pull incompatible tool versions
- Migration plan: Consider pinning to specific minor versions in `pyproject.toml`: `pytest >= 8.0, < 9.0`, etc. This is common practice for dev tools.

**Limited Deprecation Path for pydantic 2.x:**

- Risk: Using `pydantic >= 2.7`; if v3 breaks BaseModel or Field, migration could be difficult
- Impact: Would require rewriting all schema models
- Migration plan: Monitor pydantic releases; keep a branch for v3 migration testing

**loguru Dependency on sys.stderr:**

- Risk: `src/jev_cot/logging.py:51` hardcodes `sys.stderr` as console sink. If stderr is redirected to file (e.g., in a container), all color codes will leak into logs
- Impact: Low (most deployments handle this correctly), but log output could be cluttered with ANSI codes
- Migration plan: Detect if stderr is a TTY; disable colorize if not

## Architecture Concerns

**No Abstraction for Experiment Persistence:**

- Problem: Configs are loaded from YAML, logs written to JSONL, but no mechanism to load/query results after an experiment completes
- Files: No files; this is a missing layer
- Impact: Evaluation phase (Phase 11-14) will need to implement this from scratch
- Fix approach: Add `src/jev_cot/io/experiment.py` with `ExperimentRun` class that encapsulates config + logs + metadata

**Metrics Registry is Non-Extensible:**

- Problem: Hardcoded dictionary in `src/jev_cot/evaluation/metrics_registry.py`. Cannot dynamically register new metrics; ablation phases (Phase 15) may need custom metrics
- Files: `src/jev_cot/evaluation/metrics_registry.py` (lines 20-65)
- Impact: Low (currently only H1-H6); may become an issue in Phase 15 if ablations define new metrics
- Fix approach: Refactor METRICS dict into a class-based registry with `register()` and `get()` methods

**No Pluggable Retrieval Interface Yet:**

- Problem: Phase 4 calls for `retrieval/base.py` abstract interface, but `retrieval/` is empty. v1 backend (FAISS) is hardcoded into Phase 4 scope.
- Files: `retrieval/` (empty)
- Impact: Future backends (e.g., Elasticsearch) cannot be added without refactoring
- Fix approach: Follow Phase 4 spec; implement abstract base class before FAISS implementation

## Missing Documentation

**Config Field Descriptions Fragmented:**

- Issue: Field descriptions are split between `src/jev_cot/config.py` (Field() descriptions) and `configs/base.yaml` (comments)
- Files: `src/jev_cot/config.py`, `configs/base.yaml`
- Impact: Developers must check both files to understand all options
- Fix approach: Add a `docs/CONFIG.md` that mirrors all fields with examples and constraints

**No CLI Help Text for Data Tools:**

- Issue: `src/jev_cot/data/validator.py` and `src/jev_cot/data/split.py` have argparse but minimal help text
- Files: `src/jev_cot/data/validator.py:42`, `src/jev_cot/data/split.py:70`
- Impact: Users running `python -m jev_cot.data.validator --help` get minimal guidance
- Fix approach: Add detailed help text and examples to argparse setup

**No Developer Onboarding Guide:**

- Issue: README.md assumes familiarity with uv, pydantic, loguru, and the project structure
- Files: `README.md`
- Impact: New developers may struggle to understand where to add code for Phase 4+
- Fix approach: Create `docs/DEVELOPER.md` with "where to add code for Phase X" guidance

---

*Concerns audit: 2026-09-23*
