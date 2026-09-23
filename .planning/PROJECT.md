# PROJECT.md — JEV-Gated Adaptive Chain-of-Thought for Equity Research

**Status:** Active — Milestone 1 in progress  
**Created:** 2026-09-23  
**Owner:** (fill in)  
**Type:** Research / Evaluation System  
**Stack:** Python 3.11 · uv · XGBoost/LightGBM · FAISS · Gemini 1.5 Pro + Flash

---

## 1. Vision

Build a rigorous, reproducible measurement apparatus that separates **LLM reasoning** from **control/routing decisions** inside an Adaptive Chain-of-Thought pipeline for equity research.

The core question: can a compact, calibrated classifier (JEV) replace LLM self-gating in an Adaptive CoT loop — reducing cost and latency — without materially degrading evidence grounding or answer quality?

---

## 2. Problem

Adaptive CoT systems today let the LLM decide at every step whether to keep reasoning, retrieve more evidence, run a calculation, branch, or stop. This is simple but potentially wasteful:

- The LLM re-uses expensive compute for a narrow *control* task.  
- Its stopping/retrieval behavior is entangled with its verbose reasoning style.  
- Control decisions are hard to audit, calibrate, or improve independently.

---

## 3. Approach

Three pipeline **conditions** share identical retrieval, tools, and synthesis — only the **gate** differs:

| Condition | Gate |
|---|---|
| A — Vanilla | No adaptive control (single LLM pass) |
| B — Self-gate | LLM decides next action at each step |
| C — JEV-gate | Compact trained classifier (JEV) decides |

**JEV** maps a structured state snapshot → one of six actions: `CONTINUE | RETRIEVE | COMPUTE | BRANCH | STOP | ESCALATE`.

Primary comparison: **B vs C** (same LLM, same everything, gate is the only variable).

---

## 4. Research Hypotheses

| # | Hypothesis |
|---|---|
| H1 | JEV uses fewer unnecessary operations than self-gating |
| H2 | JEV lowers end-to-end latency (including JEV overhead) |
| H3 | JEV lowers cost per completed query |
| H4 | Grounding quality doesn't materially degrade |
| H5 | Answer quality stays comparable |
| H6 | JEV's confidence is calibrated |

---

## 5. Scope & Non-Goals

**In scope (v1):**
- Three pipeline conditions sharing retrieval, tools, synthesis
- JEV: compact classifier, calibrated, with confidence thresholds
- Equity research benchmark (Phase 1: tech/software + industrials)
- Full evaluation suite: efficiency, latency, cost, grounding, quality, calibration
- Factorial experiment (Gemini 1.5 Pro × Flash × {Vanilla, Self-gate, JEV-gate})
- Ablations: state features, raw-CoT vs structured, JEV size variants

**Explicitly out of scope (v1):**
- JEV is not a reasoning engine; it makes no investment recommendations
- No UI/customer-facing surface
- Phase 2 (healthcare) and Phase 3 (financials/REITs) sector expansions
- Real-time filings integration

---

## 6. Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| JEV architecture | XGBoost / LightGBM (GBT) | Compact, interpretable, fast inference, minimal dependencies |
| Retrieval (v1) | FAISS + sentence-transformers (local) | Unblocks dev without real filings; swappable interface |
| LLM backends | Gemini 1.5 Pro + Gemini 1.5 Flash | Cost contrast within same provider; Flash as cheap-gate test |
| Python version | 3.11 | Stable, well-supported by all key libs |
| Package manager | uv | Fast resolver, lockfile reproducibility |
| Config format | YAML (pydantic-validated) | Human-readable, version-controlled, typed |
| Logging | Structured JSON (jsonlines) | Machine-readable, replayable, query-able |
| Split strategy | Company-level (primary) + temporal (secondary) | Prevents leakage; tests temporal robustness |

---

## 7. Success Criteria

The project is successful if it produces a **defensible, controlled measurement** of:

1. Cost / latency / reasoning-step / tool-call deltas between self-gate and JEV-gate, **AND**
2. Whether grounding / factual accuracy / completeness / calibration stay within predefined acceptable bounds.

Both "JEV saves cost but grounding drops" and "JEV provides no benefit" are valid, publishable outcomes. The **measurement mechanism** is the deliverable, not a predetermined verdict.

---

## 8. Repository Structure

```
project/
├── .planning/           ← GSD planning artifacts (this directory)
├── data/
│   ├── raw/             ← Seed examples, source documents
│   ├── processed/       ← Trajectories, JEV training pairs
│   ├── train/           ← Labeled JEV training data
│   ├── validation/
│   └── test/
├── retrieval/           ← Retrieval interface + FAISS backend
├── models/
│   ├── jev/             ← JEV model, training, calibration
│   └── llm/             ← LLM client wrapper, self-gate
├── controller/          ← Loop, actions, state, limits
├── evaluation/          ← Grounding, quality, latency, cost, calibration
├── experiments/         ← Run scripts for all conditions + ablations
├── configs/             ← YAML config files + condition presets
├── logs/                ← Trajectory logs, matrix run outputs
├── analysis/            ← Stats, plots, error taxonomy
└── paper/               ← Results summary, figures
```

---

## 9. Key Constraints

- **Determinism**: Conditions B and C must share identical LLM, retrieval, tools, synthesis — gate is the ONLY variable.
- **Safety**: Hard caps on steps/retrievals/branches/latency/cost prevent pathological loops.
- **Auditability**: Every run is traceable to a config + version (model, prompt, dataset, seed, timestamp).
- **Model-agnosticism**: JEV input = structured state JSON only; never raw CoT text on the primary path.
- **Freeze discipline**: JEV frozen before it ever sees the test set.

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| Label quality — rule labels teach rules, not real boundary | Track human validation coverage per chunk |
| Grounding automation trust | Spot-check LLM-judge entailment vs human |
| Dataset scale (seed is small) | Treat Phase 1 results as provisional; separate data-collection workstream |
| Sector generalization | Phase 1 (clean 10-Ks) ≠ Phase 2/3 — flag explicitly in paper |
| Backend reproducibility | Pin exact Gemini API version + temperature in config |

