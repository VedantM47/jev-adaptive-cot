---
phase: 04-retrieval-layer
plan: 04
subsystem: data
tags: [faiss, sentence-transformers, pytest, benchmark-corpus, retrieval]

# Dependency graph
requires:
  - phase: 04-retrieval-layer (plan 04-02)
    provides: RetrievalConfig, base.py/faiss_retriever.py/ingest.py, MSFT_10K_FY23 seed doc + tracer test
provides:
  - 8 remaining synthetic seed documents (9-document corpus total) matching every document id referenced by data/raw/sample_examples.jsonl
  - fix for the pre-existing trailing-blank-line defect in sample_examples.jsonl
  - tests/test_retrieval_seeded.py — corpus-integrity + full-corpus end-to-end retrieval tests
affects: [04-retrieval-layer (plan 04-05, ingest CLI), phase 06 controller/tool integration]

# Actuals (#2632)
actuals:
  tokens: 6900
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Seed-document wording tuned to keep evidence paragraphs semantically distinct from decoy paragraphs, so cosine-similarity ranking recalls the right chunk within top_k=3"

key-files:
  created:
    - data/raw/documents/CRM_10K_FY23.txt
    - data/raw/documents/ADBE_10K_FY23.txt
    - data/raw/documents/CAT_10K_FY23.txt
    - data/raw/documents/MMM_10K_FY23.txt
    - data/raw/documents/HON_10K_FY23.txt
    - data/raw/documents/ADBE_Q4_Earnings_FY23.txt
    - data/raw/documents/CAT_Q4_Earnings_FY23.txt
    - data/raw/documents/MSFT_Q1_Earnings_FY22.txt
    - tests/test_retrieval_seeded.py
  modified:
    - data/raw/sample_examples.jsonl

key-decisions:
  - "Reworded CAT_10K_FY23's P1/P4 to remove overlapping 'higher sales volume' / 'favorable price realization' phrasing that was outranking the actual machine-sales evidence paragraph in cosine similarity for EQ_004's query"
  - "test_required_evidence_present_in_listed_documents parametrizes over ALL 7 examples (including EQ_007, whose required_evidence is empty and passes vacuously) rather than filtering, per the plan's literal instruction"

patterns-established:
  - "Corpus-integrity tests (id<->file set equality, filename parseability, disclaimer presence) run directly against the real data/raw/documents tree at collection time; only the FAISS index itself is built into tmp_path (module-scoped fixture, never touches data/processed)"

requirements-completed: [FR-11]

coverage:
  - id: D1
    description: "9-document synthetic seed corpus (5 new 10-Ks + 3 new earnings releases + tracer's MSFT_10K_FY23) matches every document id referenced by sample_examples.jsonl, with no orphans"
    requirement: FR-11
    verification:
      - kind: unit
        ref: "tests/test_retrieval_seeded.py#test_every_referenced_document_has_seed_file"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_seeded.py#test_every_seed_file_name_parses"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_seeded.py#test_seed_files_carry_synthetic_disclaimer"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every benchmark example's required_evidence appears verbatim (whitespace-normalized) in its listed document(s)"
    requirement: FR-11
    verification:
      - kind: unit
        ref: "tests/test_retrieval_seeded.py#test_required_evidence_present_in_listed_documents"
        status: pass
    human_judgment: false
  - id: D3
    description: "FaissRetriever over the full seed corpus recalls every required_evidence string within the top 3 chunks, for every example with non-empty evidence (EQ_001-EQ_006)"
    requirement: FR-11
    verification:
      - kind: unit
        ref: "tests/test_retrieval_seeded.py#test_seeded_retrieval_recalls_required_evidence"
        status: pass
    human_judgment: false
  - id: D4
    description: "ADBE and CAT (10-K + Q4 earnings release) chunks tag correctly as (TEN_K, PRIMARY) / (EARNINGS_RELEASE, SECONDARY), and the document_type filter isolates each tier"
    requirement: FR-11
    verification:
      - kind: unit
        ref: "tests/test_retrieval_seeded.py#test_primary_secondary_tagging_on_multi_document_companies"
        status: pass
    human_judgment: false
  - id: D5
    description: "Period filter separates MSFT's two fiscal years (FY2022 earnings release vs FY2023 10-K); unknown company returns an empty result; MSFT_Q1_Earnings_FY22 carries no full-year figures"
    requirement: FR-11
    verification:
      - kind: unit
        ref: "tests/test_retrieval_seeded.py#test_period_filter_separates_fiscal_years"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_seeded.py#test_unknown_company_returns_empty_result"
        status: pass
      - kind: unit
        ref: "tests/test_retrieval_seeded.py#test_evidence_sufficiency_document_lacks_full_year_data"
        status: pass
    human_judgment: false
  - id: D6
    description: "The pre-existing trailing-blank-line defect in sample_examples.jsonl is fixed and the full pytest suite is green"
    verification:
      - kind: unit
        ref: "tests/test_data_schema.py#test_sample_dataset_validates"
        status: pass
      - kind: other
        ref: "uv run --extra dev pytest -q (67 passed)"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-09-23
status: complete
---

# Phase 4 Plan 04: Seed Corpus Completion & Full-Corpus Retrieval Tests Summary

**Completed the 9-document synthetic benchmark seed corpus (8 new documents beyond the tracer's MSFT_10K_FY23) and proved every benchmark example's required evidence is retrievable within the top 3 FAISS results end-to-end.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-09-23 (session)
- **Completed:** 2026-09-23T18:12:03Z
- **Tasks:** 2/2
- **Files modified:** 10

## Accomplishments
- Authored 8 synthetic seed `.txt` documents (5 primary-tier 10-Ks: CRM, ADBE, CAT, MMM, HON; 3 secondary-tier earnings releases: ADBE Q4, CAT Q4, MSFT Q1 FY22), each carrying the machine-checked `# SYNTHETIC SEED DOCUMENT` disclaimer and every benchmark example's `required_evidence` string verbatim
- Fixed the pre-existing trailing-blank-line defect in `data/raw/sample_examples.jsonl` (byte-exact rstrip, records untouched) — this was the cause of the previously-failing `test_data_schema.py::test_sample_dataset_validates`
- Added `tests/test_retrieval_seeded.py` (9 test functions, 37 collected cases with parametrization) covering corpus integrity, evidence recall over the full seed corpus, primary/secondary tier tagging on multi-document companies (ADBE, CAT), and period/company filters
- Full `pytest -q` suite is green: 67 passed, 0 failed

## Task Commits

Each task was committed atomically:

1. **Task 1: Primary-tier seed documents — five 10-K filings** - `23d7cbb` (feat)
2. **Task 2: Secondary-tier earnings releases + full-corpus end-to-end retrieval tests** - `667fcd0` (feat)

## Files Created/Modified
- `data/raw/documents/CRM_10K_FY23.txt` - Salesforce 10-K seed doc, EQ_002 evidence
- `data/raw/documents/ADBE_10K_FY23.txt` - Adobe 10-K seed doc, EQ_003 evidence (Digital Media)
- `data/raw/documents/CAT_10K_FY23.txt` - Caterpillar 10-K seed doc, EQ_004 evidence (machine sales)
- `data/raw/documents/MMM_10K_FY23.txt` - 3M 10-K seed doc, EQ_005 evidence (R&D expenses)
- `data/raw/documents/HON_10K_FY23.txt` - Honeywell 10-K seed doc, EQ_006 evidence (Aerospace margin)
- `data/raw/documents/ADBE_Q4_Earnings_FY23.txt` - Adobe Q4 earnings release, EQ_003 evidence (Digital Experience)
- `data/raw/documents/CAT_Q4_Earnings_FY23.txt` - Caterpillar Q4 earnings release, EQ_004 corroborating evidence
- `data/raw/documents/MSFT_Q1_Earnings_FY22.txt` - MSFT Q1 FY22 earnings release, EQ_007 evidence-sufficiency fixture (no full-year data)
- `data/raw/sample_examples.jsonl` - trailing blank line removed (7 records byte-identical)
- `tests/test_retrieval_seeded.py` - corpus-integrity + full-corpus end-to-end retrieval tests (AC-E1 through AC-E4)

## Decisions Made
- Kept `test_required_evidence_present_in_listed_documents` parametrized over all 7 examples (not filtered to non-empty evidence), per the plan's literal spec — EQ_007 passes vacuously since its `required_evidence` list is empty, which is itself a useful integrity check that EQ_007 stays an evidence-sufficiency fixture rather than silently regaining evidence.
- Used a module-scoped `seeded_retriever` fixture (one FAISS index build per test module, not per test) to keep the full-corpus suite fast while still respecting the "never write to data/processed" constraint via `tmp_path_factory`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CAT_10K_FY23's machine-sales evidence didn't recall in the top 3 for EQ_004**
- **Found during:** Task 2, first `pytest tests/test_retrieval_seeded.py` run
- **Issue:** `test_seeded_retrieval_recalls_required_evidence[EQ_004]` failed — the required evidence string `"The increase was due to higher sales volume"` (in `CAT_10K_FY23`'s machine-sales paragraph) was not among the top 3 chunks returned for the combined CAT_10K + CAT_Q4_Earnings corpus. The 10-K's revenue-overview (P1) and outlook (P4) paragraphs also used the phrases "higher sales volume" and "favorable price realization", which made them cosine-similar enough to the query to outrank the actual machine-sales paragraph (P2).
- **Fix:** Reworded CAT_10K_FY23 P1 and P4 to drop the overlapping phrasing (replaced with "robust equipment demand" / "favorable pricing actions"), and added an explicit "machine sales volume growth trend...reported...in its fourth quarter earnings release" clause to P2 to strengthen its alignment with the query's own wording. This is exactly the escape hatch the plan specified: "If a recall assertion fails, revise the seed-document wording... Do NOT raise top_k or weaken any assertion."
- **Files modified:** `data/raw/documents/CAT_10K_FY23.txt`
- **Verification:** Re-ran `pytest tests/test_retrieval_seeded.py -v` — all 37 cases pass, including `test_seeded_retrieval_recalls_required_evidence[EQ_004]`.
- **Committed in:** `667fcd0` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix, no scope creep — required_evidence strings, top_k, and assertions were never touched)
**Impact on plan:** Necessary to satisfy the ROADMAP acceptance criterion "Retrieval works end-to-end on seeded documents"; no scope creep.

## Issues Encountered
- The worktree branch (`worktree-agent-ab7a905ecf78aeeac`) was 11 commits behind `main` at session start — it predated plans 04-01/04-02 landing. Verified the branch had zero unique commits of its own (`git log main..HEAD` empty) and fast-forwarded it to `main` (`git merge --ff-only main`) before starting work, so this plan's `depends_on: ["04-02"]` prerequisite (RetrievalConfig, base.py, faiss_retriever.py, ingest.py, the MSFT_10K_FY23 tracer doc) was actually present on disk.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The full 9-document seed corpus and its retrieval tests are ready for plan 04-05 (the `ingest.py` CLI entry point), which can now be exercised against a realistic, benchmark-matched corpus rather than the tracer's single document.
- `data/processed/` remains untouched by any test (`git status --porcelain data/processed` is empty) — every index build in this plan's tests goes to `tmp_path`.
- No blockers for downstream phases.

---
*Phase: 04-retrieval-layer*
*Completed: 2026-09-23*

## Self-Check: PASSED

All 9 created/modified files verified to exist on disk; both task commit hashes (`23d7cbb`, `667fcd0`) verified present in `git log --oneline --all`.
