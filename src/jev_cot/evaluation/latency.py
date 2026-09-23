"""
jev_cot.evaluation.latency
=============================
Per-component latency breakdown over logged trajectories (FR-16, NFR-06).
Never aggregate-only — breaks latency down by which gate/action produced it.
"""

from __future__ import annotations

from jev_cot.controller.actions import Action
from jev_cot.data.trajectory import Trajectory


def latency_breakdown(trajectories: list[Trajectory]) -> dict[str, float]:
    """
    Break down average latency by component: gate inference, retrieval,
    tool (compute/branch), and total wall-clock.
    """
    if not trajectories:
        return {}

    n = len(trajectories)
    gate_ms = 0.0
    retrieval_ms = 0.0
    tool_ms = 0.0

    for t in trajectories:
        for step in t.steps:
            if step.gate_source in ("llm", "jev"):
                gate_ms += step.latency_ms if step.gate_source == "jev" else 0.0
            if step.action == Action.RETRIEVE:
                retrieval_ms += step.latency_ms
            elif step.action in (Action.COMPUTE, Action.BRANCH):
                tool_ms += step.latency_ms

    return {
        "avg_gate_inference_ms": gate_ms / n,
        "avg_retrieval_ms": retrieval_ms / n,
        "avg_tool_ms": tool_ms / n,
        "avg_total_wall_clock_seconds": sum(t.total_latency_seconds for t in trajectories) / n,
    }
