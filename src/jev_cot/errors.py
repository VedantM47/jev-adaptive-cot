"""
jev_cot.errors
================
Every error in this project raises loudly with a short, greppable code —
no silent fallback substitution (a malformed LLM response, a missing key,
a bad config never gets quietly replaced with a guessed default). If
something is wrong, you get an exception with a code you can search this
file for, not a plausible-looking wrong answer.

Usage::

    raise GateResponseParseError(f"could not parse JSON: {text!r}")
    # -> JevCotError: [JEV-GATE-001] could not parse JSON: '...'
"""

from __future__ import annotations


class JevCotError(Exception):
    """Base class for every error this project raises. Carries a fixed `code`."""

    code: str = "JEV-000"

    def __init__(self, message: str) -> None:
        super().__init__(f"[{self.code}] {message}")


# ── Gate / LLM errors (JEV-GATE-xxx) ─────────────────────────────────────────
class GateResponseParseError(JevCotError):
    """The self-gate or quality judge's LLM response could not be parsed as expected."""

    code = "JEV-GATE-001"


class MissingAPIKeyError(JevCotError):
    """A required API key environment variable is not set."""

    code = "JEV-GATE-002"


# ── Controller errors (JEV-CTRL-xxx) ─────────────────────────────────────────
class LimitExceededError(JevCotError):
    """A hard safety limit (steps/retrievals/branches/latency/cost) was hit."""

    code = "JEV-CTRL-001"


# ── Retrieval errors (JEV-RETR-xxx) ──────────────────────────────────────────
class RetrievalContractError(JevCotError):
    """A retrieval backend's _search() result violated the retrieve() contract."""

    code = "JEV-RETR-001"


# ── JEV classifier errors (JEV-MODEL-xxx) ────────────────────────────────────
class ModelNotFittedError(JevCotError):
    """A JEVModel method was called before fit() or load()."""

    code = "JEV-MODEL-001"


# ── External integration errors (JEV-EXT-xxx) ────────────────────────────────
class ExternalAPIError(JevCotError):
    """A third-party API (Gemini, TypeSafe Jev) returned an unusable response."""

    code = "JEV-EXT-001"
