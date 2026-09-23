"""
jev_cot.experiments.run_vanilla
==================================
Condition A — Vanilla: question -> retrieval -> LLM -> logged trajectory.
No adaptive control at all; one retrieval call, one LLM call, per question.

Usage::

    python -m jev_cot.experiments.run_vanilla --config configs/conditions/vanilla.yaml
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence

from jev_cot.config import load_config
from jev_cot.controller.actions import Action
from jev_cot.data.trajectory import Trajectory, TrajectoryStep, append_trajectory
from jev_cot.experiments.common import get_retriever, load_dataset, new_run_id
from jev_cot.logging import logger, setup_logging
from jev_cot.models.llm.client import LLMClient


def run_vanilla(config_path: str, dataset_path: str, log_dir: str = "logs") -> str:
    """Run the vanilla baseline over *dataset_path*, return the run_id."""
    cfg = load_config(config_path)
    run_id = new_run_id("vanilla")
    setup_logging(log_dir=log_dir, run_id=run_id)

    retriever = get_retriever(cfg)
    client = LLMClient(model=cfg.llm, temperature=cfg.temperature, max_tokens=cfg.max_tokens)
    examples = load_dataset(dataset_path)

    out_path = f"{log_dir}/{run_id}_trajectories.jsonl"

    for example in examples:
        start = time.perf_counter()
        result = retriever.retrieve(
            company=example.company,
            period=example.period,
            query=example.question,
            top_k=cfg.retrieval.top_k,
        )
        evidence = "\n".join(f"- {c.text}" for c in result.chunks) or "(no evidence found)"
        prompt = (
            f"Answer this equity-research question using ONLY the evidence below.\n\n"
            f"Question: {example.question}\n\nEvidence:\n{evidence}\n\nAnswer:"
        )
        response = client.generate(prompt)
        total_latency = time.perf_counter() - start

        trajectory = Trajectory(
            run_id=run_id,
            example_id=example.id,
            condition="vanilla",
            llm=cfg.llm,
            question=example.question,
            evidence_snippets=tuple(c.text for c in result.chunks),
            steps=(
                TrajectoryStep(
                    step_index=0,
                    state={"num_retrievals": 1, "evidence_count": len(result.chunks)},
                    action=Action.RETRIEVE,
                    confidence=1.0,
                    gate_source="none",
                    latency_ms=result.latency_ms,
                    cost_usd=0.0,
                ),
                TrajectoryStep(
                    step_index=1,
                    state={"num_retrievals": 1, "evidence_count": len(result.chunks)},
                    action=Action.STOP,
                    confidence=1.0,
                    gate_source="none",
                    latency_ms=response.latency_ms,
                    cost_usd=response.cost_usd,
                ),
            ),
            final_answer=response.text,
            total_latency_seconds=total_latency,
            total_cost_usd=response.cost_usd,
            total_llm_calls=1,
            total_input_tokens=response.input_tokens,
            total_output_tokens=response.output_tokens,
        )
        append_trajectory(trajectory, out_path)
        logger.info(
            "vanilla trajectory complete",
            example_id=example.id,
            cost_usd=response.cost_usd,
            latency_s=total_latency,
        )

    print(f"Wrote {len(examples)} trajectories to {out_path}")
    return run_id


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the vanilla (Condition A) baseline.")
    parser.add_argument("--config", default="configs/conditions/vanilla.yaml")
    parser.add_argument("--dataset", default="data/raw/sample_examples.jsonl")
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args(argv)

    try:
        run_vanilla(args.config, args.dataset, args.log_dir)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
