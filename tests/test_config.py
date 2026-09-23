"""
Tests for jev_cot.config — config loading, validation, and immutability.

Acceptance criteria covered:
  AC-1  Loading a valid YAML → typed ExperimentConfig object.
  AC-2  Missing required field → pydantic ValidationError (loud failure).
  AC-3  Invalid field value → pydantic ValidationError.
  AC-4  Non-existent file → FileNotFoundError.
  AC-5  base.yaml round-trip: all key fields match expected values.
  AC-6  tool_limits defaults are populated correctly.
  AC-7  Config object is immutable (frozen pydantic model).
  AC-8  Condition enum: only valid literals accepted.
  AC-9  jev_version defaults to "none" when omitted.
  AC-10 Timestamp is auto-populated when not specified in YAML.
  AC-11 retrieval block loads typed.
  AC-12 retrieval defaults when omitted.
  AC-13 invalid retrieval values raise.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from jev_cot.config import ExperimentConfig, RetrievalConfig, ToolLimitsConfig, load_config

# ── Helpers ───────────────────────────────────────────────────────────────────


def _minimal_yaml(tmp_path: Path, extra: str = "") -> Path:
    """Write a YAML with all required fields + optional *extra* lines."""
    content = (
        "llm: gemini-1.5-pro-latest\n"
        "prompt_version: v1\n"
        "retrieval_version: v1\n"
        "dataset_version: v1\n" + extra
    )
    p = tmp_path / "cfg.yaml"
    p.write_text(content, encoding="utf-8")
    return p


# ── Test suite ────────────────────────────────────────────────────────────────


class TestLoadConfig:
    # AC-1, AC-5 ──────────────────────────────────────────────────────────────
    def test_valid_base_yaml(self, base_yaml: Path) -> None:
        """Loading configs/base.yaml returns a correctly typed object."""
        cfg = load_config(base_yaml)
        assert isinstance(cfg, ExperimentConfig)
        assert cfg.llm == "gemini-1.5-pro-latest"
        assert cfg.condition == "vanilla"
        assert cfg.random_seed == 42
        assert cfg.temperature == 0.0
        assert cfg.max_tokens == 4096
        assert cfg.prompt_version == "v0.1"
        assert cfg.jev_version == "none"

    # AC-2 ────────────────────────────────────────────────────────────────────
    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        """A YAML missing a required field raises ValidationError."""
        bad = tmp_path / "bad.yaml"
        bad.write_text("temperature: 0.0\n", encoding="utf-8")  # missing llm, versions
        with pytest.raises(ValidationError) as exc_info:
            load_config(bad)
        # Confirm the error message mentions the missing field
        assert "llm" in str(exc_info.value) or "prompt_version" in str(exc_info.value)

    # AC-3 ────────────────────────────────────────────────────────────────────
    def test_temperature_out_of_range_raises(self, tmp_path: Path) -> None:
        """temperature > 2.0 raises ValidationError."""
        p = _minimal_yaml(tmp_path, extra="temperature: 5.0\n")
        with pytest.raises(ValidationError):
            load_config(p)

    def test_negative_max_steps_raises(self, tmp_path: Path) -> None:
        """max_steps < 1 raises ValidationError."""
        p = _minimal_yaml(tmp_path, extra="max_steps: 0\n")
        with pytest.raises(ValidationError):
            load_config(p)

    def test_invalid_condition_raises(self, tmp_path: Path) -> None:
        """An unknown condition literal raises ValidationError."""
        p = _minimal_yaml(tmp_path, extra="condition: oracle\n")
        with pytest.raises(ValidationError):
            load_config(p)

    # AC-4 ────────────────────────────────────────────────────────────────────
    def test_file_not_found_raises(self) -> None:
        """A non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config("nonexistent/path/to/config.yaml")

    # AC-6 ────────────────────────────────────────────────────────────────────
    def test_tool_limits_defaults(self, base_yaml: Path) -> None:
        """tool_limits defaults match the spec values."""
        cfg = load_config(base_yaml)
        assert isinstance(cfg.tool_limits, ToolLimitsConfig)
        assert cfg.tool_limits.max_retrievals == 10
        assert cfg.tool_limits.max_branches == 3
        assert cfg.tool_limits.max_compute_calls == 5

    def test_tool_limits_overridable(self, tmp_path: Path) -> None:
        """tool_limits values can be overridden in YAML."""
        extra = "tool_limits:\n  max_retrievals: 3\n  max_branches: 1\n  max_compute_calls: 2\n"
        p = _minimal_yaml(tmp_path, extra=extra)
        cfg = load_config(p)
        assert cfg.tool_limits.max_retrievals == 3
        assert cfg.tool_limits.max_branches == 1

    # AC-7 ────────────────────────────────────────────────────────────────────
    def test_config_is_immutable(self, base_yaml: Path) -> None:
        """Frozen pydantic model — mutation raises an exception."""
        cfg = load_config(base_yaml)
        with pytest.raises(Exception):
            cfg.llm = "something-else"  # type: ignore[misc]

    # AC-8 ────────────────────────────────────────────────────────────────────
    def test_valid_conditions_accepted(self, tmp_path: Path) -> None:
        """All three valid condition literals are accepted."""
        for cond in ("vanilla", "selfgate", "jevgate"):
            p = _minimal_yaml(tmp_path, extra=f"condition: {cond}\n")
            cfg = load_config(p)
            assert cfg.condition == cond

    # AC-9 ────────────────────────────────────────────────────────────────────
    def test_jev_version_defaults_to_none(self, tmp_path: Path) -> None:
        """jev_version defaults to 'none' when omitted from YAML."""
        p = _minimal_yaml(tmp_path)
        cfg = load_config(p)
        assert cfg.jev_version == "none"

    # AC-10 ───────────────────────────────────────────────────────────────────
    def test_timestamp_auto_populated(self, tmp_path: Path) -> None:
        """timestamp is set automatically even when absent from YAML."""
        p = _minimal_yaml(tmp_path)
        cfg = load_config(p)
        assert cfg.timestamp  # non-empty
        # Should be parseable as ISO-8601
        from datetime import datetime

        datetime.fromisoformat(cfg.timestamp)  # raises if malformed


class TestRetrievalConfig:
    # AC-11 retrieval block ───────────────────────────────────────────────────
    def test_base_yaml_retrieval_block(self, base_yaml: Path) -> None:
        """configs/base.yaml's retrieval block loads with the documented defaults."""
        cfg = load_config(base_yaml)
        assert cfg.retrieval.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert cfg.retrieval.chunk_max_words == 120
        assert cfg.retrieval.chunk_overlap_words == 20
        assert cfg.retrieval.top_k == 5
        assert cfg.retrieval.documents_dir == "data/raw/documents"
        assert cfg.retrieval.index_dir == "data/processed/faiss_index"

    # AC-12 retrieval defaults when omitted ──────────────────────────────────
    def test_retrieval_defaults_when_omitted(self, tmp_path: Path) -> None:
        """A YAML that omits the retrieval block still loads with RetrievalConfig defaults."""
        p = _minimal_yaml(tmp_path)
        cfg = load_config(p)
        assert cfg.retrieval == RetrievalConfig()

    # AC-13 invalid retrieval values raise ───────────────────────────────────
    def test_overlap_not_smaller_than_window_raises(self, tmp_path: Path) -> None:
        """chunk_overlap_words >= chunk_max_words raises ValidationError."""
        extra = "retrieval:\n  chunk_max_words: 50\n  chunk_overlap_words: 50\n"
        p = _minimal_yaml(tmp_path, extra=extra)
        with pytest.raises(ValidationError):
            load_config(p)

    @pytest.mark.parametrize("top_k", [0, 101])
    def test_top_k_out_of_range_raises(self, tmp_path: Path, top_k: int) -> None:
        """top_k outside 1..100 raises ValidationError."""
        extra = f"retrieval:\n  top_k: {top_k}\n"
        p = _minimal_yaml(tmp_path, extra=extra)
        with pytest.raises(ValidationError):
            load_config(p)

    def test_empty_embedding_model_raises(self, tmp_path: Path) -> None:
        """An empty embedding_model raises ValidationError."""
        extra = 'retrieval:\n  embedding_model: ""\n'
        p = _minimal_yaml(tmp_path, extra=extra)
        with pytest.raises(ValidationError):
            load_config(p)

    def test_retrieval_config_is_frozen(self, base_yaml: Path) -> None:
        """RetrievalConfig is frozen — mutation raises an exception."""
        cfg = load_config(base_yaml)
        with pytest.raises(Exception):
            cfg.retrieval.top_k = 99  # type: ignore[misc]
