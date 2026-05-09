# Graph API Routes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose graph-native game init and confirmed-action turn execution through separate API routes without changing the legacy `/session/init` and `/session/{game_id}/turn` routes.

**Architecture:** Add a `GraphRepo` app dependency beside the existing save and scenario repos. Graph routes call the already-tested graph init and graph turn adapter, then return the graph-derived front snapshot as JSON. No SSE, classify, confirmation, or LLM narration is added in this slice.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice adds:

- `POST /session/graph/init`
- `POST /session/{game_id}/graph/turn`
- `GraphRepo` factory/dependency wiring
- API tests that use `LocalFsGraphRepo`

This slice does not add:

- natural-language classify,
- pending confirmation handling,
- SSE event streaming,
- client UI calls,
- replacement of legacy `/session/{game_id}/turn`.

## File Structure

- `server/src/api/schema.py`
  - Graph route request and response models.
- `server/src/api/deps.py`
  - `get_graph_repo`.
- `server/src/api/routes/session.py`
  - Separate graph init and graph turn handlers.
- `server/src/db/factory.py`
  - Production `SupabaseGraphRepo` factory.
- `server/run_api.py`
  - Optional `graph_repo` app state for tests and production create path.
- `server/tests/api/test_graph_session_routes.py`
  - Route tests for graph init, graph turn, missing game, and read-only action rejection.

## Task 1: Graph API Tests

**Files:**
- Create: `server/tests/api/test_graph_session_routes.py`

- [x] **Step 1: Write failing route tests**

Add tests that assert:

- graph init persists graph/progress and returns hero/place state,
- graph turn moves the player and persists turn count,
- missing graph game returns 404,
- query action returns 422 and does not advance turn count.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py -q
```

Expected RED: graph route schema/dependencies do not exist yet.

## Task 2: Route Implementation

**Files:**
- Modify: `server/src/api/schema.py`
- Modify: `server/src/api/deps.py`
- Modify: `server/src/api/routes/session.py`
- Modify: `server/src/db/factory.py`
- Modify: `server/run_api.py`

- [x] **Step 1: Add graph route schemas**

Create `GraphTurnRequest` and reuse the existing `InitRequest` for graph init.

- [x] **Step 2: Add graph repo dependency**

Expose `get_graph_repo` from app state and return HTTP 503 when production wiring is absent.

- [x] **Step 3: Wire production graph repo**

Build `SupabaseGraphRepo` from the same Supabase URL and service key as other server repos.

- [x] **Step 4: Add routes**

Add graph routes under the existing protected session router:

- `POST /session/graph/init`
- `POST /session/{game_id}/graph/turn`

Map missing graph saves to 404 and invalid graph actions to 422.

- [x] **Step 5: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py -q
```

Expected GREEN: graph API tests pass.

## Task 3: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-api-routes.md`

- [x] **Step 1: Update roadmap**

Add the current-state bullet:

```markdown
- Separate graph API routes can initialize a graph game and execute one confirmed graph action.
```

- [x] **Step 2: Run related tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py server\tests\game\flow\test_init_graph.py server\tests\game\runtime\test_graph_action_turn.py -q
```

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\api\schema.py server\src\api\deps.py server\src\api\routes\session.py server\src\db\factory.py server\run_api.py server\tests\api\test_graph_session_routes.py
```

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

## Stop Point

After this slice, graph-native gameplay can be driven through separate JSON API routes. The next useful slice is confirmation-aware graph turn flow: classify natural-language input into `Action`, emit pending confirmations for risky actions, and only call `run_graph_action_turn` after confirmation.
