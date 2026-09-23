"""
jev_cot.retrieval.ingest
=========================
Ingest pipeline: read, chunk, tag, embed, and index a local document
corpus into the on-disk FAISS artifacts :class:`FaissRetriever` loads.

Also provides the ``main()`` CLI entry point that drives the pipeline from
a YAML ``ExperimentConfig`` (see :mod:`jev_cot.config`).

Usage::

    from jev_cot.retrieval.faiss_retriever import SentenceTransformerEmbedder
    from jev_cot.retrieval.ingest import build_index

    embedder = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2")
    manifest = build_index(
        "data/raw/documents",
        "data/processed/faiss_index",
        embedder,
        chunk_max_words=120,
        chunk_overlap_words=20,
        retrieval_version="faiss-v0.1",
    )

Or, as a CLI::

    python -m jev_cot.retrieval.ingest --config configs/base.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import jsonlines

from jev_cot.config import load_config
from jev_cot.logging import logger, setup_logging
from jev_cot.retrieval.base import Chunk, parse_document_id
from jev_cot.retrieval.faiss_retriever import (
    CHUNKS_FILENAME,
    INDEX_FILENAME,
    MANIFEST_FILENAME,
    IndexManifest,
    SentenceTransformerEmbedder,
)

_PARAGRAPH_SPLIT_PATTERN: Final = re.compile(r"\n\s*\n")


# ── Reading ────────────────────────────────────────────────────────────────────
def read_document(path: Path) -> str:
    """
    Read a UTF-8 seed document, dropping comment lines.

    A line is a comment when its ``lstrip()`` starts with ``#`` (used to keep
    the synthetic-data disclaimer out of the index).

    Args:
        path: Path to the ``.txt`` document.

    Returns:
        The document text with comment lines removed.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not line.lstrip().startswith("#")]
    return "\n".join(kept)


# ── Chunking ───────────────────────────────────────────────────────────────────
def chunk_text(text: str, *, max_words: int, overlap_words: int) -> list[str]:
    """
    Split *text* into paragraph-aware, word-windowed chunks.

    Paragraphs are separated by a blank line. A paragraph of at most
    *max_words* words becomes one chunk. A longer paragraph is split into
    overlapping windows of *max_words* words, advancing by
    ``max_words - overlap_words`` each step and stopping once a window
    reaches the paragraph's end (never emitting a window fully contained
    in the previous one).

    Args:
        text: The document text (paragraphs separated by a blank line).
        max_words: Max words per chunk.
        overlap_words: Words shared by consecutive windows.

    Returns:
        A list of chunk texts, one entry per emitted window.

    Raises:
        ValueError: Unless ``0 <= overlap_words < max_words``.
    """
    if not (0 <= overlap_words < max_words):
        raise ValueError(
            "overlap_words must satisfy 0 <= overlap_words < max_words, got "
            f"overlap_words={overlap_words}, max_words={max_words}"
        )
    step = max_words - overlap_words

    chunks: list[str] = []
    for raw_paragraph in _PARAGRAPH_SPLIT_PATTERN.split(text):
        paragraph = " ".join(raw_paragraph.split())
        if not paragraph:
            continue
        words = paragraph.split()
        if len(words) <= max_words:
            chunks.append(paragraph)
            continue
        start = 0
        while start < len(words):
            end = min(start + max_words, len(words))
            chunks.append(" ".join(words[start:end]))
            if end == len(words):
                break
            start += step
    return chunks


# ── Discovery ──────────────────────────────────────────────────────────────────
def discover_documents(documents_dir: str | Path) -> list[Path]:
    """
    List the ``.txt`` seed documents in *documents_dir*.

    Args:
        documents_dir: Directory to glob (non-recursive).

    Returns:
        Sorted list of ``.txt`` file paths.

    Raises:
        FileNotFoundError: If *documents_dir* does not exist.
        ValueError: If *documents_dir* contains no ``.txt`` files (research
            Pitfall 1: never silently index an empty corpus).
    """
    dir_path = Path(documents_dir)
    if not dir_path.exists():
        raise FileNotFoundError(f"Documents directory not found: {dir_path.resolve()}")
    documents = sorted(p for p in dir_path.glob("*.txt") if p.is_file())
    if not documents:
        raise ValueError(f"No .txt documents found in {dir_path.resolve()}")
    return documents


# ── Loading ────────────────────────────────────────────────────────────────────
def load_chunks(documents_dir: str | Path, *, max_words: int, overlap_words: int) -> list[Chunk]:
    """
    Discover, parse, and chunk every document in *documents_dir*.

    Source tier is tagged here, once, from each document's id (via
    :func:`parse_document_id`) — never recomputed at query time.

    Args:
        documents_dir: Directory of ``{DOCUMENT_ID}.txt`` seed documents.
        max_words: Max words per chunk.
        overlap_words: Words shared by consecutive windows.

    Returns:
        All chunks across every discovered document, in document-then-window order.

    Raises:
        FileNotFoundError: If *documents_dir* does not exist.
        ValueError: If *documents_dir* is empty, a filename doesn't match the
            document-id convention, or a document yields zero chunks.
    """
    chunks: list[Chunk] = []
    for path in discover_documents(documents_dir):
        try:
            metadata = parse_document_id(path.stem)
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc

        paragraphs = chunk_text(
            read_document(path), max_words=max_words, overlap_words=overlap_words
        )
        if not paragraphs:
            raise ValueError(f"{path}: produced zero chunks")

        for i, paragraph_text in enumerate(paragraphs):
            chunks.append(
                Chunk(
                    chunk_id=f"{metadata.document_id}::{i:03d}",
                    document_id=metadata.document_id,
                    company=metadata.company,
                    period=metadata.period,
                    document_type=metadata.document_type,
                    source_tier=metadata.source_tier,
                    text=paragraph_text,
                )
            )
    return chunks


# ── Index build ────────────────────────────────────────────────────────────────
def build_index(
    documents_dir: str | Path,
    index_dir: str | Path,
    embedder: SentenceTransformerEmbedder,
    *,
    chunk_max_words: int,
    chunk_overlap_words: int,
    retrieval_version: str,
) -> IndexManifest:
    """
    Chunk, embed, and index every document in *documents_dir* into *index_dir*.

    Args:
        documents_dir: Directory of ``{DOCUMENT_ID}.txt`` seed documents.
        index_dir: Directory to write ``index.faiss``, ``chunks.jsonl``, and
            ``manifest.json`` into (created if absent).
        embedder: The embedder to use — must be the same one query time uses.
        chunk_max_words: Max words per chunk.
        chunk_overlap_words: Words shared by consecutive windows.
        retrieval_version: Version tag recorded in the manifest.

    Returns:
        The :class:`IndexManifest` describing the index just built.

    Raises:
        FileNotFoundError: If *documents_dir* does not exist.
        ValueError: If *documents_dir* is empty or contains a malformed
            document id (raised by :func:`load_chunks`, before any artifact
            is written).
    """
    import faiss

    start = time.perf_counter()

    # Load chunks BEFORE creating index_dir, so a failure leaves no partial artifacts.
    chunks = load_chunks(
        documents_dir, max_words=chunk_max_words, overlap_words=chunk_overlap_words
    )

    vectors = embedder.encode([chunk.text for chunk in chunks])
    index = faiss.IndexFlatL2(embedder.dimension)
    index.add(vectors)

    dir_path = Path(index_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(dir_path / INDEX_FILENAME))

    with jsonlines.open(dir_path / CHUNKS_FILENAME, mode="w") as writer:
        for chunk in chunks:
            writer.write(chunk.model_dump(mode="json"))

    # Preserve discovery order (already alphabetically sorted) rather than
    # re-sorting, so the manifest reads in the same order documents were found.
    document_ids = tuple(dict.fromkeys(chunk.document_id for chunk in chunks))
    manifest = IndexManifest(
        embedding_model=embedder.model_name,
        dimension=embedder.dimension,
        num_documents=len(document_ids),
        num_chunks=len(chunks),
        chunk_max_words=chunk_max_words,
        chunk_overlap_words=chunk_overlap_words,
        retrieval_version=retrieval_version,
        document_ids=document_ids,
    )
    # No timestamp field, so rebuilds of the same corpus are byte-stable.
    (dir_path / MANIFEST_FILENAME).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    latency_ms = (time.perf_counter() - start) * 1000.0
    logger.info(
        "ingest completed",
        component="ingest",
        num_documents=manifest.num_documents,
        num_chunks=manifest.num_chunks,
        latency_ms=round(latency_ms, 3),
    )
    return manifest


# ── CLI ────────────────────────────────────────────────────────────────────────
def main(argv: Sequence[str] | None = None) -> None:
    """
    CLI entry point: build a FAISS index from a YAML-configured document corpus.

    Loads an :class:`~jev_cot.config.ExperimentConfig`, resolves
    documents_dir/index_dir (``--documents-dir``/``--index-dir`` override the
    config's ``retrieval:`` block), verifies the corpus exists and is
    non-empty *before* loading the embedding model, then builds the index.

    Args:
        argv: Command-line arguments (excluding the program name). Passed
            straight to ``argparse``; when ``None``, argparse reads
            ``sys.argv[1:]``. Exposed as a parameter so tests can invoke the
            CLI in-process instead of spawning a subprocess.

    Raises:
        SystemExit: With code 1 if the config, documents directory, or
            corpus is invalid. Prints ``Error: {message}`` to stderr first.

    Usage::

        python -m jev_cot.retrieval.ingest --config configs/base.yaml
    """
    parser = argparse.ArgumentParser(
        description="Build a FAISS retrieval index from a local document corpus."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/base.yaml",
        help="Path to the YAML experiment config (see jev_cot.config.ExperimentConfig).",
    )
    parser.add_argument(
        "--documents-dir",
        type=str,
        default=None,
        help="Directory of {DOCUMENT_ID}.txt seed documents. Overrides the config's "
        "retrieval.documents_dir when given.",
    )
    parser.add_argument(
        "--index-dir",
        type=str,
        default=None,
        help="Directory to write the FAISS index artifacts into. Overrides the config's "
        "retrieval.index_dir when given.",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs",
        help="Directory for this ingest run's log file.",
    )
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
        documents_dir = args.documents_dir or cfg.retrieval.documents_dir
        index_dir = args.index_dir or cfg.retrieval.index_dir

        # Cheap precheck before loading the embedding model (research Pitfall 1:
        # never pay for a model load just to fail on a missing/empty corpus).
        discover_documents(documents_dir)

        setup_logging(log_dir=args.log_dir, run_id="ingest")

        embedder = SentenceTransformerEmbedder(cfg.retrieval.embedding_model)
        manifest = build_index(
            documents_dir,
            index_dir,
            embedder,
            chunk_max_words=cfg.retrieval.chunk_max_words,
            chunk_overlap_words=cfg.retrieval.chunk_overlap_words,
            retrieval_version=cfg.retrieval_version,
        )
    except (FileNotFoundError, ValueError) as exc:
        # pydantic.ValidationError is a ValueError subclass, so config
        # validation failures are caught here too.
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Indexed {manifest.num_chunks} chunks from {manifest.num_documents} "
        f"documents into {index_dir}"
    )


if __name__ == "__main__":
    main()
