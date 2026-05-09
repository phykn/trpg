# Graph Combat Runtime Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a graph-runtime dispatcher that turns a graph-native `Action` into a combat exchange, applies graph changes, and updates `GameProgress.graph_combat_state`.

**Architecture:** Keep this below live flow. The dispatcher accepts `GameRuntimeState` plus `Action`, delegates combat rules to `game.engines.graph_combat`, applies changes through `apply_runtime_graph_changes`, and returns a new runtime plus the combat result state. It does not emit SSE, call LLMs, save to storage, or build client payloads.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers runtime dispatch only.

It includes:

- starting graph combat from an `attack` or attack `cast` action,
- advancing existing graph combat,
- mapping `pass` to defend,
- mapping hasty/flee `move` to flee,
- applying returned `GraphChange` objects atomically,
- storing ongoing combat in `progress.graph_combat_state`,
- clearing `progress.graph_combat_state` when combat ends.

It does not include:

- live `/turn` integration,
- pending confirmation handling,
- `combat_narrate`,
- client state mapping,
- persistence writes.

## File Structure

- `server/src/game/runtime/combat.py`
  - New runtime dispatcher and result model.
- `server/src/game/runtime/__init__.py`
  - Re-export dispatcher types/functions.
- `server/tests/game/runtime/test_graph_combat_dispatch.py`
  - Unit tests for start, continue, flee, defend, cast, and invalid action handling.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph runtime can dispatch combat actions.

## Task 1: Dispatcher Tests

**Files:**
- Create: `server/tests/game/runtime/test_graph_combat_dispatch.py`

- [x] **Step 1: Write failing dispatcher tests**

Create tests that assert:

- an `Action(verb="attack", what="goblin_01")` starts combat, applies the first exchange, and stores an ongoing `graph_combat_state`,
- a later `attack` against a wounded enemy can end in victory and clears `progress.graph_combat_state`,
- `Action(verb="move", how="flee")` ends combat with outcome `fled` and clears progress,
- `Action(verb="pass", how="defend")` maps to defend and advances the combat round,
- `Action(verb="cast", what="fireball", to="goblin_01")` requires a known skill and deducts MP,
- unsupported actions raise `GraphCombatDispatchError`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_combat_dispatch.py -q
```

Expected RED: `src.game.runtime.combat` does not exist.

## Task 2: Dispatcher Implementation

**Files:**
- Create: `server/src/game/runtime/combat.py`
- Modify: `server/src/game/runtime/__init__.py`

- [x] **Step 1: Implement dispatcher**

Implement:

```python
class GraphCombatDispatchError(ValueError): ...
class GraphCombatDispatchResult(BaseModel): ...
def dispatch_graph_combat_action(runtime: GameRuntimeState, action: Action) -> GraphCombatDispatchResult: ...
```

Rules:

- when no `graph_combat_state` exists, only attack/cast can start combat,
- start combat first, then run the same player action as exchange one,
- when `graph_combat_state` exists, use it directly,
- `attack` with `with` maps to a cast exchange,
- `cast` maps to a cast exchange,
- `move` with `how in {"flee", "hasty"}` maps to flee,
- `pass` maps to defend,
- terminal outcomes clear `progress.graph_combat_state`,
- ongoing outcomes store the returned state,
- original runtime is not mutated.

- [x] **Step 2: Re-export dispatcher**

Add `GraphCombatDispatchError`, `GraphCombatDispatchResult`, and `dispatch_graph_combat_action` to `server/src/game/runtime/__init__.py`.

- [x] **Step 3: Run dispatcher tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_combat_dispatch.py -q
```

Expected GREEN: dispatcher tests pass.

## Task 3: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-combat-runtime-dispatch.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/game/runtime/combat.py` dispatches graph-native combat actions inside graph runtime state.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_combat_dispatch.py server\tests\game\engines\test_graph_combat.py server\tests\llm\context\test_graph_combat_context.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\runtime\combat.py server\src\game\runtime\__init__.py server\tests\game\runtime\test_graph_combat_dispatch.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, graph combat can start, advance, persist progress, and be converted into LLM-safe context. The next useful slice is live graph flow integration behind the existing pending-confirmation boundary.
