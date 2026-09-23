# Phase 4: Retrieval Layer - Research

**Researched:** 2026-09-23
**Domain:** Vector retrieval (FAISS + sentence-transformers) for a pluggable RAG-style component in a Python research pipeline
**Confidence:** MEDIUM-HIGH (stack choices HIGH; primary/secondary tagging design and seed-corpus gap are ASSUMED and need confirmation)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None recorded as locked line-items — CONTEXT.md states: "All implementation choices are at Claude's discretion — discuss phase fast-tracked per user directive. Use ROADMAP phase goal, deliverables, acceptance criteria, and existing codebase conventions (CONVENTIONS.md, STRUCTURE.md) to guide decisions. Follow the abstract base-class + swappable-backend pattern already established for `config.py`/data schema."

### Claude's Discretion
All implementation choices (chunk size/overlap, embedding model, FAISS index type, primary/secondary tagging scheme, seed-document format, latency-logging call sites) are explicitly Claude's discretion. Mode: **Auto-generated (fast-track)** — ROADMAP deliverables/acceptance criteria serve as the spec.

### Deferred Ideas (OUT OF SCOPE)
None — discussion fast-tracked, ROADMAP scope followed as-is. Roadmap non-goals: real SEC filings integration, production-scale indexing.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FR-11 | Retrieval interface with pluggable backends; v1 = FAISS + sentence-transformers over local seeded documents; results include source metadata (primary vs. secondary, company, period, document type) | Standard Stack, Architecture Patterns, Code Examples, primary/secondary tagging design below |
| FR-14 | Every trajectory persisted per Appendix B schema: `(step, state, decision, confidence, latency, cost)` per step; `latency_breakdown` includes a `retrieval` key | Common Pitfalls (latency logging integration), Code Examples (latency instrumentation) |
| NFR-06 | Observability — latency measured **separately per component** (LLM, gate, retrieval, tool); no aggregate-only timing | Architecture Patterns, Code Examples |
| NFR-07 | Portability — Python 3.11, uv-managed deps, no hard-coded paths, all config via YAML | Standard Stack (installation), Architecture Patterns (project structure) |
</phase_requirements>

## Summary

This phase builds the first swappable component in the pipeline (`retrieval/`), following the same "typed interface + frozen config + structured logging" discipline already established by `config.py` and `data/schema.py` in Phases 1–3. The domain is well-trodden: an abstract base class defines `retrieve(company, period, document_type, query, top_k) -> list[RetrievedChunk]`; a concrete `FaissRetriever` embeds text with `sentence-transformers` and searches a `faiss.IndexFlatL2` (exact search — appropriate at seed scale, no training required); an `ingest.py` CLI chunks local documents, embeds them, and writes the index + a metadata sidecar to disk.

Two things are **not** fully specified anywhere in the existing repo and must be decided as part of this phase (both are Claude's discretion per CONTEXT.md, both are documented here as recommendations, both are `[ASSUMED]`):

1. **No source document text exists yet.** `data/raw/sample_examples.jsonl` only contains document *identifiers* (e.g. `MSFT_10K_FY23`), never document *content*. `ingest.py` needs something to ingest. The phase must add a small seed corpus of synthetic/excerpted financial text keyed to the same IDs the benchmark already references, or `ingest.py` will have nothing to index and the "works end-to-end on seeded documents" acceptance criterion is unverifiable.
2. **"Primary vs. secondary" is not defined anywhere in the codebase.** The recommended design (below) treats the regulatory filing (10-K/10-Q) as `primary` and supplementary/unaudited materials (earnings releases, press releases) as `secondary`, keyed off the document-ID naming convention already visible in the seed data (`{TICKER}_{DOCTYPE}_{PERIOD}`).

**Primary recommendation:** Implement `retrieval/base.py` as an `ABC` with one `@abstractmethod` (`retrieve`) and typed `Chunk`/`RetrievedChunk` dataclasses carrying `company`, `period`, `document_type`, `source_tier` (`"primary" | "secondary"`), `chunk_id`, `text`, `score`. Implement `FaissRetriever` using `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim) + `faiss.IndexFlatL2` wrapped in `faiss.IndexIDMap`, with a JSON/JSONL metadata sidecar mapping FAISS integer IDs back to chunk metadata (FAISS itself stores no metadata). Log every `retrieve()` call through the existing `jev_cot.logging.logger` with a `latency_ms` field and `component="retrieval"`, matching the `latency_breakdown.retrieval` key already reserved in the trajectory schema documented in `.planning/research/domain_notes.md`. Add a minimal seed text corpus under `data/raw/documents/` so `ingest.py` has something to embed, and verify the "swap test" acceptance criterion with a second, trivial in-memory backend implementing the same ABC.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Document chunking & embedding (ingest) | API/Backend (offline script) | Database/Storage (FAISS index file) | `ingest.py` is a one-shot CLI, not a service; it writes an index artifact to local disk — same pattern as `data/split.py` |
| Vector similarity search (retrieve) | API/Backend | Database/Storage (FAISS index + metadata sidecar) | `FaissRetriever.retrieve()` is called synchronously by the (future) controller loop, same call pattern as `load_config()` |
| Retrieval interface contract | API/Backend | — | `base.py` is a pure Python interface, no I/O; consumed by `controller/tools/` in later phases |
| Latency instrumentation | API/Backend | Database/Storage (`logs/*.jsonl`) | Logging happens inline in the retrieval call, persisted via the existing dual-sink logger |
| Source metadata (primary/secondary, company, period, doc type) | Database/Storage (sidecar) | API/Backend (returned in `RetrievedChunk`) | Metadata must survive the FAISS round-trip (FAISS stores only vectors+ids), so it lives in a sidecar file and is joined at query time |

This is a single-tier, local-filesystem research system (per ARCHITECTURE.md: "Production: Python 3.11+ runtime, Local filesystem") — there is no browser/CDN/SSR tier in this project. All capabilities above resolve to "API/Backend" (the Python package) plus local storage; no cross-tier misassignment risk exists for this phase.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `faiss-cpu` | 1.15.1 `[VERIFIED: pip index versions faiss-cpu, run 2026-09-23]` | Vector similarity index (exact search) | Facebook AI's reference vector-search library; already named in `.planning/research/domain_notes.md` and `.planning/PROJECT.md` §6 as the locked retrieval backend |
| `sentence-transformers` | 6.1.0 `[VERIFIED: pip index versions sentence-transformers, run 2026-09-23]` | Text embedding for chunks and queries | Already named in `.planning/research/domain_notes.md` §1 as the standard embedding library for this project; wraps HuggingFace transformer models with a simple `.encode()` API |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `numpy` | (transitive via faiss/sentence-transformers) | Vector dtype handling (`float32` required by FAISS) | Always — FAISS requires contiguous `float32` `np.ndarray` input |
| `jsonlines` | 4.0 (already a project dependency, `pyproject.toml:10`) | Metadata sidecar for chunk→FAISS-id mapping, and for the seed document corpus itself | Reuse existing project dependency rather than adding a new serialization library |
| `loguru` (via `jev_cot.logging`) | 0.7 (already a project dependency, `pyproject.toml:11`) | Per-call latency logging | Already the project's sole logging mechanism (`src/jev_cot/logging.py`); do not add a second logging library |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `faiss.IndexFlatL2` (exact search) | `faiss.IndexIVFFlat` (approximate, requires training) | IVF needs a minimum training-set size and adds an ANN accuracy/speed tradeoff; explicitly out of scope per ROADMAP non-goal "production-scale indexing" — exact search is both simpler and correct at seed-dataset scale (dozens of chunks, not millions) |
| `sentence-transformers` (`all-MiniLM-L6-v2`) | `BAAI/bge-small-en-v1.5` | bge-small tends to score higher on retrieval-focused benchmarks `[CITED: web search — "Best Sentence Transformers Models for Production 2026", markaicode.com]`, at a modest speed cost; MiniLM is smaller/faster and is the option `.planning/research/domain_notes.md` lists first. Recommend MiniLM for this phase (dev velocity, tiny corpus) but document the swap is a one-line model-name change (no interface change) since `base.py` doesn't expose embedding internals |
| Custom regex-based sentence chunker | LangChain `RecursiveCharacterTextSplitter` | Adding LangChain as a dependency for chunking alone is disproportionate (LangChain pulls in a large transitive dependency tree). A ~30-line word/token sliding-window chunker is well within "don't hand-roll" tolerance for something this simple — see Don't Hand-Roll section for where the line actually is |

**Installation:**
```bash
uv add faiss-cpu sentence-transformers
```

**Version verification:** Verified via `pip index versions faiss-cpu` → `faiss-cpu (1.15.1)`, and `pip index versions sentence-transformers` → `sentence-transformers (6.1.0)`, both run against the live PyPI index on 2026-09-23. `sentence-transformers` pulls in `torch` and `transformers` as transitive dependencies — this is a materially heavier install than anything the project has added so far (Pydantic/PyYAML/loguru/jsonlines are all pure-Python or near-zero-dependency); budget extra `uv sync` time and disk space (torch CPU wheel alone is several hundred MB).

## Package Legitimacy Audit

| Package | Registry | Age (latest release) | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `faiss-cpu` | PyPI | Latest version published 2026-09-16 (package itself is Meta's FAISS, public since 2017) | Unknown (seam could not resolve weekly-download count) | `github.com/facebookresearch/faiss` | `SUS` (raw seam verdict) | **Approved** — see note below |
| `sentence-transformers` | PyPI | Latest version published 2026-09-18 (package itself is UKP Lab's SBERT, public since 2019) | Unknown (seam could not resolve weekly-download count) | `SBERT.net` (official project site, GitHub: `UKPLab/sentence-transformers`) | `SUS` (raw seam verdict) | **Approved** — see note below |

**Note on the `SUS` verdicts:** Both packages were flagged `too-new` + `unknown-downloads` by the legitimacy seam. Inspecting the underlying signal, `publishedAt` reflects the **latest release date**, not the package's first-publish date — both packages are actively maintained (releases every few days/weeks is expected for mature, high-traffic ML infrastructure, not a slopsquat signal), and both `repoUrl` values resolve to the correct, well-known official sources (Meta's FAISS repo; SBERT's official site/repo). `weeklyDownloads: null` reflects a seam data-availability gap, not zero real-world usage — both packages are extremely widely used (this is training-knowledge / `[ASSUMED]`, not re-verified via a download-count API this session). Given the repo-URL match to the official projects, treat these as legitimate. **Per the Package Legitimacy Gate protocol, since the raw verdict is `SUS`, the planner must still insert a `checkpoint:human-verify` task before the `uv add faiss-cpu sentence-transformers` install step**, even though this researcher's assessment is that both packages are safe.

**Packages removed due to `[SLOP]` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** `faiss-cpu`, `sentence-transformers` — planner must add `checkpoint:human-verify` before each install (protocol-mandated; researcher assesses both as legitimate given repo-URL match to official Meta/UKP Lab projects).

## Architecture Patterns

### System Architecture Diagram

```
                    ┌──────────────────────────────┐
  local text docs   │        retrieval/ingest.py    │
  (data/raw/         │  1. read doc + metadata       │
   documents/*.txt)  │  2. chunk (size+overlap)      │
        │            │  3. embed chunks (ST model)   │
        └───────────▶│  4. faiss.IndexIDMap.add()    │
                     │  5. write index + sidecar      │
                     └───────────────┬────────────────┘
                                     │ writes
                                     ▼
                     data/processed/faiss_index/
                       ├── index.faiss   (FAISS binary)
                       └── metadata.jsonl (chunk_id → company/period/
                                            document_type/source_tier/text)

  ┌───────────────────────────────────────────────────────────────────┐
  │                    retrieval/base.py  (ABC)                        │
  │   retrieve(company, period, document_type, query, top_k)           │
  │        -> list[RetrievedChunk]                                     │
  └───────────────────────────┬─────────────────────────────────────────┘
                              │ implements
                              ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │              retrieval/faiss_retriever.py (FaissRetriever)         │
  │  1. embed query text (same ST model as ingest)                     │
  │  2. faiss_index.search(query_vec, top_k) -> (distances, ids)       │
  │  3. join ids against metadata sidecar                              │
  │  4. filter/boost by (company, period, document_type) match         │
  │  5. tag each hit primary/secondary via document_type               │
  │  6. log latency_ms via jev_cot.logging.logger                      │
  │  7. return ranked list[RetrievedChunk]                             │
  └───────────────────────────┬─────────────────────────────────────────┘
                              │ consumed by (future phases)
                              ▼
                  controller/tools/  (RETRIEVE action executor,
                                       Phase 6+ — not built this phase)
```

Data flow for the primary use case (a retrieval call): caller passes `(company, period, document_type, query)` → `FaissRetriever.retrieve()` embeds the query with the same model used at ingest time → FAISS returns nearest-neighbor chunk IDs by vector distance → IDs are joined against the metadata sidecar to recover text + provenance → results are tagged `primary`/`secondary` and filtered/ranked → latency is measured around the whole call and logged → typed `RetrievedChunk` objects are returned to the caller.

### Recommended Project Structure
```
retrieval/
├── __init__.py          # exists (placeholder) — keep docstring-only per CONVENTIONS.md barrel-file rule
├── base.py               # RetrievalBackend(ABC), Chunk, RetrievedChunk dataclasses
├── faiss_retriever.py    # FaissRetriever(RetrievalBackend)
└── ingest.py              # CLI: chunk + embed + build index (main() pattern per CONVENTIONS.md)

data/raw/documents/        # NEW — seed document corpus (see Open Questions #1)
├── MSFT_10K_FY23.txt
├── CRM_10K_FY23.txt
└── ...

data/processed/faiss_index/   # NEW — generated at runtime, not committed (see Common Pitfalls)
├── index.faiss
└── metadata.jsonl

tests/
└── test_retrieval.py     # follows test_data_split.py pattern: tmp_path fixtures, real files, no mocking of the index itself
```

This mirrors the existing top-level `retrieval/` placeholder already present in the repo (`retrieval/__init__.py`, currently just `# retrieval package`) — confirmed via `Read` this session — and follows the same "top-level package, not under `src/jev_cot/`" placement the project already uses for `controller/`, `evaluation/`, `models/` (per STRUCTURE.md and ARCHITECTURE.md's Component Responsibilities table, which lists `retrieval/` — not `src/jev_cot/retrieval/` — as the Retrieval Engine location).

### Pattern 1: Abstract Base Class for Swappable Backends
**What:** `retrieval/base.py` defines an `ABC` subclass with `@abstractmethod retrieve(...)`. Any concrete backend (`FaissRetriever`, a future `PineconeRetriever`, or a test double) must implement the same method signature to be instantiable.
**When to use:** Whenever the ROADMAP acceptance criterion says "adding a new backend requires only implementing the `base.py` interface" — this is exactly the ABC pattern's purpose.
**Example:**
```python
# Source: pattern synthesized from Python `abc` module docs + web search
# ("Protocol or ABC? Designing a pluggable provider interface", belderbos.dev)
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    company: str
    period: str
    document_type: str
    source_tier: str  # "primary" | "secondary"
    score: float


class RetrievalBackend(ABC):
    """Abstract retrieval interface. Concrete backends implement `retrieve()`."""

    @abstractmethod
    def retrieve(
        self,
        company: str,
        period: str,
        document_type: str | None,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Return up to `top_k` ranked chunks matching the query and filters."""
        raise NotImplementedError
```
Python's `abc` machinery prevents instantiating `RetrievalBackend` directly, and prevents instantiating any subclass that hasn't implemented every `@abstractmethod` — this is exactly the "adding a new backend requires only implementing the interface" guarantee the acceptance criterion asks for `[CITED: dev.to/qingluan Python ABC design patterns; docs.python.org abc module]`. Because pluggability here is entirely in-repo (no third-party plugin authors), a class-based `ABC` — not `typing.Protocol` — is the right choice; `Protocol` is preferred only when external code that can't/won't import your base class needs to count as a valid implementation `[CITED: belderbos.dev "Protocol or ABC? Designing a pluggable provider interface"]`, which doesn't apply here.

### Pattern 2: Metadata Sidecar for FAISS (FAISS stores vectors + IDs only)
**What:** FAISS indexes store only vectors and integer IDs — no text, no metadata. `ingest.py` must write a companion file (JSONL, reusing the project's existing `jsonlines` dependency) mapping each integer ID to its chunk's `text`, `company`, `period`, `document_type`, `source_tier`.
**When to use:** Every FAISS-backed retriever needs this; it is not optional.
**Example:**
```python
# Source: pattern from golinuxcloud.com/faiss-python-api and
# github.com/facebookresearch/faiss/wiki/Getting-started (IndexIDMap + add_with_ids)
import faiss
import numpy as np

dim = 384  # all-MiniLM-L6-v2 output dimensionality
base_index = faiss.IndexFlatL2(dim)
index = faiss.IndexIDMap(base_index)

vectors = embeddings.astype(np.float32)  # shape (n_chunks, dim)
ids = np.arange(len(vectors), dtype=np.int64)
index.add_with_ids(vectors, ids)

faiss.write_index(index, "data/processed/faiss_index/index.faiss")
# metadata.jsonl: one line per id -> {"id": int, "chunk_id": str, "text": ..., "company": ..., ...}
```
```python
# retrieval time
distances, hit_ids = index.search(query_vec.astype(np.float32), top_k)
# hit_ids[0] -> join against metadata.jsonl loaded into a dict keyed by id
```
`[CITED: github.com/facebookresearch/faiss/wiki/Getting-started; golinuxcloud.com/faiss-python-api]`

### Pattern 3: Primary vs. Secondary Source Tagging
**What:** Tag each ingested chunk's `source_tier` based on its `document_type`, derived from the existing document-ID naming convention already visible in the seed benchmark data.
**When to use:** At ingest time (write once into the metadata sidecar), not computed at query time.
**Evidence for the naming convention** — read directly from `data/raw/sample_examples.jsonl` this session, document IDs quoted verbatim: `"MSFT_10K_FY23"` (line 1), `"CRM_10K_FY23"` (line 2), `"ADBE_10K_FY23"`, `"ADBE_Q4_Earnings_FY23"` (line 3), `"CAT_10K_FY23"`, `"CAT_Q4_Earnings_FY23"` (line 4), `"MMM_10K_FY23"` (line 5), `"HON_10K_FY23"` (line 6), `"MSFT_Q1_Earnings_FY22"` (line 7) `[VERIFIED: data/raw/sample_examples.jsonl:1-7]`. The pattern is `{TICKER}_{DOCTYPE}_{PERIOD}` where `DOCTYPE ∈ {10K, Q4_Earnings, Q1_Earnings, ...}`.
**Recommended mapping `[ASSUMED — design decision, not found in any spec doc]`:**

| document_type token in ID | Canonical `document_type` | `source_tier` | Rationale |
|---|---|---|---|
| `10K` | `"10K"` | `"primary"` | Audited annual regulatory filing — the authoritative source of record in equity research |
| `10Q` (not yet in seed data but same family) | `"10Q"` | `"primary"` | Audited-adjacent quarterly regulatory filing |
| `Q1_Earnings` / `Q2_Earnings` / `Q3_Earnings` / `Q4_Earnings` | `"earnings_release"` | `"secondary"` | Unaudited, company-issued press release — corroborating/supplementary in equity-research convention |

This directly supports `multi_document_synthesis` questions in the benchmark (e.g. `EQ_003`, which cites both `ADBE_10K_FY23` and `ADBE_Q4_Earnings_FY23` — one primary, one secondary) and the `contradiction_detection` question `EQ_004` (`CAT_10K_FY23` vs `CAT_Q4_Earnings_FY23`), both read this session from `data/raw/sample_examples.jsonl:3-4`. **This mapping must be presented to the user for confirmation** (see Assumptions Log) since it is not a locked decision — but it is directly derivable from data already in the repo and is a reasonable domain default (10-K/10-Q = SEC-audited primary source; earnings releases = unaudited secondary/corroborating source, consistent with standard equity-research sourcing hierarchy).

### Anti-Patterns to Avoid
- **Computing `source_tier` at query time via string matching on the query text:** Tag it once at ingest time and store it in the sidecar. Computing it per-query duplicates logic between `ingest.py` and `faiss_retriever.py` and risks the two falling out of sync.
- **Re-embedding the query with a different model instance/config than was used at ingest:** Embedding dimensionality and semantics must match exactly between ingest and query time, or FAISS search returns nonsense. Pin the model name in both places from a single source (e.g. a `retrieval_version`-keyed constant, echoing `retrieval_version: "faiss-v0.1"` already present in `configs/base.yaml:18`).
- **Returning raw FAISS L2 distances as the `score` field without documenting the convention:** L2 distance is lower-is-better; if any downstream JEV-state feature (Phase 6, `evidence.coverage`/`evidence.agreement` per `.planning/research/domain_notes.md` §3) expects higher-is-better similarity, an un-normalized/undocumented score will silently invert rankings later. Document (in the dataclass docstring) whether `score` is distance or similarity, and pick one consistently.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vector similarity search / nearest-neighbor index | A custom brute-force cosine-similarity loop over numpy arrays | `faiss.IndexFlatL2` (or `IndexFlatIP` for cosine-normalized vectors) | FAISS's C++ core is SIMD-optimized and battle-tested; a hand-rolled loop is slower and easy to get wrong on edge cases (empty index, dimension mismatch, batch search) |
| Text embedding | A hand-rolled TF-IDF or bag-of-words vectorizer | `sentence-transformers` pretrained model | Semantic (not lexical) similarity is required for questions like `causal_analysis`/`multi_document_synthesis` where the query wording won't lexically match the source text; pretrained sentence embeddings capture this, TF-IDF does not |
| Index persistence (save/load) | Custom pickle-based serialization of the FAISS index object | `faiss.write_index()` / `faiss.read_index()` | FAISS ships its own binary serialization format; pickling the raw C++-backed index object is unsupported and fragile across FAISS versions `[CITED: theneuralbase.com "How to save and load FAISS index efficiently in Python"]` |

**Key insight:** The boundary for "don't hand-roll" in this phase is the vector math and index structure (FAISS, sentence-transformers) — those have correctness and performance properties that are hard to replicate correctly. The **document chunking** step (splitting text into overlapping windows) is simple enough, and specific enough to this project's small seed corpus, that a ~30-line custom function is appropriate rather than pulling in a heavy framework (e.g. LangChain) for one function's worth of logic — see Alternatives Considered above.

## Common Pitfalls

### Pitfall 1: `ingest.py` has nothing to ingest
**What goes wrong:** `ingest.py` is written correctly, but there is no source document text anywhere in the repository — `data/raw/sample_examples.jsonl` contains only document *IDs*, never document *bodies* (confirmed via `Read` this session — every line has `"documents": ["..."]` listing bare ID strings, no `text` or `content` field `[VERIFIED: data/raw/sample_examples.jsonl:1-7]`; and `BenchmarkExample` in `src/jev_cot/data/schema.py:35-37` types `documents: List[str]` as identifiers, not content `[VERIFIED: src/jev_cot/data/schema.py:35-37]`). Running `ingest.py` against the existing `data/` tree produces an empty index, which silently passes "the script ran" but fails the actual acceptance criterion ("Retrieval works end-to-end on seeded documents").
**Why it happens:** Phase 3 built the benchmark *question* schema, not a document *corpus* — no earlier phase created one.
**How to avoid:** This phase must add a small seed corpus (recommend: one short `.txt` file per document ID already referenced in `sample_examples.jsonl`, placed at `data/raw/documents/{doc_id}.txt`, containing a few realistic paragraphs — synthetic text is fine per the "Real SEC filings integration" non-goal). `ingest.py` then globs that directory.
**Warning signs:** `ingest.py` runs without error but writes an index with zero vectors; unit tests pass with `top_k=0` results and nobody notices because no test asserts `len(results) > 0`.

### Pitfall 2: Embedding model mismatch between ingest and retrieve
**What goes wrong:** `ingest.py` and `faiss_retriever.py` independently instantiate `SentenceTransformer(...)` with different model names (e.g. a typo, or someone upgrades one call site but not the other) → query vectors land in a different embedding space than indexed vectors → search returns garbage with no error.
**Why it happens:** The model name is a plain string in two files with no shared constant.
**How to avoid:** Define the model name once (e.g. as a module-level constant in `retrieval/base.py`, or read from the `retrieval_version` config field already present in `ExperimentConfig` — `src/jev_cot/config.py:68`) and import it in both `ingest.py` and `faiss_retriever.py`.
**Warning signs:** Retrieval returns technically-valid-looking but semantically-irrelevant chunks; scores/distances look unusually large or uniform.

### Pitfall 3: FAISS index binary committed to (or missing from) git
**What goes wrong:** Either the generated `.faiss` index file gets committed to git (bloats the repo, goes stale, diffs are unreadable binary noise), or it's `.gitignore`d but nothing regenerates it, so `pytest` fails on a clean checkout because the index file doesn't exist.
**Why it happens:** `.gitignore` (read this session) has no rule for `data/processed/` at all — `models/jev/checkpoints/*/` and `logs/*.jsonl` are the only generated-artifact patterns present `[VERIFIED: .gitignore]`. STRUCTURE.md states `data/{processed,train,validation,test}/` should be "Generated: Yes... Committed: No" but no matching gitignore rule currently exists.
**How to avoid:** Add a `.gitignore` rule for the generated index (e.g. `data/processed/faiss_index/`), and make unit tests build a small index into `tmp_path` (pytest fixture, same pattern as `test_data_split.py`) rather than depending on a pre-built index living on disk.
**Warning signs:** `git status` shows a large binary diff after running `ingest.py`; CI fails with `FileNotFoundError` on a fresh clone.

### Pitfall 4: Treating FAISS distance as a probability/confidence
**What goes wrong:** `IndexFlatL2` returns squared L2 distances (unbounded, lower = more similar) — passing this raw into a downstream "confidence" or "score" field that other code (e.g. Phase 6's structured-state extractor, which needs `evidence.coverage`/`agreement` signals per `.planning/research/domain_notes.md` §3) expects to be bounded/higher-is-better silently corrupts later features.
**Why it happens:** FAISS's `search()` return value naming (`D` for distances) doesn't self-document the direction.
**How to avoid:** Either normalize embeddings and use `IndexFlatIP` (inner product ≈ cosine similarity when vectors are L2-normalized, higher = more similar, bounded [-1, 1]) — `sentence-transformers`' `encode(..., normalize_embeddings=True)` makes this a one-line change `[CITED: sbert.net "Computing Embeddings" docs]` — or explicitly document and convert L2 distance to a similarity score before returning it in `RetrievedChunk.score`. Recommend the `IndexFlatIP` + normalized-embeddings route since it gives a self-documenting, bounded score for free.
**Warning signs:** Downstream code sorts by `score` ascending in one place and descending in another; "confidence" values greater than 1.0 appear in logs.

### Pitfall 5: Latency logged only in aggregate, not per-component
**What goes wrong:** A single `logger.info("retrieval done", latency=total_seconds)` call at the end of a broader function makes it impossible to distinguish embedding time from FAISS search time from metadata-join time — violates NFR-06 ("Observability: Latency must be measured separately per component ... No aggregate-only timing") `[VERIFIED: .planning/REQUIREMENTS.md:107-108]`.
**Why it happens:** It's the path of least resistance to wrap the whole `retrieve()` call in one timer.
**How to avoid:** At minimum, log one `latency_ms` per `retrieve()` call tagged `component="retrieval"` (this satisfies the Phase 4 acceptance criterion "Per-call latency is measured and logged"), matching the `latency_breakdown.retrieval` key already reserved in the trajectory-log example in `.planning/research/domain_notes.md` §4. If ingest is also timed, tag it separately (`component="ingest"`) so it's never confused with query-time retrieval latency in the same log stream.
**Warning signs:** `latency_breakdown` in a trajectory log has a `retrieval` key that's suspiciously close to `total` (embedding-model load time leaking into the per-call number rather than being a one-time amortized cost).

## Code Examples

### Latency logging integration (matches existing `jev_cot.logging` pattern)
```python
# Source: pattern from src/jev_cot/logging.py (read this session) +
# CONVENTIONS.md "Include contextual data as keyword arguments"
from __future__ import annotations

import time
from jev_cot.logging import logger


class FaissRetriever(RetrievalBackend):
    def retrieve(
        self,
        company: str,
        period: str,
        document_type: str | None,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        start = time.perf_counter()
        # ... embed query, faiss search, join metadata, filter/tag ...
        results: list[RetrievedChunk] = []  # placeholder for real logic
        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "retrieval call completed",
            component="retrieval",
            company=company,
            period=period,
            document_type=document_type,
            top_k=top_k,
            num_results=len(results),
            latency_ms=round(latency_ms, 2),
        )
        return results
```
This follows the exact convention documented in CONVENTIONS.md ("Include contextual data as keyword arguments: `logger.info("Event", key=value)`") and reuses the project's single logging entry point rather than introducing a second timing/logging mechanism. Note `setup_logging()` must already have been called by the caller (same contract as every other module in this codebase — logging setup is not `retrieval/`'s responsibility).

### Swap-test pattern for the ABC acceptance criterion
```python
# Source: pattern synthesized from tests/test_data_split.py's determinism-testing
# style (parametrize + shared assertions across implementations)
import pytest
from retrieval.base import RetrievalBackend
from retrieval.faiss_retriever import FaissRetriever


class _DummyBackend(RetrievalBackend):
    """Trivial second implementation — proves base.py is a real, swappable interface."""

    def retrieve(self, company, period, document_type, query, top_k=5):
        return []


@pytest.mark.parametrize("backend_cls", [FaissRetriever, _DummyBackend])
def test_backend_conforms_to_interface(backend_cls) -> None:
    """Any RetrievalBackend subclass is instantiable and callable with the same signature."""
    # FaissRetriever needs an index_path fixture; _DummyBackend needs nothing —
    # construct each accordingly, then assert both expose retrieve(...).
    assert hasattr(backend_cls, "retrieve")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `IndexFlatL2` returning raw squared-L2 distance as "relevance score" | Normalize embeddings + `IndexFlatIP` for a bounded, higher-is-better cosine-similarity score | Standard sentence-transformers/FAISS practice, not a recent change | Avoids the score-direction ambiguity described in Pitfall 4 |
| Fixed small chunk sizes (200–300 tokens) for general RAG | Larger chunks (1,000–1,800 tokens) with 15–20% overlap specifically for financial 10-K/10-Q text | Reflects domain-specific findings, e.g. Snowflake's finance-RAG research using 1,800-token chunks with 300-token overlap `[CITED: web search — snowflake.com/en/engineering-blog/impact-retrieval-chunking-finance-rag]` | At Phase 4's seed-corpus scale this doesn't materially matter, but the recommendation below leans toward the larger end of general guidance (512–1024 tokens, 15% overlap) rather than default small-chunk RAG presets, since financial narrative sections (MD&A, segment discussion) lose meaning when split too finely |

**Deprecated/outdated:** None specific to this stack — FAISS and sentence-transformers are both actively maintained, no deprecated API surface identified in this research pass.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No source document text/corpus exists anywhere in the repo yet; this phase must create one (`data/raw/documents/*.txt`) for `ingest.py` to have anything to embed | Summary, Pitfall 1 | If a document corpus is expected to come from elsewhere (e.g. a follow-up data-collection task), the plan may build the wrong deliverable or block on a missing input; low risk to reverse since it only adds files, doesn't remove anything |
| A2 | `source_tier` (`primary`/`secondary`) should be derived from `document_type` via the mapping `10K/10Q → primary`, `{Q1-Q4}_Earnings → secondary` | Architecture Patterns / Pattern 3 | If the intended semantics of "primary/secondary" are actually about retrieval-relevance-to-the-question rather than document-authority-tier, the tagging logic (and any downstream JEV state feature depending on it) would need rework; moderate risk since it affects a schema field |
| A3 | Chunk size ~512–1024 tokens with ~15% overlap is appropriate for this seed corpus | Standard Stack (Alternatives), State of the Art | Low risk at seed scale (few documents); chunk-size tuning is cheap to revisit later and doesn't lock in any external contract |
| A4 | `all-MiniLM-L6-v2` (not `bge-small-en-v1.5`) is the right default embedding model for this phase | Standard Stack | Low risk — both are drop-in via the same `sentence-transformers` API; swapping later requires only re-running `ingest.py`, no interface change |
| A5 | FAISS-cpu / sentence-transformers package legitimacy: both `SUS`-flagged packages are legitimate despite the seam's `too-new`/`unknown-downloads` signals, based on repo-URL match to the official Meta/UKP Lab projects | Package Legitimacy Audit | Low risk of actual malicious package (repo URLs match well-known official sources), but per protocol the planner must still gate the install behind `checkpoint:human-verify` |
| A6 | `IndexFlatIP` + normalized embeddings (cosine similarity) is preferable to raw `IndexFlatL2` distance for the `score` field | Common Pitfalls (Pitfall 4) | Low risk — this is an internal implementation choice with no external contract; easy to change later without touching `base.py`'s public interface |

**If this table is empty:** N/A — see rows above; several claims here need user confirmation before being treated as locked, particularly A1 (seed corpus) and A2 (primary/secondary mapping) since they affect what "correct" looks like for the unit tests this phase must write.

## Open Questions

1. **What should the seed document corpus actually contain?**
   - What we know: Document IDs already referenced by `data/raw/sample_examples.jsonl` (e.g. `MSFT_10K_FY23`, `ADBE_Q4_Earnings_FY23`) — read verbatim this session, lines 1–7.
   - What's unclear: Whether the corpus should be short synthetic excerpts (fastest to build, matches the "no real SEC filings" non-goal) or lightly-edited real public filing text (more realistic, but raises the same "real SEC filings integration" non-goal question the ROADMAP explicitly excludes).
   - Recommendation: Synthetic short excerpts (a few paragraphs per doc, written to contain the exact `gold_claims`/`required_evidence` strings already present in `sample_examples.jsonl` so retrieval tests can assert real content match) — cheapest, fully within non-goals, and makes tests self-verifying against data already in the repo.

2. **Should `document_type` be a free-form string or a `StrEnum` (matching the codebase's established `QuestionType`/`Action` pattern)?**
   - What we know: CONVENTIONS.md documents `StrEnum` as the standard for closed string enumerations in this codebase (`QuestionType`, `Action`).
   - What's unclear: Whether the seed corpus's document types (`10K`, `Q1_Earnings`...`Q4_Earnings`) are the final closed set, or whether more types (e.g. `10Q`, `proxy_statement`) will be added in later phases/sectors.
   - Recommendation: Use a `StrEnum` for consistency with the rest of the codebase, but keep it small and easy to extend (`10K`, `10Q`, `earnings_release`) since the exact taxonomy isn't locked anywhere.

3. **Does the FAISS index need to be rebuildable/regenerable by the test suite, or checked into a fixture?**
   - What we know: `.gitignore` has no rule for `data/processed/`; STRUCTURE.md says processed data should not be committed.
   - What's unclear: Whether tests should build a tiny in-`tmp_path` index per test run (slower, but matches `test_data_split.py`'s existing pattern of not depending on committed generated artifacts) or use a small pre-built fixture index committed under `tests/fixtures/`.
   - Recommendation: Build in `tmp_path` at test time — consistent with the existing test suite's convention (no mocking, real files, `tmp_path`-scoped) and avoids committing a binary fixture.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `faiss-cpu` (Python package) | `retrieval/faiss_retriever.py`, `retrieval/ingest.py` | ✗ (not installed in this environment; not yet in `pyproject.toml`/`uv.lock`) | — | `uv add faiss-cpu` — no other fallback needed, package verified available on PyPI (1.15.1) |
| `sentence-transformers` (Python package) | `retrieval/faiss_retriever.py`, `retrieval/ingest.py` | Present at the OS/global Python level on this machine (`python -c "import sentence_transformers"` succeeded), but **not yet a project dependency** in `pyproject.toml`/`uv.lock` | 6.1.0 (PyPI latest) | `uv add sentence-transformers` — must still be added to the project's own dependency set; do not rely on it being globally available on other machines/CI |
| `torch` (transitive dep of `sentence-transformers`) | `sentence-transformers` | Present globally on this machine (2.14.0) | — | Installed automatically as a transitive dependency by `uv add sentence-transformers`; note this is a heavy dependency (large wheel) |
| `uv` | Package management (NFR-07) | ✓ | 0.11.7 | — |
| Python 3.11 | Runtime | ✓ | 3.11.8 | — |
| Network access (PyPI) | `uv add`/`uv sync` for new packages | ✓ (confirmed — `pip index versions` reached the live PyPI index during this research session) | — | — |

**Missing dependencies with no fallback:** None — both new packages are resolvable from PyPI and no offline/fallback path is needed for a local dev environment.

**Missing dependencies with fallback:** `faiss-cpu`, `sentence-transformers` — both need `uv add`, gated behind `checkpoint:human-verify` per the Package Legitimacy Audit above.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ (`[VERIFIED: pyproject.toml:16]`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]` |
| Quick run command | `pytest tests/test_retrieval.py -v` |
| Full suite command | `pytest tests/ --cov=src/jev_cot --cov=retrieval` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-11 | Given company/period/document_type, `FaissRetriever.retrieve()` returns ranked chunks with correct `primary`/`secondary` tagging | unit | `pytest tests/test_retrieval.py::test_source_tier_tagging -x` | ❌ Wave 0 |
| FR-11 | End-to-end: `ingest.py` on the seed corpus → `FaissRetriever.retrieve()` returns non-empty, relevant results | integration | `pytest tests/test_retrieval.py::test_end_to_end_seeded_documents -x` | ❌ Wave 0 |
| FR-11 / ROADMAP AC-3 | Swap test: a second `RetrievalBackend` implementation is instantiable and callable through the same interface | unit | `pytest tests/test_retrieval.py::test_backend_conforms_to_interface -x` | ❌ Wave 0 |
| FR-14 / NFR-06 | Every `retrieve()` call logs a `latency_ms` field tagged `component="retrieval"` | unit | `pytest tests/test_retrieval.py::test_latency_is_logged -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_retrieval.py -v`
- **Per wave merge:** `pytest tests/ --cov=src/jev_cot --cov=retrieval`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_retrieval.py` — covers FR-11, FR-14, NFR-06 (new file)
- [ ] `data/raw/documents/*.txt` — seed document corpus (new; see Open Question 1 / Pitfall 1) — needed before any retrieval test can produce non-trivial results
- [ ] `uv add faiss-cpu sentence-transformers` — framework/dependency install, gated behind `checkpoint:human-verify` per Package Legitimacy Audit

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This is a local-only, single-user research CLI; no auth surface introduced by this phase |
| V3 Session Management | No | No sessions in this phase |
| V4 Access Control | No | No multi-user access control surface |
| V5 Input Validation | Yes | Validate `company`/`period`/`document_type` filter inputs to `retrieve()` are non-empty strings; validate `top_k > 0`; this is ordinary defensive coding, not a formal input-validation library requirement at this scale |
| V6 Cryptography | No | No secrets or cryptographic material handled by this phase (embedding models and FAISS indexes are not sensitive credentials) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via document filenames in `ingest.py` (if document IDs are ever derived from untrusted external input rather than the repo's own seed corpus) | Tampering | Resolve and validate all file paths stay within `data/raw/documents/`; this phase only reads locally-authored seed files, so risk is low, but `ingest.py`'s glob logic should not follow symlinks outside the project tree |
| Loading a `.faiss` index file from an untrusted source | Tampering | FAISS index files are binary blobs deserialized by a C++ library; only load index files this project generates itself (`ingest.py`'s own output), never accept an externally-supplied `.faiss` file as untrusted input — not a concern for this phase since there's no external-index-ingestion feature, but worth noting for any future "load a pre-built index" feature |

This phase has a minimal security surface (local filesystem, no network-facing service, no auth, no secrets) — the above is included for completeness per the Security Domain requirement, not because significant risk was identified.

## Sources

### Primary (HIGH confidence)
- `pip index versions faiss-cpu` / `pip index versions sentence-transformers` — live PyPI registry query, run 2026-09-23 `[VERIFIED]`
- `src/jev_cot/config.py`, `src/jev_cot/logging.py`, `src/jev_cot/data/schema.py`, `src/jev_cot/controller/actions.py`, `data/raw/sample_examples.jsonl`, `configs/base.yaml`, `pyproject.toml`, `.gitignore` — all read directly this session `[VERIFIED]`
- `.planning/research/domain_notes.md`, `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` (Phase 4 section) — project-authored specification documents, read directly this session

### Secondary (MEDIUM confidence)
- GitHub FAISS wiki — `github.com/facebookresearch/faiss/wiki/Getting-started` (IndexIDMap/add_with_ids/write_index/read_index patterns)
- Sentence Transformers official docs — `sbert.net/docs/package_reference/sentence_transformer/model.html`, `sbert.net/examples/sentence_transformer/applications/computing-embeddings/README.html`
- `belderbos.dev` — "Protocol or ABC? Designing a pluggable provider interface"
- Snowflake Engineering Blog — "Long-Context Isn't All You Need: How Retrieval & Chunking Impact Finance RAG"

### Tertiary (LOW confidence)
- Various WebSearch-aggregated blog posts on chunking best practices, embedding model comparisons (golinuxcloud.com, theneuralbase.com, markaicode.com, atlan.com) — used to corroborate general guidance, not treated as authoritative for any specific numeric claim beyond what's cross-referenced with the Snowflake finance-RAG source above

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — both `faiss-cpu` and `sentence-transformers` are explicitly named as locked choices in `.planning/PROJECT.md` §6 and `.planning/research/domain_notes.md` §1, and versions were verified live against PyPI
- Architecture: HIGH — the ABC + swappable-backend pattern is explicitly directed by CONTEXT.md ("Follow the abstract base-class + swappable-backend pattern already established for `config.py`/data schema") and directly mirrors existing, read-verified code conventions
- Primary/secondary tagging design: MEDIUM (ASSUMED, needs confirmation) — no spec document defines this; the recommended mapping is derived from the existing document-ID naming convention in seed data plus standard equity-research sourcing hierarchy, but was not locked by the user
- Pitfalls: HIGH — several pitfalls (no seed corpus, no `.gitignore` rule for `data/processed/`) were confirmed by directly reading repo state this session, not inferred

**Research date:** 2026-09-23
**Valid until:** 2026-10-23 (30 days — FAISS/sentence-transformers APIs are stable; re-verify package versions if this phase is picked up substantially later)
