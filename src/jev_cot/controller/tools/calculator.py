"""
jev_cot.controller.tools.calculator
=====================================
Real calculator tool for COMPUTE actions (FR-05) — financial arithmetic,
not LLM-generated numbers.
"""

from __future__ import annotations

from collections.abc import Callable


def yoy_change_pct(current: float, prior: float) -> float:
    """Year-over-year percent change: (current - prior) / prior * 100."""
    if prior == 0:
        raise ValueError("prior value is 0 — YoY % change is undefined")
    return float((current - prior) / prior * 100.0)


def cagr(begin_value: float, end_value: float, num_years: float) -> float:
    """Compound annual growth rate, as a percent."""
    if begin_value <= 0 or num_years <= 0:
        raise ValueError("begin_value and num_years must be positive")
    return float(((end_value / begin_value) ** (1.0 / num_years) - 1.0) * 100.0)


def margin_pct(numerator: float, denominator: float) -> float:
    """A margin/ratio expressed as a percent, e.g. operating income / revenue."""
    if denominator == 0:
        raise ValueError("denominator is 0 — margin % is undefined")
    return numerator / denominator * 100.0


# Dispatch table used by the controller loop's COMPUTE handler.
CALCULATOR_OPS: dict[str, Callable[..., float]] = {
    "yoy_change_pct": yoy_change_pct,
    "cagr": cagr,
    "margin_pct": margin_pct,
}


def run_calculation(op: str, **kwargs: float) -> float:
    """Dispatch to a named calculator op. Raises KeyError for an unknown op."""
    if op not in CALCULATOR_OPS:
        raise KeyError(f"Unknown calculator op {op!r}. Known ops: {sorted(CALCULATOR_OPS)}")
    return CALCULATOR_OPS[op](**kwargs)
