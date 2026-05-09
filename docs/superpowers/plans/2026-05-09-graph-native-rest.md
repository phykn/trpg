# Graph-Native Rest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a graph-native safe-rest planner that restores character resources and reports the next turn count.

**Architecture:** Keep encounter resolution out of this slice. The planner reads `GameRuntimeState`, emits graph changes for character HP/MP/gold, and returns `next_turn_count`; the caller will apply graph changes through the runtime apply wrapper and update progress in a later flow-integration slice.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers safe full recovery only.

It does not roll dangerous encounters, summon enemies, persist runtime changes, or wire live `/turn`.

## File Structure

- `server/src/game/engines/graph_rest.py`
  - New pure graph safe-rest planner.
- `server/tests/game/engines/test_graph_rest.py`
  - Unit tests for HP/MP recovery, gold cost, next dawn turn, unsafe-location rejection, and validation.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph-native safe-rest planning exists.

## Task 1: Rest Tests

**Files:**
- Create: `server/tests/game/engines/test_graph_rest.py`

- [x] **Step 1: Write failing graph rest tests**

Create tests that assert:

- safe rest sets `hp` to `max_hp` and `mp` to `max_mp`,
- safe rest deducts `RULES.recovery.cost_gold`,
- result reports `next_dawn_turn(progress.turn_count)`,
- the result changes apply through `apply_runtime_graph_changes`,
- unsafe location raises `GraphRestError`,
- insufficient gold raises `GraphRestError`,
- missing actor raises `GraphRestError`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_rest.py -q
```

Expected RED: `src.game.engines.graph_rest` does not exist.

## Task 2: Safe-Rest Planner

**Files:**
- Create: `server/src/game/engines/graph_rest.py`

- [x] **Step 1: Implement safe-rest planner**

Implement:

- `GraphRestError(ValueError)`
- `GraphRestResult(BaseModel)`
- `plan_safe_rest(runtime, actor_id)`

Rules:

- actor must be a character node,
- actor must be alive unless `alive` is absent,
- actor must have enough `gold` for `RULES.recovery.cost_gold`,
- if actor has a current `located_at` edge and that location has `sleep_risk != "safe"`, reject,
- emit `set_node_property` changes for `gold`, `hp`, and `mp`,
- return `next_turn_count=next_dawn_turn(runtime.progress.turn_count)`.

- [x] **Step 2: Run graph rest tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_rest.py -q
```

Expected GREEN: graph rest tests pass.

## Task 3: Roadmap And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-native-rest.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/game/engines/graph_rest.py` plans graph-native safe-rest recovery changes.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_rest.py server\tests\game\runtime\test_runtime_apply.py server\tests\game\domain\test_graph_contract.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\engines\graph_rest.py server\tests\game\engines\test_graph_rest.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, Phase 5 covers movement, item placement, non-damage item use, quest status, runtime apply, and safe rest. The next slice should start growth/skill planning or defer to a live-flow integration pass.
