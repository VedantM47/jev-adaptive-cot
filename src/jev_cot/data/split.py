"""
jev_cot.data.split
==================
CLI tool to split a dataset into train/val/test by company.
Ensures zero company overlap across splits.
"""

import argparse
import hashlib
import sys
from pathlib import Path

import jsonlines


def get_company_hash(company_id: str, seed: int) -> float:
    """Returns a deterministic float in [0, 1) for a given company and seed."""
    h = hashlib.md5(f"{company_id}:{seed}".encode()).hexdigest()
    return int(h, 16) / (16**32)


def split_dataset(input_file: str | Path, output_dir: str | Path, seed: int = 42) -> None:
    """
    Splits the dataset into train (70%), val (15%), test (15%) by company.
    """
    input_path = Path(input_file)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_file = out_dir / "train.jsonl"
    val_file = out_dir / "val.jsonl"
    test_file = out_dir / "test.jsonl"

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    train_count = 0
    val_count = 0
    test_count = 0

    with (
        jsonlines.open(input_path, mode="r") as reader,
        jsonlines.open(train_file, mode="w") as train_writer,
        jsonlines.open(val_file, mode="w") as val_writer,
        jsonlines.open(test_file, mode="w") as test_writer,
    ):
        for obj in reader:
            # We assume the validator has run, so 'company' exists
            company = obj.get("company", "UNKNOWN")
            h = get_company_hash(company, seed)

            if h < 0.70:
                train_writer.write(obj)
                train_count += 1
            elif h < 0.85:
                val_writer.write(obj)
                val_count += 1
            else:
                test_writer.write(obj)
                test_count += 1

    print(f"Split complete. Seed: {seed}")
    print(f"Train: {train_count} examples")
    print(f"Val:   {val_count} examples")
    print(f"Test:  {test_count} examples")


def main() -> None:
    parser = argparse.ArgumentParser(description="Split a dataset into train/val/test by company.")
    parser.add_argument("input_file", type=str, help="Path to the input JSONL file.")
    parser.add_argument("output_dir", type=str, help="Directory to save the splits.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for splitting.")
    args = parser.parse_args()

    split_dataset(args.input_file, args.output_dir, args.seed)


if __name__ == "__main__":
    main()
