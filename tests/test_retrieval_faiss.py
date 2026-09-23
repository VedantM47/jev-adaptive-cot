"""
Tracer end-to-end test for the retrieval layer (Phase 4, plan 04-02).

Acceptance criteria covered:
- AC-1: build_index on data/raw/documents followed by FaissRetriever.retrieve()
  returns, as the top chunk, the MSFT_10K_FY23 paragraph containing
  "$211.9 billion", tagged document_type=10K and source_tier=primary.
- AC-2: Every retrieve() call measures latency_ms around the backend search
  and emits exactly one loguru record with component="retrieval" and latency_ms.
- AC-3: RetrievedChunk.score is a cosine similarity in [-1, 1].
- AC-4: An unmatched filter (unknown company) returns an empty chunk tuple
  but still logs latency, rather than raising.

Tests never write to data/processed — every index is built into tmp_path.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from jev_cot.config import RetrievalConfig
from jev_cot.logging import logger
from jev_cot.retrieval.base import DocumentType, SourceTier
from jev_cot.retrieval.faiss_retriever import FaissRetriever
from jev_cot.retrieval.ingest import build_index

if TYPE_CHECKING:
    from jev_cot.retrieval.faiss_retriever import IndexManifest, SentenceTransformerEmbedder

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def retrieval_log_records() -> Iterator[list[dict[str, Any]]]:
    """Capture loguru records whose extra ``component`` is ``"retrieval"``."""
    records: list[dict[str, Any]] = []

    def _sink(message: Any) -> None:
        record = message.record
        if record["extra"].get("component") == "retrieval":
            records.append(record)

    handler_id = logger.add(_sink)
    try:
        yield records
    finally:
        logger.remove(handler_id)


def _build_seed_index(embedder: SentenceTransformerEmbedder, index_dir: Path) -> IndexManifest:
    settings = RetrievalConfig()
    return build_index(
        REPO_ROOT / "data" / "raw" / "documents",
        index_dir,
        embedder,
        chunk_max_words=settings.chunk_max_words,
        chunk_overlap_words=settings.chunk_overlap_words,
        retrieval_version="faiss-v0.1",
    )


# AC-1, AC-2, AC-3 ────────────────────────────────────────────────────────────
def test_tracer_end_to_end(
    embedder: SentenceTransformerEmbedder,
    tmp_path: Path,
    retrieval_log_records: list[dict[str, Any]],
) -> None:
    """Seed doc -> ingest -> FAISS -> retrieve() returns the tagged revenue chunk."""
    index_dir = tmp_path / "idx"
    manifest = _build_seed_index(embedder, index_dir)
    assert "MSFT_10K_FY23" in manifest.document_ids

    retriever = FaissRetriever.from_index_dir(index_dir, embedder=embedder)
    result = retriever.retrieve(
        company="MSFT",
        period="FY2023",
        query="What was Microsoft's total revenue in fiscal year 2023?",
        top_k=3,
    )

    assert len(result.chunks) > 0
    top = result.chunks[0]
    assert "$211.9 billion" in top.text
    assert top.document_id == "MSFT_10K_FY23"
    assert top.document_type is DocumentType.TEN_K
    assert top.source_tier is SourceTier.PRIMARY
    assert -1.0 <= top.score <= 1.0

    for chunk in result.chunks:
        assert chunk.company == "MSFT"
        assert chunk.period == "FY2023"
    assert result.latency_ms > 0
    assert result.backend == "FaissRetriever"

    assert len(retrieval_log_records) == 1
    record = retrieval_log_records[0]
    assert record["extra"]["latency_ms"] == round(result.latency_ms, 3)
    assert record["extra"]["backend"] == "FaissRetriever"


# AC-4 ─────────────────────────────────────────────────────────────────────────
def test_unknown_company_returns_empty_but_still_logs_latency(
    embedder: SentenceTransformerEmbedder,
    tmp_path: Path,
    retrieval_log_records: list[dict[str, Any]],
) -> None:
    """A company with no matching chunks returns an empty result, not an error."""
    index_dir = tmp_path / "idx"
    _build_seed_index(embedder, index_dir)

    retriever = FaissRetriever.from_index_dir(index_dir, embedder=embedder)
    result = retriever.retrieve(company="ZZZZ", period="FY2023", query="anything at all")

    assert result.chunks == ()
    assert result.latency_ms >= 0

    assert len(retrieval_log_records) == 1
    record = retrieval_log_records[0]
    assert record["extra"]["num_results"] == 0
