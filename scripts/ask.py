"""CLI: python scripts/ask.py "should I choose A or B?" [--llm ollama/qwen3:8b]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from jev_cot.config import load_config  # noqa: E402
from jev_cot.decision.jev_local import LocalJev  # noqa: E402
from jev_cot.decision.pipeline import answer  # noqa: E402
from jev_cot.errors import JevCotError  # noqa: E402
from jev_cot.models.llm.client import LLMClient  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("question")
    ap.add_argument("--llm", default="ollama/qwen3:8b")
    args = ap.parse_args()

    cfg = load_config(REPO_ROOT / "configs" / "base.yaml")
    d = cfg.decision
    jev = LocalJev(model=d.jev_model, host=d.ollama_host, n_permutations=d.n_permutations)
    client = LLMClient(model=args.llm, temperature=cfg.temperature, max_tokens=cfg.max_tokens)
    try:
        result = answer(args.question, client, jev, use_llm_router=d.use_llm_router)
    except JevCotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if result.decision is not None:
        print(result.decision.to_prompt_block())
        print()
    else:
        print("(not a decision question; answered by the LLM directly)\n")
    print(result.answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
