# Research Notes — JEV-Gated Adaptive CoT for Equity Research

**Created:** 2026-09-23  
**Purpose:** Domain context and implementation guidance for the development team

---

## 1. Stack Compatibility Notes

### Python 3.11 + uv
- `uv` uses PEP 621 `pyproject.toml`; lock file is `uv.lock`
- Key command: `uv sync` installs from lockfile; `uv add <pkg>` adds and locks
- uv is significantly faster than pip for resolution; good for CI reproducibility

### XGBoost / LightGBM for JEV
- Both support multi-class classification natively (6 actions = 6-class problem)
- **XGBoost:** `objective='multi:softprob'`, `num_class=6` → outputs per-class probabilities (needed for confidence + calibration)
- **LightGBM:** `objective='multiclass'`, `num_class=6` → similar
- Both support feature importance — useful for state-feature ablations (Phase 16)
- Serialization: `model.save_model('jev.json')` (XGBoost) or `model.save_model('jev.txt')` (LightGBM) — use these for the frozen artifact, not pickle
- Temperature scaling for calibration: applies a scalar `T` to logits before softmax; isotonic regression as fallback — `sklearn.isotonic.IsotonicRegression` can calibrate per-class probabilities

### FAISS + sentence-transformers
- `sentence-transformers` model recommendation for financial text: `all-MiniLM-L6-v2` (fast, good quality) or `BAAI/bge-small-en-v1.5` (better for retrieval)
- FAISS index type for small seed dataset: `IndexFlatL2` (exact search, no training needed)
- For larger scale: `IndexIVFFlat` (requires training, faster at scale)
- Chunk size for financial documents: 512 tokens with 50-token overlap is a good starting point

### Gemini API
- Use `google-generativeai` Python package
- Pro: `gemini-1.5-pro-latest` | Flash: `gemini-1.5-flash-latest`
- Token counting: `model.count_tokens(content)` before calling
- Cost tracking: Pro ≈ \$3.50/1M input tokens + \$10.50/1M output; Flash ≈ \$0.35/1M + \$1.05/1M (verify current pricing)
- Structured output: use `response_schema` with `generation_config` for JSON-mode gate decisions

---

## 2. Action Space Design Notes

The 6-action space maps cleanly to controller dispatch:

| Action | Controller behavior |
|---|---|
| `CONTINUE` | Run another LLM reasoning step on current evidence |
| `RETRIEVE` | Call retrieval layer with updated query (derived from state) |
| `COMPUTE` | Call calculator tool with parameters extracted from reasoning trace |
| `BRANCH` | Fork reasoning into N parallel paths (N configurable, default 2); merge before synthesis |
| `STOP` | Invoke synthesizer on accumulated evidence/claims |
| `ESCALATE` | Trigger fallback policy (configurable: LLM self-gate or STOP+synthesize) |

Safety guard trigger order: check limits BEFORE dispatching any action.

---

## 3. State Schema Implementation Notes (Appendix A)

Key extraction challenges:
- `evidence.coverage` — requires tracking which required_evidence items have been addressed; needs `required_evidence` from the dataset schema at extraction time
- `evidence.agreement / contradiction` — simple heuristic: compare top-K retrieved chunks; contradiction flag if chunks from same source have conflicting numerical values
- `reasoning.confidence_delta` — track rolling confidence across steps; delta = confidence[t] - confidence[t-1]
- `reasoning.unresolved_claims` — count claims in current reasoning that lack cited evidence (LLM-generated, needs parsing)
- `task.complexity` — static per question type (e.g., factual=0.3, causal=0.8); can be refined later

For v1: `confidence` in the reasoning block should be estimated from the LLM's own stated uncertainty (parse from CoT) — but this creates a soft dependency on LLM wording. Alternative: use retrieval coverage as a proxy for confidence.

---

## 4. Trajectory Logging Schema (Appendix B) — Implementation Notes

Use `jsonlines` library for streaming writes (important for long runs).

Each trajectory file: one JSON object per trajectory. Trajectory contains:
```json
{
  "run_id": "...",          // unique run identifier
  "config_hash": "...",     // hash of the run config (for provenance)
  "query_id": "EQ_001",
  "model": "gemini-1.5-pro",
  "condition": "JEV",
  "gate_version": "jev_frozen_v1",
  "steps": 4,
  "trajectory": [...],
  "latency_breakdown": {
    "total": 11.2,
    "llm_inference": 8.1,
    "gate_inference": 0.04,
    "retrieval": 2.1,
    "tools": 0.96
  },
  "cost": 0.09,
  "token_breakdown": {
    "llm_input": 12000,
    "llm_output": 1800,
    "total": 13800
  },
  "grounding_score": 0.94,
  "answer_score": 0.91
}
```

Recommend adding `config_hash` and `gate_version` to the schema beyond what Appendix B shows — these are essential for provenance.

---

## 5. Company-Level Split Logic

The split must never leak: if a company appears in train, all its questions are in train.

```python
import hashlib


def company_hash(company_id: str, seed: int) -> float:
    h = hashlib.md5(f"{company_id}:{seed}".encode()).hexdigest()
    return int(h, 16) / (16**32)  # deterministic float in [0, 1)


# Then: < 0.70 → train, < 0.85 → val, else → test
```

This avoids shuffling issues and is truly deterministic across platforms.

---

## 6. Evaluation Metrics Reference

### Grounding
- **Grounding Precision** = `|supported_cited_claims| / |cited_claims|`
- **Grounding Recall** = `|supported_required_claims| / |required_claims|` (required_claims from gold)

### Calibration
- **ECE** = Σ_b (|B_b|/n) × |acc(B_b) - conf(B_b)| over M bins
- **Brier Score** = (1/N) Σ (p̂ - y)² (lower is better)
- Reliability diagram: x-axis = mean confidence per bin, y-axis = fraction correct; perfect calibration = diagonal

### Efficiency
- **Ops saved** = `steps_selfgate - steps_jevgate` per matched pair (same question, same LLM)
- **Cost ratio** = `cost_jevgate / cost_selfgate`

---

## 7. LLM Self-Gate Prompt Design

The self-gate prompt should output structured JSON to enable reliable parsing:

```
System: You are a reasoning controller. Given the current state of a financial analysis task,
decide the next action. Output ONLY a JSON object with:
{"action": "<ACTION>", "confidence": <0-1>, "reasoning": "<one sentence>"}
where <ACTION> is one of: CONTINUE, RETRIEVE, COMPUTE, BRANCH, STOP, ESCALATE.

State:
{state_json}
```

Use `response_schema` in Gemini's structured output mode to enforce this. Log the raw response before parsing for debugging.

---

## 8. Phase 1 Sector — Suggested Seed Companies

For the minimum viable seed dataset (Phase 3), suggested companies that have clean, consistent public filings:

**Tech/Software (examples):**
- Microsoft (MSFT) — highly structured 10-K, well-segmented revenue
- Salesforce (CRM) — SaaS metrics, good for multi-period comparison
- Adobe (ADBE) — subscription revenue, clear segment reporting

**Industrials (examples):**
- Caterpillar (CAT) — input cost/margin compression narratives
- 3M (MMM) — diversified, good for comparison/synthesis questions
- Honeywell (HON) — mix of tech + industrial, causal analysis rich

Use FY2022 + FY2023 filings for Phase 1 (readily available; pre-training cutoff considerations for LLM evaluation).

---

## 9. Key Papers / Prior Work to Note

- **Adaptive RAG** (Jeong et al., 2024) — adaptive retrieval based on query complexity; similar problem but without a separate gate model
- **Self-RAG** (Asai et al., 2023) — LLM learns to generate reflection tokens for retrieval decisions; closest prior work to Condition B
- **FinRAG / FinBench** — financial QA benchmarks; review for overlap avoidance
- **REACT** (Yao et al., 2022) — reasoning + acting paradigm; foundational for adaptive CoT
- **Calibration of LLMs** (Kadavath et al., 2022) — baseline for LLM confidence calibration; JEV calibration should outperform

---

## 10. Risk Mitigations

### Label quality
- Track `label_source` distribution in the label report (Phase 9)
- Target: ≥20% of ambiguous cases reviewed by human before JEV training
- Flag any action class with <10 human-validated examples as "low confidence" in the paper

### Grounding automation
- Run automated grounding vs. human grounding on a stratified sample (all 7 question types) before trusting automated scores
- Report inter-rater agreement (Cohen's κ) between LLM-judge and human

### Backend reproducibility
- Pin `google-generativeai` package version in `uv.lock`
- Log exact model version string returned by the API (not just the alias)
- Set temperature=0 for gate prompts; allow temperature>0 only for the synthesizer

### Pathological loops
- Implement a global trajectory hash at each step; if state_hash repeats → ESCALATE immediately (catches loops the step-counter alone might miss if BRANCH inflates step count)

