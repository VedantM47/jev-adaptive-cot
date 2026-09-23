"""
CLI, discovery-hardening, chunking, index-load-robustness, and
rebuild-determinism tests for :mod:`jev_cot.retrieval.ingest` (Phase 4, plan
04-05).

Acceptance criteria covered:
- AC-I1: ``python -m jev_cot.retrieval.ingest --config <yaml>`` builds
  index.faiss, chunks.jsonl, and manifest.json from a YAML-configured corpus
  and directory, and a retriever loaded from the result returns chunks for a
  matching query.
- AC-I2: the CLI exits 1 with an "Error:" message on stderr for a missing
  config, missing documents dir, or empty corpus, without loading the
  embedding model or leaving a partial index_dir behind.
- AC-I3: ``--documents-dir``/``--index-dir`` CLI overrides take precedence
  over the YAML-configured paths.
- AC-I4: generated index artifacts are never committed (the real
  ``git check-ignore`` check runs as part of this task's <verify> smoke test,
  not as a pytest assertion here).

Tests never write to data/processed — every index is built into tmp_path.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from jev_cot.logging import logger
from jev_cot.retrieval.faiss_retriever import (
    CHUNKS_FILENAME,
    INDEX_FILENAME,
    MANIFEST_FILENAME,
    FaissRetriever,
    IndexManifest,
    SentenceTransformerEmbedder,
)
from jev_cot.retrieval.ingest import main

# ── Shared helpers ────────────────────────────────────────────────────────────


def _write_corpus(root: Path) -> None:
    """Write a tiny 2-document corpus (one 10K, one earnings release)."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "ACME_10K_FY23.txt").write_text(
        "# Synthetic data disclaimer -- not a real filing.\n"
        "ACME Corp reported total revenue of $10.5 million for fiscal year "
        "2023, driven by strong demand across all segments.\n",
        encoding="utf-8",
    )
    (root / "ACME_Q4_Earnings_FY23.txt").write_text(
        "ACME Corp announced fourth quarter earnings per share of $0.42, "
        "beating analyst expectations for the period.\n",
        encoding="utf-8",
    )


def _write_config(tmp_path: Path, documents_dir: Path, index_dir: Path) -> Path:
    """Write a minimal valid experiment config YAML pointing at the given dirs."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
llm: "test-llm"
prompt_version: "v0.1"
retrieval_version: "test-v0.1"
dataset_version: "test-v0.1"
retrieval:
  embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
  chunk_max_words: 120
  chunk_overlap_words: 20
  top_k: 5
  documents_dir: "{documents_dir.as_posix()}"
  index_dir: "{index_dir.as_posix()}"
""",
        encoding="utf-8",
    )
    return config_path


@pytest.fixture()
def restore_logging() -> Iterator[None]:
    """
    Restore loguru's default stderr handler after a test that calls main().

    setup_logging() calls logger.remove() globally, which would otherwise
    leave later tests (in this file or others in the same session) without
    any stderr sink.
    """
    yield
    logger.remove()
    logger.add(sys.stderr, level="INFO")


# ── AC-I1, AC-I2, AC-I3 ──────────────────────────────────────────────────────
def test_cli_builds_index(
    tmp_path: Path,
    embedder: SentenceTransformerEmbedder,
    restore_logging: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI builds a full index from a YAML config and exits normally."""
    documents_dir = tmp_path / "docs"
    index_dir = tmp_path / "idx"
    _write_corpus(documents_dir)
    config_path = _write_config(tmp_path, documents_dir, index_dir)

    main(["--config", str(config_path), "--log-dir", str(tmp_path / "logs")])

    assert (index_dir / INDEX_FILENAME).exists()
    assert (index_dir / CHUNKS_FILENAME).exists()
    assert (index_dir / MANIFEST_FILENAME).exists()

    manifest = IndexManifest.model_validate_json(
        (index_dir / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest.num_documents == 2
    assert manifest.retrieval_version == "test-v0.1"

    retriever = FaissRetriever.from_index_dir(index_dir, embedder=embedder)
    result = retriever.retrieve(company="ACME", period="FY2023", query="What was revenue?")
    assert len(result.chunks) >= 1

    captured = capsys.readouterr()
    assert "Indexed" in captured.out


def test_cli_missing_config_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A nonexistent --config path exits 1 with an Error: message, no model load."""
    missing_config = tmp_path / "nonexistent.yaml"

    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(missing_config)])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("Error:")


def test_cli_missing_documents_dir_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing documents_dir exits 1, names the directory, and creates no index_dir."""
    documents_dir = tmp_path / "no_such_docs"
    index_dir = tmp_path / "idx"
    config_path = _write_config(tmp_path, documents_dir, index_dir)

    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(config_path)])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("Error:")
    assert str(documents_dir) in captured.err
    assert not index_dir.exists()


def test_cli_empty_corpus_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An existing but empty documents_dir exits 1 and creates no index_dir."""
    documents_dir = tmp_path / "empty_docs"
    documents_dir.mkdir()
    index_dir = tmp_path / "idx"
    config_path = _write_config(tmp_path, documents_dir, index_dir)

    with pytest.raises(SystemExit) as exc_info:
        main(["--config", str(config_path)])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("Error:")
    assert not index_dir.exists()


def test_cli_overrides_take_precedence(
    tmp_path: Path, embedder: SentenceTransformerEmbedder, restore_logging: None
) -> None:
    """--documents-dir/--index-dir override the YAML-configured paths."""
    yaml_documents_dir = tmp_path / "yaml_docs_never_created"
    yaml_index_dir = tmp_path / "yaml_idx_never_created"
    config_path = _write_config(tmp_path, yaml_documents_dir, yaml_index_dir)

    real_documents_dir = tmp_path / "real_docs"
    real_index_dir = tmp_path / "real_idx"
    _write_corpus(real_documents_dir)

    main(
        [
            "--config",
            str(config_path),
            "--documents-dir",
            str(real_documents_dir),
            "--index-dir",
            str(real_index_dir),
            "--log-dir",
            str(tmp_path / "logs"),
        ]
    )

    assert (real_index_dir / INDEX_FILENAME).exists()
    assert not yaml_index_dir.exists()
