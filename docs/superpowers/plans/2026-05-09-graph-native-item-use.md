# Graph-Native Item Use Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a graph-native item-use planner for non-damage consumables and trigger items.

**Architecture:** Keep this slice pure and additive. The planner reads item and character node properties, returns `GraphChange` objects for HP/MP/buff updates and consumable removal, and rejects damage consumables until the graph-native combat/death-save slice owns that behavior.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers:

- heal consumables,
- MP restore consumables,
- buff consumables,
- trigger-only items,
- consumable item removal from `carries`.

It does not handle damage consumables, death saves, revive coins, quest trigger resolution, or live `/turn` wiring.

## File Structure

- `server/src/game/engines/graph_item_use.py`
  - New pure graph item-use planner.
- `server/tests/game/engines/test_graph_item_use.py`
  - Unit tests for healing, MP restore, buff append, trigger result, consumption, and validation.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph-native non-damage item use planning exists.

## Task 1: Item Use Tests

**Files:**
- Create: `server/tests/game/engines/test_graph_item_use.py`

- [x] **Step 1: Write failing graph item-use tests**

Create tests that assert:

- heal consumable caps HP at `max_hp` and removes the carried item,
- MP restore caps MP at `max_mp`,
- buff consumable appends an `active_buffs` entry,
- trigger-only item returns `kind="trigger"` and is not consumed,
- missing item, missing actor, not-carried item, full HP heal, and damage consumable raise `GraphItemUseError`,
- every emitted change can be applied one by one with `apply_graph_change`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_item_use.py -q
```

Expected RED: `src.game.engines.graph_item_use` does not exist.

## Task 2: Item Use Planner

**Files:**
- Create: `server/src/game/engines/graph_item_use.py`

- [x] **Step 1: Implement item-use planner**

Implement:

- `GraphItemUseError(ValueError)`
- `GraphItemUseResult(BaseModel)`
- `plan_item_use(graph, actor_id, item_id, target_id=None)`

Rules:

- item must be an item node,
- actor and target must be character nodes,
- actor must carry the item through a `carries` edge,
- `effects.type != "consumable"` is rejected,
- `effect="heal"` sets target `hp` to `min(max_hp, hp + amount)`,
- `effect="mp_restore"` sets target `mp` to `min(max_mp, mp + amount)`,
- `effect="buff"` appends `{description, duration}` to target `active_buffs`,
- `effects is None` produces a trigger result and no stat changes,
- `effect="damage"` raises because damage belongs to graph-native combat,
- `consumable=true` removes the actor's `carries` edge after the effect.

- [x] **Step 2: Run graph item-use tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_item_use.py -q
```

Expected GREEN: graph item-use tests pass.

## Task 3: Roadmap And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-native-item-use.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/game/engines/graph_item_use.py` plans graph-native non-damage item-use changes.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_item_use.py server\tests\game\engines\test_graph_transfer.py server\tests\game\domain\test_graph_contract.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\engines\graph_item_use.py server\tests\game\engines\test_graph_item_use.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, Phase 5 covers movement, item placement, and non-damage item-use planning. The next slice should handle quest state transitions or add a shared graph-runtime apply wrapper.
