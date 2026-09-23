"""
jev_cot.controller.synthesizer
=================================
STOP -> final answer, synthesized from accumulated evidence (FR-05 context).
"""

from __future__ import annotations

from jev_cot.controller.state import TrajectorySoFar
from jev_cot.models.llm.client import LLMClient, LLMResponse

_SYNTHESIS_PROMPT = """Answer the following equity-research question using ONLY the evidence below.
Cite the evidence directly where relevant. If the evidence is insufficient, say so explicitly.

Question: {question}

Evidence:
{evidence}

Answer:"""


def synthesize_answer(client: LLMClient, trajectory: TrajectorySoFar) -> LLMResponse:
    """Ask the LLM to produce a final answer from the trajectory's collected evidence."""
    evidence_block = (
        "\n".join(f"- {snippet}" for snippet in trajectory.evidence_snippets)
        or "(no evidence collected)"
    )
    prompt = _SYNTHESIS_PROMPT.format(question=trajectory.question, evidence=evidence_block)
    return client.generate(prompt)
