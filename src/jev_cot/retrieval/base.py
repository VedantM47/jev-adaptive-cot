"""
jev_cot.retrieval.base
=======================
Swappable retrieval interface (Phase 4, FR-11).

Defines the abstract ``RetrievalBackend`` template method, the typed
document/chunk/query/result models every backend shares, and the
document-id convention that derives primary/secondary source tagging
once, at ingest time.

A new backend implements only ``_search()``. The concrete, ``@final``
``retrieve()`` method on this base class validates input, times the
search, enforces the result contract (top_k, filter match, score
ordering), logs latency with ``component="retrieval"``, and returns a
typed ``RetrievalResult``.

Usage::

    from jev_cot.retrieval.base import RetrievalBackend, RetrievedChunk

    class EchoBackend(RetrievalBackend):
        def _search(self, request):
            return []

    result = EchoBackend().retrieve(company="MSFT", period="FY2023", query="revenue")
"""

from __future__ import annotations

import re
import time
import types
import typing
from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, model_validator

from jev_cot.logging import logger

# ── Latency component tag ────────────────────────────────────────────────────
LATENCY_COMPONENT: Final = "retrieval"


# ── Source tiering ────────────────────────────────────────────────────────────
class SourceTier(StrEnum):
    """Authority tier of a document's source (PRD equity-research sourcing hierarchy)."""

    PRIMARY = "primary"
    SECONDARY = "secondary"


class DocumentType(StrEnum):
    """The document types recognized by the seed corpus naming convention."""

    TEN_K = "10K"
    TEN_Q = "10Q"
    EARNINGS_RELEASE = "earnings_release"


# Audited regulatory filings (10-K/10-Q) are the source of record; company-issued
# earnings releases are unaudited and merely corroborating. Tagged once here so
# ingest and every backend agree by construction (see Chunk's validator below).
SOURCE_TIER_BY_DOCUMENT_TYPE: Final[Mapping[DocumentType, SourceTier]] = types.MappingProxyType(
    {
        DocumentType.TEN_K: SourceTier.PRIMARY,
        DocumentType.TEN_Q: SourceTier.PRIMARY,
        DocumentType.EARNINGS_RELEASE: SourceTier.SECONDARY,
    }
)

# {TICKER}_{10K|10Q|Q[1-4]_Earnings}_FY{YY|YYYY} — deliberately rejects dots,
# slashes, and lowercase letters so a malformed document id fails loudly.
_DOCUMENT_ID_PATTERN = re.compile(
    r"^(?P<company>[A-Z][A-Z0-9]{0,9})_(?P<doctype>10K|10Q|Q[1-4]_Earnings)_(?P<period>FY\d{2}|FY\d{4})$"
)

_DOCTYPE_TOKEN_TO_DOCUMENT_TYPE: Final[Mapping[str, DocumentType]] = types.MappingProxyType(
    {
        "10K": DocumentType.TEN_K,
        "10Q": DocumentType.TEN_Q,
        "Q1_Earnings": DocumentType.EARNINGS_RELEASE,
        "Q2_Earnings": DocumentType.EARNINGS_RELEASE,
        "Q3_Earnings": DocumentType.EARNINGS_RELEASE,
        "Q4_Earnings": DocumentType.EARNINGS_RELEASE,
    }
)


class DocumentMetadata(BaseModel):
    """Metadata parsed from a ``{TICKER}_{DOCTYPE}_{PERIOD}`` document id."""

    model_config = {"frozen": True}

    document_id: str = Field(description="Original document id, e.g. 'MSFT_10K_FY23'")
    company: str = Field(description="Ticker parsed from the document id, e.g. 'MSFT'")
    period: str = Field(description="Normalized fiscal period, e.g. 'FY2023' (4-digit year)")
    document_type: DocumentType = Field(description="Document type parsed from the document id")
    source_tier: SourceTier = Field(
        description="Authority tier derived from document_type via SOURCE_TIER_BY_DOCUMENT_TYPE"
    )


def parse_document_id(document_id: str) -> DocumentMetadata:
    """
    Parse a ``{TICKER}_{10K|10Q|Q[1-4]_Earnings}_FY{YY|YYYY}`` document id.

    A 2-digit period is normalized to 4 digits (``FY23`` -> ``FY2023``) so it
    matches :class:`jev_cot.data.schema.BenchmarkExample.period`.

    Args:
        document_id: The document id to parse, e.g. ``"MSFT_10K_FY23"``.

    Returns:
        A frozen :class:`DocumentMetadata` with company/period/document_type/source_tier.

    Raises:
        ValueError: If *document_id* does not match the expected pattern.
    """
    match = _DOCUMENT_ID_PATTERN.match(document_id)
    if match is None:
        raise ValueError(
            f"Document id {document_id!r} does not match the expected pattern "
            f"'{{TICKER}}_{{10K|10Q|Q[1-4]_Earnings}}_FY{{YY|YYYY}}' "
            f"(pattern: {_DOCUMENT_ID_PATTERN.pattern!r})"
        )
    company = match.group("company")
    doctype_token = match.group("doctype")
    period_token = match.group("period")

    document_type = _DOCTYPE_TOKEN_TO_DOCUMENT_TYPE[doctype_token]
    # FYxx -> FY20xx; FYxxxx is already 4 digits.
    period = f"FY20{period_token[2:]}" if len(period_token) == 4 else period_token

    return DocumentMetadata(
        document_id=document_id,
        company=company,
        period=period,
        document_type=document_type,
        source_tier=SOURCE_TIER_BY_DOCUMENT_TYPE[document_type],
    )


# ── Chunk / result models ─────────────────────────────────────────────────────
class Chunk(BaseModel):
    """A single indexed span of text with its provenance metadata."""

    model_config = {"frozen": True}

    chunk_id: str = Field(description="Unique id, e.g. 'MSFT_10K_FY23::000'")
    document_id: str = Field(description="Source document id, e.g. 'MSFT_10K_FY23'")
    company: str = Field(description="Ticker, e.g. 'MSFT'")
    period: str = Field(description="Normalized fiscal period, e.g. 'FY2023'")
    document_type: DocumentType = Field(description="Document type this chunk was sourced from")
    source_tier: SourceTier = Field(description="Authority tier; must agree with document_type")
    text: str = Field(min_length=1, description="Chunk text")

    @model_validator(mode="after")
    def _check_tier_matches_document_type(self) -> Self:
        expected = SOURCE_TIER_BY_DOCUMENT_TYPE[self.document_type]
        if self.source_tier != expected:
            raise ValueError(
                f"Chunk {self.chunk_id!r} has source_tier={self.source_tier!r}, "
                f"but document_type={self.document_type!r} requires {expected!r}"
            )
        return self


class RetrievedChunk(Chunk):
    """A :class:`Chunk` ranked by a query, carrying its similarity score."""

    score: float = Field(ge=-1.0, le=1.0, description="Cosine similarity; higher = more relevant")


class RetrievalQuery(BaseModel):
    """A validated retrieval request."""

    model_config = {"frozen": True, "str_strip_whitespace": True}

    company: str = Field(min_length=1, max_length=32, description="Ticker to filter on")
    period: str = Field(min_length=1, max_length=16, description="Fiscal period to filter on")
    query: str = Field(min_length=1, max_length=2000, description="Natural-language query text")
    document_type: DocumentType | None = Field(
        default=None, description="Optional document_type filter"
    )
    top_k: int = Field(default=5, ge=1, le=100, description="Max chunks to return")


class RetrievalResult(BaseModel):
    """The typed result of a single :meth:`RetrievalBackend.retrieve` call."""

    model_config = {"frozen": True}

    query: RetrievalQuery = Field(description="The validated request that produced this result")
    chunks: tuple[RetrievedChunk, ...] = Field(description="Ranked chunks, descending by score")
    backend: str = Field(description="RetrievalBackend.backend_name that produced this result")
    latency_ms: float = Field(
        ge=0.0, description="Wall-clock time spent in _search(), in milliseconds"
    )

    @property
    def latency_seconds(self) -> float:
        """``latency_ms`` in seconds — the unit of Appendix B ``latency_breakdown["retrieval"]``."""
        return self.latency_ms / 1000.0


class RetrievalContractError(RuntimeError):
    """Raised when a backend's ``_search()`` result violates the retrieve() contract."""


# ── Abstract backend ──────────────────────────────────────────────────────────
class RetrievalBackend(ABC):
    """
    Abstract retrieval interface. Concrete backends implement only ``_search()``.

    ``retrieve()`` is a concrete, ``@final`` template method: it validates
    input, times ``_search()``, enforces the result contract, logs latency,
    and returns a typed :class:`RetrievalResult`. This is what lets a new
    backend be added by implementing only the interface (ROADMAP swap-test AC).
    """

    @property
    def backend_name(self) -> str:
        """The concrete backend's class name, recorded on every RetrievalResult."""
        return type(self).__name__

    @typing.final
    def retrieve(
        self,
        *,
        company: str,
        period: str,
        query: str,
        document_type: DocumentType | None = None,
        top_k: int = 5,
    ) -> RetrievalResult:
        """
        Validate, search, time, log, and return a typed retrieval result.

        Args:
            company: Ticker to filter on.
            period: Fiscal period to filter on.
            query: Natural-language query text.
            document_type: Optional document_type filter.
            top_k: Max chunks to return.

        Returns:
            A :class:`RetrievalResult` with ranked chunks and measured latency.

        Raises:
            pydantic.ValidationError: If the request arguments are invalid.
            RetrievalContractError: If ``_search()``'s result violates the
                contract (too many chunks, filter mismatch, non-descending scores).
        """
        # (a) Validate before any search or log — a ValidationError propagates untouched.
        request = RetrievalQuery(
            company=company,
            period=period,
            query=query,
            document_type=document_type,
            top_k=top_k,
        )

        # (b) Time only the search itself (research Pitfall 5: never aggregate timing).
        start = time.perf_counter()
        chunks = self._search(request)
        latency_ms = (time.perf_counter() - start) * 1000.0

        # (c) Enforce the result contract.
        self._check_contract(request, chunks)

        # (d) Log latency — never query text or chunk text (threat T-04-05).
        logger.info(
            "retrieval call completed",
            component=LATENCY_COMPONENT,
            backend=self.backend_name,
            company=request.company,
            period=request.period,
            document_type=(request.document_type.value if request.document_type else None),
            top_k=request.top_k,
            num_results=len(chunks),
            latency_ms=round(latency_ms, 3),
        )

        # (e) Return the result with the unrounded latency.
        return RetrievalResult(
            query=request,
            chunks=tuple(chunks),
            backend=self.backend_name,
            latency_ms=latency_ms,
        )

    def _check_contract(self, request: RetrievalQuery, chunks: list[RetrievedChunk]) -> None:
        """Raise RetrievalContractError if *chunks* violates the retrieve() contract."""
        if len(chunks) > request.top_k:
            raise RetrievalContractError(
                f"{self.backend_name}._search returned {len(chunks)} chunks, "
                f"exceeding top_k={request.top_k}"
            )
        for chunk in chunks:
            if chunk.company != request.company or chunk.period != request.period:
                raise RetrievalContractError(
                    f"{self.backend_name}._search returned chunk {chunk.chunk_id!r} with "
                    f"company/period ({chunk.company!r}, {chunk.period!r}) that does not "
                    f"match the request ({request.company!r}, {request.period!r})"
                )
            if request.document_type is not None and chunk.document_type != request.document_type:
                raise RetrievalContractError(
                    f"{self.backend_name}._search returned chunk {chunk.chunk_id!r} with "
                    f"document_type={chunk.document_type!r}, expected {request.document_type!r}"
                )
        scores = [chunk.score for chunk in chunks]
        if any(earlier < later for earlier, later in zip(scores, scores[1:], strict=False)):
            raise RetrievalContractError(
                f"{self.backend_name}._search returned scores not in non-increasing order: {scores}"
            )

    @abstractmethod
    def _search(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        """
        Return at most ``request.top_k`` chunks matching every filter.

        Results must be ranked by descending score. Implementations must
        never log latency themselves — the base class's ``retrieve()``
        template method owns all latency logging.

        Args:
            request: The validated retrieval request.

        Returns:
            A list of at most ``request.top_k`` :class:`RetrievedChunk`,
            each matching ``request.company``/``request.period`` and, when
            set, ``request.document_type``.
        """
        raise NotImplementedError
