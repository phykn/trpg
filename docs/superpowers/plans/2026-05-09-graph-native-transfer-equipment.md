# Graph-Native Transfer And Equipment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add graph-native item transfer, equip, and unequip planners that return validated `GraphChange` objects.

**Architecture:** Keep economic rules, carry limits, and stat requirements out of this slice. The new pure engine only moves item placement edges (`carries`, `equips`, `located_at`, `hidden_at`, `reward_of`) so graph invariants remain the source of truth for where an item is.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers item placement and equipment edges only.

It does not wire live `/turn`, does not price trades, does not enforce carry weight, and does not validate item stat requirements.

## File Structure

- `server/src/game/engines/graph_transfer.py`
  - New pure graph item placement planner.
- `server/tests/game/engines/test_graph_transfer.py`
  - Unit tests for transfer, equip, unequip, source validation, and slot replacement.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph-native transfer/equipment planning exists.

## Task 1: Transfer And Equipment Tests

**Files:**
- Create: `server/tests/game/engines/test_graph_transfer.py`

- [x] **Step 1: Write failing graph transfer tests**

Create tests that assert:

- transferring an item from one carrier to another removes the old `carries` edge and adds a new one,
- transferring an equipped item removes `equips` and adds destination `carries`,
- equipping a carried item removes `carries` and adds `equips` with `slot`,
- equipping into an occupied slot unequips the old item back to `carries`,
- unequipping removes `equips` and adds `carries`,
- wrong source and missing ids raise `GraphTransferError`,
- every emitted change can be applied one by one with `apply_graph_change`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_transfer.py -q
```

Expected RED: `src.game.engines.graph_transfer` does not exist.

## Task 2: Transfer And Equipment Planner

**Files:**
- Create: `server/src/game/engines/graph_transfer.py`

- [x] **Step 1: Implement graph transfer planner**

Implement:

- `GraphTransferError(ValueError)`
- `GraphItemTransferResult(BaseModel)`
- `plan_item_transfer(graph, item_id, to_character_id, from_node_id=None)`
- `plan_item_equip(graph, character_id, item_id, slot)`
- `plan_item_unequip(graph, character_id, item_id)`

Rules:

- item must be an item node,
- character targets must be character nodes,
- `from_node_id`, when present, must match the current placement owner,
- transfer removes the current placement edge and adds `carries:<to_character_id>:<item_id>`,
- equip removes the current placement edge and adds `equips:<character_id>:<item_id>` with `{"slot": slot}`,
- equipping into a filled slot removes the old `equips` edge and adds `carries:<character_id>:<old_item_id>`,
- unequip removes the matching `equips` edge and adds `carries:<character_id>:<item_id>`.

- [x] **Step 2: Run graph transfer tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_transfer.py -q
```

Expected GREEN: graph transfer tests pass.

## Task 3: Roadmap And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-native-transfer-equipment.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/game/engines/graph_transfer.py` plans graph-native item transfer, equip, and unequip changes.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_transfer.py server\tests\game\engines\test_graph_move.py server\tests\game\domain\test_graph_contract.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\engines\graph_transfer.py server\tests\game\engines\test_graph_transfer.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, Phase 5 has graph-native planners for movement and item placement. The next slice should choose between item use planning and a shared graph-runtime apply wrapper.
