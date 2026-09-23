"""
jev_cot.experiments.collect_trajectories
===========================================
Runs Condition B (self-gate) across the dataset and dumps the raw
(state, action) pairs JEV will train on.

Usage::

    python -m jev_cot.experiments.collect_trajectories
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import jsonlines

from jev_cot.config import load_config
from jev_cot.controller.loop import run_trajectory
from jev_cot.data.trajectory import append_trajectory
from jev_cot.experiments.common import get_retriever, load_dataset, new_run_id
from jev_cot.logging import logger, setup_logging
from jev_cot.models.llm.client import LLMClient
from jev_cot.models.llm.self_gate import LLMSelfGate


def collect(
    config_path: str = "configs/conditions/selfgate.yaml",
    dataset_path: str = "data/raw/sample_examples.jsonl",
    trajectories_out: str = "data/processed/trajectories.jsonl",
    jev_examples_out: str = "data/processed/jev_examples.jsonl",
    log_dir: str = "logs",
) -> None:
    cfg = load_config(config_path)
    run_id = new_run_id("collect")
    setup_logging(log_dir=log_dir, run_id=run_id)

    retriever = get_retriever(cfg)
    client = LLMClient(model=cfg.llm, temperature=cfg.temperature, max_tokens=cfg.max_tokens)
    examples = load_dataset(dataset_path)

    Path(jev_examples_out).parent.mkdir(parents=True, exist_ok=True)
    num_pairs = 0
    with jsonlines.open(jev_examples_out, mode="w") as jev_writer:
        for example in examples:
            gate = LLMSelfGate(
                LLMClient(model=cfg.llm, temperature=cfg.temperature, max_tokens=256)
            )
            trajectory = run_trajectory(example, cfg, retriever, client, gate, run_id)
            append_trajectory(trajectory, trajectories_out)

            for step in trajectory.steps:
                jev_writer.write({"state": step.state, "action": step.action.value})
                num_pairs += 1

            logger.info("collected trajectory", example_id=example.id, steps=len(trajectory.steps))

    print(f"Wrote {len(examples)} trajectories -> {trajectories_out}")
    print(f"Wrote {num_pairs} (state, action) pairs -> {jev_examples_out}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Collect (state, action) pairs for JEV training.")
    parser.add_argument("--config", default="configs/conditions/selfgate.yaml")
    parser.add_argument("--dataset", default="data/raw/sample_examples.jsonl")
    parser.add_argument("--trajectories-out", default="data/processed/trajectories.jsonl")
    parser.add_argument("--jev-examples-out", default="data/processed/jev_examples.jsonl")
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args(argv)

    try:
        collect(
            args.config,
            args.dataset,
            args.trajectories_out,
            args.jev_examples_out,
            args.log_dir,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
