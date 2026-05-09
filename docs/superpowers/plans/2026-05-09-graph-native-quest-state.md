# Graph-Native Quest State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add graph-native quest state planners for accept, abandon, complete, and fail transitions.

**Architecture:** Keep this slice focused on quest node properties. The new engine returns `GraphChange` objects that update `status`, `success_reason`, or `fail_reason`; trigger detection, reward payment, active quest progress, and live flow wiring stay in later slices.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers quest state transitions only.

It does not inspect trigger edges, give rewards, mutate progress `active_quest_id`, or wire live `/turn`.

## File Structure

- `server/src/game/engines/graph_quest.py`
  - New pure graph quest state planner.
- `server/tests/game/engines/test_graph_quest.py`
  - Unit tests for accept, abandon, complete, fail, idempotent terminal handling, and validation.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph-native quest state planning exists.

## Task 1: Quest State Tests

**Files:**
- Create: `server/tests/game/engines/test_graph_quest.py`

- [x] **Step 1: Write failing graph quest tests**

Create tests that assert:

- pending quest accept sets `status` to `active`,
- active quest abandon sets `status` to `abandoned`,
- active quest complete sets `status` and `success_reason`,
- active quest fail sets `status` and `fail_reason`,
- terminal quests reject later state changes,
- missing quest ids and non-quest nodes raise `GraphQuestError`,
- every emitted change can be applied one by one with `apply_graph_change`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_quest.py -q
```

Expected RED: `src.game.engines.graph_quest` does not exist.

## Task 2: Quest State Planner

**Files:**
- Create: `server/src/game/engines/graph_quest.py`

- [x] **Step 1: Implement graph quest planner**

Implement:

- `GraphQuestError(ValueError)`
- `GraphQuestResult(BaseModel)`
- `plan_quest_accept(graph, quest_id)`
- `plan_quest_abandon(graph, quest_id)`
- `plan_quest_complete(graph, quest_id, reason=None)`
- `plan_quest_fail(graph, quest_id, reason=None)`

Rules:

- quest id must resolve to a quest node,
- `accept` allows `locked` or `pending`, and leaves `active` unchanged,
- `abandon` allows `pending` or `active`,
- `complete` allows `active`,
- `fail` allows `pending` or `active`,
- `completed`, `failed`, and `abandoned` reject further state changes,
- result includes the previous and next status.

- [x] **Step 2: Run graph quest tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_quest.py -q
```

Expected GREEN: graph quest tests pass.

## Task 3: Roadmap And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-native-quest-state.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/game/engines/graph_quest.py` plans graph-native quest status transitions.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_quest.py server\tests\game\domain\test_graph_contract.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\engines\graph_quest.py server\tests\game\engines\test_graph_quest.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, Phase 5 covers movement, item placement, non-damage item use, and quest status planning. The next slice should handle rest planning or add a shared graph-runtime apply wrapper.
