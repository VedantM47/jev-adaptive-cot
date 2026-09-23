# Introduction

## What this is

A research system that answers one question: **can a small, cheap, trained classifier replace an LLM's own step-by-step control decisions in a multi-step reasoning pipeline — without losing answer quality?**

The domain is equity research (10-K filings, earnings releases). The system answers financial questions by retrieving evidence and reasoning over it in a loop — and the loop needs to decide, at every step, whether to keep reasoning, fetch more evidence, run a calculation, branch into a second angle, or stop and answer. Normally an LLM makes that decision itself, on every step, burning expensive compute on what's really just routing logic. This project builds a compact classifier (**JEV**) that makes the same decision instead, and measures whether that swap is actually a good idea.

## The three conditions

| Condition | What decides the next step |
|---|---|
| **A — Vanilla** | Nobody. One retrieval, one LLM answer. No loop. |
| **B — Self-gate** | The LLM itself, prompted for a structured decision every step. |
| **C — JEV-gate** | A trained classifier (XGBoost), reading a structured state snapshot. |

B and C share identical retrieval, tools, and answer-synthesis code — the gate is the only thing that differs. That's what makes the B-vs-C comparison meaningful.

## Backend

There's no separate frontend/backend split in the traditional web-app sense — `src/jev_cot/` **is** the backend, a plain installable Python package:

- **`config.py`** — typed, validated experiment configuration (YAML → Pydantic)
- **`retrieval/`** — FAISS + sentence-transformers document search
- **`controller/`** — the adaptive loop, safety limits, tools (calculator, branch), the state extractor
- **`models/llm/`** — the Gemini API client + the LLM self-gate
- **`models/jev/`** — the classifier itself: training, calibration, the frozen-model gate
- **`evaluation/`** — efficiency, latency, grounding, answer-quality, calibration metrics
- **`experiments/`** — the runner scripts that tie it all together (one per condition, plus the full matrix)
- **`analysis/`** — statistics, error taxonomy, the auto-generated results report

None of this needs a server. Every script in `experiments/` runs standalone from the command line and writes its results to `logs/` as JSON-lines.

## Frontend

`app.py` at the repo root is a small Streamlit UI that sits directly on top of the backend above — no API layer in between, since Streamlit runs the Python code in-process. Three tabs:

1. **Run a Question** — pick one benchmark question and a condition, run it live, watch the step-by-step trace and the answer come back.
2. **Results** — the full factorial matrix table + a cost chart, once you've run `run_matrix.py`.
3. **About** — the problem statement, for anyone opening the app cold.

## What you need to actually run it

One thing: a **Gemini API key** (free tier, from https://aistudio.google.com/apikey). Copy `.env.example` to `.env` and paste it in. Nothing else is external — retrieval and the classifier are 100% local.

See `TESTING-GUIDE.md` for how to verify everything works, and `PROJECT-OVERVIEW.md` for the full technical deep-dive (architecture, every requirement, what's simplified and why).
