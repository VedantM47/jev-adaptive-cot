"""
jev_cot.models.jev.calibrate
===============================
Calibrate JEV's confidence output and freeze the final model artifact
(FR-10, NFR-05). Uses a held-out calibration split, separate from the
train/val split train.py used — the frozen artifact never sees the same
rows it will later be tested on.

Usage::

    python -m jev_cot.models.jev.calibrate
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

from jev_cot.evaluation.calibration import brier_score, expected_calibration_error
from jev_cot.models.jev.model import JEVModel
from jev_cot.models.jev.train import load_training_data


def _confidences_and_correctness(
    proba: np.ndarray, y_true: list[str], classes: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray]:
    pred_idx = np.argmax(proba, axis=1)
    confidences = proba[np.arange(len(proba)), pred_idx]
    correct = np.array([classes[idx] == label for idx, label in zip(pred_idx, y_true, strict=True)])
    return confidences, correct


def calibrate_and_freeze(
    data_path: str = "data/train/jev_labeled.jsonl",
    size: str = "M",
    frozen_dir: str = "models/jev/checkpoints/jev_frozen_v1",
    seed: int = 42,
) -> dict[str, object]:
    X, y = load_training_data(data_path)
    if len(X) < 6:
        raise ValueError(f"Need at least 6 rows to split train/calibrate, got {len(X)}")

    X_train, X_calib, y_train, y_calib = train_test_split(X, y, test_size=0.3, random_state=seed)

    model = JEVModel(size=size)
    model.fit(X_train, y_train)

    pre_proba = model.predict_proba(X_calib)
    pre_conf, pre_correct = _confidences_and_correctness(pre_proba, y_calib, model.classes)
    pre_ece = expected_calibration_error(pre_conf, pre_correct)

    model.calibrate(X_calib, y_calib)

    post_proba = model.predict_proba(X_calib)
    post_conf, post_correct = _confidences_and_correctness(post_proba, y_calib, model.classes)
    post_ece = expected_calibration_error(post_conf, post_correct)

    one_hot = np.zeros((len(y_calib), len(model.classes)))
    for i, label in enumerate(y_calib):
        one_hot[i, model.classes.index(label)] = 1.0
    post_brier = brier_score(post_proba, one_hot)

    model.save(frozen_dir)
    Path(frozen_dir, "calibration_report.json").write_text(
        json.dumps(
            {
                "version": "jev_frozen_v1",
                "size": size,
                "pre_calibration_ece": round(pre_ece, 4),
                "post_calibration_ece": round(post_ece, 4),
                "post_calibration_brier": round(post_brier, 4),
                "n_calibration_examples": len(y_calib),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "pre_calibration_ece": pre_ece,
        "post_calibration_ece": post_ece,
        "post_calibration_brier": post_brier,
        "frozen_dir": frozen_dir,
    }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Calibrate and freeze the JEV model.")
    parser.add_argument("--data", default="data/train/jev_labeled.jsonl")
    parser.add_argument("--size", default="M", choices=["S", "M", "L"])
    parser.add_argument("--frozen-dir", default="models/jev/checkpoints/jev_frozen_v1")
    args = parser.parse_args(argv)

    try:
        result = calibrate_and_freeze(args.data, args.size, args.frozen_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Pre-calibration ECE:  {result['pre_calibration_ece']:.4f}")
    print(f"Post-calibration ECE: {result['post_calibration_ece']:.4f}")
    print(f"Post-calibration Brier: {result['post_calibration_brier']:.4f}")
    print(f"Frozen model saved to: {result['frozen_dir']}")


if __name__ == "__main__":
    main()
