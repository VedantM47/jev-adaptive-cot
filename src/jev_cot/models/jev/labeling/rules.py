"""
jev_cot.models.jev.labeling.rules
====================================
Rule-based labeling pass (FR-09, simplified for a working v1 — no separate
LLM-judge relabel pass or human review queue; every label is either the
self-gate's own recorded decision or a rule-corrected override, and every
row carries ``label_source`` for traceability).

Input: data/processed/jev_examples.jsonl  (state, action pairs from
       collect_trajectories.py — the self-gate's own decisions)
Output: data/train/jev_labeled.jsonl      (state, action, label_source)
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import jsonlines

from jev_cot.controller.actions import Action


def apply_rules(state: dict[str, Any], self_gate_action: str) -> tuple[str, str]:
    """
    Apply simple correctness rules on top of the self-gate's own decision.

    Returns:
        (label, label_source) — label_source is "rule" when a rule fired,
        otherwise "self_gate" (the self-gate's decision is trusted as-is).
    """
    has_required = bool(state.get("has_required_evidence", False))
    evidence_count = int(state.get("evidence_count", 0))
    num_retrievals = int(state.get("num_retrievals", 0))
    num_steps = int(state.get("num_steps_taken", 0))

    # Rule 1: all required evidence is in hand — the correct move is to stop, not retrieve/branch.
    if has_required and self_gate_action in (Action.RETRIEVE.value, Action.BRANCH.value):
        return Action.STOP.value, "rule"

    # Rule 2: no evidence yet and the gate said STOP/CONTINUE — premature, retrieve first.
    if (
        evidence_count == 0
        and num_steps == 0
        and self_gate_action
        in (
            Action.STOP.value,
            Action.CONTINUE.value,
        )
    ):
        return Action.RETRIEVE.value, "rule"

    # Rule 3: many retrievals with zero evidence gained — stop rather than keep retrieving blindly.
    if num_retrievals >= 3 and evidence_count == 0 and self_gate_action == Action.RETRIEVE.value:
        return Action.STOP.value, "rule"

    return self_gate_action, "self_gate"


def label_dataset(input_path: str | Path, output_path: str | Path) -> dict[str, int]:
    """Apply rules to every row in *input_path*, write labeled rows to *output_path*."""
    in_p, out_p = Path(input_path), Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    source_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()

    with jsonlines.open(in_p) as reader, jsonlines.open(out_p, mode="w") as writer:
        for row in reader:
            label, source = apply_rules(row["state"], row["action"])
            writer.write({"state": row["state"], "action": label, "label_source": source})
            source_counts[source] += 1
            action_counts[label] += 1

    return {**source_counts, "_total": sum(source_counts.values())}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Apply rule-based labeling to JEV training pairs.")
    parser.add_argument("--input", default="data/processed/jev_examples.jsonl")
    parser.add_argument("--output", default="data/train/jev_labeled.jsonl")
    args = parser.parse_args(argv)

    try:
        stats = label_dataset(args.input, args.output)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Labeled {stats['_total']} examples -> {args.output}")
    print(f"Label sources: {dict(stats)}")


if __name__ == "__main__":
    main()
