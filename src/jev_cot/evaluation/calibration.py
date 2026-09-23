"""
jev_cot.evaluation.calibration
=================================
Calibration metrics (FR-19, H6): Expected Calibration Error and Brier score.
"""

from __future__ import annotations

import numpy as np


def expected_calibration_error(
    confidences: np.ndarray, correct: np.ndarray, num_bins: int = 10
) -> float:
    """
    Standard ECE: bin predictions by confidence, compare mean confidence to
    accuracy in each bin, weight by bin size.

    Args:
        confidences: Predicted confidence (max class probability) per example, in [0, 1].
        correct: 1.0/True if the top prediction was correct, else 0.0/False.
        num_bins: Number of equal-width confidence bins.
    """
    confidences = np.asarray(confidences, dtype=np.float64)
    correct = np.asarray(correct, dtype=np.float64)
    n = len(confidences)
    if n == 0:
        return 0.0

    bin_edges = np.linspace(0.0, 1.0, num_bins + 1)
    ece = 0.0
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:], strict=True):
        in_bin = (
            (confidences > lo) & (confidences <= hi)
            if lo > 0
            else (confidences >= lo) & (confidences <= hi)
        )
        if not np.any(in_bin):
            continue
        bin_acc = float(np.mean(correct[in_bin]))
        bin_conf = float(np.mean(confidences[in_bin]))
        ece += (np.sum(in_bin) / n) * abs(bin_acc - bin_conf)
    return float(ece)


def brier_score(probabilities: np.ndarray, one_hot_targets: np.ndarray) -> float:
    """Multi-class Brier score: mean squared error between predicted probs and one-hot targets."""
    probabilities = np.asarray(probabilities, dtype=np.float64)
    one_hot_targets = np.asarray(one_hot_targets, dtype=np.float64)
    return float(np.mean(np.sum((probabilities - one_hot_targets) ** 2, axis=1)))
