---
phase: 04-retrieval-layer
plan: 03
subsystem: retrieval
tags: [pytest, pydantic, loguru, retrieval, contract-testing]

# Dependency graph
requires:
  - phase: 04-02
    provides: "RetrievalBackend ABC with @final retrieve() template method; FaissRetriever; parse_document_id/SOURCE_TIER_BY_DOCUMENT_TYPE; Chunk/RetrievedChunk/RetrievalQuery/RetrievalResult; RetrievalContractError; ingest.build_index/load_chunks; session-scoped embedder fixture"
provides:
  - "tests/test_retrieval_base.py: a second RetrievalBackend implementation (_InMemoryKeywordBackend) that implements only _search, proving base.py is a real swappable interface (ROADMAP swap-test AC)"
  - "Parametrized contract tests proving FaissRetriever and _InMemoryKeywordBackend satisfy the identical RetrievalBackend contract through a base-typed consumer"
  - "Abstract-enforcement tests: RetrievalBackend and any subclass missing _search raise TypeError on instantiation"
  - "Latency-logging tests: exactly one component='retrieval' log record per retrieve() call, and that record's latency_ms lands in the run's JSON-lines log file written by setup_logging()"
  - "Four RetrievalContractError coverage tests: wrong company, wrong document_type under a filter, unsorted scores, more than top_k chunks"
  - "Document-id tagging tests: all 9 benchmark document ids (+ a 10Q) parse to correct company/period/type/tier; every id in data/raw/sample_examples.jsonl matches its example's company/period; 8 malformed ids raise ValueError; SOURCE_TIER_BY_DOCUMENT_TYPE covers every DocumentType and is immutable"
  - "Input-validation tests: inconsistent Chunk tier, frozen RetrievedChunk, out-of-range score, and 7 invalid RetrievalQuery shapes all rejected before any _search call or log record"
affects: ["04-04", "04-05"]

# Actuals (#2632)
actuals:
  tokens: 5719
  tasks: 2
  commits: 2
  plan_head_before: 9e4f490fa01e16455ce887463127992a54341b7b

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Swap test via a second minimal RetrievalBackend subclass (_InMemoryKeywordBackend, Jaccard keyword scoring) implementing only _search, exercised through the same parametrized fixture and base-typed consumer as FaissRetriever"
    - "Loguru sink-based log capture fixture (component=='retrieval' filter) plus a restore_logging fixture that re-adds the default stderr handler after a test calls setup_logging(), since setup_logging() calls logger.remove() globally"
    - "Rogue-backend contract-violation tests: tiny RetrievalBackend subclasses whose _search deliberately violates one contract rule each, asserting retrieve() raises RetrievalContractError"

key-files:
  created:
    - "tests/test_retrieval_base.py"
  modified: []

key-decisions:
  - "Worktree branch had not yet picked up plans 04-01/04-02's merged work (its HEAD was exactly main's merge-base, no divergent commits); fast-forwarded onto main before starting, same resolution 04-02-SUMMARY.md documented for the prior worktree."
  - "No .venv existed in this fresh worktree; recreated it with `uv venv --python 3.11` + `uv sync --extra dev` (matching pyproject.toml's `requires-python` and the project's Python 3.11 mypy target) before running any test."
  - "Both tasks' test suites passed against base.py/faiss_retriever.py/ingest.py exactly as plan 04-02 left them — no src/ changes were needed for either task, so both commits are test-only."
  - "Followed the plan's `<action>` block verbatim for the synthetic ACME/BETA corpus, the in-memory backend's Jaccard scoring, the parametrized backend fixture, and every test's assertions — no interpretation needed."

patterns-established:
  - "A second, deliberately-minimal RetrievalBackend implementation is the standing swap-test fixture for this codebase: any future backend can be verified the same way, by running it through the same parametrized `backend` fixture and the shared contract test."

requirements-completed: [FR-11, FR-14, NFR-06]

coverage:
  - id: D1
    description: "A second backend (_InMemoryKeywordBackend) implementing ONLY _search is instantiable and passes the identical contract assertions as FaissRetriever through a RetrievalBackend-typed consumer (swap test)"
    requirement: "FR-11"
    verification:
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestSwapContract::test_swap_backends_share_contract[faiss]"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestSwapContract::test_swap_backends_share_contract[in_memory]"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestSwapContract::test_document_type_filter_applies_to_every_backend[faiss]"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestSwapContract::test_document_type_filter_applies_to_every_backend[in_memory]"
        status: pass
    human_judgment: false
  - id: D2
    description: "RetrievalBackend itself, and any subclass missing _search, cannot be instantiated"
    verification:
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestAbstractEnforcement::test_base_class_is_abstract"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestAbstractEnforcement::test_subclass_without_search_is_not_instantiable"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every retrieve() call on either backend emits exactly one component='retrieval' record with a measured latency_ms, and that value is written to the run's JSON-lines log by setup_logging()"
    requirement: "FR-14"
    verification:
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestLatencyLogging::test_each_call_emits_one_latency_record[faiss]"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestLatencyLogging::test_each_call_emits_one_latency_record[in_memory]"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestLatencyLogging::test_latency_written_to_run_jsonl"
        status: pass
    human_judgment: false
  - id: D4
    description: "A backend that violates the contract (wrong company, wrong document_type under a filter, unsorted scores, more than top_k chunks) raises RetrievalContractError"
    requirement: "NFR-06"
    verification:
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestContractViolations::test_wrong_company_raises"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestContractViolations::test_wrong_document_type_raises_when_filtered"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestContractViolations::test_unsorted_scores_raise"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestContractViolations::test_too_many_chunks_raises"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every document ID in data/raw/sample_examples.jsonl parses to the example's company and period with the correct primary/secondary tier, and all 9 benchmark ids plus a 10Q parse correctly"
    requirement: "FR-11"
    verification:
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestDocumentIdTagging::test_parse_document_id"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestDocumentIdTagging::test_every_sample_document_id_matches_its_example"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestDocumentIdTagging::test_invalid_document_ids_raise"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestDocumentIdTagging::test_tier_mapping_covers_every_document_type"
        status: pass
    human_judgment: false
  - id: D6
    description: "Malformed document ids, an inconsistent Chunk tier, an out-of-range score, and invalid RetrievalQuery shapes are all rejected before any _search call or log record"
    requirement: "NFR-06"
    verification:
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestInputValidation::test_chunk_rejects_inconsistent_tier"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestInputValidation::test_retrieved_chunk_is_frozen"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestInputValidation::test_score_out_of_range_rejected"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_base.py::TestInputValidation::test_invalid_query_rejected_before_search"
        status: pass
    human_judgment: false

# Metrics
duration: 55min
completed: 2026-09-23
status: complete
---

# Phase 4 Plan 3: Retrieval Interface Contract Tests Summary

**45-test suite (tests/test_retrieval_base.py) proving base.py's swap test, abstract-class enforcement, per-call latency logging into the run's JSON-lines log, four RetrievalContractError violation modes, and full document-ID tagging/validation coverage — exercised entirely against plan 04-02's base.py/faiss_retriever.py/ingest.py without needing a single source change.**

## Performance

- **Duration:** 55 min (approx, includes fresh-worktree `uv sync` of the torch/faiss/sentence-transformers stack)
- **Completed:** 2026-09-23
- **Tasks:** 2/2 completed
- **Files modified:** 1

## Accomplishments
- `_InMemoryKeywordBackend(RetrievalBackend)` — a second, deliberately trivial backend implementing only `_search` (lowercase word-set Jaccard scoring over a synthetic ACME/BETA corpus) — proves `base.py` is a real, swappable interface: both it and `FaissRetriever` pass the identical parametrized contract test through a `RetrievalBackend`-typed consumer (`_collect_evidence`).
- `TestAbstractEnforcement` proves `RetrievalBackend()` and a subclass that doesn't implement `_search` both raise `TypeError` on instantiation.
- `TestLatencyLogging` proves each `retrieve()` call emits exactly one `component="retrieval"` loguru record carrying `backend`, `latency_ms`, and `num_results`, and separately proves that latency value is present in the run's `.log.jsonl` file after `setup_logging()` + `logger.remove()` (flush).
- `TestContractViolations` exercises four deliberately rogue backends (wrong company, wrong `document_type` under a filter, unsorted scores, `top_k + 1` chunks) and asserts each raises `RetrievalContractError`.
- `TestDocumentIdTagging` parametrizes `parse_document_id` over all 9 document ids referenced by `data/raw/sample_examples.jsonl` plus a `10Q` case, asserts every id in that benchmark file round-trips to its example's `company`/`period`, parametrizes 8 malformed ids that must raise `ValueError`, and asserts `SOURCE_TIER_BY_DOCUMENT_TYPE` covers every `DocumentType` and is immutable (`MappingProxyType`).
- `TestInputValidation` asserts a `Chunk` with a tier/`document_type` mismatch, a mutation of a frozen `RetrievedChunk`, and an out-of-range `score` all fail pydantic validation, and parametrizes 7 invalid `RetrievalQuery` shapes (blank/whitespace company, blank period/query, `top_k` out of `[1, 100]`, an unknown `document_type`) that must be rejected by `retrieve()` before a spy backend's `_search` is ever called and before any log record is captured.

## Task Commits

Each task was committed atomically:

1. **Task 1: Swap test, abstract-enforcement, latency-to-JSONL and contract-violation tests** - `257f7c5` (test)
2. **Task 2: Document-ID parsing, tier mapping and input-validation tests** - `c8c4d34` (test)

**Plan metadata:** (this commit — SUMMARY.md update + state/roadmap/requirements advancement)

## Files Created/Modified
- `tests/test_retrieval_base.py` - Swap test, abstract enforcement, latency-logging, contract-violation, document-ID tagging, and input-validation tests (45 tests, all passing; no base.py changes needed)

## Decisions Made
- Fast-forwarded this plan's worktree branch onto `main` before starting (its HEAD was exactly `main`'s merge-base with no divergent commits) — the branch had not yet picked up plans 04-01/04-02's merged work, mirroring the exact resolution 04-02-SUMMARY.md documented for its own (different) worktree.
- Recreated `.venv` with `uv venv --python 3.11` + `uv sync --extra dev` since this fresh worktree had no virtual environment at all — matches `pyproject.toml`'s `requires-python = ">=3.11"` and `[tool.mypy] python_version = "3.11"`, avoiding the Python-3.14-vs-numpy-stub mypy failure plan 04-02 already diagnosed.
- Followed the plan's `<action>` block verbatim: the synthetic ACME/BETA corpus (3+2+2 one-line paragraphs), the in-memory backend's Jaccard-overlap scoring and `(-score, chunk_id)` sort, the `backend` fixture's `faiss`/`in_memory` parametrization, and every test's exact assertions — no interpretation needed.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' verification (`pytest`, `ruff check`, `ruff format --check`, `mypy src/`) passed against `base.py` unchanged, so no source-level auto-fixes (Rules 1-3) were needed.

## Issues Encountered
- This plan's worktree (`worktree-agent-ac56842b557cd0765`) had not yet picked up plans 04-01/04-02's merged work (missing `RetrievalConfig`, `retrieval/base.py`/`faiss_retriever.py`/`ingest.py`, the installed FAISS/sentence-transformers/torch stack, and all Phase 4 planning docs). Resolved with `git merge main --ff-only` before starting — a clean fast-forward, no divergent worktree commits, no conflict risk.
- The worktree had no `.venv` at all (a fresh worktree checkout). Resolved with `uv venv --python 3.11` followed by `uv sync --extra dev`, which installed the full dev stack including the heavy `torch`/`sentence-transformers`/`faiss-cpu` dependencies.
- First test run of `tests/test_retrieval_faiss.py` (baseline check) and `tests/test_retrieval_base.py` both passed on the first attempt against the inherited `base.py`/`faiss_retriever.py`/`ingest.py` — no rogue-backend or validation test exposed a defect requiring a source fix.

## User Setup Required

None - no external service configuration required. The embedding model (`sentence-transformers/all-MiniLM-L6-v2`) was already cached from plan 04-02's test run; no re-download needed for the `faiss`-parametrized tests in this plan.

## Next Phase Readiness
- The ROADMAP swap-test acceptance criterion ("Adding a new backend requires only implementing the `base.py` interface") is now proven by a real second backend, not just asserted in prose.
- `base.py`'s contract enforcement (top_k bound, company/period/document_type filter match, non-increasing score order) has explicit rogue-backend coverage; `parse_document_id`'s regex has explicit malformed-id coverage (path traversal, lowercase, wrong doctype, missing/duplicate period).
- 04-04 (full seed corpus — adding the remaining 8 documents referenced by `data/raw/sample_examples.jsonl`) and 04-05 (ingest CLI + hardening) can proceed without any changes to this plan's test file; `test_every_sample_document_id_matches_its_example` already asserts every one of those document ids parses correctly, independent of whether the corresponding `.txt` file exists yet.
- No blockers for subsequent Phase 4 plans.

---
*Phase: 04-retrieval-layer*
*Completed: 2026-09-23*

## Self-Check: PASSED
