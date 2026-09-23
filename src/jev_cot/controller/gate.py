"""
jev_cot.controller.gate
=========================
Shared gate protocol — both the LLM self-gate (Condition B) and JEV
(Condition C) implement this same interface so the controller loop can
call either interchangeably. This is what makes B vs C a controlled
comparison: only the object behind ``Gate`` changes.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from jev_cot.controller.actions import Action
from jev_cot.controller.state import ControllerState


class GateDecision(BaseModel):
    """A gate's decision for one controller step."""

    model_config = {"frozen": True}

    action: Action
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(description="'llm' or 'jev' — which gate produced this decision")


class Gate(Protocol):
    """Anything that can decide the next action from a ControllerState."""

    def decide(self, state: ControllerState) -> GateDecision: ...
