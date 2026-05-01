# CLAUDE.md

## Architecture

This is a multi-agent pipeline: **Input Parsing → Profiler → Recommendation → Critic**, sequenced by an Orchestrator. The full pipeline spec lives in `.claude/coffee_agent_prd.md`.

### Agent communication
Agents pass **typed Pydantic objects**, not raw strings. The chain is:
- `list[str]` (raw inputs) → Input Parsing Agent → `list[BeanProfile]` persisted to DB
- `list[BeanProfile]` (full history) → Profiler Agent → `TasteProfile` persisted to DB
- `TasteProfile` → Recommendation Agent → `list[RecommendationCandidate]`
- candidates + profile → Critic Agent → pruned `list[RecommendationCandidate]` + `critic_notes`

### LLM calls
All agents route through `app/llm.py::llm_complete(prompt, span)`. It uses the `google.genai` SDK (not the deprecated `google.generativeai`). Prompts must end with `"Return only valid JSON. No preamble, no markdown fences."` — the function strips markdown fences if the model wraps its output anyway.

### Scoring is deterministic, not LLM-based
`app/tools/scorer.py::score_candidate()` computes match scores using a fixed rubric: origin (+0.3), process (+0.2), roast level (+0.2), flavor overlap (+0.1 each, capped at 0.3), avoided flavor penalty (−0.15). The Critic Agent does qualitative review on top of these scores.

### Agents that use a ReAct loop
Input Parsing and Recommendation agents are designed as ReAct loops (max 5 iterations). Profiler and Critic agents make a single LLM call each. The Orchestrator is pure Python control flow with no LLM calls.

### Database
`asyncpg` connection pool initialized in `app/db/connection.py`. All queries are in `app/db/queries.py` as typed async functions. `bean_profiles` has a `UNIQUE(user_id, roaster, name)` constraint — all inserts use upsert. Schema in `app/db/migrations/001_init.sql`.

## Implementation Status

**Built:** Pydantic models, DB layer, all tools (`detect_input`, `web_search`, `scrape_page`, `scrape_roaster_catalog`, `score_candidate`), LLM wrapper, LLM call logging.

**Not yet built:** `app/agents/` (all four agents + orchestrator), `app/main.py` (FastAPI endpoints), `TraceLogger` in `app/observability/`.

The PRD in `.claude/coffee_agent_prd.md` contains exact prompt templates, ReAct loop pseudocode, and FastAPI endpoint schemas to implement against.
