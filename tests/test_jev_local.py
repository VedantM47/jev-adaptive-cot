"""Mocked tests for the local Jev (no Ollama needed)."""

from __future__ import annotations

import math
from typing import Any

import pytest
import requests

from jev_cot.decision.jev_local import LocalJev
from jev_cot.decision.types import DecisionRequest, DecisionResult
from jev_cot.errors import JevResponseError, JevUnavailableError
from jev_cot.models.llm.client import LLMClient


class FakeResp:
    def __init__(self, data: dict[str, Any]) -> None:
        self._d = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._d


def _lp(probs: dict[str, float]) -> dict[str, Any]:
    return {
        "logprobs": [
            {"top_logprobs": [{"token": t, "logprob": math.log(p)} for t, p in probs.items()]}
        ]
    }


REQ = DecisionRequest("Which career?", ("Data science", "Product management"))


def test_probabilities_sum_to_one() -> None:
    jev = LocalJev(post=lambda *a, **k: FakeResp(_lp({"A": 0.6, " B": 0.3})))
    res = jev.decide(REQ)
    assert sum(res.probabilities.values()) == pytest.approx(1.0)
    assert res.n_samples == 3
    assert res.choice == max(res.probabilities, key=lambda o: res.probabilities[o])


def test_permutation_averaging_removes_position_bias() -> None:
    # Model always prefers letter A regardless of content: pure position bias.
    jev = LocalJev(n_permutations=2, post=lambda *a, **k: FakeResp(_lp({"A": 0.8, "B": 0.2})))
    res = jev.decide(REQ)
    assert res.probabilities["Data science"] == pytest.approx(0.5)
    assert res.probabilities["Product management"] == pytest.approx(0.5)


def test_tracks_real_preference_across_orderings() -> None:
    def post(url: str, json: dict[str, Any], **_: Any) -> FakeResp:
        prompt = json["messages"][0]["content"]
        a_is_ds = "A. Data science" in prompt
        return FakeResp(_lp({"A": 0.9, "B": 0.1} if a_is_ds else {"A": 0.1, "B": 0.9}))

    res = LocalJev(n_permutations=2, post=post).decide(REQ)
    assert res.choice == "Data science"
    assert res.confidence == pytest.approx(0.9)


def test_missing_logprobs_raises() -> None:
    jev = LocalJev(post=lambda *a, **k: FakeResp({"message": {"content": "A"}}))
    with pytest.raises(JevResponseError):
        jev.decide(REQ)


def test_no_option_letter_raises() -> None:
    jev = LocalJev(post=lambda *a, **k: FakeResp(_lp({"Hello": 0.9})))
    with pytest.raises(JevResponseError):
        jev.decide(REQ)


def test_connection_error_raises_unavailable() -> None:
    def post(*a: Any, **k: Any) -> FakeResp:
        raise requests.ConnectionError("refused")

    with pytest.raises(JevUnavailableError, match="ollama pull"):
        LocalJev(post=post).decide(REQ)


@pytest.mark.parametrize("n", [0, 1, 9])
def test_option_count_validation(n: int) -> None:
    jev = LocalJev(post=lambda *a, **k: FakeResp(_lp({"A": 1.0})))
    with pytest.raises(ValueError):
        jev.decide(DecisionRequest("q", tuple(f"o{i}" for i in range(n))))


def test_health_check() -> None:
    ok = LocalJev(get=lambda *a, **k: FakeResp({}))
    assert ok.health_check() is True

    def boom(*a: Any, **k: Any) -> FakeResp:
        raise requests.ConnectionError("x")

    assert LocalJev(get=boom).health_check() is False


def test_to_prompt_block_format() -> None:
    res = DecisionResult(
        options=("Data science", "Product management"),
        probabilities={"Data science": 0.642, "Product management": 0.358},
        choice="Data science",
        confidence=0.642,
        model="qwen3:8b",
        latency_ms=1.0,
        n_samples=3,
    )
    assert res.to_prompt_block() == (
        "JEV DECISION (model=qwen3:8b, 3 samples)\n"
        "- Data science: 64.2%\n- Product management: 35.8%\n"
        "Top: Data science (confidence 0.64)"
    )


def test_ollama_client_path(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], **_: Any) -> FakeResp:
        seen["url"], seen["json"] = url, json
        return FakeResp({"message": {"content": "hi"}, "prompt_eval_count": 7, "eval_count": 2})

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setenv("OLLAMA_HOST", "http://h:1")
    out = LLMClient("ollama/qwen3:8b", temperature=0.1, max_tokens=50).generate("yo")
    assert seen["url"] == "http://h:1/api/chat"
    assert seen["json"]["model"] == "qwen3:8b"
    assert seen["json"]["think"] is False
    assert seen["json"]["options"] == {"temperature": 0.1, "num_predict": 50}
    assert (out.text, out.input_tokens, out.output_tokens, out.cost_usd) == ("hi", 7, 2, 0.0)
