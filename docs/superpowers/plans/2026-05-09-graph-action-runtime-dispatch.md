# Graph Action Runtime Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a common graph-runtime dispatcher that routes confirmed graph-native `Action` objects to the graph planners already built.

**Architecture:** Keep this as a lower runtime layer, not a live flow replacement. The dispatcher receives a `GameRuntimeState` and one already-approved `Action`, calls the matching graph planner, applies `GraphChange` objects through `apply_runtime_graph_changes`, and returns a new runtime. Risk confirmation, LLM calls, SSE events, persistence writes, and client payloads remain outside this slice.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers confirmed runtime execution for existing graph planners.

It includes:

- move,
- transfer,
- equip and unequip through `transfer.how`,
- item use,
- quest accept and abandon,
- safe rest,
- combat start/advance through the graph combat runtime dispatcher,
- normal turn-count advancement for executed non-rest actions,
- rest turn-count jump to next dawn.

It does not include:

- classify,
- pending confirmation creation,
- query answering,
- live `/turn`,
- quest completion trigger checks,
- growth choices.

## File Structure

- `server/src/game/runtime/dispatch.py`
  - New common graph action dispatcher.
- `server/src/game/runtime/__init__.py`
  - Re-export dispatcher types/functions.
- `server/tests/game/runtime/test_graph_action_dispatch.py`
  - Unit tests for routing and progress updates.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that confirmed graph actions can run through one runtime seam.

## Task 1: Dispatcher Tests

**Files:**
- Create: `server/tests/game/runtime/test_graph_action_dispatch.py`

- [x] **Step 1: Write failing dispatcher tests**

Create tests that assert:

- `move` applies `located_at` changes and increments `turn_count`,
- `transfer` with `how="equip"` equips a carried item,
- `use` applies healing and consumes the item,
- `rest` restores HP/MP and sets `turn_count` to `next_dawn_turn`,
- `attack` delegates to graph combat dispatch and stores ongoing combat progress,
- `query` raises `GraphActionDispatchError` because query belongs to read-only flow.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_dispatch.py -q
```

Expected RED: `src.game.runtime.dispatch` does not exist.

## Task 2: Dispatcher Implementation

**Files:**
- Create: `server/src/game/runtime/dispatch.py`
- Modify: `server/src/game/runtime/__init__.py`

- [x] **Step 1: Implement result and error models**

Implement:

```python
class GraphActionDispatchError(ValueError): ...
class GraphActionDispatchResult(BaseModel): ...
```

The result stores:

- `runtime`,
- `kind`,
- `applied`,
- `changed_node_ids`,
- `changed_edge_ids`,
- `outcome`.

- [x] **Step 2: Implement action routing**

Implement:

```python
def dispatch_graph_action(runtime: GameRuntimeState, action: Action) -> GraphActionDispatchResult: ...
```

Rules:

- if `runtime.progress.graph_combat_state` exists, delegate to `dispatch_graph_combat_action`,
- `attack` and `cast` delegate to `dispatch_graph_combat_action`,
- `move` uses `plan_character_move` with `destination = action.to or action.what`,
- `transfer` uses:
  - `how="equip"` -> `plan_item_equip`,
  - `how="unequip"` -> `plan_item_unequip`,
  - otherwise -> `plan_item_transfer`,
- `use` uses `plan_item_use`,
- `rest` uses `plan_safe_rest`,
- `speak`, `perceive`, `query`, and `pass` outside combat raise `GraphActionDispatchError`,
- non-rest successful actions increment `turn_count` by one,
- rest sets `turn_count` to `GraphRestResult.next_turn_count`.

- [x] **Step 3: Re-export dispatcher**

Add `GraphActionDispatchError`, `GraphActionDispatchResult`, and `dispatch_graph_action` to `server/src/game/runtime/__init__.py`.

- [x] **Step 4: Run dispatcher tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_dispatch.py -q
```

Expected GREEN: dispatcher tests pass.

## Task 3: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-action-runtime-dispatch.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/game/runtime/dispatch.py` routes confirmed graph-native actions to graph planners.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_dispatch.py server\tests\game\runtime\test_graph_combat_dispatch.py server\tests\game\runtime\test_runtime_apply.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\runtime\dispatch.py server\src\game\runtime\__init__.py server\tests\game\runtime\test_graph_action_dispatch.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, existing graph planners can be exercised through one runtime seam. The next useful slice is live graph flow integration behind the existing pending-confirmation checks.
