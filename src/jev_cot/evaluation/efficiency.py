"""
jev_cot.evaluation.efficiency
================================
Efficiency/cost aggregation over logged trajectories (FR-16, H1/H3).
"""

from __future__ import annotations

from pathlib import Path

from jev_cot.controller.actions import Action
from jev_cot.data.trajectory import Trajectory, load_trajectories


def summarize(trajectories: list[Trajectory]) -> dict[str, float]:
    """Aggregate ops/cost/latency metrics across a list of trajectories."""
    if not trajectories:
        return {}

    n = len(trajectories)

    def count_action(t: Trajectory, action: Action) -> int:
        return sum(1 for s in t.steps if s.action == action)

    return {
        "n_trajectories": n,
        "avg_steps": sum(len(t.steps) for t in trajectories) / n,
        "avg_llm_calls": sum(t.total_llm_calls for t in trajectories) / n,
        "avg_retrievals": sum(count_action(t, Action.RETRIEVE) for t in trajectories) / n,
        "avg_compute_calls": sum(count_action(t, Action.COMPUTE) for t in trajectories) / n,
        "avg_branches": sum(count_action(t, Action.BRANCH) for t in trajectories) / n,
        "avg_input_tokens": sum(t.total_input_tokens for t in trajectories) / n,
        "avg_output_tokens": sum(t.total_output_tokens for t in trajectories) / n,
        "avg_total_tokens": (
            sum(t.total_input_tokens + t.total_output_tokens for t in trajectories) / n
        ),
        "avg_cost_usd": sum(t.total_cost_usd for t in trajectories) / n,
        "total_cost_usd": sum(t.total_cost_usd for t in trajectories),
        "avg_latency_seconds": sum(t.total_latency_seconds for t in trajectories) / n,
    }


def summarize_file(path: str | Path) -> dict[str, float]:
    """Load trajectories from *path* and summarize them."""
    return summarize(load_trajectories(path))
