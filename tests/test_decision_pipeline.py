"""Tests for the decision router and pipeline (fakes only; no Ollama)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jev_cot.config import load_config
from jev_cot.decision.pipeline import answer
from jev_cot.decision.router import detect_decision, detect_decision_llm
from jev_cot.decision.types import DecisionRequest, DecisionResult
from jev_cot.errors import GateResponseParseError, JevUnavailableError

BASE_YAML = Path(__file__).resolve().parent.parent / "configs" / "base.yaml"


@pytest.mark.parametrize(
    ("question", "options"),
    [
        ("Should I choose data science or product management?",
         ("data science", "product management")),
        ("Should I pursue an MBA vs a master's in CS?", ("MBA", "master's in CS")),
        ("Should I choose the backend track or the ML track?", ("backend", "ML")),
        ("Python vs Rust?", ("Python", "Rust")),
        ("Which is better: React, Vue, or Svelte?", ("React", "Vue", "Svelte")),
        ("Help me decide between Paris and Berlin.", ("Paris", "Berlin")),
        ("Coffee or tea?", ("Coffee", "tea")),
        ("Should I go with AWS or GCP for my startup?", ("AWS", "GCP")),
    ],
)
def test_router_detects(question: str, options: tuple[str, ...]) -> None:
    req = detect_decision(question)
    assert req is not None
    assert req.options == options


def test_router_extracts_context() -> None:
    q = "I'm a CS student who likes math. Should I choose data science or product management?"
    req = detect_decision(q)
    assert req is not None
    assert req.options == ("data science", "product management")
    assert req.context == "I'm a CS student who likes math."


@pytest.mark.parametrize(
    "q", ["What is the capital of France?", "Explain how transformers work.", "", "Should I sleep?"]
)
def test_router_rejects_non_decisions(q: str) -> None:
    assert detect_decision(q) is None


class FakeResp:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeClient:
    def __init__(self, text: str = "ok") -> None:
        self.prompts: list[str] = []
        self.text = text

    def generate(self, prompt: str) -> FakeResp:
        self.prompts.append(prompt)
        return FakeResp(self.text)


class FakeJev:
    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def decide(self, req: DecisionRequest) -> DecisionResult:
        self.calls += 1
        if self.fail:
            raise JevUnavailableError("ollama down")
        n = len(req.options)
        probs = {o: (0.7 if i == 0 else 0.3 / (n - 1)) for i, o in enumerate(req.options)}
        return DecisionResult(
            options=req.options,
            probabilities=probs,
            choice=req.options[0],
            confidence=0.7,
            model="fake",
            latency_ms=1.0,
            n_samples=3,
        )


def test_decision_is_grounded() -> None:
    client, jev = FakeClient("final"), FakeJev()
    res = answer("Should I choose data science or product management?", client, jev)
    assert res.routed_to_jev and res.decision is not None
    assert res.answer == "final"
    assert jev.calls == 1 and len(client.prompts) == 1
    prompt = client.prompts[0]
    assert res.decision.to_prompt_block() in prompt
    assert "0.7" in prompt or "70" in prompt
    assert "Do not invent different numbers" in prompt


def test_non_decision_skips_jev() -> None:
    client, jev = FakeClient(), FakeJev()
    res = answer("What is the capital of France?", client, jev)
    assert not res.routed_to_jev and res.decision is None
    assert jev.calls == 0
    assert client.prompts == ["What is the capital of France?"]


def test_jev_unavailable_propagates() -> None:
    client = FakeClient()
    with pytest.raises(JevUnavailableError):
        answer("Coffee or tea?", client, FakeJev(fail=True))
    assert client.prompts == []


def test_llm_router_only_when_enabled() -> None:
    q = "Is it wiser to rent, or buy a home near the office"  # no cue, no '?'
    assert detect_decision(q) is None
    client = FakeClient('{"is_decision": true, "options": ["rent", "buy"]}')
    jev = FakeJev()
    off = answer(q, client, jev)
    assert not off.routed_to_jev and jev.calls == 0
    on = answer(q, client, jev, use_llm_router=True)
    assert on.routed_to_jev and on.decision is not None
    assert on.decision.options == ("rent", "buy")


def test_llm_router_bad_json_raises() -> None:
    with pytest.raises(GateResponseParseError):
        detect_decision_llm("x", FakeClient("no json"))
    assert detect_decision_llm("x", FakeClient('{"is_decision": false}')) is None


def test_base_yaml_has_decision_block() -> None:
    cfg = load_config(BASE_YAML)
    assert cfg.decision.jev_model == "qwen3:8b"
    assert cfg.decision.n_permutations == 3
    assert cfg.decision.use_llm_router is False

