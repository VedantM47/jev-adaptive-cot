# Testing Guide

## 1. Automated tests (no API key needed)

```powershell
uv sync --extra dev              # install everything, once
uv run pytest                    # 139 tests, all offline
```

With coverage:
```powershell
uv run pytest --cov=jev_cot --cov-report=term-missing
```

Also runs on every push via GitHub Actions (`.github/workflows/`).

**What's covered without a key:** config loading, retrieval (real FAISS index built from the seed corpus), the controller loop's wiring (using a fake LLM), JEV train/calibrate/save/load (real XGBoost + sklearn), all evaluation math (grounding, calibration, efficiency). See `tests/test_pipeline_smoke.py` for the end-to-end wiring proof.

**What's NOT covered without a key:** anything that calls the real Gemini API (`models/llm/client.py`'s actual network call) — that needs Section 2 below.

Also check code quality:
```powershell
uv run ruff check src/ tests/ app.py
uv run mypy src/ app.py
```
Both should report clean.

---

## 2. Manual test — the real pipeline (needs a Gemini key)

1. Get a free key: https://aistudio.google.com/apikey
2. `cp .env.example .env` and paste your key in
3. Run the cheapest possible smoke test first:
   ```powershell
   uv run python -m jev_cot.experiments.run_vanilla
   ```
   This is Condition A — one retrieval + one LLM call per question, 9 questions, costs a fraction of a cent on Flash. If this works, the API key and wiring are good.

4. Then the fuller pipeline, in order:
   ```powershell
   uv run python -m jev_cot.experiments.run_selfgate        # Condition B
   uv run python -m jev_cot.experiments.collect_trajectories
   uv run python -m jev_cot.models.jev.labeling.rules
   uv run python -m jev_cot.models.jev.train                # trains S/M/L, prints accuracy table
   uv run python -m jev_cot.models.jev.calibrate             # freezes models/jev/checkpoints/jev_frozen_v1/
   uv run python -m jev_cot.experiments.run_jevgate          # Condition C, now that JEV exists
   ```

5. Score any run for grounding/quality:
   ```powershell
   uv run python -m jev_cot.experiments.evaluate_run --trajectories logs/<run>_trajectories.jsonl
   ```

6. The full comparison (the actual deliverable):
   ```powershell
   uv run python -m jev_cot.experiments.run_matrix
   uv run python -m jev_cot.analysis.generate_report
   ```
   Produces `logs/matrix_runs/matrix_results.json` and `paper/results_summary.md`.

---

## 3. Testing the frontend

```powershell
uv run streamlit run app.py
```
Opens in your browser at `http://localhost:8501`. Three tabs:

- **Run a Question** — needs the API key from Section 2. Pick a question + condition, hit Run, watch it work live.
- **Results** — reads `logs/matrix_runs/matrix_results.json` if it exists (run Section 2 step 6 first). Empty/informational otherwise, no error.
- **About** — static, no key needed, works immediately.

If it doesn't boot: `uv sync --extra dev` first (streamlit is a project dependency, not a global install).

---

## 4. Known simplifications (won't look like a bug if you know this going in)

- Grounding/answer-quality scoring uses a lightweight heuristic + a single combined LLM-judge call (not 7 separate calls) — see `docs/PROJECT-OVERVIEW.md` §7 for why.
- The seed dataset is 9 documents / 6 questions — enough to prove the pipeline works, not enough for a statistically powerful result. `jev_cot.analysis.statistics` will still run a paired t-test on it, but treat the p-value as illustrative, not conclusive.
- `models/jev/train.py` needs at least ~10-30 collected trajectory steps to train meaningfully — running `collect_trajectories.py` on all 6 seed questions with Condition B should produce enough.
