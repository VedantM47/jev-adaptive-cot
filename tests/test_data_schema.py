"""
Tests for jev_cot.data schema validation.
"""

from pathlib import Path

import jsonlines
import pytest
from pydantic import ValidationError

from jev_cot.data.schema import BenchmarkExample, QuestionType


def test_schema_valid_example():
    """A valid example parses correctly."""
    data = {
        "id": "EQ_TEST",
        "company": "AAPL",
        "period": "FY23",
        "question": "What is the revenue?",
        "type": "factual_retrieval",
        "documents": ["doc1"],
        "gold_claims": ["claim1"],
        "required_evidence": ["evidence1"],
        "difficulty": 0.5,
    }
    example = BenchmarkExample.model_validate(data)
    assert example.id == "EQ_TEST"
    assert example.type == QuestionType.FACTUAL_RETRIEVAL


def test_schema_invalid_difficulty():
    """Difficulty > 1.0 raises ValidationError."""
    data = {
        "id": "EQ_TEST",
        "company": "AAPL",
        "period": "FY23",
        "question": "Q",
        "type": "factual_retrieval",
        "documents": [],
        "gold_claims": [],
        "required_evidence": [],
        "difficulty": 1.5,
    }
    with pytest.raises(ValidationError):
        BenchmarkExample.model_validate(data)


def test_sample_dataset_validates():
    """The provided sample dataset passes schema validation completely."""
    root = Path(__file__).parent.parent
    sample_path = root / "data" / "raw" / "sample_examples.jsonl"

    with jsonlines.open(sample_path) as reader:
        types_seen = set()
        for obj in reader:
            ex = BenchmarkExample.model_validate(obj)
            types_seen.add(ex.type)

    # All 7 question types should be represented
    assert len(types_seen) == 7
