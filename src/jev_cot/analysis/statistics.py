"""
jev_cot.analysis.statistics
==============================
Paired comparisons between two conditions on the same questions (FR-24):
mean/median/std, 95% CI, and a paired t-test per metric. No claim in the
final report should be made without a number from here backing it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from jev_cot.data.trajectory import Trajectory, load_trajectories


@dataclass(frozen=True)
class PairedResult:
    metric: str
    mean_a: float
    mean_b: float
    mean_diff: float
    ci_95_low: float
    ci_95_high: float
    t_statistic: float
    p_value: float
    n_pairs: int


def _metric_series(trajectories: list[Trajectory], metric: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for t in trajectories:
        if metric == "cost_usd":
            values[t.example_id] = t.total_cost_usd
        elif metric == "latency_seconds":
            values[t.example_id] = t.total_latency_seconds
        elif metric == "num_steps":
            values[t.example_id] = float(len(t.steps))
        elif metric == "grounding_recall":
            values[t.example_id] = t.grounding_recall or 0.0
        elif metric == "answer_quality":
            values[t.example_id] = t.answer_score or 0.0
        else:
            raise ValueError(f"Unknown metric {metric!r}")
    return values


def paired_compare(
    trajectories_a: list[Trajectory], trajectories_b: list[Trajectory], metric: str
) -> PairedResult:
    """
    Paired comparison of *metric* between condition A and condition B, matched
    by example_id (both runs must have used the same benchmark examples).
    """
    series_a = _metric_series(trajectories_a, metric)
    series_b = _metric_series(trajectories_b, metric)
    shared_ids = sorted(set(series_a) & set(series_b))
    if len(shared_ids) < 2:
        raise ValueError(
            f"Need at least 2 shared example_ids to run a paired test, got {len(shared_ids)}"
        )

    a = np.array([series_a[i] for i in shared_ids])
    b = np.array([series_b[i] for i in shared_ids])
    diff = a - b

    t_stat, p_value = stats.ttest_rel(a, b)
    se = diff.std(ddof=1) / np.sqrt(len(diff)) if len(diff) > 1 else 0.0
    ci_low, ci_high = diff.mean() - 1.96 * se, diff.mean() + 1.96 * se

    return PairedResult(
        metric=metric,
        mean_a=float(a.mean()),
        mean_b=float(b.mean()),
        mean_diff=float(diff.mean()),
        ci_95_low=float(ci_low),
        ci_95_high=float(ci_high),
        t_statistic=float(t_stat),
        p_value=float(p_value),
        n_pairs=len(shared_ids),
    )


def compare_files(path_a: str, path_b: str, metrics: tuple[str, ...]) -> list[PairedResult]:
    """Load two trajectory files and run paired comparisons across *metrics*."""
    trajectories_a = load_trajectories(path_a)
    trajectories_b = load_trajectories(path_b)
    return [paired_compare(trajectories_a, trajectories_b, m) for m in metrics]
