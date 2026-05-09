# Graph Combat Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let graph-native combat progress save and load without replacing the legacy combat state yet.

**Architecture:** Add a separate `graph_combat_state` field to `GameProgress`. This avoids overloading the legacy `combat_state` shape during migration and lets graph runtime paths persist `GraphCombatState` independently.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers persistence shape only.

It includes:

- `GameProgress.graph_combat_state`,
- LocalFs graph progress row round-trip,
- runtime load preservation of graph combat progress.

It does not include:

- live `/turn` graph combat dispatch,
- client combat panel changes,
- removal of legacy `combat_state`.

## File Structure

- `server/src/game/domain/progress.py`
  - Add optional `graph_combat_state`.
- `server/tests/db/test_graph_progress_rows.py`
  - Assert row round-trip for graph combat progress.
- `server/tests/game/runtime/test_load.py`
  - Assert runtime load preserves graph combat progress.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph-native combat progress can be persisted.

## Task 1: Failing Tests

**Files:**
- Modify: `server/tests/db/test_graph_progress_rows.py`
- Modify: `server/tests/game/runtime/test_load.py`

- [x] **Step 1: Add graph combat progress tests**

Add tests that create:

```python
GraphCombatState(
    location_id="town",
    player_id="player",
    enemy_ids=["rat"],
    participant_ids=["player", "rat"],
    sides={"player": "player", "rat": "enemy"},
    round=2,
)
```

Assert `progress_to_row` includes `graph_combat_state`, and `progress_from_row` restores the same model. Also assert `load_runtime_state` preserves `progress.graph_combat_state`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_progress_rows.py server\tests\game\runtime\test_load.py -q
```

Expected RED: `GameProgress` rejects `graph_combat_state`.

## Task 2: Progress Field

**Files:**
- Modify: `server/src/game/domain/progress.py`

- [x] **Step 1: Add `graph_combat_state`**

Import `GraphCombatState` from `src.game.domain.combat` and add:

```python
graph_combat_state: GraphCombatState | None = None
```

Keep legacy `combat_state` unchanged.

- [x] **Step 2: Run progress tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_progress_rows.py server\tests\game\runtime\test_load.py -q
```

Expected GREEN: graph combat progress round-trips.

## Task 3: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-combat-progress.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `GameProgress.graph_combat_state` persists graph-native combat progress separately from legacy combat state.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_progress_rows.py server\tests\game\runtime\test_load.py server\tests\game\engines\test_graph_combat.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\domain\progress.py server\tests\db\test_graph_progress_rows.py server\tests\game\runtime\test_load.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, graph combat can be planned, safely described for LLM input, and persisted in progress. The next useful slice is a graph-runtime dispatcher that starts or advances `graph_combat_state`.
