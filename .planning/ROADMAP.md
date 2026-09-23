# ROADMAP.md — JEV-Gated Adaptive CoT for Equity Research

**Milestone:** M1 — Research System v1  
**Status:** In Progress  
**Updated:** 2026-09-23

---

## Milestone 1 — Research System v1

> Build the full measurement apparatus: pipeline conditions A/B/C, JEV classifier, benchmark dataset, evaluation suite, and factorial experiment runner.

---

### Phase 1 — Repo Scaffolding & Config System
**Status:** `[x] done`  
**Source:** PRD Chunk 0  
**Dependencies:** none

**Objective:** Create the foundational project skeleton that every later component builds on.

**Deliverables:**
- Full repository directory structure (per §10 of PRD)
- `config.py` — YAML config loader with pydantic validation, covering all fields in §6.6
- `configs/base.yaml` — example base configuration file
- Structured JSON logging infrastructure (`logs/`)
- pytest test runner setup + CI stub (GitHub Actions)
- `pyproject.toml` / `uv.lock` with initial dependencies
- `README.md` with project overview and "how to run" instructions
- Initial git commit

**Acceptance Criteria:**
- Loading a sample config produces a validated, typed config object; fails loudly on invalid input
- `pytest` passes on the stub codebase (empty tests pass, no import errors)
- `uv sync` completes and installs all dependencies from lockfile

**Non-goals:** No LLM calls, no retrieval, no JEV.

---

### Phase 2 — Research Spec as Machine-Readable Artifacts
**Status:** `[x] done`  
**Source:** PRD Chunk 1  
**Dependencies:** Phase 1

**Objective:** Freeze the core research vocabulary as shared code artifacts so all later phases import from a single source of truth.

**Deliverables:**
- `controller/actions.py` — Action enum (`CONTINUE | RETRIEVE | COMPUTE | BRANCH | STOP | ESCALATE`)
- `configs/conditions/vanilla.yaml` — Condition A preset
- `configs/conditions/selfgate.yaml` — Condition B preset
- `configs/conditions/jevgate.yaml` — Condition C preset
- `evaluation/metrics_registry.py` — Metrics registry (names, types, formulas) as stubs

**Acceptance Criteria:**
- Every later phase imports the action enum and condition presets rather than redefining them
- Importing `metrics_registry.py` produces a complete list of all metrics from §4 (H1–H6) without errors

**Non-goals:** No metric *implementation*, no training, no LLM calls.

---

### Phase 3 — Equity Research Benchmark: Schema & Loader
**Status:** `[ ] pending`  
**Status:** `[x] done`  
**Source:** PRD Chunk 2  
**Dependencies:** Phase 1

**Objective:** Define the canonical data format and build the dataset infrastructure.

**Deliverables:**
- `data/schema.py` — pydantic schema for Appendix C (id, company, period, question, type, documents, gold_claims, required_evidence, difficulty)
- `data/validator.py` — CLI validator that rejects malformed examples with actionable errors
- `data/split.py` — Company-level (70/15/15) + temporal split CLI with deterministic seed
- `data/raw/sample_examples.jsonl` — ≥1 hand-crafted example per type A–G, sourced from Phase 1 sectors (tech/software + industrials/retail)
- Unit tests: splitter produces zero company overlap between train and test sets; output is deterministic given same seed

**Acceptance Criteria:**
- Splitter output is bit-for-bit identical across runs with the same seed
- A pytest assertion confirms zero company overlap between train and test
- All 7 question types (A–G) have at least one example in `sample_examples.jsonl`

**Non-goals:** Full-scale data collection; Phase 2/3 sectors; real filings integration.

---

### Phase 4 — Retrieval Layer
**Status:** `[ ] pending`  
**Source:** PRD Chunk 3  
**Dependencies:** Phase 3

**Objective:** Build a pluggable retrieval interface backed by FAISS + sentence-transformers.

**Deliverables:**
- `retrieval/base.py` — abstract retrieval interface (company + period + document_type → ranked chunks)
- `retrieval/faiss_retriever.py` — FAISS + sentence-transformers implementation
- `retrieval/ingest.py` — ingestion script for local documents into FAISS index
- Unit tests: given company/period, retriever returns chunks with correct primary/secondary tagging; latency logged per call

**Acceptance Criteria:**
- Retrieval works end-to-end on seeded documents
- Per-call latency is measured and logged in the trajectory schema
- Adding a new backend requires only implementing the `base.py` interface (swap test)

**Non-goals:** Real SEC filings integration; production-scale indexing.

---

### Phase 5 — Vanilla LLM Baseline (Condition A)
**Status:** `[ ] pending`  
**Source:** PRD Chunk 4  
**Dependencies:** Phase 4

**Objective:** Implement the non-adaptive baseline and the shared LLM client wrapper used by all conditions.

**Deliverables:**
- `models/llm/client.py` — LLM wrapper with per-call token count, cost, and latency tracking; swappable backend via config (Gemini 1.5 Pro / Flash)
- `experiments/run_vanilla.py` — End-to-end vanilla run: question → retrieval → LLM → logged trajectory
- One logged trajectory per sample question, following Appendix B schema

**Acceptance Criteria:**
- `run_vanilla.py` on the sample dataset produces one logged trajectory per question with cost/latency/tokens populated
- Switching `llm_backend` in config (Pro → Flash) requires no code change

**Non-goals:** Adaptive control; JEV; any evaluation beyond logging.

---

### Phase 6 — Structured State Extractor
**Status:** `[ ] pending`  
**Source:** PRD Chunk 5  
**Dependencies:** Phase 5

**Objective:** Build the component that converts a live reasoning trace into the structured state JSON that JEV will consume.

**Deliverables:**
- `controller/state.py` — Typed state object (Appendix A schema) + extraction function
- Ablation switch: `--emit-raw-cot` flag (off by default) that also emits raw CoT trace
- Unit tests: for a fixed synthetic trajectory, extractor produces the exact expected JSON (golden test for every state field)

**Acceptance Criteria:**
- Golden test passes: fixed input → exact expected JSON output
- Raw CoT path is never triggered unless the ablation flag is explicitly set

**Non-goals:** JEV training; controller loop; any downstream use of the state.

---

### Phase 7 — Adaptive CoT with LLM Self-Gate (Condition B) + Controller
**Status:** `[ ] pending`  
**Source:** PRD Chunk 6  
**Dependencies:** Phase 6

**Objective:** Build the full adaptive controller loop and the LLM self-gate, completing Condition B.

**Deliverables:**
- `controller/loop.py` — Deterministic controller: `state → gate_decision → dispatch(action)`
- `controller/limits.py` — Hard safety guards (max steps, max retrievals, max branches, max latency, max cost) as shared code for all conditions
- `models/llm/self_gate.py` — LLM self-gate: prompt LLM for structured action + confidence, parse response
- `controller/tools/calculator.py` — Real calculator tool for COMPUTE actions (YoY %, CAGR, etc.)
- `controller/tools/branch.py` — BRANCH fork + merge logic
- `controller/synthesizer.py` — STOP → final answer from accumulated evidence/claims
- `experiments/run_selfgate.py` — End-to-end Condition B runner
- Pathological loop test: forced repeated RETRIEVE confirms max-limit guard triggers ESCALATE/STOP

**Acceptance Criteria:**
- Full Appendix B trajectories produced (every step: state, decision, confidence, latency, cost logged)
- Pathological loop test passes
- Safety limits apply identically to B and C (verified by shared `limits.py`)

**Non-goals:** JEV; Condition C; evaluation metrics.

---

### Phase 8 — Trajectory Collection for JEV Training
**Status:** `[ ] pending`  
**Source:** PRD Chunk 7  
**Dependencies:** Phase 7

**Objective:** Generate the raw `(state, action)` training pairs for JEV by running Condition B across the full seed dataset.

**Deliverables:**
- `experiments/collect_trajectories.py` — Runs Condition B on the seed dataset, stores all trajectories
- `data/processed/trajectories.jsonl` — Raw trajectory logs
- `data/processed/jev_examples.jsonl` — One `(state, action)` pair per controller step

**Acceptance Criteria:**
- Every row in `jev_examples.jsonl` has a valid state JSON matching Appendix A schema exactly
- One row per controller step across all trajectories (count verifiable)

**Non-goals:** Labeling; JEV training; evaluation.

---

### Phase 9 — JEV Label Generation Pipeline
**Status:** `[ ] pending`  
**Source:** PRD Chunk 8  
**Dependencies:** Phase 8

**Objective:** Build the three-stage label pipeline (rules → LLM judge → human validation) that produces final JEV training labels.

**Deliverables:**
- `models/jev/labeling/rules.py` — Rule-based labeler (evidence coverage, requires_calculation, contradiction, etc.)
- `models/jev/labeling/llm_judge.py` — LLM-judge relabeling pass for ambiguous rule outputs
- `models/jev/labeling/review_queue.py` — Human review CLI/export (CSV/JSON queue for confirm/override)
- `data/train/jev_labeled.jsonl` — Final labeled dataset with `label_source: rule | llm | human` per row
- Label distribution report (per action, per source) to surface class imbalance

**Acceptance Criteria:**
- Every labeled example has a non-empty `label_source`
- Report script prints label distribution per action and per source

**Non-goals:** JEV model training; any evaluation metric.

---

### Phase 10 — JEV Model Training
**Status:** `[ ] pending`  
**Source:** PRD Chunk 9  
**Dependencies:** Phase 9

**Objective:** Train JEV (XGBoost/LightGBM) on the labeled state→action pairs.

**Deliverables:**
- `models/jev/model.py` — JEV model class (GBT-based, config-driven architecture switch)
- `models/jev/train.py` — Training script using company-level split from Phase 3
- `models/jev/eval.py` — Validation evaluation script
- JEV-S, JEV-M, JEV-L variants (controlled by config: max_depth, n_estimators, etc.)
- `models/jev/checkpoints/` — Per-variant checkpoints + parameter count + inference latency table

**Acceptance Criteria:**
- Trained model beats majority-class baseline on validation accuracy
- Per-size latency and parameter counts logged to a comparison table
- Each size variant has a standalone checkpoint loadable without retraining

**Non-goals:** Calibration; integration into controller; test-set evaluation (JEV must be frozen first).

---

### Phase 11 — JEV Calibration
**Status:** `[ ] pending`  
**Source:** PRD Chunk 10  
**Dependencies:** Phase 10

**Objective:** Calibrate JEV's confidence outputs and freeze the model artifact.

**Deliverables:**
- `evaluation/calibration.py` — ECE, Brier score, class-wise calibration, reliability diagram
- `models/jev/calibrate.py` — Temperature scaling + isotonic regression calibration scripts
- `models/jev/checkpoints/jev_frozen_v1/` — Frozen, calibrated model artifact (version-tagged)

**Acceptance Criteria:**
- Post-calibration ECE is measurably lower than pre-calibration on the held-out calibration split
- Frozen model is version-tagged; a check prevents any retraining against test data from this point

**Non-goals:** Controller integration; test-set evaluation.

---

### Phase 12 — JEV Integration into Controller (Condition C)
**Status:** `[ ] pending`  
**Source:** PRD Chunk 11  
**Dependencies:** Phase 11, Phase 7

**Objective:** Wire the frozen JEV model into the controller as the gate, completing Condition C.

**Deliverables:**
- `models/jev/gate.py` — JEV gate implementing the same interface as `self_gate.py`
- `experiments/run_jevgate.py` — End-to-end Condition C runner
- Diff test: B and C runs on same questions produce trajectories differing only in gating decisions/source

**Acceptance Criteria:**
- Condition C runs end-to-end on sample dataset
- Diff test confirms retrieval, tools, and synthesis code paths are byte-identical between B and C
- Confidence-threshold fallback (ESCALATE) is config-toggleable (off by default for primary comparison)

**Non-goals:** Full evaluation; ablations; factorial matrix.

---

### Phase 13 — Evaluation Suite: Efficiency, Latency & Cost
**Status:** `[ ] pending`  
**Source:** PRD Chunk 12  
**Dependencies:** Phase 8 (trajectory format); can run in parallel with Phases 9–12

**Objective:** Build the efficiency/latency/cost evaluation layer over logged trajectories.

**Deliverables:**
- `evaluation/efficiency.py` — Aggregates: LLM calls, reasoning steps, tokens (in/out/total), retrieval calls, compute calls, branches, \$ cost
- `evaluation/latency.py` — Latency breakdown: total wall-clock, LLM inference, gate inference, retrieval, tool
- Report generator: per-condition summary tables

**Acceptance Criteria:**
- Running on Condition A/B trajectories produces correct, spot-checked aggregate numbers
- All metrics match the names in `metrics_registry.py` (no new names introduced)

---

### Phase 14 — Evaluation Suite: Grounding & Answer Quality
**Status:** `[ ] pending`  
**Source:** PRD Chunk 13  
**Dependencies:** Phase 8 (trajectory format); can run in parallel with Phases 9–12

**Objective:** Build the grounding precision/recall and multi-dimensional answer quality evaluation layer.

**Deliverables:**
- `evaluation/grounding/claim_extractor.py` — Extracts claims from a final answer
- `evaluation/grounding/entailment.py` — LLM-judge claim→evidence entailment scoring (versioned prompt)
- `evaluation/grounding/metrics.py` — Grounding Precision + Grounding Recall
- `evaluation/quality/scorer.py` — Multi-dimensional quality scorer (7 dimensions)
- `evaluation/human_eval_export.py` — Blinded human-evaluation export (no condition metadata)

**Acceptance Criteria:**
- On hand-labeled gold examples, automated grounding precision/recall match human judgment within agreed tolerance
- Human-eval export contains no condition-identifying metadata

---

### Phase 15 — Full Factorial Experiment Runner
**Status:** `[ ] pending`  
**Source:** PRD Chunk 14  
**Dependencies:** Phases 5, 12, 13, 14

**Objective:** Run the complete experimental matrix and produce the primary comparison results.

**Deliverables:**
- `experiments/run_matrix.py` — Matrix runner: `{Pro, Flash} × {Vanilla, Self-gate, JEV-gate}` on full test set
- `logs/matrix_runs/` — All trajectories + aggregate metrics per (LLM × condition) cell
- Pre-flight diff check (reuses Phase 12 diff test) run before each matrix cell

**Acceptance Criteria:**
- One full matrix run on seed dataset completes end-to-end
- Results table has every (LLM × condition) cell populated
- Full config provenance captured per run

---

### Phase 16 — Ablation Suite
**Status:** `[ ] pending`  
**Source:** PRD Chunk 15  
**Dependencies:** Phase 15

**Objective:** Run all ablations (state features, raw-CoT vs structured, JEV size).

**Deliverables:**
- `experiments/ablations/feature_ablations.py` — 6 JEV feature-ablation variants
- `experiments/ablations/raw_cot_ablation.py` — Raw CoT vs structured state comparison
- `experiments/ablations/size_ablation.py` — JEV-S/M/L comparison
- Per-ablation frozen checkpoint + evaluation report

**Acceptance Criteria:**
- Each ablation variant has its own frozen checkpoint and evaluation report
- All ablation results are directly comparable to the main JEV result (same eval pipeline, same test set)

---

### Phase 17 — Oracle Gate Experiment
**Status:** `[ ] pending`  
**Source:** PRD Chunk 16  
**Dependencies:** Phase 15

**Objective:** Establish the theoretical upper bound by running an oracle gate.

**Deliverables:**
- `experiments/run_oracle.py` — Oracle controller using gold trajectory annotations
- Oracle metrics sit at or above best of JEV/self-gate on efficiency (sanity check)

**Acceptance Criteria:**
- Oracle run completes and its metrics are a valid upper bound

---

### Phase 18 — Error Taxonomy & Failure Analysis
**Status:** `[ ] pending`  
**Source:** PRD Chunk 17  
**Dependencies:** Phase 15

**Objective:** Classify every trajectory into an error taxonomy and build the efficiency-win/grounding-loss cross-tabulation.

**Deliverables:**
- `analysis/error_taxonomy.py` — JEV + self-gate error classifiers; assigns each trajectory exactly one bucket (or "no error")
- Cross-tab report: efficiency wins × grounding failures

**Acceptance Criteria:**
- Every trajectory in a matrix run is classified
- Cross-tab flags any trajectory where efficiency win co-occurs with a grounding failure

---

### Phase 19 — Statistical Analysis & Final Reporting
**Status:** `[ ] pending`  
**Source:** PRD Chunk 18  
**Dependencies:** Phases 15, 16, 17, 18

**Objective:** Produce the final, publication-ready results summary.

**Deliverables:**
- `analysis/statistics.py` — Paired comparisons, mixed-effects analysis
- `analysis/plots.py` — Quality-vs-cost plot + reliability diagrams
- `paper/results_summary.md` — Auto-generated results document (tables + plots), reproducible from `logs/matrix_runs/` with a single command

**Acceptance Criteria:**
- Report is reproducible end-to-end from a single command
- No claim in the summary is stated without an accompanying CI or paired-test result

---

## Backlog (Post-M1)

- Phase 2 sector expansion: healthcare / biopharma
- Phase 3 sector expansion: financials, insurance, REITs
- Full-scale data collection (statistical power for paired comparisons)
- Real SEC EDGAR filings integration
- JEV retraining on larger labeled dataset
- Customer-facing API or UI surface (explicitly deferred from v1)

