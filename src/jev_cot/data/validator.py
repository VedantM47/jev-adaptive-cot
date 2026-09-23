"""
jev_cot.data.validator
======================
CLI tool to validate a JSONL dataset against the BenchmarkExample schema.
"""

import argparse
import sys
from pathlib import Path
import jsonlines
from pydantic import ValidationError

from jev_cot.data.schema import BenchmarkExample


def validate_file(path: str | Path) -> bool:
    """
    Validates a JSONL file. Prints errors to stderr.
    Returns True if valid, False otherwise.
    """
    path = Path(path)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        return False

    all_valid = True
    with jsonlines.open(path) as reader:
        for idx, obj in enumerate(reader):
            try:
                BenchmarkExample.model_validate(obj)
            except ValidationError as e:
                print(f"Validation error on line {idx + 1}:", file=sys.stderr)
                print(e, file=sys.stderr)
                print("-" * 40, file=sys.stderr)
                all_valid = False

    return all_valid


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a benchmark JSONL dataset.")
    parser.add_argument("file", type=str, help="Path to the JSONL file to validate.")
    args = parser.parse_args()

    if validate_file(args.file):
        print(f"Successfully validated {args.file}.")
        sys.exit(0)
    else:
        print(f"Validation failed for {args.file}.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
