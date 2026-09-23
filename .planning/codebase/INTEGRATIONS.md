---
last_mapped_commit: 237e58f437bc3e9685c2501dd1b012143667e3d4
last_mapped_at: 2026-09-23
---
# External Integrations

**Analysis Date:** 2026-09-23

## APIs & External Services

**LLM / AI:**

- Google Gemini API - Primary LLM for experiment runs
  - Model: `gemini-1.5-pro-latest` (default, configurable in `configs/base.yaml`)
  - SDK/Client: Not yet integrated (planned, referenced in README Phase 5)
  - Auth: Requires Google API key via environment variable (exact var name to be defined during Phase 5 implementation)
  - Configuration: Model name specified in `ExperimentConfig.llm` field via YAML (`src/jev_cot/config.py`)

## Data Storage

**Databases:**

- None currently integrated (local-only)

**File Storage:**

- Local filesystem only
  - Logs: JSON-lines format written to `logs/{run_id}.log.jsonl` (`src/jev_cot/logging.py`)
  - Data: JSONL format for benchmark examples and trajectories (`data/` directory)
  - Models: Checkpoint files in `models/jev/checkpoints/` (Git-ignored, tracked separately via DVC or Git LFS)
  - Configuration: YAML files in `configs/` directory

**Caching:**

- None integrated

## Authentication & Identity

**Auth Provider:**

- Custom configuration-based auth
  - Implementation: Environment variable placeholders (not yet implemented; will be added in Phase 5 when Google Gemini SDK is integrated)
  - Currently all auth details are configuration-driven via `ExperimentConfig`

## Monitoring & Observability

**Error Tracking:**

- None

**Logs:**

- Dual-sink approach via loguru (`src/jev_cot/logging.py`):
  - **Console**: Human-readable colored output to stderr (development)
  - **File**: JSON-lines format to `logs/{run_id}.log.jsonl` for machine processing and trajectory replay
  - Log rotation: 100 MB per file, 30-day retention, gzip compression

## CI/CD & Deployment

**Hosting:**

- Not yet deployed (research codebase, local execution only)

**CI Pipeline:**

- GitHub Actions configured in `.planning/ROADMAP.md` (planned for Phase 1)
- Test command: `uv run pytest`
- Lint command: `uv run ruff check src/ tests/`
- Type check command: `uv run mypy src/`

## Environment Configuration

**Required env vars:**

- `GOOGLE_API_KEY` (or equivalent) - For Google Gemini API access (exact name TBD during Phase 5 LLM client implementation)

**Secrets location:**

- `.env` file (Git-ignored, not committed). Environment-specific credentials loaded at runtime.

## Webhooks & Callbacks

**Incoming:**

- None

**Outgoing:**

- None

## Planned Integrations (Future Phases)

**Phase 4 — Retrieval Layer:**

- FAISS (Facebook AI Similarity Search)
  - Purpose: Vector similarity search for context retrieval
  - Configuration reference: `retrieval_version: "faiss-v0.1"` in all configs (`configs/base.yaml`, `configs/conditions/*.yaml`)
  - Not yet a runtime dependency (will be added to `pyproject.toml` during Phase 4)

**Phase 5 — LLM Client:**

- Google Generative AI SDK
  - Wraps Gemini API with typed interface
  - Location: `models/llm/` (currently placeholder)

**Phase 10+ — Experiment Management:**

- Potential integration with experiment tracking tools (e.g., Weights & Biases, MLflow) — mentioned in evaluation context but not yet scoped

---

*Integration audit: 2026-09-23*
