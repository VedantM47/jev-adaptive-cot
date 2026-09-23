"""
jev_cot.analysis.error_taxonomy
==================================
Classify every trajectory into exactly one error bucket (FR-23), plus a
cross-tab flagging "efficiency win but grounding loss" cases — the
interesting failure mode this whole project exists to catch.
"""

from __future__ import annotations

from enum import StrEnum

from jev_cot.data.trajectory import Trajectory

_HARD_STEP_CEILING = 50


class ErrorType(StrEnum):
    NO_ERROR = "no_error"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    LOW_GROUNDING = "low_grounding"
    LOW_ANSWER_QUALITY = "low_answer_quality"
    LOOP_LIMIT_HIT = "loop_limit_hit"
    NO_EVIDENCE_RETRIEVED = "no_evidence_retrieved"


def classify(trajectory: Trajectory) -> ErrorType:
    """Assign *trajectory* to exactly one error bucket."""
    if len(trajectory.steps) >= _HARD_STEP_CEILING:
        return ErrorType.LOOP_LIMIT_HIT
    if not trajectory.evidence_snippets:
        return ErrorType.NO_EVIDENCE_RETRIEVED
    if trajectory.grounding_recall is not None and trajectory.grounding_recall < 0.5:
        return ErrorType.INSUFFICIENT_EVIDENCE
    if trajectory.grounding_precision is not None and trajectory.grounding_precision < 0.5:
        return ErrorType.LOW_GROUNDING
    if trajectory.answer_score is not None and trajectory.answer_score < 0.5:
        return ErrorType.LOW_ANSWER_QUALITY
    return ErrorType.NO_ERROR


def classify_all(trajectories: list[Trajectory]) -> dict[str, ErrorType]:
    """Return {example_id: ErrorType} for every trajectory."""
    return {t.example_id: classify(t) for t in trajectories}


def efficiency_win_grounding_loss(
    efficient: list[Trajectory], baseline: list[Trajectory]
) -> list[str]:
    """
    Example ids where *efficient* used fewer steps than *baseline* but scored
    lower grounding recall — the exact failure mode "efficiency win but
    grounding loss" this project's whole measurement design exists to catch.
    """
    baseline_by_id = {t.example_id: t for t in baseline}
    flagged: list[str] = []
    for t in efficient:
        base = baseline_by_id.get(t.example_id)
        if base is None:
            continue
        fewer_steps = len(t.steps) < len(base.steps)
        lower_grounding = (t.grounding_recall or 0.0) < (base.grounding_recall or 0.0)
        if fewer_steps and lower_grounding:
            flagged.append(t.example_id)
    return flagged
