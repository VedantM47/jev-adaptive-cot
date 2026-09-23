# REQUIREMENTS.md — JEV-Gated Adaptive CoT for Equity Research

**Milestone:** M1 — Research System v1  
**Status:** Approved  
**Source:** PRD v1 (PRD_JEV_Adaptive_CoT.md)

---

## Functional Requirements

### FR-01 · Action Space
The system shall define and enforce a fixed 6-action space: `CONTINUE | RETRIEVE | COMPUTE | BRANCH | STOP | ESCALATE`. All components (controller, gates, logging, evaluation) shall reference this shared enum.

### FR-02 · Three Pipeline Conditions
The system shall implement three named, reproducible pipeline conditions:
- **Condition A** — Vanilla: single LLM pass, no adaptive control
- **Condition B** — Self-gate: LLM chooses next action at each step
- **Condition C** — JEV-gate: compact trained classifier chooses next action

All three conditions shall share identical retrieval, tool, and synthesis code paths. The gate is the **only** variable between B and C.

### FR-03 · Structured State Extractor
The system shall extract a structured state JSON (Appendix A schema) from `(question, evidence, reasoning-so-far, tool-call-history)` without passing raw CoT text through as a feature on the primary path. Raw CoT shall be gated behind an explicit ablation switch.

### FR-04 · Deterministic Controller
The controller loop shall be deterministic: given the same gate decision, it executes the same action. Hard safety limits (max steps, max retrievals, max branches, max latency, max cost) shall apply identically to Conditions B and C.

### FR-05 · COMPUTE Tool
The system shall implement a real calculator tool for financial computations (e.g., YoY % change, CAGR). COMPUTE decisions shall invoke this tool.

### FR-06 · BRANCH Reasoning
BRANCH shall create a parallel reasoning fork that is merged before synthesis.

### FR-07 · ESCALATE Fallback
If gate confidence < configurable threshold → ESCALATE → deterministic fallback (LLM self-gate or STOP+synthesize). This is a secondary experiment, toggled via config.

### FR-08 · JEV Model
JEV shall be a compact classifier (XGBoost/LightGBM) trained on `(structured_state → action)` pairs with calibrated confidence. Three size variants (JEV-S, JEV-M, JEV-L) shall be supported via config switch. Inference latency and parameter count shall be logged.

### FR-09 · JEV Label Pipeline
Labels shall be generated in three stages: (1) rule-based bootstrap, (2) LLM-judge review, (3) human validation queue. Label provenance (`rule | llm | human`) shall be recorded per example.

### FR-10 · JEV Calibration
Post-training calibration (temperature scaling; isotonic regression fallback) shall be applied using a calibration split separate from the test set. The frozen, calibrated model artifact shall be version-tagged.

### FR-11 · Retrieval Layer
A retrieval interface with pluggable backends shall be implemented. v1 backend: FAISS + sentence-transformers over local seeded documents. Results shall include source metadata (primary vs. secondary, company, period, document type).

### FR-12 · Equity Research Benchmark
The benchmark shall support question types A–G (factual retrieval, comparison, multi-document synthesis, contradiction detection, calculation, causal/evidence-grounded analysis, evidence sufficiency). The schema from Appendix C shall be the canonical format.

### FR-13 · Data Splits
Company-level split (70/15/15 train/val/test, primary) and temporal split (secondary) shall be implemented as a deterministic CLI script. Zero company overlap between train and test is a hard constraint.

### FR-14 · Trajectory Logging
Every trajectory shall be persisted in the Appendix B schema format: `(step, state, decision, confidence, latency, cost)` per step, plus aggregate `(total latency, total cost, grounding_score, answer_score)`. All trajectories must be replayable from logs.

### FR-15 · Reproducibility Config
Every experiment run shall write a config file capturing: LLM, JEV version, prompt version, retrieval version, dataset version, temperature, max tokens, max steps, tool limits, random seed, timestamp.

### FR-16 · Evaluation Suite — Efficiency & Latency
Metrics: LLM calls, reasoning steps, input/output tokens, retrieval calls, computation calls, branches, total tokens, estimated \$ cost. Latency breakdown: total wall-clock, LLM inference, gate inference, retrieval, tool.

### FR-17 · Evaluation Suite — Grounding
Grounding Precision (`supported_claims / cited_claims`) and Grounding Recall (`supported_required_claims / required_claims`) shall be computed per trajectory. Claim extraction and entailment scoring shall use an LLM-judge with a versioned, auditable prompt.

### FR-18 · Evaluation Suite — Answer Quality
Multi-dimensional scoring: factual accuracy, evidence support, citation correctness, completeness, calculation correctness, contradiction handling, uncertainty calibration. Blinded human-evaluation export (no condition labels) shall be available.

### FR-19 · Evaluation Suite — Calibration
ECE, Brier score, class-wise calibration, and reliability diagram generation shall be implemented for JEV confidence assessment.

### FR-20 · Factorial Experiment Runner
An automated matrix runner shall execute `{Gemini 1.5 Pro, Gemini 1.5 Flash} × {Vanilla, Self-gate, JEV-gate}` on the full test set, pairing identical questions across conditions.

### FR-21 · Ablation Suite
State-feature ablations (full / evidence-only / reasoning-only / remove-confidence / remove-contradiction / remove-question-type), raw-CoT-vs-structured ablation, and JEV-S/M/L size ablation shall each produce a frozen checkpoint and evaluation report.

### FR-22 · Oracle Gate
An oracle controller that selects the "correct" next action (from gold trajectory annotations) shall be implemented as an upper-bound baseline.

### FR-23 · Error Taxonomy
JEV and self-gate error types shall be classified per trajectory. An efficiency-win-but-grounding-loss cross-tabulation shall be produced.

### FR-24 · Statistical Analysis
Paired comparisons (mean, median, std, 95% CI, paired test), mixed-effects analysis (LLM × gating), and a quality-vs-cost plot shall be generated. All claims in the results summary shall have an accompanying CI or paired-test result.

---

## Non-Functional Requirements

### NFR-01 · Determinism
Same config + seed → identical output, always.

### NFR-02 · Model-Agnosticism
JEV input = structured state JSON only. No raw CoT text on the primary path.

### NFR-03 · Auditability
Every label-generation step, every model training run, every experiment run is traceable to config + version.

### NFR-04 · Safety Guards
Hard caps on steps, retrievals, branches, latency, and cost must prevent pathological controller loops.

### NFR-05 · Freeze Discipline
JEV must never see the final test set before being frozen. Calibration uses a separate held-out split.

### NFR-06 · Observability
Latency must be measured separately per component (LLM, gate, retrieval, tool). No aggregate-only timing.

### NFR-07 · Portability
Python 3.11, uv-managed dependencies, no hard-coded paths, all configuration via YAML.

---

## Constraints & Boundaries

- **v1 sectors:** Phase 1 only (tech/software + industrials/retail). Phase 2 (healthcare) and Phase 3 (financials/REITs) are explicitly deferred.
- **No UI.** This is a research + evaluation system.
- **JEV is not a reasoner.** It makes no investment recommendations.
- **Seed dataset:** small enough to unblock development; statistical power depends on later scale-up (separate workstream).

