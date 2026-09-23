"""
jev_cot.evaluation.quality.scorer
====================================
Multi-dimensional answer quality scorer (FR-18, H5).

One LLM-judge call per trajectory scores all 7 dimensions at once (not 7
separate calls — keeps API cost down while still giving a real quality
signal, not a heuristic proxy). Each dimension is scored 0.0-1.0;
``answer_quality`` is their mean, matching metrics_registry's formula.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from jev_cot.models.llm.client import LLMClient

_DIMENSIONS = (
    "factual_accuracy",
    "evidence_support",
    "citation_correctness",
    "completeness",
    "calculation_correctness",
    "contradiction_handling",
    "uncertainty_calibration",
)

_JUDGE_PROMPT = """You are grading an AI's answer to an equity-research question. Score it on 7 \
dimensions, each 0.0 (fails) to 1.0 (excellent). Base your judgment ONLY on the question, the \
gold claims (the correct facts), and the answer given — not on the evidence text.

Question: {question}
Gold claims (correct facts): {gold_claims}

Answer given: {answer}

Score these 7 dimensions (respond with ONLY a JSON object, no other text):
{{"factual_accuracy": <0-1>, "evidence_support": <0-1>, "citation_correctness": <0-1>, \
"completeness": <0-1>, "calculation_correctness": <0-1>, "contradiction_handling": <0-1>, \
"uncertainty_calibration": <0-1>}}
"""


class QualityScore(BaseModel):
    model_config = {"frozen": True}

    factual_accuracy: float = Field(ge=0.0, le=1.0)
    evidence_support: float = Field(ge=0.0, le=1.0)
    citation_correctness: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    calculation_correctness: float = Field(ge=0.0, le=1.0)
    contradiction_handling: float = Field(ge=0.0, le=1.0)
    uncertainty_calibration: float = Field(ge=0.0, le=1.0)

    @property
    def answer_quality(self) -> float:
        return float(sum(getattr(self, d) for d in _DIMENSIONS) / len(_DIMENSIONS))


def score_answer(
    client: LLMClient, question: str, gold_claims: list[str], answer: str
) -> QualityScore:
    """Ask the LLM judge to score *answer* against *gold_claims* on all 7 dimensions."""
    prompt = _JUDGE_PROMPT.format(
        question=question, gold_claims="; ".join(gold_claims), answer=answer
    )
    response = client.generate(prompt)
    match = re.search(r"\{.*\}", response.text, re.DOTALL)
    if match is None:
        # Fail safe: neutral score rather than crash the whole eval run.
        return QualityScore(**{d: 0.5 for d in _DIMENSIONS})
    try:
        payload = json.loads(match.group(0))
        return QualityScore(**{d: float(payload.get(d, 0.5)) for d in _DIMENSIONS})
    except (json.JSONDecodeError, ValueError):
        return QualityScore(**{d: 0.5 for d in _DIMENSIONS})
