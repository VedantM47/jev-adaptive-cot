"""
jev_cot.analysis.generate_report
===================================
Auto-generates paper/results_summary.md from logs/matrix_runs/matrix_results.json
— reproducible from a single command (FR-24 / ROADMAP Phase 19).

Usage::

    python -m jev_cot.analysis.generate_report
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path


def generate_report(
    matrix_results_path: str = "logs/matrix_runs/matrix_results.json",
    output_path: str = "paper/results_summary.md",
) -> str:
    results_file = Path(matrix_results_path)
    if not results_file.exists():
        raise FileNotFoundError(
            f"{results_file} not found — run `python -m jev_cot.experiments.run_matrix` first"
        )
    results = json.loads(results_file.read_text(encoding="utf-8"))

    lines = [
        "# Results Summary",
        "",
        "Auto-generated from `logs/matrix_runs/matrix_results.json`. Reproduce with:",
        "```",
        "python -m jev_cot.experiments.run_matrix",
        "python -m jev_cot.analysis.generate_report",
        "```",
        "",
        "## Full Factorial Matrix",
        "",
        "| LLM | Condition | Avg Cost ($) | Avg Latency (s) | Avg Steps | "
        "Grounding Recall | Answer Quality |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results.values():
        lines.append(
            f"| {r.get('llm', '?')} | {r.get('condition', '?')} | "
            f"{r.get('avg_cost_usd', 0):.4f} | {r.get('avg_latency_seconds', 0):.2f} | "
            f"{r.get('avg_steps', 0):.1f} | {r.get('avg_grounding_recall', 0):.2f} | "
            f"{r.get('avg_answer_quality', 0):.2f} |"
        )

    lines += [
        "",
        "## Note on Caveats",
        "",
        "- Seed dataset is small (provisional results — see PROJECT.md Risks). "
        "Statistical significance testing (see `jev_cot.analysis.statistics`) should "
        "be run on paired trajectory files before treating any single-run difference "
        "above as conclusive.",
        "- Grounding/quality scores use the lightweight heuristics/single-call judge "
        "documented in `jev_cot.evaluation.grounding.metrics` and "
        "`jev_cot.evaluation.quality.scorer` — good enough for relative comparison "
        "between conditions, not a substitute for full human evaluation.",
        "",
    ]

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")
    return str(out_file)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate paper/results_summary.md.")
    parser.add_argument("--matrix-results", default="logs/matrix_runs/matrix_results.json")
    parser.add_argument("--output", default="paper/results_summary.md")
    args = parser.parse_args(argv)

    try:
        path = generate_report(args.matrix_results, args.output)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
