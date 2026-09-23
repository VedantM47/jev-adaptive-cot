"""
jev_cot.evaluation.metrics_registry
===================================
Registry of primary metrics defined in the research specification.

This module defines the metric names, types, and mathematical formulas
as stubs. Implementations will be added in Phase 13/14.
"""

from typing import Dict, Any


class MetricDefinition:
    def __init__(self, name: str, description: str, formula: str):
        self.name = name
        self.description = description
        self.formula = formula


METRICS: Dict[str, MetricDefinition] = {
    # H1 - Efficiency
    "ops_saved": MetricDefinition(
        name="ops_saved",
        description="Reduction in reasoning/tool steps vs self-gate",
        formula="steps_selfgate - steps_jevgate",
    ),
    # H2 - Latency
    "latency_reduction": MetricDefinition(
        name="latency_reduction",
        description="Reduction in end-to-end latency",
        formula="latency_selfgate - latency_jevgate",
    ),
    # H3 - Cost
    "cost_ratio": MetricDefinition(
        name="cost_ratio",
        description="Ratio of JEV-gate cost to self-gate cost",
        formula="cost_jevgate / cost_selfgate",
    ),
    # H4 - Grounding
    "grounding_precision": MetricDefinition(
        name="grounding_precision",
        description="Fraction of cited claims supported by evidence",
        formula="|supported_cited_claims| / |cited_claims|",
    ),
    "grounding_recall": MetricDefinition(
        name="grounding_recall",
        description="Fraction of required claims supported by evidence",
        formula="|supported_required_claims| / |required_claims|",
    ),
    # H5 - Answer Quality
    "answer_quality": MetricDefinition(
        name="answer_quality",
        description="Multi-dimensional answer quality score (0-1)",
        formula="weighted_sum(factual_accuracy, evidence_support, citation_correctness, completeness, calculation_correctness, contradiction_handling, uncertainty_calibration)",
    ),
    # H6 - Calibration
    "ece": MetricDefinition(
        name="ece",
        description="Expected Calibration Error",
        formula="Σ_b (|B_b|/n) * |acc(B_b) - conf(B_b)| over M bins",
    ),
    "brier_score": MetricDefinition(
        name="brier_score", description="Brier Score", formula="(1/N) * Σ (p_hat - y)^2"
    ),
}
