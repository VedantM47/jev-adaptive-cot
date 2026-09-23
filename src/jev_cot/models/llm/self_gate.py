"""
jev_cot.models.llm.self_gate
==============================
LLM self-gate (Condition B): prompts the LLM for a structured next-action
decision + confidence, parses the JSON response.
"""

from __future__ import annotations

import json
import re

from jev_cot.controller.actions import Action
from jev_cot.controller.gate import GateDecision
from jev_cot.controller.state import ControllerState
from jev_cot.errors import GateResponseParseError
from jev_cot.models.llm.client import LLMClient, LLMResponse

_PROMPT_TEMPLATE = """You are the control-flow gate for a financial research assistant.
Given the current state of a reasoning trajectory, decide the SINGLE best next action.

Valid actions: CONTINUE, RETRIEVE, COMPUTE, BRANCH, STOP, ESCALATE
- CONTINUE: keep reasoning with current evidence, no new tool call needed
- RETRIEVE: fetch more evidence from the documents
- COMPUTE: run a financial calculation (e.g. YoY %, CAGR) on numbers already retrieved
- BRANCH: explore a second angle on the question in parallel
- STOP: you have enough evidence to answer definitively, finish now
- ESCALATE: you are stuck or uncertain, hand off to a fallback

Question: {question}
Question type: {question_type}
Steps taken so far: {num_steps}
Retrievals so far: {num_retrievals}
Evidence snippets collected: {evidence_count}
Has all required evidence (heuristic): {has_required_evidence}
Last action taken: {last_action}

Respond with ONLY a JSON object, no other text:
{{"action": "<ONE_OF_THE_SIX_ACTIONS>", "confidence": <float 0.0-1.0>}}
"""


def _build_prompt(state: ControllerState) -> str:
    return _PROMPT_TEMPLATE.format(
        question=state.question,
        question_type=state.question_type.value,
        num_steps=state.num_steps_taken,
        num_retrievals=state.num_retrievals,
        evidence_count=state.evidence_count,
        has_required_evidence=state.has_required_evidence,
        last_action=state.last_action.value if state.last_action else "none",
    )


def _parse_response(text: str) -> tuple[Action, float]:
    """
    Parse the gate's JSON response, tolerating markdown code fences.

    Raises:
        GateResponseParseError: (JEV-GATE-001) if the response has no JSON
            object, an invalid action name, or a non-numeric confidence.
            Never silently substituted with a guessed action — a malformed
            gate response is a real problem that should stop the run, not
            be masked by a plausible-looking fake decision.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise GateResponseParseError(
            f"LLM self-gate response contained no JSON object. Raw response: {text!r}"
        )
    try:
        payload = json.loads(match.group(0))
        action = Action(str(payload["action"]).upper())
        confidence = float(payload.get("confidence", 0.5))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise GateResponseParseError(
            f"LLM self-gate response could not be parsed as a valid action/confidence "
            f"pair: {exc}. Raw response: {text!r}"
        ) from exc
    confidence = max(0.0, min(1.0, confidence))
    return action, confidence


class LLMSelfGate:
    """Implements the ``Gate`` protocol by asking the LLM directly."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client
        self.last_response: LLMResponse | None = None

    def decide(self, state: ControllerState) -> GateDecision:
        """
        Raises:
            GateResponseParseError: (JEV-GATE-001) if the LLM's response can't
                be parsed. Propagates — no hardcoded fallback action.
        """
        prompt = _build_prompt(state)
        response = self._client.generate(prompt)
        self.last_response = response
        action, confidence = _parse_response(response.text)
        return GateDecision(action=action, confidence=confidence, source="llm")
