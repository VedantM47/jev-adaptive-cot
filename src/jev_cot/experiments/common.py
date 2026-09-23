"""
jev_cot.experiments.common
=============================
Shared setup helpers for the experiment runner scripts — loading the
benchmark dataset and getting a ready-to-query retriever (building the
FAISS index on first use if it doesn't exist yet).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import jsonlines

from jev_cot.config import ExperimentConfig
from jev_cot.data.schema import BenchmarkExample
from jev_cot.retrieval.faiss_retriever import FaissRetriever, SentenceTransformerEmbedder
from jev_cot.retrieval.ingest import build_index


def load_dataset(path: str | Path) -> list[BenchmarkExample]:
    """Load benchmark examples from a JSONL file."""
    with jsonlines.open(path) as reader:
        return [BenchmarkExample.model_validate(obj) for obj in reader]


def get_retriever(cfg: ExperimentConfig) -> FaissRetriever:
    """Return a ready FaissRetriever, building the index first if it's missing."""
    index_dir = Path(cfg.retrieval.index_dir)
    if not (index_dir / "manifest.json").exists():
        embedder = SentenceTransformerEmbedder(cfg.retrieval.embedding_model)
        build_index(
            cfg.retrieval.documents_dir,
            cfg.retrieval.index_dir,
            embedder,
            chunk_max_words=cfg.retrieval.chunk_max_words,
            chunk_overlap_words=cfg.retrieval.chunk_overlap_words,
            retrieval_version=cfg.retrieval_version,
        )
    return FaissRetriever.from_index_dir(index_dir)


def new_run_id(prefix: str) -> str:
    """Generate a short, unique run id: '{prefix}_{8 hex chars}'."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
