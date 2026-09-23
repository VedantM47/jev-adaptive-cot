"""
jev_cot.controller.tools.branch
==================================
BRANCH fork + merge (FR-06): explore two rephrased sub-queries in parallel,
merge their evidence back into the main trajectory before synthesis.

Kept deliberately simple — this is a working implementation for a controlled
comparison experiment, not a production multi-agent fork/join system.
"""

from __future__ import annotations

from jev_cot.retrieval.base import RetrievalBackend


def branch_and_merge(
    retriever: RetrievalBackend,
    *,
    company: str,
    period: str,
    base_query: str,
    top_k: int = 3,
) -> list[str]:
    """
    Fork the base query into two variants, retrieve for each, merge unique evidence.

    Returns:
        A deduplicated list of evidence chunk texts from both branches.
    """
    variants = [
        base_query,
        f"{base_query} (financial details, exact figures)",
    ]
    merged: dict[str, str] = {}
    for variant in variants:
        result = retriever.retrieve(company=company, period=period, query=variant, top_k=top_k)
        for chunk in result.chunks:
            merged[chunk.chunk_id] = chunk.text
    return list(merged.values())
