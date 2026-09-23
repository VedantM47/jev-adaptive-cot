"""
jev_cot.config
==============
Typed, validated experiment configuration loader.

Every experiment run must load a config through this module so that
all fields required by PRD §6.6 are present and validated before
any pipeline code executes.

Usage::

    from jev_cot.config import load_config
    cfg = load_config("configs/base.yaml")
    print(cfg.llm, cfg.random_seed)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class ToolLimitsConfig(BaseModel):
    """Hard safety caps on tool-call counts (PRD §6.4, §8)."""

    model_config = {"frozen": True}

    max_retrievals: int = Field(ge=1, default=10, description="Max retrieval calls per trajectory")
    max_branches: int = Field(ge=1, default=3, description="Max BRANCH forks per trajectory")
    max_compute_calls: int = Field(ge=1, default=5, description="Max COMPUTE calls per trajectory")


class ExperimentConfig(BaseModel):
    """
    Canonical config object for a single experiment run.

    Covers all fields mandated by PRD §6.6:
    - LLM identity + sampling params
    - Version strings for every swappable component
    - Safety limits
    - Reproducibility fields (seed, timestamp)
    - Condition identifier
    """

    model_config = {"frozen": True}

    # ── Identity ──────────────────────────────────────────────────────────────
    run_id: str | None = Field(
        default=None,
        description="Unique run identifier. Auto-generated at runtime if None.",
    )

    # ── LLM ───────────────────────────────────────────────────────────────────
    llm: str = Field(description="LLM model name, e.g. 'gemini-1.5-pro-latest'")
    temperature: float = Field(ge=0.0, le=2.0, default=0.0)
    max_tokens: int = Field(ge=1, default=4096)

    # ── Component versions (all required — PRD §6.6, §8 auditability) ─────────
    jev_version: str = Field(
        default="none",
        description="JEV checkpoint version. 'none' for Conditions A and B.",
    )
    prompt_version: str = Field(description="Version tag for all prompts used in this run")
    retrieval_version: str = Field(description="Version tag for the retrieval index/config")
    dataset_version: str = Field(description="Version tag for the benchmark dataset")

    # ── Control limits ────────────────────────────────────────────────────────
    max_steps: int = Field(ge=1, default=15, description="Max controller steps per trajectory")
    max_latency_seconds: float = Field(
        ge=0.0, default=120.0, description="Max wall-clock seconds per trajectory"
    )
    max_cost_usd: float = Field(
        ge=0.0, default=1.0, description="Max estimated USD cost per trajectory"
    )
    tool_limits: ToolLimitsConfig = Field(default_factory=ToolLimitsConfig)

    # ── Reproducibility ───────────────────────────────────────────────────────
    random_seed: int = Field(default=42)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp, auto-set at config load time.",
    )

    # ── Condition ─────────────────────────────────────────────────────────────
    condition: Literal["vanilla", "selfgate", "jevgate"] = Field(
        default="vanilla",
        description="Experimental condition. Controls which gate is used.",
    )

    # ── Fallback policy (secondary experiment — off by default) ───────────────
    enable_escalate_fallback: bool = Field(
        default=False,
        description="If True, JEV confidence < threshold triggers ESCALATE fallback.",
    )
    escalate_confidence_threshold: float = Field(
        ge=0.0,
        le=1.0,
        default=0.5,
        description="Confidence threshold below which ESCALATE is triggered.",
    )


def load_config(path: str | Path) -> ExperimentConfig:
    """
    Load and validate an experiment config from a YAML file.

    Args:
        path: Path to a YAML config file.

    Returns:
        A frozen, validated :class:`ExperimentConfig` object.

    Raises:
        FileNotFoundError: If *path* does not exist.
        pydantic.ValidationError: If the YAML content fails schema validation.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p.resolve()}")
    with p.open(encoding="utf-8") as f:
        raw: object = yaml.safe_load(f)
    return ExperimentConfig.model_validate(raw)
