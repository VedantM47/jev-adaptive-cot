# What's Left — Plain Report

**Scope reset:** college project, working code, not production. No more heavy research/plan-check/code-review/verify gates unless you ask for one. Just build → test it runs → move on.

---

## 1. What's Actually Done (real, tested, working)

- Config system (YAML → typed Python objects)
- Shared action vocabulary (the 6 actions every later piece uses)
- Benchmark dataset (9 documents, 6+ example questions, schema + validator + splitter)
- **Retrieval**: FAISS + sentence-transformers, fully working — you can embed documents, build an index, and search it. 132 tests pass.

That's it. That's the whole "backend" so far — there is no frontend, this project never has one (research pipeline, not an app — output is JSON logs + a results report, not a UI).

---

## 2. What's Left (everything else — 15 phases' worth)

Think of it as 5 real chunks of work, not 15 scary phase names:

### Chunk A — Get the LLM actually calling out and answering questions (Phases 5-6)
- A wrapper around the Gemini API (send prompt, get answer, track tokens/cost)
- A script that takes a question → retrieves docs → asks Gemini → logs the answer
- A function that looks at "what's happened so far in the reasoning" and turns it into a clean JSON snapshot (this JSON is what the classifier will later read)

**This is the first point where you need the Gemini API integration.** Nothing before this needs any external API.

### Chunk B — The actual "adaptive" loop (Phase 7)
- A loop: look at state → decide next move (retrieve more? do math? stop?) → do it → repeat
- Two ways to decide the next move exist by the end of this chunk: ask Gemini directly (self-gate), or hardcoded safety limits so it can't loop forever
- A basic calculator tool (for %, growth rate math) and a "branch" (try two lines of reasoning, merge them)

### Chunk C — Train the classifier that replaces Gemini's decision-making (Phases 8-12)
This is the actual novel/interesting part of the project:
- Run the Chunk B loop across your dataset, save every (state → what Gemini decided to do) pair
- Label those pairs (some rules, maybe some manual labeling — doesn't need to be fancy for a college project)
- Train a small classifier (XGBoost, this is like 20 lines of code with real libraries) on those pairs
- Calibrate it (make sure "80% confident" actually means right 80% of the time — also just a library call)
- Swap it in as a second way to run the loop

### Chunk D — Prove it worked / didn't work (Phases 13-14, 16-18)
- Count stuff: how many LLM calls, how much it cost, how long it took — for both methods
- Score answer quality — did it cite the right evidence, is the answer actually correct
- Compare the two methods on the same questions

### Chunk E — Write it up (Phase 15, 19)
- Run everything once, save all the numbers
- Make a couple of comparison tables/charts
- Write the results in plain English with the numbers to back it up

---

## 3. Integrations Needed (only ONE real external integration)

### Gemini API — needed starting Chunk A
That's the only external service this project touches. Everything else (FAISS, the classifier) runs 100% locally, no API needed.

**What you need to do right now, before Chunk A can start:**

1. Get a Gemini API key: https://aistudio.google.com/apikey (free tier is enough for a college project — Gemini 1.5 Flash is generous)
2. I'll set up a `.env` file (git-ignored, never committed) that holds the key
3. Code reads it via `os.environ["GEMINI_API_KEY"]` — never hardcoded, never in a committed file

**Env setup I'll do once you have the key:**
```
GEMINI_API_KEY=<your key here>
```
in a `.env` file at the project root, plus a `.env.example` (committed, no real key, just shows the shape) so it's obvious what's needed.

That's the entire integration surface. No database, no auth service, no cloud hosting, no other APIs.

---

## 4. On "bullshit files" — before I touch anything

You're right that `.planning/` has a lot of process paperwork (a SUMMARY.md + CONTEXT.md + RESEARCH.md per phase). I don't want to delete stuff blindly and lose real information, so — quick call:

- **Keep it simple going forward:** no more RESEARCH.md, no more separate CONTEXT.md, no more REVIEW.md. Just a PLAN.md and a short SUMMARY.md per phase (or honestly, I can just build and tell you what I built — skip the paperwork entirely if you want).
- **Existing files:** I'm not deleting the Phase 1-4 planning docs without you confirming — they're not hurting anything sitting in `.planning/`, they're not part of the actual codebase (`src/`, `tests/`) that gets graded/run. If you want them gone, say the word and I'll clear `.planning/phases/*/` down to just what's needed.

---

## What I need from you to keep moving

1. **A Gemini API key** — get one, paste it here (or tell me to remind you and I'll wait)
2. **Confirm:** skip research/plan-check/review entirely from here, just build+test+move on?
3. **Confirm:** leave existing `.planning/` docs alone, or clear them out?

Once I have the key I go straight into Chunk A, no ceremony.
