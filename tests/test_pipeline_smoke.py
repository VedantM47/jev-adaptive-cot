"""
End-to-end smoke test for the full pipeline (Phases 5-19), using a fake
LLMClient so this runs offline — no GEMINI_API_KEY needed. Proves the
wiring is correct: controller loop, self-gate, JEV training/calibration,
JEV-gate, and evaluation math all actually work together.

Real Gemini calls are NOT exercised here — that needs a live API key and
is out of scope for an automated test (see README for the manual smoke
test once a key is configured).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from jev_cot.config import load_config
from jev_cot.controller.actions import Action
from jev_cot.controller.gate import GateDecision
from jev_cot.controller.loop import run_trajectory
from jev_cot.controller.state import ControllerState
from jev_cot.data.trajectory import Trajectory
from jev_cot.evaluation.calibration import expected_calibration_error
from jev_cot.evaluation.efficiency import summarize
from jev_cot.evaluation.grounding.metrics import grounding_precision, grounding_recall
from jev_cot.experiments.common import get_retriever, load_dataset
from jev_cot.models.jev.gate import JEVGate
from jev_cot.models.jev.labeling.rules import apply_rules
from jev_cot.models.jev.model import FEATURE_NAMES, JEVModel
from jev_cot.models.llm.client import LLMResponse


@dataclass
class FakeLLMClient:
    """Drop-in stand-in for LLMClient that never touches the network."""

    model_name: str = "fake-model"
    fixed_text: str = "The answer is derived from the retrieved evidence."

    def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(
            text=self.fixed_text,
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0001,
            latency_ms=1.0,
            model=self.model_name,
        )


class FakeGate:
    """A gate that always retrieves once then stops — deterministic, offline."""

    def __init__(self) -> None:
        self.last_response = None
        self._calls = 0

    def decide(self, state: ControllerState) -> GateDecision:
        self._calls += 1
        action = Action.RETRIEVE if self._calls == 1 else Action.STOP
        return GateDecision(action=action, confidence=0.9, source="fake")


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_controller_loop_runs_end_to_end(repo_root: Path) -> None:
    """The controller loop wires retrieval + a gate + synthesis without touching the network."""
    cfg = load_config(repo_root / "configs" / "base.yaml")
    retriever = get_retriever(cfg)
    examples = load_dataset(repo_root / "data" / "raw" / "sample_examples.jsonl")

    trajectory = run_trajectory(
        examples[0], cfg, retriever, FakeLLMClient(), FakeGate(), run_id="smoke_test"
    )

    assert isinstance(trajectory, Trajectory)
    assert trajectory.steps[-1].action == Action.STOP
    assert trajectory.final_answer == "The answer is derived from the retrieved evidence."
    assert trajectory.total_llm_calls >= 1


def test_jev_train_predict_calibrate_roundtrip(tmp_path: Path) -> None:
    """JEV: fit on synthetic (state, action) pairs, predict, calibrate, save/load."""
    import numpy as np

    rng = np.random.default_rng(42)
    n = 40
    X = rng.random((n, len(FEATURE_NAMES))).astype("float32")
    # has_required_evidence high -> STOP, else RETRIEVE (deterministic-ish synthetic rule)
    y = ["STOP" if row[5] > 0.5 else "RETRIEVE" for row in X]

    model = JEVModel(size="S")
    model.fit(X[:30], y[:30])
    proba = model.predict_proba(X[30:])
    assert proba.shape == (10, len(set(y[:30])))

    model.calibrate(X[30:], y[30:])
    calibrated_proba = model.predict_proba(X[30:])
    assert calibrated_proba.shape == proba.shape

    save_dir = tmp_path / "jev_test_checkpoint"
    model.save(save_dir)
    reloaded = JEVModel.load(save_dir)
    assert reloaded.num_parameters() > 0

    gate = JEVGate(reloaded)
    state = ControllerState(
        question="q",
        question_type="factual_retrieval",  # type: ignore[arg-type]
        company="MSFT",
        period="FY2023",
        evidence_count=3,
        has_required_evidence=True,
    )
    decision = gate.decide(state)
    assert decision.source == "jev"
    assert 0.0 <= decision.confidence <= 1.0


def test_labeling_rules_override_premature_stop() -> None:
    state = {"has_required_evidence": False, "evidence_count": 0, "num_steps_taken": 0}
    label, source = apply_rules(state, "STOP")
    assert label == "RETRIEVE"
    assert source == "rule"


def test_grounding_metrics_basic() -> None:
    evidence = ["Revenue increased 7% to $211.9 billion in FY2023."]
    recall = grounding_recall(["Revenue increased 7% to $211.9 billion"], evidence)
    assert recall == 1.0

    precision = grounding_precision("Revenue increased 7% to $211.9 billion in FY2023.", evidence)
    assert precision == 1.0


def test_calibration_ece_zero_for_perfect_predictions() -> None:
    import numpy as np

    confidences = np.array([1.0, 1.0, 1.0, 1.0])
    correct = np.array([1.0, 1.0, 1.0, 1.0])
    assert expected_calibration_error(confidences, correct) == pytest.approx(0.0)


def test_efficiency_summary_handles_empty_list() -> None:
    assert summarize([]) == {}


def test_rules_dataset_roundtrip(tmp_path: Path) -> None:
    """label_dataset() reads jev_examples.jsonl and writes jev_labeled.jsonl correctly."""
    from jev_cot.models.jev.labeling.rules import label_dataset

    input_path = tmp_path / "jev_examples.jsonl"
    input_path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {
                    "state": {"has_required_evidence": True, "evidence_count": 2},
                    "action": "RETRIEVE",
                },
                {
                    "state": {"has_required_evidence": False, "evidence_count": 1},
                    "action": "COMPUTE",
                },
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "jev_labeled.jsonl"
    stats = label_dataset(input_path, output_path)
    assert stats["_total"] == 2
    assert output_path.exists()


def test_self_gate_raises_on_malformed_response_no_hardcoded_fallback() -> None:
    """A malformed gate response must raise JEV-GATE-001, never silently guess an action."""
    from jev_cot.errors import GateResponseParseError
    from jev_cot.models.llm.self_gate import LLMSelfGate

    gate = LLMSelfGate(FakeLLMClient(fixed_text="not json at all"))
    state = ControllerState(
        question="q",
        question_type="factual_retrieval",
        company="MSFT",
        period="FY2023",  # type: ignore[arg-type]
    )
    with pytest.raises(GateResponseParseError) as exc_info:
        gate.decide(state)
    assert "JEV-GATE-001" in str(exc_info.value)


def test_quality_scorer_raises_on_malformed_response_no_hardcoded_fallback() -> None:
    """A malformed judge response must raise JEV-GATE-001, never silently return 0.5s."""
    from jev_cot.errors import GateResponseParseError
    from jev_cot.evaluation.quality.scorer import score_answer

    with pytest.raises(GateResponseParseError) as exc_info:
        score_answer(FakeLLMClient(fixed_text="garbage"), "q", ["claim"], "answer")
    assert "JEV-GATE-001" in str(exc_info.value)
