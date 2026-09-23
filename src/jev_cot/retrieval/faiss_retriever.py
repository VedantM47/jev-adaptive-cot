"""
jev_cot.retrieval.faiss_retriever
==================================
FAISS + sentence-transformers implementation of :class:`RetrievalBackend`.

Loads a ``faiss.IndexFlatL2`` built by :mod:`jev_cot.retrieval.ingest`
plus its ``chunks.jsonl`` sidecar and ``manifest.json`` (FAISS itself
stores only vectors and integer ids, so text and provenance metadata
live in the sidecar and are joined at query time by FAISS row id).

Embeddings are L2-normalized at both ingest and query time, so squared
L2 distance ``d`` converts to cosine similarity as ``1 - d / 2`` — a
bounded, higher-is-better score computed without changing the
``IndexFlatL2`` index type.

Usage::

    from jev_cot.retrieval.faiss_retriever import FaissRetriever

    retriever = FaissRetriever.from_index_dir("data/processed/faiss_index")
    result = retriever.retrieve(company="MSFT", period="FY2023", query="revenue")
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import jsonlines
import numpy as np
from pydantic import BaseModel, Field

from jev_cot.retrieval.base import Chunk, RetrievalBackend, RetrievalQuery, RetrievedChunk

if TYPE_CHECKING:
    import numpy.typing as npt

# ── Artifact filenames ────────────────────────────────────────────────────────
INDEX_FILENAME: Final = "index.faiss"
CHUNKS_FILENAME: Final = "chunks.jsonl"
MANIFEST_FILENAME: Final = "manifest.json"


class IndexManifest(BaseModel):
    """Records the exact ingest configuration a FAISS index was built with."""

    model_config = {"frozen": True}

    embedding_model: str = Field(description="Fully-qualified model id used for every vector")
    dimension: int = Field(ge=1, description="Embedding dimensionality")
    num_documents: int = Field(ge=1, description="Number of source documents ingested")
    num_chunks: int = Field(ge=1, description="Number of chunks indexed (== index.ntotal)")
    chunk_max_words: int = Field(ge=1, description="chunk_max_words used to build this index")
    chunk_overlap_words: int = Field(
        ge=0, description="chunk_overlap_words used to build this index"
    )
    retrieval_version: str = Field(min_length=1, description="Version tag for this index build")
    document_ids: tuple[str, ...] = Field(description="Document ids included in this index")


class SentenceTransformerEmbedder:
    """Wraps a single sentence-transformers model shared by ingest and query."""

    def __init__(self, model_name: str) -> None:
        """
        Load *model_name* on CPU (NFR-01 determinism).

        Args:
            model_name: Fully-qualified Hugging Face model id.
        """
        # The heavy torch/transformers import is paid only when an embedder is
        # actually built, not merely when this module is imported.
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        # trust_remote_code is never passed (defaults False) — no remote code
        # execution from a downloaded model (threat T-04-01).
        self._model: Any = SentenceTransformer(model_name, device="cpu")
        dim = self._model.get_embedding_dimension()
        if not isinstance(dim, int):
            raise ValueError(
                f"Model {model_name!r} returned a non-int embedding dimension: {dim!r}"
            )
        self._dimension = dim

    @property
    def model_name(self) -> str:
        """The fully-qualified model id this embedder was built with."""
        return self._model_name

    @property
    def dimension(self) -> int:
        """The embedding dimensionality this model produces."""
        return self._dimension

    def encode(self, texts: Sequence[str]) -> npt.NDArray[np.float32]:
        """
        Embed *texts* into L2-normalized float32 vectors.

        Args:
            texts: Non-empty sequence of strings to embed.

        Returns:
            A contiguous ``(len(texts), self.dimension)`` float32 array.

        Raises:
            ValueError: If *texts* is empty, or the model returns an
                unexpected shape.
        """
        if len(texts) == 0:
            raise ValueError("encode() requires at least one text, got an empty sequence")
        raw = self._model.encode(
            list(texts),
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        # FAISS requires contiguous float32; the explicit conversion also
        # satisfies mypy's warn_return_any on the untyped sentence-transformers return.
        vectors = np.ascontiguousarray(raw, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[1] != self._dimension:
            raise ValueError(
                f"Expected an (N, {self._dimension}) embedding array, got shape {vectors.shape}"
            )
        return vectors


class FaissRetriever(RetrievalBackend):
    """FAISS ``IndexFlatL2`` retrieval backend over normalized embeddings."""

    def __init__(
        self,
        *,
        index: Any,
        chunks: Sequence[Chunk],
        manifest: IndexManifest,
        embedder: SentenceTransformerEmbedder,
    ) -> None:
        """
        Wrap an in-memory FAISS index with its chunks, manifest, and embedder.

        Args:
            index: A loaded ``faiss.Index`` (``IndexFlatL2``).
            chunks: Chunks in FAISS id order (row *i* == FAISS id *i*).
            manifest: The manifest this index was built with.
            embedder: The embedder to use for query-time encoding; must match
                the manifest's recorded model and dimension.

        Raises:
            ValueError: If the index, chunks, manifest, or embedder disagree
                on count, dimension, or embedding model (research Pitfall 2).
        """
        if index.ntotal != len(chunks):
            raise ValueError(
                f"FAISS index.ntotal={index.ntotal} does not match len(chunks)={len(chunks)}"
            )
        if manifest.num_chunks != len(chunks):
            raise ValueError(
                f"manifest.num_chunks={manifest.num_chunks} does not match "
                f"len(chunks)={len(chunks)}"
            )
        if index.d != manifest.dimension:
            raise ValueError(
                f"FAISS index.d={index.d} does not match manifest.dimension={manifest.dimension}"
            )
        if embedder.model_name != manifest.embedding_model:
            raise ValueError(
                f"embedder.model_name={embedder.model_name!r} does not match "
                f"manifest.embedding_model={manifest.embedding_model!r}"
            )
        if embedder.dimension != manifest.dimension:
            raise ValueError(
                f"embedder.dimension={embedder.dimension} does not match "
                f"manifest.dimension={manifest.dimension}"
            )

        self._index = index
        self._chunks: tuple[Chunk, ...] = tuple(chunks)
        self._manifest = manifest
        self._embedder = embedder

    @property
    def manifest(self) -> IndexManifest:
        """The manifest this retriever's index was built with."""
        return self._manifest

    @classmethod
    def from_index_dir(
        cls,
        index_dir: str | Path,
        embedder: SentenceTransformerEmbedder | None = None,
    ) -> FaissRetriever:
        """
        Load a FaissRetriever from a directory of index artifacts.

        Args:
            index_dir: Directory containing ``index.faiss``, ``chunks.jsonl``,
                and ``manifest.json`` (see :mod:`jev_cot.retrieval.ingest`).
            embedder: Embedder to use for query-time encoding. When ``None``,
                one is built from ``manifest.embedding_model`` so ingest and
                query always share one model (research Pitfall 2).

        Returns:
            A ready-to-query :class:`FaissRetriever`.

        Raises:
            FileNotFoundError: If any of the three artifact files is missing.
        """
        import faiss

        dir_path = Path(index_dir)
        manifest_path = dir_path / MANIFEST_FILENAME
        chunks_path = dir_path / CHUNKS_FILENAME
        index_path = dir_path / INDEX_FILENAME

        for path in (manifest_path, chunks_path, index_path):
            if not path.exists():
                raise FileNotFoundError(
                    f"FAISS index artifact not found: {path.resolve()} — "
                    "build it with jev_cot.retrieval.ingest"
                )

        manifest = IndexManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

        chunks: list[Chunk] = []
        with jsonlines.open(chunks_path, mode="r") as reader:
            for obj in reader:
                chunks.append(Chunk.model_validate(obj))

        index = faiss.read_index(str(index_path))

        if embedder is None:
            embedder = SentenceTransformerEmbedder(manifest.embedding_model)

        return cls(index=index, chunks=chunks, manifest=manifest, embedder=embedder)

    def _search(self, request: RetrievalQuery) -> list[RetrievedChunk]:
        """See :meth:`RetrievalBackend._search`."""
        candidate_positions = {
            i
            for i, chunk in enumerate(self._chunks)
            if chunk.company == request.company
            and chunk.period == request.period
            and (request.document_type is None or chunk.document_type == request.document_type)
        }
        if not candidate_positions:
            return []

        query_vec = self._embedder.encode([request.query])
        # Rank the whole index exactly; production-scale indexing is a
        # ROADMAP non-goal at this phase's seed-corpus scale.
        distances, ids = self._index.search(query_vec, self._index.ntotal)

        hits: list[RetrievedChunk] = []
        for distance, chunk_id in zip(distances[0], ids[0], strict=True):
            position = int(chunk_id)
            if position < 0 or position not in candidate_positions:
                continue
            score = max(-1.0, min(1.0, 1.0 - float(distance) / 2.0))
            chunk = self._chunks[position]
            hits.append(RetrievedChunk.model_validate({**chunk.model_dump(), "score": score}))

        hits.sort(key=lambda hit: (-hit.score, hit.chunk_id))
        return hits[: request.top_k]
