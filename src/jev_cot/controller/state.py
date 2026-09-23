"""
jev_cot.controller.state
=========================
Structured state extractor (FR-03, NFR-02).

Converts the controller's running trajectory into a typed, JSON-serializable
snapshot that both the LLM self-gate and JEV consume to decide the next
action. Raw chain-of-thought text is never included unless the caller
explicitly opts in via ``include_raw_cot`` (off by default, matching the
project's model-agnosticism constraint).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from jev_cot.controller.actions import Action
from jev_cot.data.schema import QuestionType


class StepRecord(BaseModel):
    """One completed controller step, summarized (never raw CoT)."""

    model_config = {"frozen": True}

    step_index: int
    action: Action
    summary: str = Field(description="Short, non-CoT summary of what this step produced")


class ControllerState(BaseModel):
    """
    The structured snapshot passed to a gate (LLM self-gate or JEV) to decide
    the next action. This is JEV's ONLY input — never raw reasoning text.
    """

    model_config = {"frozen": True}

    question: str
    question_type: QuestionType
    company: str
    period: str

    num_steps_taken: int = 0
    num_retrievals: int = 0
    num_computations: int = 0
    num_branches: int = 0

    evidence_count: int = 0
    has_required_evidence: bool = False
    distinct_documents_seen: int = 0

    last_action: Action | None = None
    step_history: tuple[StepRecord, ...] = ()

    elapsed_seconds: float = 0.0

    # Ablation-only field — never populated on the primary path.
    raw_cot: str | None = Field(default=None, description="Raw CoT trace; ablation-only")

    def to_feature_dict(self) -> dict[str, float]:
        """Flatten the numeric/boolean fields JEV trains on (state -> action)."""
        return {
            "num_steps_taken": float(self.num_steps_taken),
            "num_retrievals": float(self.num_retrievals),
            "num_computations": float(self.num_computations),
            "num_branches": float(self.num_branches),
            "evidence_count": float(self.evidence_count),
            "has_required_evidence": float(self.has_required_evidence),
            "distinct_documents_seen": float(self.distinct_documents_seen),
            "elapsed_seconds": float(self.elapsed_seconds),
        }


class TrajectorySoFar(BaseModel):
    """Accumulated, mutable-by-replacement record the controller loop threads through."""

    model_config = {"frozen": True}

    question: str
    question_type: QuestionType
    company: str
    period: str
    required_evidence: tuple[str, ...] = ()

    steps: tuple[StepRecord, ...] = ()
    evidence_snippets: tuple[str, ...] = ()
    documents_seen: tuple[str, ...] = ()
    start_time: float = 0.0

    def with_step(
        self,
        action: Action,
        summary: str,
        *,
        new_evidence: tuple[str, ...] = (),
        new_documents: tuple[str, ...] = (),
    ) -> TrajectorySoFar:
        """Return a new TrajectorySoFar with one more step appended (immutable-state pattern)."""
        step = StepRecord(step_index=len(self.steps), action=action, summary=summary)
        return self.model_copy(
            update={
                "steps": (*self.steps, step),
                "evidence_snippets": tuple(dict.fromkeys((*self.evidence_snippets, *new_evidence))),
                "documents_seen": tuple(dict.fromkeys((*self.documents_seen, *new_documents))),
            }
        )


def extract_state(
    trajectory: TrajectorySoFar,
    *,
    elapsed_seconds: float,
    include_raw_cot: bool = False,
    raw_cot_text: str | None = None,
) -> ControllerState:
    """
    Extract a :class:`ControllerState` snapshot from *trajectory*.

    Args:
        trajectory: The accumulated trajectory so far.
        elapsed_seconds: Wall-clock seconds since the trajectory started.
        include_raw_cot: Ablation switch — off by default (NFR-02).
        raw_cot_text: Raw CoT text, only used when include_raw_cot is True.

    Returns:
        A frozen :class:`ControllerState`.
    """
    required = set(trajectory.required_evidence)
    have = set(trajectory.evidence_snippets)
    has_required = required.issubset(have) if required else len(have) > 0

    return ControllerState(
        question=trajectory.question,
        question_type=trajectory.question_type,
        company=trajectory.company,
        period=trajectory.period,
        num_steps_taken=len(trajectory.steps),
        num_retrievals=sum(1 for s in trajectory.steps if s.action == Action.RETRIEVE),
        num_computations=sum(1 for s in trajectory.steps if s.action == Action.COMPUTE),
        num_branches=sum(1 for s in trajectory.steps if s.action == Action.BRANCH),
        evidence_count=len(trajectory.evidence_snippets),
        has_required_evidence=has_required,
        distinct_documents_seen=len(trajectory.documents_seen),
        last_action=trajectory.steps[-1].action if trajectory.steps else None,
        step_history=trajectory.steps,
        elapsed_seconds=elapsed_seconds,
        raw_cot=raw_cot_text if include_raw_cot else None,
    )
