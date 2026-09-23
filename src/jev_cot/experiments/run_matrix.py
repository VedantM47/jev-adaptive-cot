"""
jev_cot.experiments.run_matrix
=================================
Full factorial experiment runner (FR-20): {Pro, Flash} x {Vanilla,
Self-gate, JEV-gate} on the test set, with per-cell evaluation. This is
the primary comparison result the whole project measures.

Usage::

    python -m jev_cot.experiments.run_matrix
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

import yaml

from jev_cot.config import ExperimentConfig, load_config
from jev_cot.errors import JevCotError
from jev_cot.experiments.evaluate_run import evaluate
from jev_cot.experiments.run_jevgate import run_jevgate
from jev_cot.experiments.run_selfgate import run_selfgate
from jev_cot.experiments.run_vanilla import run_vanilla

_LLMS = ("gemini-pro-latest", "gemini-flash-latest")
_CONDITIONS = ("vanilla", "selfgate", "jevgate")


def _write_temp_config(cfg: ExperimentConfig, tmp_dir: Path, name: str) -> str:
    path = tmp_dir / f"{name}.yaml"
    dumped = cfg.model_dump(mode="json", exclude={"timestamp"})
    path.write_text(yaml.safe_dump(dumped), encoding="utf-8")
    return str(path)


def run_matrix(
    dataset_path: str = "data/raw/sample_examples.jsonl",
    checkpoint_dir: str = "models/jev/checkpoints/jev_frozen_v1",
    log_dir: str = "logs/matrix_runs",
    judge_model: str = "gemini-flash-latest",
) -> dict[str, dict[str, object]]:
    base = load_config("configs/base.yaml")
    results: dict[str, dict[str, object]] = {}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for llm in _LLMS:
            for condition in _CONDITIONS:
                cell = f"{llm}__{condition}"
                cfg = base.model_copy(
                    update={
                        "llm": llm,
                        "condition": condition,
                        "jev_version": "jev_frozen_v1" if condition == "jevgate" else "none",
                    }
                )
                cfg_path = _write_temp_config(cfg, tmp_dir, cell)

                if condition == "vanilla":
                    run_id = run_vanilla(cfg_path, dataset_path, log_dir)
                elif condition == "selfgate":
                    run_id = run_selfgate(cfg_path, dataset_path, log_dir)
                else:
                    run_id = run_jevgate(cfg_path, dataset_path, checkpoint_dir, log_dir)

                traj_path = f"{log_dir}/{run_id}_trajectories.jsonl"
                summary = evaluate(traj_path, dataset_path, judge_model)
                results[cell] = {"llm": llm, "condition": condition, **summary}

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    results_path = Path(log_dir) / "matrix_results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the full factorial experiment matrix.")
    parser.add_argument("--dataset", default="data/raw/sample_examples.jsonl")
    parser.add_argument("--checkpoint-dir", default="models/jev/checkpoints/jev_frozen_v1")
    parser.add_argument("--log-dir", default="logs/matrix_runs")
    parser.add_argument("--judge-model", default="gemini-flash-latest")
    args = parser.parse_args(argv)

    try:
        results = run_matrix(args.dataset, args.checkpoint_dir, args.log_dir, args.judge_model)
    except (FileNotFoundError, ValueError, JevCotError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"{'Cell':<40}{'Avg Cost':<12}{'Avg Latency(s)':<16}{'Grounding R':<14}{'Quality'}")
    for cell, r in results.items():
        print(
            f"{cell:<40}{r.get('avg_cost_usd', 0):<12.4f}"
            f"{r.get('avg_latency_seconds', 0):<16.2f}"
            f"{r.get('avg_grounding_recall', 0):<14.2f}"
            f"{r.get('avg_answer_quality', 0):.2f}"
        )
    print(f"\nFull results: {args.log_dir}/matrix_results.json")


if __name__ == "__main__":
    main()
