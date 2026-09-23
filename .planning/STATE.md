# STATE.md — Project Memory

**Project:** JEV-Gated Adaptive CoT for Equity Research  
**Last Updated:** 2026-09-23  
**Current Phase:** Phase 1 (Repo Scaffolding) — not yet started

---

## Current Status

| Item | Value |
|---|---|
| Active Milestone | M1 — Research System v1 |
| Active Phase | Phase 1 — Repo Scaffolding & Config System |
| Phase Status | Complete |
| Phases Complete | 1 / 19 |
| Last Commit | feat: Phase 1 — repo scaffold, config loader, logging, CI stub |

---

## Key Decisions Made

| Date | Decision | Rationale |
|---|---|---|
| 2026-09-23 | JEV architecture: XGBoost/LightGBM GBT | Compact, interpretable, fast inference, minimal dependencies |
| 2026-09-23 | Retrieval: FAISS + sentence-transformers (local) | Unblocks dev without real filings; swappable interface via base.py |
| 2026-09-23 | LLM backends: Gemini 1.5 Pro + Gemini 1.5 Flash | Cost contrast within same provider; cross-size comparison |
| 2026-09-23 | Python 3.11 + uv | Stable, reproducible, fast resolver |
| 2026-09-23 | Config format: YAML + pydantic validation | Human-readable, type-safe, version-controlled |
| 2026-09-23 | Split strategy: company-level (primary), temporal (secondary) | Prevents leakage; tests temporal robustness |
| 2026-09-23 | Phase 1 sectors: tech/software + industrials/retail | Clean 10-K structure; easy/hard question contrast |
| 2026-09-23 | Git init: yes, with initial commit | Auditability from day one |

---

## Open Questions / Decisions Pending

| # | Question | Owner | Target Phase |
|---|---|---|---|
| OQ-01 | Exact Gemini API version to pin (for reproducibility) | (fill in) | Phase 5 |
| OQ-02 | Which 2–3 specific tech/industrial companies for Phase 1 seed dataset | (fill in) | Phase 3 |
| OQ-03 | Human validation coverage target for JEV labels (what % needs human review?) | (fill in) | Phase 9 |
| OQ-04 | Agreed tolerance for automated grounding vs. human grounding judgment | (fill in) | Phase 14 |
| OQ-05 | Confidence threshold for ESCALATE fallback (secondary experiment) | (fill in) | Phase 12 |
| OQ-06 | JEV-S/M/L size definitions (n_estimators, max_depth ranges for each) | (fill in) | Phase 10 |

---

## Phase Progress Log

| Phase | Started | Completed | Notes |
|---|---|---|---|
| Phase 1 | 2026-09-23 | 2026-09-23 | Completed repo scaffold and config loader |
| Phase 2 | — | — | |
| Phase 3 | — | — | |
| … | — | — | |

---

## Workstreams (Parallel)

After Phase 8 (trajectory collection), the following can run in parallel:
- **Stream A:** Phases 9→10→11→12 (JEV training pipeline)
- **Stream B:** Phases 13, 14 (evaluation suite — efficiency/grounding)

After Phase 15 (factorial experiment):
- **Stream C:** Phases 16, 17, 18 (ablations, oracle, error taxonomy) — all parallel
- **Stream D:** Phase 19 (stats + reporting) — depends on C

---

## Important File Index

| File | Purpose |
|---|---|
| `.planning/PROJECT.md` | Project vision, architecture, decisions |
| `.planning/REQUIREMENTS.md` | FR/NFR registry (FR-01 through FR-24) |
| `.planning/ROADMAP.md` | All 19 phases with acceptance criteria |
| `.planning/STATE.md` | This file — live project memory |
| `.planning/config.json` | GSD workflow preferences |
| `configs/base.yaml` | Base experiment config (created in Phase 1) |
| `controller/actions.py` | Action enum — shared by ALL components (Phase 2) |
| `data/schema.py` | Benchmark example schema — Appendix C (Phase 3) |
| `controller/state.py` | JEV state schema — Appendix A (Phase 6) |
| `models/jev/checkpoints/jev_frozen_v1/` | Frozen calibrated JEV artifact (Phase 11) |

