"""Shared pytest fixtures for the jev-cot test suite."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from jev_cot.retrieval.faiss_retriever import SentenceTransformerEmbedder


@pytest.fixture(scope="session")
def base_yaml() -> Path:
    """Absolute path to the base experiment config, resolved relative to repo root."""
    root = Path(__file__).parent.parent
    p = root / "configs" / "base.yaml"
    assert p.exists(), f"configs/base.yaml not found at {p}"
    return p


@pytest.fixture(scope="session")
def embedder() -> SentenceTransformerEmbedder:
    """
    Session-scoped embedder shared by all retrieval tests.

    Loads the model named by RetrievalConfig().embedding_model once per test
    session (the first load downloads the model from huggingface.co if it is
    not already cached locally).
    """
    from jev_cot.config import RetrievalConfig
    from jev_cot.retrieval.faiss_retriever import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder(RetrievalConfig().embedding_model)
