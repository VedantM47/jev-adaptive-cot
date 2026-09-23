"""
Tests for jev_cot.retrieval.base — the swappable RetrievalBackend contract.

Acceptance criteria covered:
  AC-S1  Swap test: a second backend implementing only ``_search`` (an
         in-memory keyword backend) passes the identical contract assertions
         as FaissRetriever through a consumer typed against RetrievalBackend.
  AC-S2  RetrievalBackend itself, and any subclass missing ``_search``,
         cannot be instantiated.
  AC-L1  Every retrieve() call emits exactly one component="retrieval"
         loguru record with a measured latency_ms.
  AC-L2  That latency_ms value is written to the run's JSON-lines log file
         by setup_logging().
  AC-C1  A backend that violates the retrieve() contract (wrong company,
         wrong document_type, unsorted scores, more than top_k chunks)
         raises RetrievalContractError.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from jev_cot.config import RetrievalConfig
from jev_cot.logging import logger, setup_logging
from jev_cot.retrieval.base import (
    SOURCE_TIER_BY_DOCUMENT_TYPE,
    Chunk,
    DocumentType,
    RetrievalBackend,
    RetrievalContractError,
    RetrievalQuery,
    RetrievalResult,
    RetrievedChunk,
    SourceTier,
)
from jev_cot.retrieval.faiss_retriever import FaissRetriever
from jev_cot.retrieval.ingest import build_index, load_chunks

if TYPE_CHECKING:
    from jev_cot.retrieval.faiss_retriever import SentenceTransformerEmbedder


# ── Synthetic corpus ─────────────────────────────────────────────────────────
def _write_corpus(root: Path) -> Path:
    """
    Write a small synthetic ACME/BETA corpus into ``root / "docs"``.

    Args:
        root: Directory to create the ``docs`` subdirectory under.

    Returns:
        The ``docs`` directory containing the three seed ``.txt`` files.
    """
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    (docs_dir / "ACME_10K_FY23.txt").write_text(
        "# SYNTHETIC\n"
        "ACME Corp total revenue for fiscal year 2023 was $5.2 billion, an increase "
        "of 12% year over year.\n"
        "\n"
        "Gross margin improved to 62% in fiscal year 2023, compared to 58% in the "
        "prior year, driven by cost efficiencies.\n"
        "\n"
        "Research and development expense grew to $410 million in fiscal year 2023 "
        "as ACME invested in new product lines.\n",
        encoding="utf-8",
    )
    (docs_dir / "ACME_Q4_Earnings_FY23.txt").write_text(
        "# SYNTHETIC\n"
        "In the fourth quarter of fiscal year 2023, ACME Corp reported revenue of "
        "$1.4 billion, up 10% year over year.\n"
        "\n"
        "ACME provided guidance for fiscal year 2024 revenue growth in the range of "
        "8% to 11%.\n",
        encoding="utf-8",
    )
    (docs_dir / "BETA_10K_FY23.txt").write_text(
        "# SYNTHETIC\n"
        "BETA Industries reported total revenue of $3.1 billion for fiscal year "
        "2023, a decline of 2%.\n"
        "\n"
        "Operating margin for BETA Industries was 18% in fiscal year 2023, down "
        "from 21% the prior year.\n",
        encoding="utf-8",
    )
    return docs_dir


# ── Second backend implementation (proves the swap test) ────────────────────
class _InMemoryKeywordBackend(RetrievalBackend):
    """A trivial second backend implementing ONLY ``_search`` — proves base.py is swappable."""

    def __init__(self, chunks: Sequence[Chunk]) -> None:
        """Store the corpus chunks to search over."""
        self._chunks: tuple[Chunk, ...] = tuple(chunks)

    def _search(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        """Rank chunks by lowercase word-set Jaccard overlap with the query."""
        query_words = set(request.query.lower().split())
        hits: list[RetrievedChunk] = []
        for chunk in self._chunks:
            if chunk.company != request.company or chunk.period != request.period:
                continue
            if request.document_type is not None and chunk.document_type != request.document_type:
                continue
            chunk_words = set(chunk.text.lower().split())
            union = query_words | chunk_words
            score = len(query_words & chunk_words) / len(union) if union else 0.0
            hits.append(RetrievedChunk.model_validate({**chunk.model_dump(), "score": score}))
        hits.sort(key=lambda hit: (-hit.score, hit.chunk_id))
        return hits[: request.top_k]


# ── Backend fixture (parametrized over both implementations) ────────────────
@pytest.fixture(params=["faiss", "in_memory"])
def backend(request: pytest.FixtureRequest, tmp_path: Path) -> RetrievalBackend:
    """A RetrievalBackend built from the synthetic ACME/BETA corpus, one per implementation."""
    corpus_dir = _write_corpus(tmp_path)
    settings = RetrievalConfig()
    if request.param == "faiss":
        embedder: SentenceTransformerEmbedder = request.getfixturevalue("embedder")
        index_dir = tmp_path / "idx"
        build_index(
            corpus_dir,
            index_dir,
            embedder,
            chunk_max_words=settings.chunk_max_words,
            chunk_overlap_words=settings.chunk_overlap_words,
            retrieval_version="test-v1",
        )
        return FaissRetriever.from_index_dir(index_dir, embedder=embedder)
    chunks = load_chunks(
        corpus_dir,
        max_words=settings.chunk_max_words,
        overlap_words=settings.chunk_overlap_words,
    )
    return _InMemoryKeywordBackend(chunks)


def _collect_evidence(backend: RetrievalBackend, **kwargs: Any) -> RetrievalResult:
    """A consumer using only the base RetrievalBackend API — proves backends are swappable."""
    return backend.retrieve(**kwargs)


# ── Log capture fixtures ─────────────────────────────────────────────────────
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


@pytest.fixture()
def restore_logging() -> Iterator[None]:
    """Restore loguru's default stderr handler after a test calls setup_logging()."""
    try:
        yield
    finally:
        logger.remove()
        logger.add(sys.stderr, level="INFO")


# ── AC-S2 ─────────────────────────────────────────────────────────────────────
class TestAbstractEnforcement:
    def test_base_class_is_abstract(self) -> None:
        """RetrievalBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            RetrievalBackend()  # type: ignore[abstract]

    def test_subclass_without_search_is_not_instantiable(self) -> None:
        """A RetrievalBackend subclass that doesn't implement _search cannot be instantiated."""

        class _Incomplete(RetrievalBackend):
            pass

        with pytest.raises(TypeError):
            _Incomplete()  # type: ignore[abstract]


# ── AC-S1 ─────────────────────────────────────────────────────────────────────
class TestSwapContract:
    def test_swap_backends_share_contract(self, backend: RetrievalBackend) -> None:
        """Both backends satisfy the identical contract through the base RetrievalBackend API."""
        result = _collect_evidence(
            backend, company="ACME", period="FY2023", query="ACME revenue", top_k=10
        )
        assert isinstance(result, RetrievalResult)
        assert 1 <= len(result.chunks) <= 10

        tiers_seen: set[SourceTier] = set()
        previous_score: float | None = None
        for chunk in result.chunks:
            assert chunk.company == "ACME"
            assert chunk.period == "FY2023"
            assert chunk.source_tier == SOURCE_TIER_BY_DOCUMENT_TYPE[chunk.document_type]
            tiers_seen.add(chunk.source_tier)
            if previous_score is not None:
                assert previous_score >= chunk.score
            previous_score = chunk.score

        assert tiers_seen == {SourceTier.PRIMARY, SourceTier.SECONDARY}
        assert result.backend == type(backend).__name__
        assert result.latency_ms >= 0
        assert result.latency_seconds == result.latency_ms / 1000

    def test_document_type_filter_applies_to_every_backend(self, backend: RetrievalBackend) -> None:
        """A document_type filter restricts results to the matching source_tier."""
        earnings = _collect_evidence(
            backend,
            company="ACME",
            period="FY2023",
            query="fourth quarter revenue guidance",
            document_type=DocumentType.EARNINGS_RELEASE,
            top_k=10,
        )
        assert len(earnings.chunks) > 0
        for chunk in earnings.chunks:
            assert chunk.document_id == "ACME_Q4_Earnings_FY23"
            assert chunk.source_tier == SourceTier.SECONDARY

        ten_k = _collect_evidence(
            backend,
            company="ACME",
            period="FY2023",
            query="revenue gross margin",
            document_type=DocumentType.TEN_K,
            top_k=10,
        )
        assert len(ten_k.chunks) > 0
        for chunk in ten_k.chunks:
            assert chunk.document_id == "ACME_10K_FY23"
            assert chunk.source_tier == SourceTier.PRIMARY


# ── AC-L1, AC-L2 ────────────────────────────────────────────────────────────
class TestLatencyLogging:
    def test_each_call_emits_one_latency_record(
        self, backend: RetrievalBackend, retrieval_log_records: list[dict[str, Any]]
    ) -> None:
        """Each retrieve() call emits exactly one component="retrieval" log record."""
        result1 = _collect_evidence(
            backend, company="ACME", period="FY2023", query="revenue", top_k=5
        )
        result2 = _collect_evidence(
            backend, company="BETA", period="FY2023", query="operating margin", top_k=5
        )

        assert len(retrieval_log_records) == 2
        for record, result in zip(retrieval_log_records, (result1, result2), strict=True):
            extra = record["extra"]
            assert extra["component"] == "retrieval"
            assert extra["backend"] == type(backend).__name__
            assert isinstance(extra["latency_ms"], float)
            assert extra["latency_ms"] >= 0
            assert extra["num_results"] == len(result.chunks)

    def test_latency_written_to_run_jsonl(self, tmp_path: Path, restore_logging: None) -> None:
        """A retrieve() call's latency_ms lands in the run's JSON-lines log file."""
        log_dir = tmp_path / "logs"
        setup_logging(log_dir=log_dir, run_id="retrieval-latency")

        corpus_dir = _write_corpus(tmp_path)
        settings = RetrievalConfig()
        chunks = load_chunks(
            corpus_dir,
            max_words=settings.chunk_max_words,
            overlap_words=settings.chunk_overlap_words,
        )
        backend = _InMemoryKeywordBackend(chunks)
        result = backend.retrieve(company="ACME", period="FY2023", query="revenue", top_k=5)

        logger.remove()  # flush and close every sink, including the file handler

        log_file = log_dir / "retrieval-latency.log.jsonl"
        raw_lines = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line]
        matching = [
            parsed
            for line in raw_lines
            if (parsed := json.loads(line))["record"]["extra"].get("component") == "retrieval"
        ]
        assert len(matching) == 1
        assert matching[0]["record"]["extra"]["latency_ms"] == round(result.latency_ms, 3)


# ── AC-C1 ─────────────────────────────────────────────────────────────────────
def _make_chunk(
    *,
    chunk_id: str = "ACME_10K_FY23::000",
    document_id: str = "ACME_10K_FY23",
    company: str = "ACME",
    period: str = "FY2023",
    document_type: DocumentType = DocumentType.TEN_K,
    source_tier: SourceTier = SourceTier.PRIMARY,
    text: str = "chunk text",
    score: float = 0.5,
) -> RetrievedChunk:
    """Build a RetrievedChunk with sensible ACME/10K defaults, overridable per test."""
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        company=company,
        period=period,
        document_type=document_type,
        source_tier=source_tier,
        text=text,
        score=score,
    )


class _WrongCompanyBackend(RetrievalBackend):
    """Returns a chunk for a company outside the request — must be rejected."""

    def _search(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        return [_make_chunk(company="OTHER", period=request.period)]


class _WrongDocumentTypeBackend(RetrievalBackend):
    """Returns an earnings-release chunk while a 10K filter is set — must be rejected."""

    def _search(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        return [
            _make_chunk(
                chunk_id="ACME_Q4_Earnings_FY23::000",
                document_id="ACME_Q4_Earnings_FY23",
                document_type=DocumentType.EARNINGS_RELEASE,
                source_tier=SourceTier.SECONDARY,
            )
        ]


class _UnsortedScoresBackend(RetrievalBackend):
    """Returns scores not in non-increasing order — must be rejected."""

    def _search(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        return [
            _make_chunk(chunk_id="ACME_10K_FY23::000", score=0.3),
            _make_chunk(chunk_id="ACME_10K_FY23::001", score=0.9),
        ]


class _TooManyChunksBackend(RetrievalBackend):
    """Returns more than top_k chunks — must be rejected."""

    def _search(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        return [
            _make_chunk(chunk_id=f"ACME_10K_FY23::{i:03d}", score=1.0 - i * 0.1)
            for i in range(request.top_k + 1)
        ]


class TestContractViolations:
    def test_wrong_company_raises(self) -> None:
        """A backend returning a chunk for a company outside the request raises."""
        with pytest.raises(RetrievalContractError):
            _WrongCompanyBackend().retrieve(company="ACME", period="FY2023", query="revenue")

    def test_wrong_document_type_raises_when_filtered(self) -> None:
        """A backend returning a chunk whose document_type != the requested filter raises."""
        with pytest.raises(RetrievalContractError):
            _WrongDocumentTypeBackend().retrieve(
                company="ACME",
                period="FY2023",
                query="revenue",
                document_type=DocumentType.TEN_K,
            )

    def test_unsorted_scores_raise(self) -> None:
        """A backend returning scores not in non-increasing order raises."""
        with pytest.raises(RetrievalContractError):
            _UnsortedScoresBackend().retrieve(company="ACME", period="FY2023", query="revenue")

    def test_too_many_chunks_raises(self) -> None:
        """A backend returning more chunks than top_k raises."""
        with pytest.raises(RetrievalContractError):
            _TooManyChunksBackend().retrieve(
                company="ACME", period="FY2023", query="revenue", top_k=1
            )
