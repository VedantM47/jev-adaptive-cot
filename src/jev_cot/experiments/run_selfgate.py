"""
jev_cot.experiments.run_selfgate
===================================
Condition B — Self-gate: full adaptive controller loop, LLM decides the
next action at each step.

Usage::

    python -m jev_cot.experiments.run_selfgate --config configs/conditions/selfgate.yaml
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from jev_cot.config import load_config
from jev_cot.controller.loop import run_trajectory
from jev_cot.data.trajectory import append_trajectory
from jev_cot.errors import JevCotError
from jev_cot.experiments.common import get_retriever, load_dataset, new_run_id
from jev_cot.logging import logger, setup_logging
from jev_cot.models.llm.client import LLMClient
from jev_cot.models.llm.self_gate import LLMSelfGate


def run_selfgate(config_path: str, dataset_path: str, log_dir: str = "logs") -> str:
    """Run Condition B over *dataset_path*, return the run_id."""
    cfg = load_config(config_path)
    run_id = new_run_id("selfgate")
    setup_logging(log_dir=log_dir, run_id=run_id)

    retriever = get_retriever(cfg)
    client = LLMClient(model=cfg.llm, temperature=cfg.temperature, max_tokens=cfg.max_tokens)
    examples = load_dataset(dataset_path)
    out_path = f"{log_dir}/{run_id}_trajectories.jsonl"

    for example in examples:
        gate = LLMSelfGate(LLMClient(model=cfg.llm, temperature=cfg.temperature, max_tokens=256))
        trajectory = run_trajectory(example, cfg, retriever, client, gate, run_id)
        append_trajectory(trajectory, out_path)
        logger.info(
            "selfgate trajectory complete",
            example_id=example.id,
            steps=len(trajectory.steps),
            cost_usd=trajectory.total_cost_usd,
        )

    print(f"Wrote {len(examples)} trajectories to {out_path}")
    return run_id


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the self-gate (Condition B) controller.")
    parser.add_argument("--config", default="configs/conditions/selfgate.yaml")
    parser.add_argument("--dataset", default="data/raw/sample_examples.jsonl")
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args(argv)

    try:
        run_selfgate(args.config, args.dataset, args.log_dir)
    except (FileNotFoundError, ValueError, JevCotError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
