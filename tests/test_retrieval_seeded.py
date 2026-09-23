"""
Corpus-integrity and full-corpus end-to-end retrieval tests (Phase 4, plan 04-04).

Acceptance criteria covered:
- AC-E1: Corpus integrity — every document id referenced by
  data/raw/sample_examples.jsonl has a matching seed file, every seed file
  name is a parseable document id, and every seed file carries the
  synthetic-data disclaimer.
- AC-E2: Evidence recall — every required_evidence string of every benchmark
  example appears verbatim (whitespace-normalized) in its listed document(s),
  and FaissRetriever.retrieve() over the full seed corpus returns each
  required_evidence string within the top 3 chunks for (company, period,
  question).
- AC-E3: Tier tagging — for ADBE and CAT (10-K + Q4 earnings release), 10-K
  chunks are tagged (TEN_K, PRIMARY) and earnings-release chunks are tagged
  (EARNINGS_RELEASE, SECONDARY); the document_type filter isolates each tier.
- AC-E4: Period and company filters — a period filter separates fiscal years
  for the same company, and an unknown company returns an empty result.

Tests never write to data/processed — the seeded index is built once per
module into a tmp_path_factory directory shared by every test in this file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from jev_cot.config import RetrievalConfig
from jev_cot.data.schema import BenchmarkExample
from jev_cot.retrieval.base import DocumentType, SourceTier, parse_document_id
from jev_cot.retrieval.faiss_retriever import FaissRetriever
from jev_cot.retrieval.ingest import build_index, read_document

if TYPE_CHECKING:
    from jev_cot.retrieval.faiss_retriever import SentenceTransformerEmbedder

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
DOCS_DIR: Final = REPO_ROOT / "data" / "raw" / "documents"
EXAMPLES_PATH: Final = REPO_ROOT / "data" / "raw" / "sample_examples.jsonl"


# ── Example loading ────────────────────────────────────────────────────────────
def _load_examples() -> list[BenchmarkExample]:
    """Read EXAMPLES_PATH, skipping blank lines, into typed BenchmarkExample rows."""
    examples: list[BenchmarkExample] = []
    for line in EXAMPLES_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        examples.append(BenchmarkExample.model_validate(json.loads(stripped)))
    return examples


def _normalize(text: str) -> str:
    """Collapse all whitespace runs to single spaces for substring comparison."""
    return " ".join(text.split())


EXAMPLES: Final = _load_examples()
EXAMPLES_WITH_EVIDENCE: Final = [ex for ex in EXAMPLES if ex.required_evidence]
SEED_FILES: Final = sorted(DOCS_DIR.glob("*.txt"))


# ── Fixtures ───────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def seeded_retriever(
    embedder: SentenceTransformerEmbedder, tmp_path_factory: pytest.TempPathFactory
) -> FaissRetriever:
    """Build the full seed corpus into a tmp_path index once per module."""
    index_dir = tmp_path_factory.mktemp("seeded_faiss_index")
    settings = RetrievalConfig()
    build_index(
        DOCS_DIR,
        index_dir,
        embedder,
        chunk_max_words=settings.chunk_max_words,
        chunk_overlap_words=settings.chunk_overlap_words,
        retrieval_version="faiss-v0.1",
    )
    return FaissRetriever.from_index_dir(index_dir, embedder=embedder)


# AC-E1 ────────────────────────────────────────────────────────────────────────
def test_every_referenced_document_has_seed_file() -> None:
    """Every example's documents list resolves to a seed file, with no orphans."""
    referenced = {doc_id for example in EXAMPLES for doc_id in example.documents}
    seed_stems = {path.stem for path in SEED_FILES}
    assert referenced == seed_stems
    assert len(seed_stems) == 9


@pytest.mark.parametrize("path", SEED_FILES, ids=lambda p: p.stem)
def test_every_seed_file_name_parses(path: Path) -> None:
    """Every seed file's stem is a valid {TICKER}_{DOCTYPE}_{PERIOD} document id."""
    parse_document_id(path.stem)


@pytest.mark.parametrize("path", SEED_FILES, ids=lambda p: p.stem)
def test_seed_files_carry_synthetic_disclaimer(path: Path) -> None:
    """Every seed file's first line is the machine-checked synthetic disclaimer."""
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("# SYNTHETIC SEED DOCUMENT")


# AC-E2 ────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("example", EXAMPLES, ids=lambda ex: ex.id)
def test_required_evidence_present_in_listed_documents(example: BenchmarkExample) -> None:
    """Every required_evidence string is a verbatim substring of a listed document."""
    doc_texts = [
        _normalize(read_document(DOCS_DIR / f"{doc_id}.txt")) for doc_id in example.documents
    ]
    for evidence in example.required_evidence:
        normalized_evidence = _normalize(evidence)
        assert any(normalized_evidence in doc_text for doc_text in doc_texts), (
            f"{example.id}: evidence {evidence!r} not found in any of {example.documents}"
        )


def test_evidence_sufficiency_document_lacks_full_year_data() -> None:
    """MSFT_Q1_Earnings_FY22 is scoped to the quarter only — no full-year figures."""
    text = read_document(DOCS_DIR / "MSFT_Q1_Earnings_FY22.txt").lower()
    assert "full year" not in text
    assert "full-year" not in text
    assert "azure" in text


@pytest.mark.parametrize("example", EXAMPLES_WITH_EVIDENCE, ids=lambda ex: ex.id)
def test_seeded_retrieval_recalls_required_evidence(
    example: BenchmarkExample, seeded_retriever: FaissRetriever
) -> None:
    """Every required_evidence string is recalled within the top 3 chunks."""
    result = seeded_retriever.retrieve(
        company=example.company,
        period=example.period,
        query=example.question,
        top_k=3,
    )
    normalized_chunks = [_normalize(chunk.text) for chunk in result.chunks]
    for evidence in example.required_evidence:
        normalized_evidence = _normalize(evidence)
        assert any(normalized_evidence in chunk_text for chunk_text in normalized_chunks), (
            f"{example.id}: evidence {evidence!r} not recalled in top 3 chunks "
            f"(got {[chunk.chunk_id for chunk in result.chunks]})"
        )


# AC-E3 ────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("company", "primary_doc_id", "secondary_doc_id"),
    [
        ("ADBE", "ADBE_10K_FY23", "ADBE_Q4_Earnings_FY23"),
        ("CAT", "CAT_10K_FY23", "CAT_Q4_Earnings_FY23"),
    ],
)
def test_primary_secondary_tagging_on_multi_document_companies(
    company: str,
    primary_doc_id: str,
    secondary_doc_id: str,
    seeded_retriever: FaissRetriever,
) -> None:
    """10-K chunks tag (TEN_K, PRIMARY); earnings chunks tag (EARNINGS_RELEASE, SECONDARY)."""
    result = seeded_retriever.retrieve(
        company=company,
        period="FY2023",
        query="segment revenue and operating margin",
        top_k=20,
    )
    doc_ids = {chunk.document_id for chunk in result.chunks}
    assert primary_doc_id in doc_ids
    assert secondary_doc_id in doc_ids

    for chunk in result.chunks:
        if chunk.document_id == primary_doc_id:
            assert chunk.document_type is DocumentType.TEN_K
            assert chunk.source_tier is SourceTier.PRIMARY
        elif chunk.document_id == secondary_doc_id:
            assert chunk.document_type is DocumentType.EARNINGS_RELEASE
            assert chunk.source_tier is SourceTier.SECONDARY

    filtered = seeded_retriever.retrieve(
        company=company,
        period="FY2023",
        query="segment revenue and operating margin",
        document_type=DocumentType.EARNINGS_RELEASE,
        top_k=20,
    )
    assert len(filtered.chunks) > 0
    for chunk in filtered.chunks:
        assert chunk.document_id == secondary_doc_id
        assert chunk.document_type is DocumentType.EARNINGS_RELEASE
        assert chunk.source_tier is SourceTier.SECONDARY


# AC-E4 ────────────────────────────────────────────────────────────────────────
def test_period_filter_separates_fiscal_years(seeded_retriever: FaissRetriever) -> None:
    """A period filter isolates each fiscal year's documents for the same company."""
    fy2022 = seeded_retriever.retrieve(
        company="MSFT", period="FY2022", query="quarterly revenue growth", top_k=20
    )
    assert len(fy2022.chunks) > 0
    for chunk in fy2022.chunks:
        assert chunk.document_id == "MSFT_Q1_Earnings_FY22"
        assert chunk.source_tier is SourceTier.SECONDARY

    fy2023 = seeded_retriever.retrieve(
        company="MSFT", period="FY2023", query="annual revenue growth", top_k=20
    )
    assert len(fy2023.chunks) > 0
    for chunk in fy2023.chunks:
        assert chunk.document_id == "MSFT_10K_FY23"
        assert chunk.source_tier is SourceTier.PRIMARY


def test_unknown_company_returns_empty_result(seeded_retriever: FaissRetriever) -> None:
    """A company with no matching chunks returns an empty result, not an error."""
    result = seeded_retriever.retrieve(company="ZZZZ", period="FY2023", query="anything at all")
    assert result.chunks == ()
    assert result.latency_ms >= 0
