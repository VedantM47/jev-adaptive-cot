---
phase: 04-retrieval-layer
plan: 05
subsystem: retrieval
tags: [ingest, cli, faiss, security, testing, determinism]

# Dependency graph
requires:
  - phase: 04-02
    provides: "RetrievalBackend/FaissRetriever/SentenceTransformerEmbedder/IndexManifest; ingest.py's read_document/chunk_text/discover_documents/load_chunks/build_index"
provides:
  - "jev_cot.retrieval.ingest: main(argv) CLI entry point (python -m jev_cot.retrieval.ingest --config <yaml>)"
  - "jev_cot.retrieval.ingest: discover_documents() hardened against symlinks and out-of-root paths (threat T-04-02)"
  - ".gitignore rule for data/processed/faiss_index/ (generated FAISS artifacts never committed)"
  - "tests/test_retrieval_ingest.py: CLI, discovery/chunking, index-load-robustness, and rebuild-determinism test coverage"
affects: []

# Actuals (#2632)
actuals:
  tokens: 6262
  tasks: 3
  commits: 3
  plan_head_before: 9e4f490fa01e16455ce887463127992a54341b7b

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CLI convention: main(argv: Sequence[str] | None = None) -> None with argparse, in-process testable via an explicit argv parameter; errors caught as (FileNotFoundError, ValueError) (ValidationError is a ValueError subclass), printed as 'Error: {msg}' to stderr, sys.exit(1)"
    - "Cheap precheck before expensive setup: discover_documents() runs before setup_logging()/SentenceTransformerEmbedder() construction, so a missing/empty corpus never pays the embedding-model load cost"
    - "Defense-in-depth path containment: discover_documents rejects any *.txt entry that is a symlink, then independently checks the entry's resolved path is relative to the resolved documents_dir root"
    - "Module-scoped build + function-scoped shutil.copytree fixture pair, so index-corruption tests each get a private, freely-tamperable copy without rebuilding (and re-embedding) the index once per test"

key-files:
  created:
    - "tests/test_retrieval_ingest.py"
    - ".planning/phases/04-retrieval-layer/deferred-items.md"
  modified:
    - "src/jev_cot/retrieval/ingest.py"
    - ".gitignore"

key-decisions:
  - "Worktree branch (worktree-agent-a314c8e6e6c1849d3) had not yet picked up plans 04-01/04-02's merged work (missing RetrievalConfig, installed FAISS/sentence-transformers/torch, retrieval/ package). Fast-forwarded onto main (git merge main --ff-only) before starting, since merge-base(HEAD, main) == HEAD — a clean fast-forward with zero divergent worktree commits, matching the 04-02 precedent."
  - "Recreated .venv pinned to Python 3.11 (uv venv --python 3.11 && uv sync --extra dev) rather than accept whatever interpreter uv would otherwise pick, matching pyproject.toml's requires-python and [tool.mypy] python_version = \"3.11\" pin (same environment-setup issue documented in 04-02-SUMMARY.md)."
  - "Task 3's faiss_retriever.py changes were conditional on a test exposing a gap ('Modify faiss_retriever.py only if a test exposes a missing check'). All 6 load-robustness/determinism tests passed against the unmodified plan-04-02 FaissRetriever.__init__ guards on first run — no source change was needed. This also closes 04-02-SUMMARY.md's coverage-D4 gap ('mismatch-rejection ValueError branches ... have no dedicated unit test')."
  - "Kept the module docstring's ACs scoped to AC-I1..AC-I4 (Task 1's RED instruction) and used '# AC-H1 discovery / AC-H2 chunking' / '# AC-R1 load robustness / AC-D1 determinism' section-header comments for Tasks 2-3's ACs, per CONVENTIONS.md's acceptance-criteria comment pattern and the plan's literal action text, rather than rewriting the module docstring each task."

patterns-established:
  - "CLI tests that call main() directly (in-process, not subprocess) request a restore_logging fixture that re-adds loguru's default stderr sink after the test, since setup_logging() calls logger.remove() globally and would otherwise silence later tests in the same session."
  - "Index-corruption tests build the index once per module (module-scoped fixture + embedder) and hand each test a private tmp_path copy via shutil.copytree, avoiding N re-embeddings for N corruption scenarios."

requirements-completed: [FR-11, NFR-07]

coverage:
  - id: T1
    description: "python -m jev_cot.retrieval.ingest --config configs/base.yaml builds index.faiss, chunks.jsonl and manifest.json under the YAML-configured index_dir and exits 0"
    requirement: "NFR-07"
    verification:
      - kind: integration
        ref: "tests/test_retrieval_ingest.py::test_cli_builds_index"
        status: pass
      - kind: manual
        ref: "Real CLI smoke test: uv run --extra dev python -m jev_cot.retrieval.ingest --config configs/base.yaml (this task's <verify>)"
        status: pass
    human_judgment: false
  - id: T2
    description: "The ingest CLI exits 1 with an Error: message on stderr for a missing config, missing documents dir or empty corpus, without loading the embedding model"
    requirement: "NFR-07"
    verification:
      - kind: unit
        ref: "tests/test_retrieval_ingest.py::test_cli_missing_config_exits_1"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_ingest.py::test_cli_missing_documents_dir_exits_1"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_ingest.py::test_cli_empty_corpus_exits_1"
        status: pass
    human_judgment: false
  - id: T3
    description: "data/processed/faiss_index/ is git-ignored, so generated index binaries are never committed"
    verification:
      - kind: manual
        ref: "git check-ignore -q data/processed/faiss_index/index.faiss; git status --porcelain data/processed logs (this task's <verify>)"
        status: pass
    human_judgment: false
  - id: T4
    description: "discover_documents refuses symlinked files and files resolving outside documents_dir"
    requirement: "FR-11"
    verification:
      - kind: unit
        ref: "tests/test_retrieval_ingest.py::test_discover_rejects_symlink"
        status: pass
    human_judgment: false
  - id: T5
    description: "FaissRetriever.from_index_dir fails loudly on missing artifacts, embedding-model mismatch, chunk-count mismatch and tampered tier tags"
    requirement: "FR-11"
    verification:
      - kind: unit
        ref: "tests/test_retrieval_ingest.py::test_missing_artifact_raises[index.faiss|chunks.jsonl|manifest.json]"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_ingest.py::test_missing_index_dir_raises"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_ingest.py::test_embedding_model_mismatch_raises"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_ingest.py::test_chunk_count_mismatch_raises"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_ingest.py::test_tampered_source_tier_rejected"
        status: pass
    human_judgment: false
  - id: T6
    description: "Rebuilding the index from the same corpus yields byte-identical chunks.jsonl and manifest.json and identical ranked results"
    requirement: "NFR-01"
    verification:
      - kind: unit
        ref: "tests/test_retrieval_ingest.py::test_rebuild_is_deterministic"
        status: pass
    human_judgment: false

# Metrics
duration: 75min
completed: 2026-09-23
status: complete
---

# Phase 4 Plan 5: Ingest CLI, Discovery Hardening, and Load Robustness Summary

**Config-driven `python -m jev_cot.retrieval.ingest` CLI, symlink/path-containment hardening on document discovery, a git-ignore rule for the generated FAISS index, and 20 new tests locking every CLI error path, discovery/chunking edge case, index-load failure mode, and rebuild-determinism guarantee.**

## Performance

- **Duration:** 75 min
- **Started:** 2026-09-23
- **Completed:** 2026-09-23
- **Tasks:** 3/3 completed
- **Files modified:** 4 (2 created, 2 modified) plus 1 untracked deferred-items log

## Accomplishments
- `src/jev_cot/retrieval/ingest.py`: added `main(argv: Sequence[str] | None = None) -> None`, the CLI entry point the ROADMAP's "ingestion script for local documents into FAISS index" deliverable calls for. Loads an `ExperimentConfig` via `load_config`, resolves `documents_dir`/`index_dir` (CLI `--documents-dir`/`--index-dir` override the YAML `retrieval:` block), runs `discover_documents()` as a cheap precheck *before* constructing the embedding model, then calls `setup_logging()` and `build_index()`. `(FileNotFoundError, ValueError)` — including `pydantic.ValidationError`, a `ValueError` subclass — are caught, printed as `Error: {message}` to stderr, and exit with code 1.
- `discover_documents()` hardened against threat T-04-02: a symlinked `*.txt` entry is refused outright (`ValueError` naming the file), and any entry whose resolved path escapes the resolved `documents_dir` is refused too (defense-in-depth path containment), on top of the existing missing-dir/empty-corpus checks.
- `.gitignore`: added `data/processed/faiss_index/` under a new "Generated retrieval index" section, so the FAISS binary and its sidecars are never committed — verified with `git check-ignore` and an empty `git status --porcelain data/processed logs`.
- `tests/test_retrieval_ingest.py` (new, 20 tests): 5 CLI tests (build, missing-config, missing-documents-dir, empty-corpus, override-precedence), 9 discovery/chunking tests (symlink rejection, non-.txt/subdirectory exclusion + sort order, bad-filename and comment-only-document errors, exact chunking-window/overlap/whitespace semantics, comment-line stripping), and 6 index-load-robustness/determinism tests (per-artifact missing-file, missing index_dir, embedding-model mismatch, chunk-count mismatch, tampered `source_tier`, byte-identical rebuild with matching ranked results within `1e-6`).
- Real CLI smoke test against `configs/base.yaml` succeeded: `Indexed 5 chunks from 1 documents into data/processed/faiss_index`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Config-driven ingest CLI + git-ignored index directory** - `a3c4259` (feat)
2. **Task 2: Harden document discovery and lock chunking behavior** - `7f8cdf4` (feat)
3. **Task 3: Index-load robustness and rebuild determinism tests** - `f8095a4` (test)

**Plan metadata:** (this commit — SUMMARY.md update + state/roadmap/requirements advancement)

## Files Created/Modified
- `src/jev_cot/retrieval/ingest.py` - Added `main()` CLI entry point; hardened `discover_documents()` against symlinks and path escapes
- `.gitignore` - Added `data/processed/faiss_index/` ignore rule
- `tests/test_retrieval_ingest.py` - New: 20 tests across CLI, discovery/chunking, index-load robustness, and rebuild determinism
- `.planning/phases/04-retrieval-layer/deferred-items.md` - New: logs one pre-existing, out-of-scope test failure found during the final full-suite sanity check

## Decisions Made
- Fast-forwarded the worktree branch onto `main` before starting (same situation and same resolution as 04-02: `merge-base(HEAD, main) == HEAD`, a clean fast-forward with no divergent commits) since the worktree was missing plans 04-01/04-02's merged work entirely.
- Recreated `.venv` pinned to Python 3.11 (`uv venv --python 3.11 && uv sync --extra dev`) to match `pyproject.toml`'s `requires-python`/mypy target, per the same environment issue 04-02-SUMMARY.md documented.
- Task 3 required no `faiss_retriever.py` changes — every load-robustness/determinism test passed against the unmodified plan-04-02 `FaissRetriever.__init__` guards on the first run, closing the coverage gap 04-02-SUMMARY.md flagged (coverage D4: "mismatch-rejection ValueError branches ... have no dedicated unit test").
- Kept the module docstring's ACs scoped to `AC-I1..AC-I4` (Task 1's literal RED instruction) and used `# AC-H1 discovery / AC-H2 chunking` and `# AC-R1 load robustness / AC-D1 determinism` section-header comments for Tasks 2/3, following CONVENTIONS.md's acceptance-criteria comment pattern.

## Deviations from Plan

None — plan executed exactly as written for all three tasks. The worktree fast-forward and Python 3.11 venv recreation are environment/tooling corrections (Rule 3 — blocking issue), not changes to any planned deliverable, matching the precedent already documented in 04-02-SUMMARY.md.

## Issues Encountered
- The worktree branch had not picked up plans 04-01/04-02's merged work (same root cause as 04-02: a worktree created before those plans merged to `main`). Resolved with `git merge main --ff-only` — verified `git merge-base HEAD main` equalled the worktree's own HEAD before merging, so the fast-forward carried zero risk of losing or overwriting worktree-local commits.
- No local `.venv` existed in this worktree (worktrees don't share `.venv`, which is git-ignored). Created one with `uv venv --python 3.11` and `uv sync --extra dev`; `mypy src/` reported "Success: no issues found in 15 source files" on the first run afterward, confirming the 3.11 pin avoided the numpy-stub/PEP-695 issue 04-02 hit under a default 3.14 interpreter.
- Final full-suite sanity check (`uv run --extra dev pytest`, all test files) surfaced one pre-existing, unrelated failure: `tests/test_data_schema.py::test_sample_dataset_validates` fails with `jsonlines.jsonlines.InvalidLineError` reading `data/raw/sample_examples.jsonl` (malformed JSON on line 8). Neither file is in this plan's `files_modified`; both were last touched at Phase 3 commit `8b9b2d9`, before any Phase 4 work. Out of scope per the executor's scope-boundary rule — logged to `.planning/phases/04-retrieval-layer/deferred-items.md`, not fixed.

## User Setup Required

None - no external service configuration required. The embedding model was already cached locally from plan 04-02's test run; this plan's tests and CLI smoke test reused that cache (no new huggingface.co downloads needed beyond the initial 04-02 one).

## Next Phase Readiness
- The ROADMAP's Phase 4 deliverable set (`retrieval/base.py`, `retrieval/faiss_retriever.py`, `retrieval/ingest.py`) is now fully delivered: an abstract, swappable retrieval interface; a FAISS + sentence-transformers backend; and a config-driven, hardened, tested ingestion CLI.
- One out-of-scope, pre-existing test failure remains open in the repo (`tests/test_data_schema.py::test_sample_dataset_validates`), tracked in `.planning/phases/04-retrieval-layer/deferred-items.md` for a future Phase 3/data-schema fix.
- No blockers for downstream phases that consume the retrieval layer (e.g. a controller/agent phase calling `RetrievalBackend.retrieve()`).

---
*Phase: 04-retrieval-layer*
*Completed: 2026-09-23*

## Self-Check: PASSED

All created/modified files verified present on disk; commits `a3c4259`, `7f8cdf4`, `f8095a4` verified present in git log.
