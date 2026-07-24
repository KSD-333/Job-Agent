# AI Career Agent — Scaffold

This is a working skeleton, not a finished system: it imports, compiles,
and the graph wires together correctly, but most agent functions raise
`NotImplementedError` at the exact point where real logic (LLM calls,
scraping, PDF rendering) needs to go. Errors from unimplemented functions
are caught and appended to `state["errors"]` rather than crashing the
pipeline, so you can run `python graph_flow/graph.py` right away and see
it flow start-to-end with empty results.

## What's here

- `graph_flow/state.py` — the shared `CareerAgentState` TypedDict every node reads/writes
- `graph_flow/graph.py` — builds the main LangGraph pipeline + a separate interview-prep graph
- `agents/*.py` — one file per agent, each with a `run_*` function matching the LangGraph node signature `(state) -> dict`
- `prompts/*.md` — prompt templates referenced by the agents (fill in `{placeholders}` at call time)
- `database/*.csv` — seeded with headers only
- `resumes/resume.json` — the fixed schema Agent 1 should populate
- `app.py` — FastAPI wrapper exposing `/run-pipeline`, `/interview-prep`, `/tracker/status`

## One important deviation from the original spec

The `langgraph/` folder was renamed to **`graph_flow/`**. A folder literally
named `langgraph` sitting next to your code shadows the real `langgraph`
pip package on Python's import path — `from langgraph.graph import StateGraph`
would import your own empty folder instead of the library and fail
immediately. Keep this rename (or pick a different name) rather than
reverting it.

## Getting it running

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in GROQ_API_KEY etc.
python graph_flow/graph.py
```

You'll see it complete with `qualified_matches: 0` and a handful of
`NotImplementedError` messages in `errors` — that's expected until you
wire up the TODOs.

## Suggested build order

1. **`agents/resume_agent.py`** — get one real resume turning into `resume.json`. Everything downstream depends on this.
2. **`agents/discovery_agent.py`** — start with `fetch_greenhouse_jobs` / `fetch_lever_jobs` (stable public APIs). Treat LinkedIn/Naukri/Wellfound as a later, higher-risk phase.
3. **`agents/matcher_agent.py`** — deterministic skill overlap first (rapidfuzz), LLM scoring second.
4. **`agents/tailor_agent.py`** — the hallucination-check step (`validate_no_hallucination`) matters more than the PDF rendering; get that right before polishing layout.
5. **`agents/cover_letter_agent.py`**, then **`agents/tracker_agent.py`** (already has working CSV/file logic, just needs upstream data).
6. **`agents/recruiter_agent.py`** and **`agents/interview_agent.py`** last — both depend on real job/company data existing first.
7. Analytics (`analytics_node` in `graph_flow/graph.py`) and the Learning Agent (skill-gap detection) already have working logic once `tracker_rows` and `qualified_matches` are populated for real.

## Notes on the tech stack choices

- **Postgres vs CSV**: the scaffold uses CSV as source of truth (via `agents/tracker_agent.py`) to keep the MVP simple. `DATABASE_URL` is wired into `utils/config.py` if/when you want to migrate.
- **Recruiter Research Agent**: implemented to only use public sources (careers pages, public LinkedIn search) — deliberately does not guess emails or scrape private profile data. Verify contacts manually before outreach.
