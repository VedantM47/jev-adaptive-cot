"""
jev_cot.models.jev.gate
==========================
JEV gate (Condition C) — implements the same ``Gate`` interface as the LLM
self-gate, so the controller loop can't tell the difference (FR-08, FR-12).
"""

from __future__ import annotations

from jev_cot.controller.gate import GateDecision
from jev_cot.controller.state import ControllerState
from jev_cot.models.jev.model import JEVModel


class JEVGate:
    """Implements the ``Gate`` protocol using a trained/frozen JEVModel."""

    def __init__(self, model: JEVModel) -> None:
        self._model = model
        self.last_response = None  # JEV makes no LLM call — no cost/tokens to fold in

    @classmethod
    def from_checkpoint(cls, checkpoint_dir: str) -> JEVGate:
        return cls(JEVModel.load(checkpoint_dir))

    def decide(self, state: ControllerState) -> GateDecision:
        action, confidence = self._model.predict(state)
        return GateDecision(action=action, confidence=confidence, source="jev")
