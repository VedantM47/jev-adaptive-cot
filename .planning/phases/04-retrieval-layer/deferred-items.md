# Deferred Items — Phase 4

Out-of-scope discoveries logged during plan execution (not fixed — see
executor scope-boundary rule).

## 04-05: `tests/test_data_schema.py::test_sample_dataset_validates` fails

- **Found during:** Plan 04-05, final full-suite sanity check (`uv run --extra dev pytest`).
- **Symptom:** `jsonlines.jsonlines.InvalidLineError: line contains invalid json: Expecting value: line 2 column 1 (char 1) (line 8)` reading `data/raw/sample_examples.jsonl`.
- **Scope:** Neither `data/raw/sample_examples.jsonl` nor `tests/test_data_schema.py` is in plan 04-05's `files_modified`; both were last touched at Phase 3 commit `8b9b2d9` ("feat: Phase 3 — Equity research benchmark schema & loader"), before any Phase 4 work. Pre-existing, unrelated to the retrieval-layer ingest CLI.
- **Action:** Not fixed here (out of scope per executor scope-boundary rule). Flagging for a future Phase 3/data-schema fix — `data/raw/sample_examples.jsonl` appears to contain a malformed JSON line (line 8).
