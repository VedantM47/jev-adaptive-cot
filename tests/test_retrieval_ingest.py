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
from jev_cot.retrieval.ingest import (
    chunk_text,
    discover_documents,
    load_chunks,
    main,
    read_document,
)

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


# AC-H1 discovery / AC-H2 chunking ──────────────────────────────────────────────
def test_discover_rejects_symlink(tmp_path: Path) -> None:
    """A *.txt symlink inside documents_dir, even to a file outside it, is refused."""
    documents_dir = tmp_path / "docs"
    documents_dir.mkdir()
    outside_target = tmp_path / "outside.txt"
    outside_target.write_text("ACME Corp reported revenue growth.\n", encoding="utf-8")
    link_path = documents_dir / "ACME_10K_FY23.txt"

    try:
        link_path.symlink_to(outside_target)
    except OSError:
        pytest.skip("os.symlink not permitted in this environment (e.g. Windows without privilege)")

    with pytest.raises(ValueError, match="symlink"):
        discover_documents(documents_dir)


def test_discover_ignores_non_txt_and_subdirectories(tmp_path: Path) -> None:
    """Non-.txt files and files in subdirectories are excluded; results are sorted."""
    documents_dir = tmp_path / "docs"
    documents_dir.mkdir()
    (documents_dir / "README.md").write_text("not a document", encoding="utf-8")
    sub = documents_dir / "sub"
    sub.mkdir()
    (sub / "ACME_10K_FY23.txt").write_text("nested, should be ignored", encoding="utf-8")
    (documents_dir / "ZEBRA_10K_FY23.txt").write_text("zebra doc", encoding="utf-8")
    (documents_dir / "ACME_10K_FY23.txt").write_text("acme doc", encoding="utf-8")

    found = discover_documents(documents_dir)

    assert found == sorted(found)
    assert [p.name for p in found] == ["ACME_10K_FY23.txt", "ZEBRA_10K_FY23.txt"]


def test_bad_filename_error_names_the_file(tmp_path: Path) -> None:
    """A filename that doesn't match the document-id convention names itself in the error."""
    documents_dir = tmp_path / "docs"
    documents_dir.mkdir()
    (documents_dir / "notes.txt").write_text("some notes", encoding="utf-8")

    with pytest.raises(ValueError, match="notes.txt"):
        load_chunks(documents_dir, max_words=120, overlap_words=20)


def test_comment_only_document_rejected(tmp_path: Path) -> None:
    """A document containing only comment lines yields zero chunks -> ValueError."""
    documents_dir = tmp_path / "docs"
    documents_dir.mkdir()
    (documents_dir / "ACME_10K_FY23.txt").write_text(
        "# just a disclaimer\n# nothing else here\n", encoding="utf-8"
    )

    with pytest.raises(ValueError):
        load_chunks(documents_dir, max_words=120, overlap_words=20)


def test_chunk_text_short_paragraphs() -> None:
    """Three short one-line paragraphs become exactly 3 chunks, whitespace collapsed."""
    text = "para   one.\n\npara two.\n\npara  three.\n"

    chunks = chunk_text(text, max_words=120, overlap_words=20)

    assert chunks == ["para one.", "para two.", "para three."]


def test_chunk_text_windows_long_paragraph() -> None:
    """A 250-word paragraph windows into 3 chunks of [0:120], [100:220], [200:250]."""
    words = [f"w{i}" for i in range(250)]
    text = " ".join(words)

    chunks = chunk_text(text, max_words=120, overlap_words=20)

    assert len(chunks) == 3
    assert chunks[0] == " ".join(words[0:120])
    assert chunks[1] == " ".join(words[100:220])
    assert chunks[2] == " ".join(words[200:250])
    for chunk in chunks:
        assert len(chunk.split()) <= 120
    # Consecutive chunks share exactly the last/first 20 words of the window step.
    assert chunks[0].split()[-20:] == chunks[1].split()[:20]
    assert chunks[1].split()[-20:] == chunks[2].split()[:20]


def test_chunk_text_exact_window() -> None:
    """A paragraph of exactly max_words words becomes a single chunk."""
    words = [f"w{i}" for i in range(120)]
    text = " ".join(words)

    chunks = chunk_text(text, max_words=120, overlap_words=20)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty_and_invalid() -> None:
    """Empty/whitespace-only text yields no chunks; overlap >= max_words is rejected."""
    assert chunk_text("", max_words=120, overlap_words=20) == []
    assert chunk_text("   \n\n  ", max_words=120, overlap_words=20) == []

    with pytest.raises(ValueError):
        chunk_text("some words here", max_words=10, overlap_words=10)


def test_read_document_skips_comment_lines(tmp_path: Path) -> None:
    """Lines starting with '#' (after lstrip) are absent from the returned text."""
    path = tmp_path / "ACME_10K_FY23.txt"
    path.write_text(
        "# synthetic data disclaimer\nReal paragraph text.\n  # indented comment\nMore text.\n",
        encoding="utf-8",
    )

    text = read_document(path)

    assert "#" not in text
    assert "Real paragraph text." in text
    assert "More text." in text
