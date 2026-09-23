# Phase 4: Retrieval Layer - Context

**Gathered:** 2026-09-23
**Status:** Ready for planning
**Mode:** Auto-generated (fast-track — ROADMAP deliverables/acceptance criteria serve as spec per user directive to prioritize throughput)

<domain>
## Phase Boundary

Build a pluggable retrieval interface backed by FAISS + sentence-transformers.

**Deliverables:**
- `retrieval/base.py` — abstract retrieval interface (company + period + document_type → ranked chunks)
- `retrieval/faiss_retriever.py` — FAISS + sentence-transformers implementation
- `retrieval/ingest.py` — ingestion script for local documents into FAISS index
- Unit tests: given company/period, retriever returns chunks with correct primary/secondary tagging; latency logged per call

**Acceptance Criteria:**
- Retrieval works end-to-end on seeded documents
- Per-call latency is measured and logged in the trajectory schema
- Adding a new backend requires only implementing the `base.py` interface (swap test)

**Non-goals:** Real SEC filings integration; production-scale indexing.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase fast-tracked per user directive. Use ROADMAP phase goal, deliverables, acceptance criteria, and existing codebase conventions (CONVENTIONS.md, STRUCTURE.md) to guide decisions. Follow the abstract base-class + swappable-backend pattern already established for `config.py`/data schema.

</decisions>

<code_context>
## Existing Code Insights

Refer to `.planning/codebase/STRUCTURE.md`, `.planning/codebase/CONVENTIONS.md`, and `.planning/codebase/ARCHITECTURE.md` for established layout, naming, and error-handling conventions to follow.

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond ROADMAP deliverables/acceptance criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discussion fast-tracked, ROADMAP scope followed as-is.

</deferred>
