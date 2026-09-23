"""
jev_cot.models.jev.train
===========================
Train JEV on data/train/jev_labeled.jsonl (state, action, label_source pairs).

Trains all 3 size variants (S/M/L), evaluates against a majority-class
baseline, and saves each variant's checkpoint + a latency/param-count table.

Note on the split: the seed dataset is small (PROJECT.md flags this
explicitly as provisional). Rather than reuse the benchmark's company-level
split machinery — which doesn't apply here, these rows are controller
steps, not benchmark examples — this uses a fixed-seed random split. Good
enough to prove the pipeline works end to end; a real statistical result
needs the larger-scale data-collection workstream noted in PROJECT.md.

Usage::

    python -m jev_cot.models.jev.train
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import jsonlines
import numpy as np
from sklearn.model_selection import train_test_split

from jev_cot.models.jev.model import FEATURE_NAMES, JEVModel


def load_training_data(path: str | Path) -> tuple[np.ndarray, list[str]]:
    """Load (X, y) from a jev_labeled.jsonl file."""
    X_rows: list[list[float]] = []
    y: list[str] = []
    with jsonlines.open(path) as reader:
        for row in reader:
            state = row["state"]
            X_rows.append([float(state.get(name, 0.0)) for name in FEATURE_NAMES])
            y.append(row["action"])
    return np.array(X_rows, dtype=np.float32), y


def train_all_sizes(
    data_path: str = "data/train/jev_labeled.jsonl",
    checkpoints_dir: str = "models/jev/checkpoints",
    test_size: float = 0.2,
    seed: int = 42,
) -> list[dict[str, object]]:
    X, y = load_training_data(data_path)
    if len(X) < 4:
        raise ValueError(
            f"Only {len(X)} training rows found in {data_path} — need at least 4 to split "
            "train/val. Run collect_trajectories.py + rules.py first."
        )

    label_counts = Counter(y)
    can_stratify = len(X) >= 10 and min(label_counts.values()) >= 2
    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=seed,
        stratify=y if can_stratify else None,
    )

    majority_label = label_counts.most_common(1)[0][0]
    baseline_acc = float(np.mean([label == majority_label for label in y_val]))

    results: list[dict[str, object]] = []
    for size in ("S", "M", "L"):
        model = JEVModel(size=size)
        model.fit(X_train, y_train)

        start = time.perf_counter()
        preds = [model.predict_proba(x.reshape(1, -1))[0] for x in X_val]
        inference_latency_ms = (time.perf_counter() - start) * 1000.0 / max(len(X_val), 1)

        pred_labels = [model.classes[int(np.argmax(p))] for p in preds]
        val_acc = float(np.mean([p == t for p, t in zip(pred_labels, y_val, strict=True)]))

        out_dir = Path(checkpoints_dir) / f"jev_{size.lower()}"
        model.save(out_dir)

        results.append(
            {
                "size": size,
                "val_accuracy": round(val_acc, 4),
                "baseline_accuracy": round(baseline_acc, 4),
                "beats_baseline": val_acc > baseline_acc,
                "num_parameters": model.num_parameters(),
                "inference_latency_ms_per_call": round(inference_latency_ms, 4),
                "checkpoint": str(out_dir),
            }
        )

    return results


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train JEV (S/M/L variants).")
    parser.add_argument("--data", default="data/train/jev_labeled.jsonl")
    parser.add_argument("--checkpoints-dir", default="models/jev/checkpoints")
    args = parser.parse_args(argv)

    try:
        results = train_all_sizes(args.data, args.checkpoints_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"{'Size':<6}{'Val Acc':<10}{'Baseline':<10}{'Beats?':<8}{'#Params':<10}{'Latency(ms)'}")
    for r in results:
        print(
            f"{r['size']:<6}{r['val_accuracy']:<10}{r['baseline_accuracy']:<10}"
            f"{str(r['beats_baseline']):<8}{r['num_parameters']:<10}"
            f"{r['inference_latency_ms_per_call']}"
        )


if __name__ == "__main__":
    main()
