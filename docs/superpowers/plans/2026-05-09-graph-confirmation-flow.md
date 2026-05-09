# Graph Confirmation Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make graph-native attack-start and quest status actions require explicit confirmation before graph mutation.

**Architecture:** Keep `run_graph_action_turn` as the confirmed-action executor. Add a request layer that loads graph runtime state, stores `pending_confirmation` when an action needs confirmation, and adds a graph confirm path that clears or executes the stored action. The graph front snapshot exposes `pendingConfirmation` without leaking the internal payload.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice adds confirmation for:

- attack or cast that would start combat,
- quest accept,
- quest abandon.

This slice does not add confirmation for:

- dangerous rest,
- damaging item use,
- stealing,
- natural-language classify.

Those actions need more graph-native engine support before confirmation can safely resume them.

## File Structure

- `server/src/game/runtime/confirmation.py`
  - Graph confirmation builders and confirm/cancel executor.
- `server/src/wire/graph_to_front.py`
  - `pendingConfirmation` front payload.
- `server/src/api/routes/session.py`
  - Graph turn route uses the confirmation-aware request layer.
  - New `POST /session/{game_id}/graph/confirm` route.
- `server/tests/game/runtime/test_graph_confirmation.py`
  - Runtime tests for pending, cancel, confirm, and active-pending block.
- `server/tests/wire/test_graph_to_front.py`
  - Pending confirmation is exposed without internal payload.
- `server/tests/api/test_graph_session_routes.py`
  - API tests for attack confirmation and graph confirm.

## Task 1: Runtime Confirmation Tests

**Files:**
- Create: `server/tests/game/runtime/test_graph_confirmation.py`

- [x] **Step 1: Write failing tests**

Add tests that assert:

- attack-start stores `pending_confirmation` and does not start combat,
- a second action while pending raises an active-pending error,
- cancel clears pending without graph mutation,
- confirm executes the stored attack and starts graph combat,
- quest accept stores pending and confirm changes quest status to `active`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_confirmation.py -q
```

Expected RED: `src.game.runtime.confirmation` does not exist.

## Task 2: Wire And API Tests

**Files:**
- Modify: `server/tests/wire/test_graph_to_front.py`
- Modify: `server/tests/api/test_graph_session_routes.py`

- [x] **Step 1: Add failing wire/API tests**

Assert that graph front state exposes `pendingConfirmation` and omits internal `payload`.

Assert that:

- graph attack turn returns `pendingConfirmation`,
- graph confirm with `confirm` starts combat,
- graph confirm with `cancel` clears pending.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\wire\test_graph_to_front.py server\tests\api\test_graph_session_routes.py -q
```

Expected RED: graph front state and route do not expose confirmation yet.

## Task 3: Implementation

**Files:**
- Create: `server/src/game/runtime/confirmation.py`
- Modify: `server/src/wire/graph_to_front.py`
- Modify: `server/src/api/routes/session.py`

- [x] **Step 1: Add graph confirmation builder**

Build Korean confirmation copy from graph node names/titles. Store payload as:

```python
{"kind": "graph_action", "action": action.model_dump(mode="json", by_alias=True)}
```

- [x] **Step 2: Add request executor**

`run_graph_action_request` stores pending and saves progress when confirmation is needed. Otherwise it delegates to `run_graph_action_turn`.

- [x] **Step 3: Add confirm executor**

`run_graph_confirm` validates id, clears pending on cancel, and executes the stored action on confirm.

- [x] **Step 4: Expose pending in graph front state**

Add `pending_confirmation` to `GraphFrontStatePayload` so JSON output contains `pendingConfirmation`.

- [x] **Step 5: Wire API routes**

Use `run_graph_action_request` in graph turn and add `POST /session/{game_id}/graph/confirm`.

## Task 4: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-confirmation-flow.md`

- [x] **Step 1: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_confirmation.py server\tests\wire\test_graph_to_front.py server\tests\api\test_graph_session_routes.py -q
```

- [x] **Step 2: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\runtime\confirmation.py server\src\wire\graph_to_front.py server\src\api\routes\session.py server\tests\game\runtime\test_graph_confirmation.py server\tests\wire\test_graph_to_front.py server\tests\api\test_graph_session_routes.py
```

- [x] **Step 3: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

## Stop Point

After this slice, graph routes have the same essential UX guard as legacy routes for the two most visible cases: quest start and combat start. The next useful slice is graph natural-language input: classify player text into `Action` and feed the confirmation-aware graph request layer.
