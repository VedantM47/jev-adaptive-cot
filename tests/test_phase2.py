"""
Tests for Phase 2 deliverables: Action enum, config presets, and metrics registry.
"""

from pathlib import Path
from jev_cot.controller.actions import Action
from jev_cot.config import load_config
from jev_cot.evaluation.metrics_registry import METRICS


def test_action_enum():
    """Verify that all 6 actions are present in the Action enum."""
    actions = [a.value for a in Action]
    assert "CONTINUE" in actions
    assert "RETRIEVE" in actions
    assert "COMPUTE" in actions
    assert "BRANCH" in actions
    assert "STOP" in actions
    assert "ESCALATE" in actions
    assert len(actions) == 6


def test_config_presets():
    """Verify that condition presets load correctly."""
    root = Path(__file__).parent.parent

    vanilla_cfg = load_config(root / "configs" / "conditions" / "vanilla.yaml")
    assert vanilla_cfg.condition == "vanilla"

    selfgate_cfg = load_config(root / "configs" / "conditions" / "selfgate.yaml")
    assert selfgate_cfg.condition == "selfgate"

    jevgate_cfg = load_config(root / "configs" / "conditions" / "jevgate.yaml")
    assert jevgate_cfg.condition == "jevgate"
    assert jevgate_cfg.jev_version == "jev_frozen_v1"


def test_metrics_registry():
    """Verify that all H1-H6 metrics are stubbed in the registry."""
    expected_metrics = [
        "ops_saved",
        "latency_reduction",
        "cost_ratio",
        "grounding_precision",
        "grounding_recall",
        "answer_quality",
        "ece",
        "brier_score",
    ]
    for m in expected_metrics:
        assert m in METRICS
        assert METRICS[m].name == m
