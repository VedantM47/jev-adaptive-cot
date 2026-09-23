"""
jev_cot.experiments.evaluate_run
===================================
Score a trajectories file for grounding + answer quality, fold the scores
back into the trajectory records, and print an efficiency/latency/grounding/
quality summary table for that run.

Usage::

    python -m jev_cot.experiments.evaluate_run --trajectories logs/selfgate_xxx_trajectories.jsonl
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import jsonlines

from jev_cot.data.trajectory import Trajectory, load_trajectories
from jev_cot.evaluation.efficiency import summarize
from jev_cot.evaluation.grounding.metrics import grounding_precision, grounding_recall
from jev_cot.evaluation.latency import latency_breakdown
from jev_cot.evaluation.quality.scorer import score_answer
from jev_cot.experiments.common import load_dataset
from jev_cot.models.llm.client import LLMClient


def evaluate(
    trajectories_path: str,
    dataset_path: str = "data/raw/sample_examples.jsonl",
    judge_model: str = "gemini-1.5-flash-latest",
    scored_out: str | None = None,
) -> dict[str, float]:
    trajectories = load_trajectories(trajectories_path)
    examples_by_id = {e.id: e for e in load_dataset(dataset_path)}
    judge = LLMClient(model=judge_model, temperature=0.0, max_tokens=512)

    scored: list[Trajectory] = []
    precisions: list[float] = []
    recalls: list[float] = []
    qualities: list[float] = []

    for t in trajectories:
        example = examples_by_id.get(t.example_id)
        if example is None:
            scored.append(t)
            continue

        precision = grounding_precision(t.final_answer, list(t.evidence_snippets))
        recall = grounding_recall(example.required_evidence, list(t.evidence_snippets))
        quality = score_answer(judge, example.question, example.gold_claims, t.final_answer)

        precisions.append(precision)
        recalls.append(recall)
        qualities.append(quality.answer_quality)

        scored.append(
            t.model_copy(
                update={
                    "grounding_precision": precision,
                    "grounding_recall": recall,
                    "answer_score": quality.answer_quality,
                }
            )
        )

    if scored_out:
        Path(scored_out).parent.mkdir(parents=True, exist_ok=True)
        with jsonlines.open(scored_out, mode="w") as writer:
            for t in scored:
                writer.write(t.model_dump(mode="json"))

    summary = summarize(scored)
    summary.update(latency_breakdown(scored))
    summary["avg_grounding_precision"] = sum(precisions) / len(precisions) if precisions else 0.0
    summary["avg_grounding_recall"] = sum(recalls) / len(recalls) if recalls else 0.0
    summary["avg_answer_quality"] = sum(qualities) / len(qualities) if qualities else 0.0
    return summary


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trajectories file.")
    parser.add_argument("--trajectories", required=True)
    parser.add_argument("--dataset", default="data/raw/sample_examples.jsonl")
    parser.add_argument("--judge-model", default="gemini-1.5-flash-latest")
    parser.add_argument("--scored-out", default=None)
    args = parser.parse_args(argv)

    try:
        summary = evaluate(args.trajectories, args.dataset, args.judge_model, args.scored_out)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
