# Graph Query Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer graph-native `query` actions from graph facts without advancing time or mutating the graph.

**Architecture:** Keep query handling inside graph runtime before dispatch. Query returns a Korean `message` and the unchanged graph front snapshot. Graph action API responses gain optional `status` and `message` fields while preserving the existing `game_id` and `state` shape.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice answers:

- surroundings,
- exits,
- inventory,
- status.

This slice does not add:

- LLM narration for query answers,
- query history/log persistence,
- client rendering changes,
- hidden information disclosure.

## File Structure

- `server/src/game/runtime/query.py`
  - Pure graph query answer builder.
- `server/src/game/runtime/confirmation.py`
  - Routes `Action(verb="query")` before mutation dispatch.
- `server/src/api/schema.py`
  - Graph action response model with optional `status` and `message`.
- `server/src/api/routes/session.py`
  - Graph turn/input/confirm return the richer graph action response.
- `server/tests/game/runtime/test_graph_runtime_query.py`
  - Runtime query answer tests.
- `server/tests/api/test_graph_session_routes.py`
  - API query response tests.

## Task 1: Query Tests

**Files:**
- Create: `server/tests/game/runtime/test_graph_runtime_query.py`
- Modify: `server/tests/api/test_graph_session_routes.py`

- [x] **Step 1: Write failing tests**

Add tests that assert:

- query surroundings returns a Korean answer from visible graph facts,
- query exits returns exits and does not advance `turn_count`,
- graph API returns `status="answered"` and `message`,
- graph input route can classify `query` and return `message`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_runtime_query.py server\tests\api\test_graph_session_routes.py -q
```

Expected RED: graph query runtime and graph response fields do not exist.

## Task 2: Implementation

**Files:**
- Create: `server/src/game/runtime/query.py`
- Modify: `server/src/game/runtime/confirmation.py`
- Modify: `server/src/api/schema.py`
- Modify: `server/src/api/routes/session.py`

- [x] **Step 1: Build query answers**

Use `build_graph_surroundings` and produce short Korean 합니다체 answers.

- [x] **Step 2: Route query before dispatch**

`run_graph_action_request` handles `Action(verb="query")` without saving graph/progress.

- [x] **Step 3: Return message through API**

Use a graph action response model with optional `status` and `message`.

## Task 3: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-query-flow.md`

- [x] **Step 1: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_runtime_query.py server\tests\game\runtime\test_graph_input.py server\tests\api\test_graph_session_routes.py -q
```

- [x] **Step 2: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\runtime\query.py server\src\game\runtime\confirmation.py server\src\api\schema.py server\src\api\routes\session.py server\tests\game\runtime\test_graph_runtime_query.py server\tests\api\test_graph_session_routes.py
```

- [x] **Step 3: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

## Stop Point

After this slice, graph input supports non-mutating questions. The next useful slice is graph narrative response: after a mutating action succeeds, produce a short LLM narration from graph context without letting the LLM change facts.
