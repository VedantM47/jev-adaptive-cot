"""
jev_cot.experiments.ablations.size_ablation
==============================================
JEV-S/M/L size comparison (FR-21) — train.py already trains all 3 sizes
per call, so this is a thin wrapper that prints the comparison table.

Usage::

    python -m jev_cot.experiments.ablations.size_ablation
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from jev_cot.models.jev.train import train_all_sizes


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="JEV size ablation (S vs M vs L).")
    parser.add_argument("--data", default="data/train/jev_labeled.jsonl")
    parser.add_argument("--checkpoints-dir", default="models/jev/checkpoints/ablations/size")
    args = parser.parse_args(argv)

    try:
        results = train_all_sizes(args.data, args.checkpoints_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"{'Size':<6}{'Val Acc':<10}{'#Params':<10}{'Latency(ms)'}")
    for r in results:
        print(
            f"{r['size']:<6}{r['val_accuracy']:<10}{r['num_parameters']:<10}{r['inference_latency_ms_per_call']}"
        )


if __name__ == "__main__":
    main()
