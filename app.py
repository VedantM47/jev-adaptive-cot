"""
JEV-Gated Adaptive CoT — demo frontend.

A thin Streamlit UI over the existing backend (src/jev_cot/). No separate
API layer — Streamlit runs Python directly, so this calls the same
controller loop, retriever, and LLM client the CLI scripts use.

Run with:  uv run streamlit run app.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

from jev_cot.config import load_config
from jev_cot.controller.loop import run_trajectory
from jev_cot.experiments.common import get_retriever, load_dataset, new_run_id
from jev_cot.models.jev.gate import JEVGate
from jev_cot.models.llm.client import LLMClient
from jev_cot.models.llm.self_gate import LLMSelfGate

st.set_page_config(page_title="JEV-Gated Adaptive CoT", page_icon="📊", layout="wide")

# ── Consistent Aptos display font across the whole app ──────────────────────
st.markdown(
    """
    <style>
    html, body, [class*="css"], .stMarkdown, .stText, p, span, div, label,
    h1, h2, h3, h4, h5, h6, button, input, textarea, select {
        font-family: "Aptos", "Aptos Display", "Segoe UI", -apple-system,
                     BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif !important;
    }
    code, pre, .stCode, .stCodeBlock {
        font-family: "Cascadia Code", "Consolas", monospace !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

REPO_ROOT = Path(__file__).resolve().parent
DATASET_PATH = REPO_ROOT / "data" / "raw" / "sample_examples.jsonl"
MATRIX_RESULTS_PATH = REPO_ROOT / "logs" / "matrix_runs" / "matrix_results.json"
FROZEN_JEV_PATH = REPO_ROOT / "models" / "jev" / "checkpoints" / "jev_frozen_v1"

st.title("JEV-Gated Adaptive Chain-of-Thought")
st.caption("Can a compact trained classifier replace an LLM's own control-flow decisions?")

has_key = bool(os.environ.get("GEMINI_API_KEY"))
if not has_key:
    st.warning(
        "No GEMINI_API_KEY found. Copy `.env.example` to `.env` and add your key "
        "(free at https://aistudio.google.com/apikey) before running a trajectory. "
        "The Results and About tabs work without a key."
    )

tab_run, tab_results, tab_about = st.tabs(["▶ Run a Question", "📈 Results", "ℹ About"])

# ── Tab 1: Run a single question through a condition ─────────────────────────
with tab_run:
    st.subheader("Run one benchmark question through a condition")

    if not DATASET_PATH.exists():
        st.error(f"Dataset not found at {DATASET_PATH}")
    else:
        examples = load_dataset(DATASET_PATH)
        example_labels = [f"{e.id} — {e.question[:70]}" for e in examples]

        col1, col2 = st.columns([2, 1])
        with col1:
            selected_idx = st.selectbox(
                "Question", range(len(examples)), format_func=lambda i: example_labels[i]
            )
        with col2:
            condition = st.radio("Condition", ["vanilla", "selfgate", "jevgate"])

        llm_model = st.selectbox(
            "LLM", ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest"], index=0
        )

        run_disabled = not has_key or (
            condition == "jevgate" and not FROZEN_JEV_PATH.exists()
        )
        if condition == "jevgate" and not FROZEN_JEV_PATH.exists():
            st.info(
                "No frozen JEV checkpoint yet — run `python -m jev_cot.models.jev.calibrate` "
                "first (needs collected trajectories + labels)."
            )

        if st.button("Run", type="primary", disabled=run_disabled):
            example = examples[selected_idx]
            with st.spinner(f"Running {condition} on {example.id}…"):
                try:
                    cfg = load_config(REPO_ROOT / "configs" / "base.yaml").model_copy(
                        update={"llm": llm_model, "condition": condition}
                    )
                    retriever = get_retriever(cfg)
                    client = LLMClient(
                        model=cfg.llm, temperature=cfg.temperature, max_tokens=cfg.max_tokens
                    )
                    run_id = new_run_id("ui")

                    if condition == "vanilla":
                        result = retriever.retrieve(
                            company=example.company,
                            period=example.period,
                            query=example.question,
                            top_k=cfg.retrieval.top_k,
                        )
                        evidence = "\n".join(f"- {c.text}" for c in result.chunks)
                        response = client.generate(
                            f"Answer using ONLY this evidence.\n\nQuestion: {example.question}"
                            f"\n\nEvidence:\n{evidence}\n\nAnswer:"
                        )
                        st.success("Done")
                        st.markdown(f"**Answer:** {response.text}")
                        st.metric("Cost (USD)", f"${response.cost_usd:.5f}")
                        st.metric("Latency (ms)", f"{response.latency_ms:.0f}")
                    else:
                        gate = (
                            LLMSelfGate(LLMClient(model=cfg.llm, temperature=0.0, max_tokens=256))
                            if condition == "selfgate"
                            else JEVGate.from_checkpoint(str(FROZEN_JEV_PATH))
                        )
                        trajectory = run_trajectory(example, cfg, retriever, client, gate, run_id)

                        st.success(f"Done — {len(trajectory.steps)} steps")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Cost (USD)", f"${trajectory.total_cost_usd:.5f}")
                        c2.metric("Latency (s)", f"{trajectory.total_latency_seconds:.2f}")
                        c3.metric("LLM calls", trajectory.total_llm_calls)

                        st.markdown("**Final answer:**")
                        st.write(trajectory.final_answer)

                        st.markdown("**Step-by-step trace:**")
                        for step in trajectory.steps:
                            st.text(
                                f"Step {step.step_index}: {step.action.value} "
                                f"(confidence={step.confidence:.2f}, source={step.gate_source}, "
                                f"latency={step.latency_ms:.1f}ms)"
                            )
                except Exception as exc:  # noqa: BLE001 — surface any backend error to the UI
                    st.error(f"Run failed: {exc}")

# ── Tab 2: Matrix results, if they exist ──────────────────────────────────────
with tab_results:
    st.subheader("Full factorial matrix results")
    if MATRIX_RESULTS_PATH.exists():
        results = json.loads(MATRIX_RESULTS_PATH.read_text(encoding="utf-8"))
        rows = [{"cell": k, **v} for k, v in results.items()]
        st.dataframe(rows, use_container_width=True)

        if rows:
            st.markdown("**Avg cost per condition**")
            st.bar_chart({r["cell"]: r.get("avg_cost_usd", 0) for r in rows})
    else:
        st.info(
            "No matrix results yet. Run `python -m jev_cot.experiments.run_matrix` "
            "then reload this page."
        )

# ── Tab 3: About / problem statement ──────────────────────────────────────────
with tab_about:
    st.subheader("What this project measures")
    st.markdown(
        """
Three pipeline conditions share identical retrieval, tools, and synthesis —
only the **gate** (what decides the next action) differs:

| Condition | Gate |
|---|---|
| A — Vanilla | No adaptive control (single LLM pass) |
| B — Self-gate | LLM decides next action at each step |
| C — JEV-gate | Compact trained classifier (JEV) decides |

**JEV** maps a structured state snapshot to one of six actions:
`CONTINUE | RETRIEVE | COMPUTE | BRANCH | STOP | ESCALATE`.

**Primary comparison:** B vs. C — same LLM, same everything, gate is the
only variable. The question: does replacing the LLM's own control-flow
decisions with a cheap classifier save cost/latency without hurting answer
quality or evidence grounding?

See `PROJECT-OVERVIEW.md` in the repo root for the full write-up.
        """
    )
