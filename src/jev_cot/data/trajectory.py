"""
jev_cot.data.trajectory
==========================
Trajectory schema (FR-14 / Appendix B, simplified for a working v1):
one record per controller step (state, decision, confidence, latency, cost),
plus an aggregate record per trajectory. Every run's trajectories are
replayable from these JSONL files alone.
"""

from __future__ import annotations

from pathlib import Path

import jsonlines
from pydantic import BaseModel

from jev_cot.controller.actions import Action


class TrajectoryStep(BaseModel):
    model_config = {"frozen": True}

    step_index: int
    state: dict[str, object]
    action: Action
    confidence: float
    gate_source: str
    latency_ms: float
    cost_usd: float


class Trajectory(BaseModel):
    model_config = {"frozen": True}

    run_id: str
    example_id: str
    condition: str
    llm: str
    question: str
    steps: tuple[TrajectoryStep, ...]
    evidence_snippets: tuple[str, ...] = ()
    final_answer: str
    total_latency_seconds: float
    total_cost_usd: float
    total_llm_calls: int
    total_input_tokens: int
    total_output_tokens: int
    grounding_precision: float | None = None
    grounding_recall: float | None = None
    answer_score: float | None = None


def append_trajectory(trajectory: Trajectory, path: str | Path) -> None:
    """Append *trajectory* as one line to the JSONL file at *path* (created if absent)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with jsonlines.open(p, mode="a") as writer:
        writer.write(trajectory.model_dump(mode="json"))


def load_trajectories(path: str | Path) -> list[Trajectory]:
    """Load all trajectories from a JSONL file."""
    p = Path(path)
    if not p.exists():
        return []
    with jsonlines.open(p) as reader:
        return [Trajectory.model_validate(obj) for obj in reader]
