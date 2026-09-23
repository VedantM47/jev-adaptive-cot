"""Shared pytest fixtures for the jev-cot test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def base_yaml() -> Path:
    """Absolute path to the base experiment config, resolved relative to repo root."""
    root = Path(__file__).parent.parent
    p = root / "configs" / "base.yaml"
    assert p.exists(), f"configs/base.yaml not found at {p}"
    return p
