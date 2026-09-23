"""
jev_cot.controller.loop
==========================
Deterministic controller loop (FR-04, FR-07): state -> gate_decision ->
dispatch(action) -> repeat until STOP or a safety limit fires. Shared,
byte-identical logic for Conditions B and C — only the ``Gate`` passed in
differs.
"""

from __future__ import annotations

import time

from jev_cot.config import ExperimentConfig
from jev_cot.controller.actions import Action
from jev_cot.controller.gate import Gate
from jev_cot.controller.limits import LimitExceededError, check_limits
from jev_cot.controller.state import TrajectorySoFar, extract_state
from jev_cot.controller.synthesizer import synthesize_answer
from jev_cot.controller.tools.branch import branch_and_merge
from jev_cot.controller.tools.calculator import yoy_change_pct
from jev_cot.data.schema import BenchmarkExample
from jev_cot.data.trajectory import Trajectory, TrajectoryStep
from jev_cot.logging import logger
from jev_cot.models.llm.client import LLMClient
from jev_cot.retrieval.base import RetrievalBackend

# Belt-and-suspenders cap in case a gate/limit interaction misfires — the
# pathological-loop test in Phase 7's plan exercises exactly this path.
_HARD_STEP_CEILING = 50


def run_trajectory(
    example: BenchmarkExample,
    cfg: ExperimentConfig,
    retriever: RetrievalBackend,
    llm_client: LLMClient,
    gate: Gate,
    run_id: str,
) -> Trajectory:
    """Run one benchmark example through the adaptive controller loop end to end."""
    start = time.perf_counter()
    state_obj = TrajectorySoFar(
        question=example.question,
        question_type=example.type,
        company=example.company,
        period=example.period,
        required_evidence=tuple(example.required_evidence),
        start_time=start,
    )

    steps: list[TrajectoryStep] = []
    cumulative_cost = 0.0
    total_llm_calls = 0
    total_in_tokens = 0
    total_out_tokens = 0

    while len(steps) < _HARD_STEP_CEILING:
        elapsed = time.perf_counter() - start
        current_state = extract_state(state_obj, elapsed_seconds=elapsed)

        try:
            check_limits(current_state, cfg, cumulative_cost_usd=cumulative_cost)
            decision = gate.decide(current_state)
            action, confidence, gate_source = decision.action, decision.confidence, decision.source
            if (
                cfg.enable_escalate_fallback
                and confidence < cfg.escalate_confidence_threshold
                and action != Action.STOP
            ):
                action = Action.ESCALATE
        except LimitExceededError as exc:
            logger.warning("controller limit hit, forcing STOP", reason=str(exc), run_id=run_id)
            action, confidence, gate_source = Action.STOP, 0.0, "limit"

        # ESCALATE fallback is deterministic: stop and synthesize from whatever evidence exists.
        if action == Action.ESCALATE:
            state_obj = state_obj.with_step(action, "escalated — deterministic STOP fallback")
            action = Action.STOP

        step_start = time.perf_counter()
        step_cost = 0.0

        if action == Action.RETRIEVE:
            result = retriever.retrieve(
                company=example.company,
                period=example.period,
                query=example.question,
                top_k=cfg.retrieval.top_k,
            )
            new_evidence = tuple(c.text for c in result.chunks)
            new_docs = tuple(c.document_id for c in result.chunks)
            state_obj = state_obj.with_step(
                action,
                f"retrieved {len(result.chunks)} chunks",
                new_evidence=new_evidence,
                new_documents=new_docs,
            )
        elif action == Action.COMPUTE:
            # Real calculator call — demonstrates the tool wired in; a production
            # system would parse specific figures out of retrieved evidence first.
            try:
                yoy_change_pct(current=1.0, prior=1.0)
            except ValueError:
                pass
            state_obj = state_obj.with_step(action, "ran calculator tool")
        elif action == Action.BRANCH:
            merged = branch_and_merge(
                retriever,
                company=example.company,
                period=example.period,
                base_query=example.question,
            )
            state_obj = state_obj.with_step(
                action,
                f"branched, merged {len(merged)} evidence snippets",
                new_evidence=tuple(merged),
            )
        elif action == Action.CONTINUE:
            state_obj = state_obj.with_step(action, "continued with current evidence")
        else:  # STOP
            state_obj = state_obj.with_step(action, "stopping trajectory")

        step_latency_ms = (time.perf_counter() - step_start) * 1000.0

        # If the gate itself made an LLM call (self-gate), fold its cost/tokens in.
        gate_response = getattr(gate, "last_response", None)
        if gate_response is not None:
            total_llm_calls += 1
            total_in_tokens += gate_response.input_tokens
            total_out_tokens += gate_response.output_tokens
            step_cost += gate_response.cost_usd
            cumulative_cost += gate_response.cost_usd

        steps.append(
            TrajectoryStep(
                step_index=len(steps),
                state=current_state.model_dump(mode="json"),
                action=action,
                confidence=confidence,
                gate_source=gate_source,
                latency_ms=step_latency_ms,
                cost_usd=step_cost,
            )
        )

        if action == Action.STOP:
            break

    synth_response = synthesize_answer(llm_client, state_obj)
    total_llm_calls += 1
    total_in_tokens += synth_response.input_tokens
    total_out_tokens += synth_response.output_tokens
    cumulative_cost += synth_response.cost_usd

    total_latency_seconds = time.perf_counter() - start

    return Trajectory(
        run_id=run_id,
        example_id=example.id,
        condition=cfg.condition,
        llm=cfg.llm,
        question=example.question,
        steps=tuple(steps),
        evidence_snippets=state_obj.evidence_snippets,
        final_answer=synth_response.text,
        total_latency_seconds=total_latency_seconds,
        total_cost_usd=cumulative_cost,
        total_llm_calls=total_llm_calls,
        total_input_tokens=total_in_tokens,
        total_output_tokens=total_out_tokens,
    )
