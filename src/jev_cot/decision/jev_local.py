"""
jev_cot.decision.jev_local
===========================
Open-source local "Jev": Qwen3 served by Ollama, scoring options through
next-token logprobs over option letters, averaged across option permutations
to cancel position bias.
"""

from __future__ import annotations

import math
import string
import time
from collections.abc import Callable
from typing import Any

import requests

from jev_cot.decision.types import DecisionRequest, DecisionResult
from jev_cot.errors import JevResponseError, JevUnavailableError

_EPS = 1e-6
_MIN_OPTIONS = 2
_MAX_OPTIONS = 8


class LocalJev:
    """Score decision options with a local Ollama model's next-token logprobs."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        host: str = "http://localhost:11434",
        n_permutations: int = 3,
        timeout_s: float = 60.0,
        post: Callable[..., Any] | None = None,
        get: Callable[..., Any] | None = None,
    ) -> None:
        if n_permutations < 1:
            raise ValueError("n_permutations must be >= 1")
        self.model = model
        self.host = host.rstrip("/")
        self.n_permutations = n_permutations
        self.timeout_s = timeout_s
        self._post: Callable[..., Any] = post or requests.post
        self._get: Callable[..., Any] = get or requests.get

    def _unavailable(self, exc: Exception) -> JevUnavailableError:
        return JevUnavailableError(
            f"could not reach Ollama at {self.host} ({exc}). Start Ollama and run "
            f"`ollama pull {self.model}`."
        )

    def health_check(self) -> bool:
        """True if Ollama answers GET /api/tags."""
        try:
            resp = self._get(f"{self.host}/api/tags", timeout=self.timeout_s)
        except requests.RequestException:
            return False
        return bool(getattr(resp, "status_code", 200) == 200)

    @staticmethod
    def _prompt(req: DecisionRequest, ordered: list[str]) -> str:
        letters = string.ascii_uppercase
        opts = "\n".join(f"{letters[i]}. {o}" for i, o in enumerate(ordered))
        ctx = f"Person's context:\n{req.context}\n\n" if req.context else ""
        return (
            f"{ctx}Decision question: {req.question}\n\nOptions:\n{opts}\n\n"
            "Which option has the highest probability of being the better outcome "
            "for this person? Answer with a single letter."
        )

    def _score_once(self, prompt: str, n: int) -> list[float] | None:
        """Return normalised probs per letter index, or None if no letter seen."""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 1},
            "logprobs": True,
            "top_logprobs": 20,
        }
        try:
            resp = self._post(f"{self.host}/api/chat", json=payload, timeout=self.timeout_s)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise self._unavailable(exc) from exc
        data = resp.json()
        if not isinstance(data, dict) or not data.get("logprobs"):
            raise JevResponseError(
                "Ollama response has no 'logprobs' (need Ollama >= 0.12.11): got "
                f"{list(data) if isinstance(data, dict) else type(data)}"
            )
        letters = string.ascii_uppercase[:n]
        mass = [0.0] * n
        found = False
        for entry in data["logprobs"][0].get("top_logprobs", []):
            tok = str(entry.get("token", "")).strip().upper()
            if len(tok) == 1 and tok in letters:
                mass[letters.index(tok)] += math.exp(float(entry["logprob"]))
                found = True
        if not found:
            return None
        mass = [max(m, _EPS) for m in mass]
        total = sum(mass)
        return [m / total for m in mass]

    def decide(self, req: DecisionRequest) -> DecisionResult:
        n = len(req.options)
        if not _MIN_OPTIONS <= n <= _MAX_OPTIONS:
            raise ValueError(f"need {_MIN_OPTIONS}..{_MAX_OPTIONS} options, got {n}")
        if len(set(req.options)) != n:
            raise ValueError("options must be unique")
        start = time.perf_counter()
        acc = {o: 0.0 for o in req.options}
        used = 0
        for k in range(self.n_permutations):
            shift = k % n
            ordered = list(req.options[shift:] + req.options[:shift])
            probs = self._score_once(self._prompt(req, ordered), n)
            if probs is None:
                continue
            used += 1
            for opt, p in zip(ordered, probs, strict=True):
                acc[opt] += p
        if used == 0:
            raise JevResponseError(
                f"no option letter appeared in any sample's top logprobs (model={self.model})"
            )
        total = sum(acc.values())
        probabilities = {o: v / total for o, v in acc.items()}
        choice = max(req.options, key=lambda o: probabilities[o])
        return DecisionResult(
            options=req.options,
            probabilities=probabilities,
            choice=choice,
            confidence=probabilities[choice],
            model=self.model,
            latency_ms=(time.perf_counter() - start) * 1000.0,
            n_samples=used,
        )
