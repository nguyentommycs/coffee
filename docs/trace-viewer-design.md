# Design: Pipeline Trace Viewer

## Goal

A "Traces" view in the existing React frontend that shows each recommendation pipeline
run as a waterfall: every agent span, every LLM call (with model, tokens, latency,
truncated prompt/response), and every scrape tool call, with errors and the broad-mode
retry visible. This makes the multi-agent pipeline observable and demo-able.

## Current state (verified in code)

- `app/observability/trace.py::TraceLogger` records **flat, top-level spans only**.
  The orchestrator (`app/agents/orchestrator.py::run_recommendations`) opens spans
  `profiler`, `recommendation`, `critic`, and optionally `recommendation_retry` /
  `critic_retry`. Nothing inside the agents is traced.
- The trace is already persisted: `insert_recommendation_run` writes `trace.dump()`
  into `recommendation_runs.pipeline_trace` (jsonb). **No schema migration needed.**
- No API endpoint returns `pipeline_trace` (`get_recommendation_runs` selects other
  columns only).
- `app/llm.py::llm_complete` already computes input/output token counts and latency
  per call (`LLMCallRecord`) but only emits them via `logger.debug` — the data is
  discarded. The `span: str` parameter is just a label.
- Frontend is React + Vite, no router, plain CSS in `index.css`, data fetching via
  TanStack Query in `queries.ts` / `api.ts`. `App.tsx` renders panels directly.

## Part 1 — Backend: deepen the trace

### 1a. Span schema

Keep `TraceLogger.spans` a **flat list**; add fields so the frontend can rebuild the
tree. Each span:

```json
{
  "id": "short-uuid",
  "parent_id": "short-uuid | null",
  "name": "profiler | llm:recommendation_extract | scrape_page | ...",
  "type": "agent | llm | tool",
  "start": 1723050000.123,          // epoch seconds (existing field)
  "duration_ms": 1234.56,           // existing field
  "status": "ok | error",           // existing field
  "error": "...",                   // existing, only on error
  "attrs": { ... }                  // type-specific, see below
}
```

`dump()` keeps its existing top-level shape (`pipeline_id`, `user_id`,
`total_duration_ms`, `spans`) and adds nothing else. Replace the current freeform
`"input": kwargs` with `attrs`.

Per-type `attrs`:
- **agent**: whatever kwargs the orchestrator passes (e.g. `n_beans`, `broad_mode`).
- **llm**: `model`, `label` (the existing `span` string passed to `llm_complete`),
  `input_tokens`, `output_tokens`, `retried_429` (bool), `retried_json` is not
  knowable inside llm.py — skip it; plus `prompt` and `response` **truncated to
  4000 chars each** (append `"… [truncated]"` when cut). Token fields may be null
  if `usage_metadata` is missing — never let attrs collection raise (mirror the
  existing `try/except` discipline in llm.py).
- **tool**: for scrapes: `url`, `result_chars` (or `items_found` for the catalog
  scraper); for scoring: `candidates_scored`.

### 1b. Ambient trace via contextvars (no signature churn)

Add to `app/observability/trace.py`:

```python
_current_trace: ContextVar[TraceLogger | None] = ContextVar("current_trace", default=None)
_current_span_id: ContextVar[str | None] = ContextVar("current_span_id", default=None)
```

- `TraceLogger.span(name, type="agent", **attrs)` context manager: creates the span
  with `parent_id = _current_span_id.get()`, sets `_current_span_id` to its own id
  for the duration (restore via `ContextVar.reset(token)` in `finally`).
- Module-level helper used by instrumentation sites:

```python
@contextmanager
def child_span(name: str, type: str, **attrs):
    trace = _current_trace.get()
    if trace is None:
        yield None          # no-op when no pipeline is running (e.g. /beans parsing, tests)
        return
    with trace.span(name, type=type, **attrs) as span:
        yield span
```

- The orchestrator sets/resets `_current_trace` around the pipeline (small
  helper method or context manager on TraceLogger, e.g. `with trace.activate():`).

`asyncio.gather` copies the contextvar context into each task at creation, so the
parallel `scrape_page` calls in the recommendation agent get the correct
`parent_id` automatically. Yielding a mutable span dict lets call sites append
result attrs after the work completes (e.g. `span["attrs"]["result_chars"] = len(text)`).

### 1c. Instrumentation sites (keep the diff minimal)

- `app/agents/orchestrator.py`: existing `trace.span(...)` calls gain
  `type="agent"`; wrap the pipeline body in `with trace.activate():`. No other
  logic changes.
- `app/llm.py::llm_complete`: wrap the whole call (including 429 sleep/retry) in
  `child_span(f"llm:{span}", type="llm")`; fill attrs as in 1a. On the final
  failure path the context manager already records `status="error"`.
- `app/tools/scraper.py`: wrap `scrape_page` and `scrape_roaster_catalog` bodies
  in `child_span`, recording `url` and result size.
- `app/agents/recommendation.py`: wrap the scoring loop in one
  `child_span("score_candidates", type="tool", ...)` — do **not** create a span
  per candidate.
- Do **not** instrument `parse_and_persist` / input parsing — it has no
  TraceLogger today and is out of scope.

### 1d. API

Two additions to `app/main.py` + one query in `app/db/queries.py`:

- `GET /traces?user_id=` → list of run summaries, newest first:
  `[{run_id, created_at, total_duration_ms, status, llm_calls, total_input_tokens,
  total_output_tokens, span_count}]`. Implement by fetching
  `id, created_at, pipeline_trace` rows and computing the summary in Python
  (row counts are small; no jsonb SQL gymnastics). `status` is `"error"` if any
  span errored, else `"ok"`.
- `GET /traces/{run_id}?user_id=` → `{run_id, created_at, trace: <pipeline_trace>}`;
  404 if not found **or belongs to another user** (filter by both id and user_id
  in SQL, matching the pattern in `update_bean_profile`).

Old rows persisted before this change lack `id`/`parent_id`/`type`/`attrs` — the
summary computation and the frontend must tolerate missing fields (treat as flat
top-level agent spans, tokens 0).

## Part 2 — Frontend: the viewer

No new dependencies. No router — add a lightweight view toggle.

### Navigation

`App.tsx` gains `const [view, setView] = useState<'dashboard' | 'traces'>('dashboard')`.
`Header` gets two tab buttons (Dashboard / Traces) styled consistently with
`index.css`. `view === 'traces'` renders `<TracesPanel userId={username} />`
instead of the existing panels.

### Components (`frontend/src/components/`)

- **`TracesPanel.tsx`** — layout: run list (left, ~260px), waterfall (center),
  span detail (right, shown when a span is selected; collapses when none).
  Owns `selectedRunId` / `selectedSpanId` state.
- **`TraceRunList.tsx`** — from `GET /traces`: one row per run with relative time,
  duration, `N llm calls · X tok`, and a status dot (green ok / red error).
  Clicking selects the run.
- **`TraceWaterfall.tsx`** — from `GET /traces/{id}`: rebuild the tree from
  `parent_id`, render one row per span, indented by depth, ordered by `start`.
  Each row: name, duration label, and a horizontal bar positioned/sized as a
  percentage of `total_duration_ms` (pure CSS: `left`/`width` % on an absolutely
  positioned div — no chart library). Color by `type` (agent / llm / tool),
  error spans red regardless of type. Clicking a row selects it.
- **`SpanDetail.tsx`** — name, type, status, duration, then attrs as a key/value
  list. For llm spans, `prompt` and `response` render in `<pre>` blocks with
  `overflow: auto` and monospace styling; token counts shown as
  `1,234 in / 567 out`. Error text shown prominently when present.

### Data layer

- `api.ts`: `fetchTraces(userId)`, `fetchTrace(userId, runId)`.
- `types.ts`: `TraceSummary`, `TraceSpan`, `TraceDetail` mirroring the span schema
  (all new fields optional to tolerate old traces).
- `queries.ts`: `useTraces(userId)`, `useTrace(userId, runId)` following the
  existing TanStack Query patterns. Traces are immutable once written →
  `staleTime: Infinity` on the detail query.

### Styling

Extend `index.css` following its existing conventions (class naming, spacing,
colors). Type colors should be muted/desaturated; keep the waterfall readable.

## Part 3 — Tests

Backend only (the frontend has no test setup — do not introduce one):

- `tests/test_trace.py` (new): nesting produces correct `parent_id`s; `child_span`
  is a no-op returning `None` when no trace is active; exception inside a span sets
  `status="error"` and re-raises; `dump()` retains the existing top-level keys.
- `tests/test_llm.py` or extend existing patterns: with a mocked genai client
  (follow how existing agent tests fake `llm_complete`/the client), an active
  trace collects an `llm` span with token attrs and truncated prompt.
- API tests for `GET /traces` and `GET /traces/{run_id}` with mocked queries,
  including: 404 on wrong user, summary computed correctly from a fixture trace,
  and a legacy trace (old flat spans, no `attrs`) not crashing the summary.

Verification loop: `pytest` green before and after; run the two new endpoints
against fixture data; `cd frontend && npm run build` must pass (type-checks the
new TSX).

## Out of scope (do not build)

- Dollar-cost estimation, live/streaming traces, tracing the `/beans` input-parsing
  path, DB migrations, per-candidate scoring spans, any charting library, a router.
