# PLAN.md — Phase 3: Equity Research Benchmark: Schema & Loader

**Phase:** 3 of 19  
**Status:** Ready for execution  
**Depends on:** Phase 1  
**Blocks:** Phase 4 (Retrieval)  

---

## Objective

Define the canonical data format for the Equity Research Benchmark and build the dataset infrastructure (schema validation, data splitting).

---

## Tasks

### T1 · Schema Definition — `src/jev_cot/data/schema.py`
**Type:** code  
**Files:** `src/jev_cot/data/schema.py`, `src/jev_cot/data/__init__.py`  
**Requirement:** FR-12 (Equity Research Benchmark)

Define `BenchmarkExample` using Pydantic (id, company, period, question, type, documents, gold_claims, required_evidence, difficulty). Also define `QuestionType` enum (A-G: factual_retrieval, comparison, multi_document_synthesis, contradiction_detection, calculation, causal_analysis, evidence_sufficiency).

---

### T2 · Validator CLI — `src/jev_cot/data/validator.py`
**Type:** code  
**Files:** `src/jev_cot/data/validator.py`

Create a CLI script that takes a `.jsonl` file and validates each line against `BenchmarkExample`. It should print actionable errors for malformed rows.

---

### T3 · Splitter CLI — `src/jev_cot/data/split.py`
**Type:** code  
**Files:** `src/jev_cot/data/split.py`  
**Requirement:** FR-13 (Data Splits)

Implement company-level split (70/15/15) + temporal split. Must be deterministic via a random seed (using MD5 hashing of the company name + seed to avoid shuffling issues). Outputs `train.jsonl`, `val.jsonl`, `test.jsonl`.

---

### T4 · Sample Data Generation — `data/raw/sample_examples.jsonl`
**Type:** data  
**Files:** `data/raw/sample_examples.jsonl`

Seed at least 7 hand-crafted examples (one for each of the 7 question types) sourced from Phase 1 sectors (tech/software + industrials/retail).

---

### T5 · Tests & Verification
**Type:** test  
**Files:** `tests/test_data_split.py`, `tests/test_data_schema.py`

Write unit tests to verify:
1. The splitter produces zero company overlap between train and test.
2. The splitter output is deterministic given the same seed.
3. The sample dataset passes the schema validation.

---

### T6 · Commit
**Type:** git  
Commit changes for Phase 3.

