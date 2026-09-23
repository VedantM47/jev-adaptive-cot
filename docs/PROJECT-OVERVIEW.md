# JEV-Gated Adaptive Chain-of-Thought for Equity Research
### Full Project Context — Problem, Approach, Architecture, Build Plan

> Generated 2026-09-23. Sourced from `.planning/PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, and `.planning/codebase/*.md`. Sections marked **(general context)** are my own domain knowledge, not pulled from project docs — flagged so you know what's sourced vs. added.

---

## 1. Problem Statement

Modern **Adaptive Chain-of-Thought (CoT)** systems — the kind used for equity research, financial due diligence, and multi-step document Q&A — let the LLM itself decide, at every reasoning step, whether to keep reasoning, retrieve more evidence, run a calculation, branch into parallel sub-investigations, or stop and answer.

This is simple to build but has three specific costs:

1. **The LLM burns expensive compute on a narrow control task.** Deciding "should I retrieve again?" doesn't need a frontier model — but today it's answered by one anyway, on every step, of every query.
2. **Control behavior is entangled with reasoning style.** A verbose model's "let me think about this more" and a terse model's actual stopping logic aren't separable — you can't audit or improve routing without touching the reasoning itself.
3. **Control decisions are unauditable and uncalibratable.** There's no confidence score, no error taxonomy, no way to say "the gate was 73% confident and wrong" — because the LLM's action choice is just another generation, not a measured, calibrated output.

**Core question this project answers:** *Can a small, cheap, calibrated classifier replace the LLM as the "gate" that decides the next action — without losing answer quality or evidence grounding?*

---

## 2. Approach — What We're Actually Building

Three pipeline **conditions**, built so they share every component except one:

| Condition | Name | Who decides the next action |
|---|---|---|
| **A** | Vanilla | Nobody — single LLM pass, no adaptive loop |
| **B** | Self-gate | The LLM itself (prompted for a structured decision) |
| **C** | JEV-gate | **JEV** — a compact trained classifier |

**JEV** (the thing we're building and evaluating) maps a structured snapshot of "where the reasoning currently stands" → one of six actions:

```
CONTINUE | RETRIEVE | COMPUTE | BRANCH | STOP | ESCALATE
```

The entire project is a **controlled scientific comparison**: B vs. C, same LLM, same retrieval, same tools, same synthesis — the gate is the *only* variable. This is the whole point of the architecture: if conditions B and C differ in outputs, it can only be because of the gating decision, not because something else silently changed.

### Research Hypotheses (what "success" means)

| # | Hypothesis |
|---|---|
| H1 | JEV performs fewer unnecessary operations than the LLM self-gate |
| H2 | JEV lowers end-to-end latency (JEV's own inference cost included) |
| H3 | JEV lowers cost-per-query |
| H4 | Evidence grounding doesn't materially degrade |
| H5 | Answer quality stays comparable |
| H6 | JEV's confidence output is calibrated (a 90%-confidence decision is right ~90% of the time) |

Both outcomes are publishable: "JEV wins on cost, holds on quality" *and* "JEV provides no real benefit" are both valid results. **The measurement apparatus is the deliverable — not a predetermined verdict.**

---

## 3. Existing Market / Prior-Art Landscape **(general context)**

There's no competitor-analysis document in this project's planning files, so this section is my own framing, not sourced from your docs. Treat it as context, not project-specific research.

**Adjacent existing approaches:**
- **Agentic RAG frameworks** (LangGraph, LlamaIndex agents, CrewAI, AutoGPT-style loops) — these all use an LLM (often the same one doing the reasoning) to decide control flow. No compact/calibrated classifier gate is a standard pattern in these frameworks; routing is typically prompt-based.
- **Model routing / cascade systems** (e.g. "route easy queries to a small model, hard ones to a big model") — conceptually the closest prior art, but those route *between models*, not *between actions within one reasoning trace*. JEV is action-level, not model-level.
- **Classifier-based tool selection** in some production RAG pipelines — some products use small classifiers for "should I retrieve?" as a single binary gate, but rarely extended to a full 6-action space with calibration and a controlled A/B/C comparison methodology like this project does.
- **Equity research / financial LLM tools** (e.g. various "AI analyst" copilots) — these are consumer/enterprise products, not measurement systems. They don't publish controlled comparisons of gating strategies; this project's differentiator is that it's a **research instrument**, not a product.

**What differentiates this project:** it's not trying to ship a better equity-research assistant. It's building the *harness that can prove, with statistics, whether replacing LLM self-control with a cheap classifier is a good idea at all* — something the existing agent frameworks don't attempt to measure rigorously.

---

## 4. Explicit Scope

**In scope (v1):**
- 3 pipeline conditions sharing retrieval/tools/synthesis
- JEV: compact classifier, calibrated, confidence-thresholded
- Equity research benchmark (Phase-1 sectors: tech/software + industrials/retail)
- Full evaluation suite: efficiency, latency, cost, grounding, quality, calibration
- Factorial experiment: Gemini 1.5 Pro × Flash × {Vanilla, Self-gate, JEV-gate}
- Ablations: state features, raw-CoT-vs-structured, JEV size (S/M/L)

**Explicitly out of scope (v1):**
- JEV makes **no investment recommendations** — it's a control-flow classifier, not a reasoning engine
- **No UI, no customer-facing surface** — this is a research/evaluation system, not a product
- Healthcare and financials/REITs sectors (deferred to later milestones)
- Real-time SEC filings integration (uses seeded/synthetic documents in v1)

---

## 5. Technical Architecture

There is **no frontend and no traditional web middleware** — by design (see scope above). This is a Python research pipeline, not a web app. Here's the actual shape, mapped as closely as possible onto backend/middleware/integration concepts:

```
┌────────────────────────────────────────────────────────────────┐
│  CONFIGURATION LAYER  —  src/jev_cot/config.py                  │
│  Typed, frozen (immutable) Pydantic config. Every run loads     │
│  through load_config(); nothing runs without a validated,       │
│  versioned config object.                                       │
└─────────────────────────┬─────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────┐
│  CONTROLLER LAYER  —  src/jev_cot/controller/                   │
│  The "orchestration" layer — routes each reasoning step through │
│  one of 6 actions based on which gate is active:                │
│                                                                  │
│   ┌───────────────┐  ┌───────────────┐  ┌────────────────────┐ │
│   │  LLM Self-Gate │  │  JEV Gate     │  │  Controller Loop   │ │
│   │  models/llm/   │  │  models/jev/  │  │  deterministic     │ │
│   │  (Condition B) │  │  (Condition C)│  │  state→action→     │ │
│   │                │  │               │  │  dispatch          │ │
│   └───────────────┘  └───────────────┘  └────────────────────┘ │
└─────────────────────────┬─────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────┐
│  TOOLS / INTEGRATION LAYER                                      │
│  controller/tools/  +  retrieval/                                │
│  - RETRIEVE → FAISS + sentence-transformers vector search        │
│  - COMPUTE  → real calculator tool (YoY%, CAGR, etc.)            │
│  - BRANCH   → parallel reasoning fork + merge                    │
└─────────────────────────┬─────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────┐
│  DATA & EVALUATION LAYER                                        │
│  src/jev_cot/data/       — benchmark schema, validator, splitter │
│  src/jev_cot/evaluation/ — metrics registry (H1-H6 formulas)     │
│  data/                   — raw / processed / train / val / test  │
└─────────────────────────┬─────────────────────────────────────┘
                          │
┌─────────────────────────▼─────────────────────────────────────┐
│  LOGGING / OBSERVABILITY  —  src/jev_cot/logging.py              │
│  Dual-sink: console (human) + JSON-lines file (machine-replay)  │
│  Every step logs: action, state, confidence, latency, cost      │
└────────────────────────────────────────────────────────────────┘
```

### 5.1 "Backend" — the actual system core

| Component | Role | Status |
|---|---|---|
| `config.py` | Typed, frozen (`pydantic frozen=True`) experiment config loader | Built |
| `controller/actions.py` | The 6-action enum shared by every component | Built |
| `controller/state.py` | Structured state extractor (turns a live reasoning trace into typed JSON for JEV to consume) | Planned — Phase 6 |
| `controller/loop.py` | Deterministic controller: `state → gate_decision → dispatch(action)` | Planned — Phase 7 |
| `controller/limits.py` | Hard safety guards (max steps/retrievals/branches/latency/cost) — shared by B and C | Planned — Phase 7 |
| `controller/tools/calculator.py`, `branch.py` | COMPUTE and BRANCH tool implementations | Planned — Phase 7 |
| `data/schema.py`, `validator.py`, `split.py` | Canonical benchmark format, validation, company-level splitting | **Built** |
| `evaluation/metrics_registry.py` | Declarative registry of every metric formula (H1-H6) | Built (stubs) |
| `logging.py` | Dual-sink structured logger, reused by every module | Built |

### 5.2 "Middleware" / integration layer — retrieval & tools

| Component | Role | Status |
|---|---|---|
| `retrieval/base.py` | Abstract retrieval interface — swappable backend contract | **In progress — Phase 4** |
| `retrieval/faiss_retriever.py` | FAISS + sentence-transformers implementation (local vector search over seeded docs) | **In progress — Phase 4** |
| `retrieval/ingest.py` | CLI to build a FAISS index from local documents | **In progress — Phase 4** |
| `models/llm/client.py` | LLM wrapper — per-call token/cost/latency tracking, swappable backend | Planned — Phase 5 |
| `models/llm/self_gate.py` | LLM self-gate: prompts the LLM for a structured action + confidence | Planned — Phase 7 |
| `models/jev/*` | JEV classifier: model class, training, calibration, gate integration | Planned — Phases 9-12 |

### 5.3 External integrations

| Integration | Purpose | Notes |
|---|---|---|
| **Google Gemini API** (1.5 Pro + 1.5 Flash) | The LLM being routed/gated | Cost-contrast pair — same provider, two sizes |
| **FAISS** (`faiss-cpu`) | Local vector index for retrieval | Exact search (`IndexFlatL2`) — no production-scale ANN needed at seed scale |
| **sentence-transformers** (`all-MiniLM-L6-v2`) | Embedding model for retrieval | Runs locally, ~90MB model download on first use |
| **XGBoost / LightGBM** | JEV's model architecture | Compact GBT classifier — chosen for interpretability + fast inference, not a neural net |

### 5.4 "Frontend" — there isn't one

This is intentional (`REQUIREMENTS.md` constraint: *"No UI. This is a research + evaluation system."*). All output is:
- **Structured logs** (JSON-lines, replayable) in `logs/`
- **Generated reports** — the final deliverable is `paper/results_summary.md`, auto-generated tables + plots, reproducible from a single command
- **CLI scripts** (`experiments/run_vanilla.py`, `run_selfgate.py`, `run_jevgate.py`, `run_matrix.py`) — this is how a human or CI runs the system

---

## 6. Full Feature List (by build phase)

| Phase | Feature | What it delivers |
|---|---|---|
| 1 | Repo scaffolding | Config system, logging, CI stub, project skeleton |
| 2 | Shared vocabulary | Action enum, condition presets (A/B/C), metrics registry stubs |
| 3 | Benchmark dataset | Schema (7 question types), validator, company-level splitter |
| 4 | **Retrieval layer** (in progress) | Pluggable FAISS + sentence-transformers retrieval, swap-test contract |
| 5 | Vanilla baseline (Condition A) | Single-pass LLM wrapper w/ cost/latency/token tracking |
| 6 | Structured state extractor | Converts live reasoning trace → typed JSON for JEV |
| 7 | Self-gate + controller (Condition B) | Full adaptive loop, safety limits, calculator + branch tools |
| 8 | Trajectory collection | Runs Condition B at scale to generate JEV's training data |
| 9 | JEV label pipeline | 3-stage labeling: rules → LLM-judge → human validation queue |
| 10 | JEV model training | XGBoost/LightGBM, 3 size variants (S/M/L) |
| 11 | JEV calibration | Temperature scaling, ECE/Brier metrics, frozen versioned artifact |
| 12 | JEV integration (Condition C) | Wires frozen JEV into the controller as the gate |
| 13 | Eval suite: efficiency/cost/latency | Aggregate metrics, per-component latency breakdown |
| 14 | Eval suite: grounding/quality | Claim extraction, entailment scoring, 7-dimension quality scorer |
| 15 | Full factorial experiment | {Pro, Flash} × {Vanilla, Self-gate, JEV-gate} on full test set |
| 16 | Ablation suite | Feature ablations, raw-CoT-vs-structured, JEV size comparison |
| 17 | Oracle gate | Theoretical upper-bound baseline using gold annotations |
| 18 | Error taxonomy | Classifies every trajectory's failure mode |
| 19 | Statistics & final report | Paired comparisons, mixed-effects models, auto-generated results doc |

---

## 7. "Production" Concerns — What's Being Built for Rigor, Not Deployment

There's no deployment/hosting/scaling story here — this is a research artifact, not a shipped product. What "production-grade" means in this context instead:

### 7.1 Reproducibility (NFR-01, FR-15)
- Same config + seed → **bit-for-bit identical output**, always
- Every run writes a full config dump: LLM version, JEV version, prompt version, retrieval version, dataset version, temperature, seed, timestamp
- `ExperimentConfig` is immutable (Pydantic `frozen=True`) — can't accidentally mutate parameters mid-run

### 7.2 Safety guards (NFR-04, FR-04)
- Hard caps on max steps, max retrievals, max branches, max latency, max cost — applied **identically** to Conditions B and C via shared `controller/limits.py`
- Prevents pathological infinite-loop behavior in the adaptive controller

### 7.3 Observability (NFR-06)
- Per-component latency logging (LLM inference, gate inference, retrieval, tool) — never aggregate-only
- Dual-sink logging: human-readable console + machine-replayable JSON-lines
- Every trajectory is fully replayable from logs alone

### 7.4 Auditability (NFR-03)
- Every experiment run traceable to an exact config + version
- Every label-generation step tagged with provenance (`rule | llm | human`)
- Package-legitimacy gate on every new dependency before install (this project's build process literally pauses for human sign-off on new PyPI packages)

### 7.5 Freeze discipline (NFR-05) — model-training integrity
- JEV is **never allowed to see the test set** before being frozen and version-tagged
- Calibration uses a separate held-out split from training

### 7.6 Determinism & isolation (NFR-01, NFR-02)
- Company-level train/val/test split — **zero company overlap**, enforced by a pytest assertion
- JEV's only input is structured state JSON — raw chain-of-thought text never touches the primary decision path (kept behind an explicit ablation flag)

### 7.7 Code quality bar (from the actual codebase, not aspirational)
- Python 3.11+, `uv`-managed dependencies with lockfile
- `mypy --strict` type checking
- `ruff` linting + formatting (100-char lines)
- pytest with no mocking — real files + `tmp_path` fixtures
- Every dependency install gated behind a legitimacy check before merge

---

## 8. Current Build Status (as of this document)

| Phase | Status |
|---|---|
| 1-3 | Done — real committed code (config, action enum, benchmark schema/loader) |
| 4 (Retrieval Layer) | **In progress** — researched, planned (5 sub-plans), plan-checked, currently executing |
| 5-19 | Not started |

Full technical rationale for every locked decision (Gemini as LLM, XGBoost/LightGBM for JEV, FAISS for retrieval, company-level split strategy, etc.) lives in `.planning/STATE.md` and `.planning/PROJECT.md` if you need the "why" behind any specific choice not covered above.

---

*This document is a snapshot. Re-generate it later if you want it refreshed against later build progress.*
