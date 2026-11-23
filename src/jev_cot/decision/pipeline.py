"""
jev_cot.decision.pipeline
=========================
Route decision questions to the local Jev model, then have the LLM write an
answer grounded in the returned probabilities. Non-decisions go straight to
the LLM. No silent fallback: Jev errors propagate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from jev_cot.decision.router import detect_decision, detect_decision_llm
from jev_cot.decision.types import DecisionRequest, DecisionResult


class _LLM(Protocol):
    def generate(self, prompt: str) -> Any: ...


class _Jev(Protocol):
    def decide(self, req: DecisionRequest) -> DecisionResult: ...


@dataclass(frozen=True)
class PipelineResult:
    answer: str
    routed_to_jev: bool
    decision: DecisionResult | None
    llm_response: Any


_INSTRUCTIONS = (
    "Base your recommendation on the JEV probabilities above. State each option's "
    "probability, recommend the top option unless confidence < 0.55 (then say it's close "
    "and name what would tip it), give 2-3 concrete reasons tied to the user's context, "
    "and keep it under 180 words. Do not invent different numbers."
)


def build_grounded_prompt(question: str, decision: DecisionResult) -> str:
    return f"Question: {question}\n\n{decision.to_prompt_block()}\n\n{_INSTRUCTIONS}"


def answer(
    question: str,
    client: _LLM,
    jev: _Jev,
    *,
    use_llm_router: bool = False,
) -> PipelineResult:
    req = detect_decision(question)
    if req is None and use_llm_router:
        req = detect_decision_llm(question, client)
    if req is None:
        resp = client.generate(question)
        return PipelineResult(resp.text, False, None, resp)
    decision = jev.decide(req)  # JevUnavailableError etc. propagate
    resp = client.generate(build_grounded_prompt(question, decision))
    return PipelineResult(resp.text, True, decision, resp)
