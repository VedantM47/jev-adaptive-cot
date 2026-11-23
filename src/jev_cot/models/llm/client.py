"""
jev_cot.models.llm.client
==========================
Thin wrapper around the Gemini API. Tracks tokens/cost/latency per call
and reads GEMINI_API_KEY from the environment (via .env / python-dotenv).

Usage::

    from jev_cot.models.llm.client import LLMClient

    client = LLMClient(model="gemini-flash-latest", temperature=0.0, max_tokens=1024)
    response = client.generate("What is 2+2?")
    print(response.text, response.cost_usd, response.latency_ms)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from jev_cot.errors import ExternalAPIError, MissingAPIKeyError

load_dotenv()

# Rough, non-billing-accurate per-1M-token rates (USD) — good enough to estimate
# relative cost between conditions, which is what this project actually needs.
_RATES_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "gemini-pro-latest": (1.25, 5.00),
    "gemini-flash-latest": (0.075, 0.30),
    "gemini-3.5-flash": (0.075, 0.30),
    "gemini-3.1-pro-preview": (1.25, 5.00),
}
_DEFAULT_RATE = (0.50, 1.50)
_OLLAMA_PREFIX = "ollama/"


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    model: str


class LLMClient:
    """Swappable-model wrapper around the Gemini API (google-generativeai)."""

    def __init__(self, model: str, temperature: float = 0.0, max_tokens: int = 4096) -> None:
        self.model_name = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        # Lazy import + init, so importing this module never requires an API key.
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise MissingAPIKeyError(
                    "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key "
                    "(get one free at https://aistudio.google.com/apikey)."
                )
            self._client = genai.Client(api_key=api_key)
        return self._client

    def _generate_ollama(self, prompt: str) -> LLMResponse:
        import requests

        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        name = self.model_name[len(_OLLAMA_PREFIX) :]
        payload: dict[str, Any] = {
            "model": name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        start = time.perf_counter()
        try:
            resp = requests.post(f"{host}/api/chat", json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise ExternalAPIError(
                f"Ollama request to {host} failed ({exc}). Start Ollama and run "
                f"`ollama pull {name}`."
            ) from exc
        latency_ms = (time.perf_counter() - start) * 1000.0
        try:
            text = str(data["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise ExternalAPIError(f"unexpected Ollama response: {data!r}") from exc
        return LLMResponse(
            text=text,
            input_tokens=int(data.get("prompt_eval_count", 0) or 0),
            output_tokens=int(data.get("eval_count", 0) or 0),
            cost_usd=0.0,
            latency_ms=latency_ms,
            model=self.model_name,
        )

    def generate(self, prompt: str) -> LLMResponse:
        """Send *prompt* to the model and return a typed response with cost/latency.

        Models named ``ollama/<name>`` go to a local Ollama server (OLLAMA_HOST);
        everything else goes to Gemini.
        """
        if self.model_name.startswith(_OLLAMA_PREFIX):
            return self._generate_ollama(prompt)

        from google.genai import types

        client = self._get_client()
        start = time.perf_counter()
        result = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            ),
        )
        latency_ms = (time.perf_counter() - start) * 1000.0

        text = result.text or ""
        usage = result.usage_metadata
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)

        in_rate, out_rate = _RATES_PER_1M_TOKENS.get(self.model_name, _DEFAULT_RATE)
        cost_usd = (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate

        return LLMResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            model=self.model_name,
        )
