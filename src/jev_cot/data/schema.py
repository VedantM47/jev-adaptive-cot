"""
jev_cot.data.schema
===================
Canonical data format for the Equity Research Benchmark.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class QuestionType(StrEnum):
    """The 7 question types defined in the benchmark."""

    FACTUAL_RETRIEVAL = "factual_retrieval"
    COMPARISON = "comparison"
    MULTI_DOCUMENT_SYNTHESIS = "multi_document_synthesis"
    CONTRADICTION_DETECTION = "contradiction_detection"
    CALCULATION = "calculation"
    CAUSAL_ANALYSIS = "causal_analysis"
    EVIDENCE_SUFFICIENCY = "evidence_sufficiency"


class BenchmarkExample(BaseModel):
    """
    Canonical schema for a benchmark question.
    Reference: Appendix C.
    """

    id: str = Field(description="Unique identifier for the question (e.g. EQ_001)")
    company: str = Field(description="Company ticker or identifier (e.g. MSFT)")
    period: str = Field(description="Fiscal period (e.g. FY2023)")
    question: str = Field(description="The research question to be answered")
    type: QuestionType = Field(description="The category of the question")
    documents: list[str] = Field(
        description="List of document identifiers required to answer the question"
    )
    gold_claims: list[str] = Field(
        description="List of factual claims that must be present in a correct answer"
    )
    required_evidence: list[str] = Field(
        description="List of evidence excerpts required to support the claims"
    )
    difficulty: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Optional difficulty score from 0.0 to 1.0"
    )
