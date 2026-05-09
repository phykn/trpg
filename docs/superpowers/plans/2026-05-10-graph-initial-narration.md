# Graph Initial Narration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM narration only for the first graph location, while keeping later movement turns as system-card-only results.

**Architecture:** Graph facts remain the source of truth. The graph init route may append one GM narration log built from the initial place view, but graph turn execution does not call narration for move actions. The LLM can write prose only; it cannot return graph changes, ids, rewards, or state updates.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Files

- Create `server/src/game/runtime/intro.py` for first-place narration prompt and log append.
- Modify `server/src/api/routes/session.py` so `/session/graph/init` receives `LLMClient` and appends initial narration after graph creation.
- Modify `server/tests/api/test_graph_session_routes.py` to prove graph init persists one GM narration and later move appends only an act card.
- Modify `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md` to record the new narration policy.

## Task 1: Initial Narration Behavior

- [x] **Step 1: Write the failing API test**

Add a test that initializes a graph session with a fake LLM answer, asserts the returned state log has one `gm` entry, executes a `move`, then asserts the saved log has exactly one `gm` entry and one `act` entry.

- [x] **Step 2: Run the focused test and verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py::test_graph_init_adds_intro_narration_but_move_stays_system_card_only -q
```

Expected: FAIL because graph init currently returns no GM narration log.

- [x] **Step 3: Implement minimal graph intro narration**

Create `server/src/game/runtime/intro.py` with a function that loads the current place from the graph, asks the LLM for one or two Korean sentences, appends a `GMLogEntry`, increments `next_log_id`, and saves progress. The function must not mutate graph facts or advance `turn_count`.

- [x] **Step 4: Wire graph init only**

Call the intro function only from `/session/graph/init`. Do not call it from `/session/{game_id}/graph/turn`, `/graph/input`, or `/graph/confirm`.

- [x] **Step 5: Run the focused test and verify GREEN**

Run the same focused test. Expected: PASS.

## Task 2: Regression Coverage And Docs

- [x] **Step 1: Run graph route and runtime tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py server\tests\game\runtime -q
```

Expected: all selected tests pass.

- [x] **Step 2: Update roadmap**

Record that graph init may create the only automatic LLM narration for the first location and that later move actions remain system cards.

- [x] **Step 3: Run lint**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\runtime\intro.py server\src\api\routes\session.py server\tests\api\test_graph_session_routes.py
```

Expected: all checks pass.

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: all server tests pass.
