"""
jev_cot.experiments.ablations.feature_ablations
===================================================
State-feature ablations (FR-21, simplified): since ControllerState only
exposes 8 numeric fields (no raw CoT, no categorical question_type/
confidence features), this compares 3 meaningful subsets rather than the
full 6-variant matrix the original spec sketched — full state,
evidence-only, and reasoning-only.

Usage::

    python -m jev_cot.experiments.ablations.feature_ablations
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import numpy as np
from sklearn.model_selection import train_test_split

from jev_cot.models.jev.model import FEATURE_NAMES, JEVModel
from jev_cot.models.jev.train import load_training_data

_FEATURE_SUBSETS: dict[str, tuple[str, ...]] = {
    "full": FEATURE_NAMES,
    "evidence_only": ("evidence_count", "has_required_evidence", "distinct_documents_seen"),
    "reasoning_only": (
        "num_steps_taken",
        "num_retrievals",
        "num_computations",
        "num_branches",
        "elapsed_seconds",
    ),
}


def _mask_columns(X: np.ndarray, keep: tuple[str, ...]) -> np.ndarray:
    keep_idx = [FEATURE_NAMES.index(name) for name in keep]
    masked = np.zeros_like(X)
    masked[:, keep_idx] = X[:, keep_idx]
    return masked


def run_feature_ablations(
    data_path: str = "data/train/jev_labeled.jsonl", seed: int = 42
) -> list[dict[str, object]]:
    X, y = load_training_data(data_path)
    if len(X) < 4:
        raise ValueError(f"Need at least 4 rows, got {len(X)}")

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=seed)

    results: list[dict[str, object]] = []
    for name, subset in _FEATURE_SUBSETS.items():
        X_train_masked = _mask_columns(X_train, subset)
        X_val_masked = _mask_columns(X_val, subset)

        model = JEVModel(size="M")
        model.fit(X_train_masked, y_train)
        proba = model.predict_proba(X_val_masked)
        preds = [model.classes[int(np.argmax(p))] for p in proba]
        acc = float(np.mean([p == t for p, t in zip(preds, y_val, strict=True)]))

        results.append({"variant": name, "features_used": subset, "val_accuracy": round(acc, 4)})
    return results


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="State-feature ablation comparison.")
    parser.add_argument("--data", default="data/train/jev_labeled.jsonl")
    args = parser.parse_args(argv)

    try:
        results = run_feature_ablations(args.data)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"{'Variant':<18}{'Val Accuracy'}")
    for r in results:
        print(f"{r['variant']:<18}{r['val_accuracy']}")


if __name__ == "__main__":
    main()
