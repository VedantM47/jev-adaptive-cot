"""
jev_cot.evaluation.grounding.metrics
=======================================
Grounding Precision/Recall (FR-17, H4).

Simplification note: the ROADMAP's original design uses an LLM-judge for
claim-extraction + entailment scoring. That costs an extra Gemini call per
claim per trajectory — real money, and unnecessary complexity for a
working v1. This uses a normalized word-overlap heuristic instead: a claim
"is supported" when it shares enough vocabulary with a piece of evidence.
Good enough to compare conditions against each other; swap in an LLM-judge
later (this module's function signatures are the seam) if you need
paper-grade precision.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-z0-9]+")
_OVERLAP_THRESHOLD = 0.5


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _is_supported(claim: str, evidence_pool: list[str]) -> bool:
    claim_tokens = _tokens(claim)
    if not claim_tokens:
        return False
    for evidence in evidence_pool:
        evidence_tokens = _tokens(evidence)
        if not evidence_tokens:
            continue
        overlap = len(claim_tokens & evidence_tokens) / len(claim_tokens)
        if overlap >= _OVERLAP_THRESHOLD:
            return True
    return False


def extract_claims(answer_text: str) -> list[str]:
    """Split an answer into sentence-level claims (simple, punctuation-based)."""
    sentences = re.split(r"(?<=[.!?])\s+", answer_text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 5]


def grounding_precision(answer_text: str, evidence_pool: list[str]) -> float:
    """Fraction of claims in *answer_text* supported by *evidence_pool*."""
    claims = extract_claims(answer_text)
    if not claims:
        return 0.0
    supported = sum(1 for c in claims if _is_supported(c, evidence_pool))
    return supported / len(claims)


def grounding_recall(required_evidence: list[str], evidence_pool: list[str]) -> float:
    """Fraction of *required_evidence* strings actually present in *evidence_pool*."""
    if not required_evidence:
        return 1.0
    found = sum(1 for req in required_evidence if _is_supported(req, evidence_pool))
    return found / len(required_evidence)
