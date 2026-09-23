# PLAN.md — Phase 2: Research Spec as Machine-Readable Artifacts

**Phase:** 2 of 19  
**Status:** Ready for execution  
**Depends on:** Phase 1  
**Blocks:** All subsequent phases  

---

## Objective

Freeze the core research vocabulary (actions, condition presets, and metrics) as shared code artifacts so all later phases import from a single source of truth. 

---

## Tracer Slice (end-to-end proof of life)

```
uv run python -c "from jev_cot.controller.actions import Action; print(Action.CONTINUE)"
```

---

## Tasks

### T1 · Action Enum — `src/jev_cot/controller/actions.py`
**Type:** code  
**Files:** `src/jev_cot/controller/actions.py`, `src/jev_cot/controller/__init__.py`  
**Requirement:** FR-01 (Action Space)

Implement the 6 actions: `CONTINUE | RETRIEVE | COMPUTE | BRANCH | STOP | ESCALATE` using Python's `enum.StrEnum`.

---

### T2 · Condition Config Presets
**Type:** config  
**Files:** 
- `configs/conditions/vanilla.yaml`
- `configs/conditions/selfgate.yaml`
- `configs/conditions/jevgate.yaml`  
**Requirement:** FR-02 (Three Pipeline Conditions)

Create the three YAML presets. They should contain the `condition` field, and any condition-specific overrides (like `jev_version` for `jevgate`).

---

### T3 · Metrics Registry — `src/jev_cot/evaluation/metrics_registry.py`
**Type:** code  
**Files:** `src/jev_cot/evaluation/metrics_registry.py`, `src/jev_cot/evaluation/__init__.py`  

Implement a registry (names, types, formulas as docstrings/metadata) for all metrics from H1–H6. Stubs only, no implementation.

---

### T4 · Tests & Verification
**Type:** test  
**Files:** `tests/test_phase2.py`

Test importing the enum, loading the presets using `load_config` (to ensure they are valid), and importing the metrics registry.

---

### T5 · Commit
**Type:** git  
Commit changes for Phase 2.

