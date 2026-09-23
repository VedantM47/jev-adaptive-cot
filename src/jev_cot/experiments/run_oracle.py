"""
jev_cot.experiments.run_oracle
=================================
Oracle gate (FR-22): a deterministic controller using the gold
``required_evidence`` annotations directly — the theoretical upper bound
on efficiency (it never wastes a RETRIEVE once it already has what's needed).

Usage::

    python -m jev_cot.experiments.run_oracle
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from jev_cot.config import load_config
from jev_cot.controller.actions import Action
from jev_cot.controller.gate import GateDecision
from jev_cot.controller.loop import run_trajectory
from jev_cot.controller.state import ControllerState
from jev_cot.data.trajectory import append_trajectory
from jev_cot.errors import JevCotError
from jev_cot.experiments.common import get_retriever, load_dataset, new_run_id
from jev_cot.logging import logger, setup_logging
from jev_cot.models.llm.client import LLMClient


class OracleGate:
    """Cheats using the gold required_evidence signal already in ControllerState."""

    def __init__(self) -> None:
        self.last_response = None

    def decide(self, state: ControllerState) -> GateDecision:
        if state.has_required_evidence:
            return GateDecision(action=Action.STOP, confidence=1.0, source="oracle")
        return GateDecision(action=Action.RETRIEVE, confidence=1.0, source="oracle")


def run_oracle(config_path: str, dataset_path: str, log_dir: str = "logs") -> str:
    cfg = load_config(config_path)
    run_id = new_run_id("oracle")
    setup_logging(log_dir=log_dir, run_id=run_id)

    retriever = get_retriever(cfg)
    client = LLMClient(model=cfg.llm, temperature=cfg.temperature, max_tokens=cfg.max_tokens)
    examples = load_dataset(dataset_path)
    out_path = f"{log_dir}/{run_id}_trajectories.jsonl"

    gate = OracleGate()
    for example in examples:
        trajectory = run_trajectory(example, cfg, retriever, client, gate, run_id)
        append_trajectory(trajectory, out_path)
        logger.info(
            "oracle trajectory complete", example_id=example.id, steps=len(trajectory.steps)
        )

    print(f"Wrote {len(examples)} trajectories to {out_path}")
    return run_id


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the oracle upper-bound baseline.")
    parser.add_argument("--config", default="configs/conditions/selfgate.yaml")
    parser.add_argument("--dataset", default="data/raw/sample_examples.jsonl")
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args(argv)

    try:
        run_oracle(args.config, args.dataset, args.log_dir)
    except (FileNotFoundError, ValueError, JevCotError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
