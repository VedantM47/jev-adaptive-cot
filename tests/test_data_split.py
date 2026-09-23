"""
Tests for jev_cot.data dataset splitting logic.
"""

from pathlib import Path

import jsonlines

from jev_cot.data.split import get_company_hash, split_dataset


def _create_dummy_data(
    tmp_path: Path, num_companies: int = 100, examples_per_company: int = 2
) -> Path:
    p = tmp_path / "dummy.jsonl"
    with jsonlines.open(p, "w") as writer:
        for i in range(num_companies):
            comp = f"COMP_{i}"
            for j in range(examples_per_company):
                writer.write(
                    {
                        "id": f"{comp}_{j}",
                        "company": comp,
                        "period": "FY20",
                        "question": "Q",
                        "type": "factual_retrieval",
                        "documents": [],
                        "gold_claims": [],
                        "required_evidence": [],
                    }
                )
    return p


def test_company_hash_is_deterministic():
    assert get_company_hash("AAPL", 42) == get_company_hash("AAPL", 42)
    assert get_company_hash("AAPL", 42) != get_company_hash("MSFT", 42)
    assert get_company_hash("AAPL", 42) != get_company_hash("AAPL", 43)

    # Check bounds
    h = get_company_hash("ANY", 1)
    assert 0.0 <= h < 1.0


def test_split_no_overlap(tmp_path: Path):
    """Verify that there is strictly zero company overlap between train, val, and test splits."""
    input_file = _create_dummy_data(tmp_path)
    out_dir = tmp_path / "splits"

    split_dataset(input_file, out_dir, seed=42)

    def get_companies(file_path: Path) -> set:
        comps = set()
        with jsonlines.open(file_path) as reader:
            for obj in reader:
                comps.add(obj["company"])
        return comps

    train_comps = get_companies(out_dir / "train.jsonl")
    val_comps = get_companies(out_dir / "val.jsonl")
    test_comps = get_companies(out_dir / "test.jsonl")

    assert len(train_comps.intersection(val_comps)) == 0
    assert len(train_comps.intersection(test_comps)) == 0
    assert len(val_comps.intersection(test_comps)) == 0

    total_comps = len(train_comps) + len(val_comps) + len(test_comps)
    assert total_comps == 100


def test_split_is_deterministic(tmp_path: Path):
    """Verify that running the split twice with the same seed yields identical files."""
    input_file = _create_dummy_data(tmp_path)
    out_dir1 = tmp_path / "splits1"
    out_dir2 = tmp_path / "splits2"

    split_dataset(input_file, out_dir1, seed=99)
    split_dataset(input_file, out_dir2, seed=99)

    assert (out_dir1 / "train.jsonl").read_text() == (out_dir2 / "train.jsonl").read_text()
    assert (out_dir1 / "test.jsonl").read_text() == (out_dir2 / "test.jsonl").read_text()
