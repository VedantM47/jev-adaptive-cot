"""
jev_cot.decision.router
=======================
Decide whether a user question is a multi-option decision.

`detect_decision` is a deterministic regex heuristic and spends ZERO LLM
tokens. `detect_decision_llm` is an optional, off-by-default fallback.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from jev_cot.decision.types import DecisionRequest
from jev_cot.errors import GateResponseParseError

MIN_OPTIONS = 2
MAX_OPTIONS = 8
_MAX_OPTION_WORDS = 6

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CUE = re.compile(
    r"\b(should|choose|pick|decide|better|best|which|go with|select|torn|prefer|"
    r"vs\.?|versus|opt for|pursue)\b",
    re.I,
)
_LEAD_SHOULD = re.compile(
    r"^(?:so,?\s+|well,?\s+|ok(?:ay)?,?\s+)?(?:should|shall|would|could|can|do)\s+(?:i|we)\s+"
    r"(?:(?:choose|pick|go with|take|do|pursue|select|opt for|study|learn|use|buy|get)\s+)?",
    re.I,
)
_LEAD_WHICH = re.compile(
    r"^which\b(?:[^:]*:\s*|\s+(?:one\s+)?(?:is\s+(?:better|best)|should\s+i\s+"
    r"(?:choose|pick|take|go\s+with|do|pursue))\s*(?:for me)?[,:]?\s*)",
    re.I,
)
_LEAD_BETWEEN = re.compile(r"^.*?\bbetween\s+", re.I)
_SPLIT = re.compile(r"\s+vs\.?\s+|\s+versus\s+|\s*,\s*(?:or\s+)?|\s+or\s+", re.I)
_SPLIT_BETWEEN = re.compile(r"\s*,\s*(?:and\s+)?|\s+and\s+|\s+or\s+", re.I)
_TRAIL = re.compile(r"\s+(?:for|given|considering|if|because|since|as|when|so)\s+.*$", re.I)
_ARTICLE = re.compile(r"^(?:a|an|the|to|going to)\s+", re.I)
_NOISE_SUFFIX = re.compile(r"\s+(?:track|option|path|route|choice)$", re.I)
_NOISE_PREFIX = re.compile(r"^(?:option|track|path)\s+(?=\S+$)", re.I)


def _clean_option(raw: str, *, trim_trailing: bool) -> str:
    t = raw.strip().strip("?.!;:\"' ").strip()
    if trim_trailing:
        t = _TRAIL.sub("", t)
    t = _ARTICLE.sub("", t)
    t = _NOISE_SUFFIX.sub("", t)
    t = _NOISE_PREFIX.sub("", t)
    return t.strip().strip("?.!;:,\"' ").strip()


def _extract_options(sentence: str) -> list[str]:
    s = sentence.strip()
    if re.search(r"\bbetween\b", s, re.I):
        s = _LEAD_BETWEEN.sub("", s, count=1)
        parts = _SPLIT_BETWEEN.split(s)
    else:
        if re.match(r"which\b", s, re.I):
            s = _LEAD_WHICH.sub("", s, count=1)
        s = _LEAD_SHOULD.sub("", s, count=1)
        parts = _SPLIT.split(s)
    cleaned: list[str] = []
    for i, p in enumerate(parts):
        c = _clean_option(p, trim_trailing=i == len(parts) - 1)
        if c and c.lower() not in {x.lower() for x in cleaned}:
            cleaned.append(c)
    return cleaned


def _valid(opts: list[str]) -> bool:
    return MIN_OPTIONS <= len(opts) <= MAX_OPTIONS and all(
        0 < len(o.split()) <= _MAX_OPTION_WORDS for o in opts
    )


def detect_decision(question: str) -> DecisionRequest | None:
    """Return a DecisionRequest if *question* looks like a choice among 2-8 options."""
    text = " ".join(question.split())
    if not text:
        return None
    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s]
    # Search from the last sentence backwards for one that frames a choice.
    for idx in range(len(sentences) - 1, -1, -1):
        sent = sentences[idx]
        has_sep = re.search(r"\s(?:or|vs\.?|versus)\s|\bbetween\b", sent, re.I) is not None
        if not has_sep or not (_CUE.search(sent) or sent.rstrip().endswith("?")):
            continue
        opts = _extract_options(sent)
        if _valid(opts):
            context = " ".join(sentences[:idx]).strip()
            return DecisionRequest(question=text, options=tuple(opts), context=context)
    return None


class _Generator(Protocol):
    def generate(self, prompt: str) -> Any: ...


_LLM_PROMPT = (
    "Is this a question asking the user to choose among 2-8 explicit options? "
    'Reply with JSON only: {{"is_decision":bool,"options":[short strings]}}.\n'
    "Question: {q}"
)


def detect_decision_llm(question: str, client: _Generator) -> DecisionRequest | None:
    """LLM fallback router (costs tokens; use only when the heuristic fails)."""
    resp = client.generate(_LLM_PROMPT.format(q=question))
    raw = str(getattr(resp, "text", resp))
    m = re.search(r"\{.*\}", raw, re.S)
    if m is None:
        raise GateResponseParseError(f"router: no JSON in LLM reply: {raw!r}")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise GateResponseParseError(f"router: bad JSON {raw!r}: {exc}") from exc
    if not data.get("is_decision"):
        return None
    opts: list[str] = []
    for o in data.get("options", []):
        c = _clean_option(str(o), trim_trailing=False)
        if c and c.lower() not in {x.lower() for x in opts}:
            opts.append(c)
    if not _valid(opts):
        return None
    return DecisionRequest(question=" ".join(question.split()), options=tuple(opts))
