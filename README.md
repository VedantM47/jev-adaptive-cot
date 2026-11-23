# Jev Decision Assistant

An open-source, local-first decision assistant. Ask a "should I choose A or B?" question and get a probability for each option from an open-source Jev model, followed by a recommendation grounded in those numbers.

It replaces the paid TypeSafe AI Jev API. With `ollama/qwen3:8b` used for both Jev and the answer LLM, **no API key is required**. Gemini is optional (`GEMINI_API_KEY`).

---

## What it does

You ask a decision question:

> I'm a CS student who loves math. Should I choose data science or product management?

1. **Router** - a zero-token heuristic (regex, no LLM call) decides whether the question is a choice among 2-8 options, and extracts the options. Earlier sentences become the context.
2. **Jev** - the open-source Jev (Qwen3, Apache-2.0, run locally via Ollama) scores each option. It reads next-token logprobs over option letters and averages them across option-order permutations, which reduces position bias. The result is a probability per option.
3. **LLM** - writes a short recommendation grounded in those probabilities (it is instructed not to invent different numbers).
4. **Non-decision questions** skip Jev and go straight to the LLM.

```
                      decision?
 question --> router ----yes----> Jev (probabilities) --> LLM --> grounded answer
                 |                  Qwen3 via Ollama
                 +-----no---------------------------------> LLM --> plain answer
```

If Ollama is not running, a clear error is raised. There is no silent fallback.

---

## Setup

Prerequisites: Python >= 3.11, [uv](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com) >= 0.12.11 (needed for logprobs).

```powershell
winget install Ollama.Ollama
ollama pull qwen3:8b
uv sync --extra dev
```

Then use either interface:

```powershell
# Streamlit app: open the tab "Ask (Jev Decision)"
uv run streamlit run app.py

# CLI
uv run python scripts/ask.py "I'm a CS student who loves math. Should I choose data science or product management?"
```

The CLI takes `--llm` to pick the answer model (default `ollama/qwen3:8b`). The app offers `ollama/qwen3:8b` and `gemini-flash-lite-latest`; Gemini needs `GEMINI_API_KEY` (copy `.env.example` to `.env`).

### Configuration

Settings live in the `decision:` block of [`configs/base.yaml`](configs/base.yaml):

| Key | Default | Meaning |
|---|---|---|
| `jev_model` | `qwen3:8b` | Ollama model used as Jev |
| `ollama_host` | `http://localhost:11434` | Where Ollama is served |
| `n_permutations` | `3` | Option orderings averaged to cancel position bias |
| `use_llm_router` | `false` | Enable the token-costing LLM fallback router (the heuristic router is free) |

### Example output

Illustrative only. Your numbers will differ by model and run.

```
JEV DECISION (model=qwen3:8b, 3 samples)
- data science: 58.0%
- product management: 42.0%
Top: data science (confidence 0.58)

Data science looks like the better fit (58% vs 42%). Your love of math maps
directly onto modeling and statistics, and CS skills give you a head start on
the engineering side. The gap is modest, so if you care more about shaping
what gets built than how it is analysed, product management could tip it.
```

If the top confidence is below 0.55, the LLM is told to say the call is close and name what would tip it.

### Limitations

The probabilities are LLM next-token logprobs, normalised over the options. Treat them as a rough prior, not a calibrated forecast. Option extraction is heuristic, so unusual phrasings may not be detected as decisions.

---

## Research background

This repository also contains the research system the decision layer grew out of: JEV-gated Adaptive Chain-of-Thought for equity research. It tests whether a compact, calibrated classifier (JEV) can safely replace LLM self-gating, cutting cost and latency without hurting evidence grounding or answer quality.

Docs: [Introduction](docs/INTRO.md) · [Testing Guide](docs/TESTING-GUIDE.md) · [Technical Write-up](docs/PROJECT-OVERVIEW.md)

### Hypotheses

| # | Hypothesis |
|---|---|
| H1 | JEV uses fewer unnecessary operations than LLM self-gating |
| H2 | JEV lowers end-to-end latency (including JEV overhead) |
| H3 | JEV lowers cost per completed query |
| H4 | Grounding quality doesn't materially degrade |
| H5 | Answer quality stays comparable |
| H6 | JEV's confidence is calibrated |

### Conditions

- `vanilla` - plain LLM baseline (Condition A)
- `selfgate` - the LLM decides its own next action (Condition B)
- `jevgate` - the JEV classifier gates the actions (Condition C)

The primary comparison is B vs C: same LLM, same retrieval, same tools, same synthesis. The gate is the only variable. Set the condition and other fields (`llm`, `prompt_version`, `random_seed`, `max_steps`, ...) in `configs/base.yaml`.

### Running the experiments

The experiment pipeline uses Gemini and needs `GEMINI_API_KEY` in `.env`. Each stage is runnable as `python -m jev_cot.<module>`:

```powershell
uv run python -m jev_cot.experiments.run_vanilla
uv run python -m jev_cot.experiments.run_selfgate
uv run python -m jev_cot.experiments.collect_trajectories
uv run python -m jev_cot.models.jev.labeling.rules
uv run python -m jev_cot.models.jev.train
uv run python -m jev_cot.models.jev.calibrate
uv run python -m jev_cot.experiments.run_jevgate
uv run python -m jev_cot.experiments.run_matrix
uv run python -m jev_cot.analysis.generate_report
```

### Repository structure

All real code lives under `src/jev_cot/`; the top-level `retrieval/`, `models/`, `controller/`, `evaluation/`, `experiments/` folders are unused scaffold leftovers.

```
jev-cot/
├── app.py                ← Streamlit frontend (Ask tab + research tabs)
├── scripts/ask.py        ← Decision CLI
├── docs/                 ← Intro, testing guide, technical write-up
├── src/jev_cot/
│   ├── config.py         ← Typed config loader (start here)
│   ├── decision/         ← Router, local Jev (Ollama), grounded-answer pipeline
│   ├── retrieval/        ← Retrieval interface + FAISS backend
│   ├── models/           ← jev/ (classifier, training, calibration), llm/ (client, self-gate)
│   ├── controller/       ← Controller loop, actions, state extractor, limits
│   ├── evaluation/       ← Grounding, quality, latency, cost, calibration metrics
│   ├── experiments/      ← vanilla / selfgate / jevgate / matrix runners
│   ├── analysis/         ← Statistics, error taxonomy, report generator
│   └── data/             ← Benchmark and trajectory schemas
├── configs/              ← YAML configs (base.yaml, conditions/)
├── data/                 ← Seed benchmark, trajectories, training data
└── tests/                ← pytest suite
```

### Testing and development

The full suite runs offline with no API key, using a fake LLM client:

```powershell
uv run pytest
uv run pytest --cov=jev_cot --cov-report=term-missing
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

---

## License

The Jev model used for decisions (Qwen3) is Apache-2.0. License for this repository: TBD.
