# Graph Action Turn Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an internal graph action turn adapter that loads graph runtime state, executes one confirmed action, saves graph/progress, and returns a graph-derived public state snapshot.

**Architecture:** Keep this under `game.runtime`, still below live API/flow. The adapter uses `GraphRepo` for load/save, `dispatch_graph_action` for rules, and `graph_to_front_state` for public output. It does not classify text, create confirmations, call LLMs, emit SSE, append logs, or replace legacy `/turn`.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers internal confirmed-action execution with persistence.

It includes:

- load graph runtime by `game_id`,
- execute one confirmed `Action`,
- save updated graph and progress,
- return updated runtime and graph front snapshot.

It does not include:

- API routes,
- SSE events,
- LLM classify/narrate calls,
- pending confirmation handling,
- log/history/dialogue writes.

## File Structure

- `server/src/game/runtime/turn.py`
  - New internal adapter and result model.
- `server/tests/game/runtime/test_graph_action_turn.py`
  - LocalFs persistence tests.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph runtime can execute and persist one confirmed action.

## Task 1: Turn Adapter Tests

**Files:**
- Create: `server/tests/game/runtime/test_graph_action_turn.py`

- [x] **Step 1: Write failing adapter tests**

Create async tests using `LocalFsGraphRepo` that assert:

- move action saves updated `located_at` edge, progress turn count, and front place,
- attack action saves ongoing `graph_combat_state` and front combat view,
- query action raises `GraphActionTurnError` and leaves saved graph/progress unchanged.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_turn.py -q
```

Expected RED: `src.game.runtime.turn` does not exist.

## Task 2: Turn Adapter Implementation

**Files:**
- Create: `server/src/game/runtime/turn.py`

- [x] **Step 1: Implement adapter**

Implement:

```python
class GraphActionTurnError(ValueError): ...
class GraphActionTurnResult(BaseModel): ...
async def run_graph_action_turn(repo: GraphRepo, game_id: str, action: Action) -> GraphActionTurnResult: ...
```

Rules:

- load runtime through `load_runtime_state`,
- dispatch through `dispatch_graph_action`,
- save graph first, then progress,
- build front state after dispatch,
- wrap dispatch/persistence failures in `GraphActionTurnError`,
- do not mutate the loaded runtime object in place.

- [x] **Step 2: Run adapter tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_turn.py -q
```

Expected GREEN: adapter tests pass.

## Task 3: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-action-turn-adapter.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/game/runtime/turn.py` executes and persists one confirmed graph action.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_turn.py server\tests\game\runtime\test_graph_action_dispatch.py server\tests\wire\test_graph_to_front.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\runtime\turn.py server\tests\game\runtime\test_graph_action_turn.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, graph runtime has the internal pieces needed for a future live graph `/turn` path: load, dispatch, apply, persist, and public snapshot. The next useful slice needs a live-flow design choice: whether to expose a separate graph route during migration or switch the existing route behind a feature flag.
