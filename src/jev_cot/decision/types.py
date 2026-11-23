"""Request/result types for the decision layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionRequest:
    question: str
    options: tuple[str, ...]
    context: str = ""


@dataclass(frozen=True)
class DecisionResult:
    options: tuple[str, ...]
    probabilities: dict[str, float]
    choice: str
    confidence: float
    model: str
    latency_ms: float
    n_samples: int

    def to_prompt_block(self) -> str:
        """Compact text block suitable for injecting into an LLM prompt."""
        lines = [f"JEV DECISION (model={self.model}, {self.n_samples} samples)"]
        for opt in self.options:
            lines.append(f"- {opt}: {self.probabilities[opt] * 100:.1f}%")
        lines.append(f"Top: {self.choice} (confidence {self.confidence:.2f})")
        return "\n".join(lines)
