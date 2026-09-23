"""
jev_cot.controller.limits
===========================
Hard safety guards shared identically by Conditions B and C (FR-04, NFR-04).

Prevents pathological controller loops: too many steps, too many
retrievals/branches/compute calls, too much wall-clock time, or too much
estimated cost.
"""

from __future__ import annotations

from jev_cot.config import ExperimentConfig
from jev_cot.controller.state import ControllerState


class LimitExceededError(RuntimeError):
    """Raised when a hard safety limit is hit — the controller must STOP."""


def check_limits(
    state: ControllerState,
    cfg: ExperimentConfig,
    *,
    cumulative_cost_usd: float,
) -> None:
    """
    Raise :class:`LimitExceededError` if *state* has crossed any hard limit in *cfg*.

    Called before dispatching every action so B and C are bound by identical
    guards (this is what makes them a controlled comparison).
    """
    if state.num_steps_taken >= cfg.max_steps:
        raise LimitExceededError(f"max_steps ({cfg.max_steps}) reached")
    if state.num_retrievals >= cfg.tool_limits.max_retrievals:
        raise LimitExceededError(f"max_retrievals ({cfg.tool_limits.max_retrievals}) reached")
    if state.num_branches >= cfg.tool_limits.max_branches:
        raise LimitExceededError(f"max_branches ({cfg.tool_limits.max_branches}) reached")
    if state.num_computations >= cfg.tool_limits.max_compute_calls:
        raise LimitExceededError(f"max_compute_calls ({cfg.tool_limits.max_compute_calls}) reached")
    if state.elapsed_seconds >= cfg.max_latency_seconds:
        raise LimitExceededError(f"max_latency_seconds ({cfg.max_latency_seconds}) reached")
    if cumulative_cost_usd >= cfg.max_cost_usd:
        raise LimitExceededError(f"max_cost_usd ({cfg.max_cost_usd}) reached")
