# Graph Wire Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a graph-runtime wire snapshot builder for the small public state needed before live graph flow integration.

**Architecture:** Keep this additive beside legacy `wire/to_front.py`. The builder reads `GameRuntimeState`, derives hero/place/combat views from graph facts, and returns Pydantic models. It does not call LLMs, mutate runtime state, localize prose, or replace the current client payload yet.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers public graph-derived state.

It includes:

- hero id/name/resources/stats,
- HP/MP state words computed on the server,
- current place id/name/description/exits/visible targets,
- combat view from `progress.graph_combat_state`,
- exclusion of hidden characters from visible place targets.

It does not include:

- existing legacy `to_front_state` replacement,
- localized labels,
- inventory/equipment panels,
- quest cards,
- story graph.

## File Structure

- `server/src/wire/graph_to_front.py`
  - New graph runtime snapshot builder and Pydantic models.
- `server/tests/wire/test_graph_to_front.py`
  - Unit tests for hero, place, hidden target filtering, and combat view.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph runtime can produce a minimal public wire snapshot.

## Task 1: Snapshot Tests

**Files:**
- Create: `server/tests/wire/test_graph_to_front.py`

- [x] **Step 1: Write failing snapshot tests**

Create tests that assert:

- hero resources include raw current/max values plus `healthy`, `hurt`, `critical`, `downed`, `ready`, `strained`, `drained` state words,
- place view is built from `located_at` and `connects_to` edges,
- hidden characters connected by `hidden_at` are not visible targets,
- combat view is present when `progress.graph_combat_state` exists,
- serialized snapshot does not include `GraphChange` or internal edge ids.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\wire\test_graph_to_front.py -q
```

Expected RED: `src.wire.graph_to_front` does not exist.

## Task 2: Snapshot Builder

**Files:**
- Create: `server/src/wire/graph_to_front.py`

- [x] **Step 1: Implement models and builder**

Implement:

```python
class GraphResourcePayload(BaseModel): ...
class GraphHeroPayload(BaseModel): ...
class GraphPlacePayload(BaseModel): ...
class GraphCombatPayload(BaseModel): ...
class GraphFrontStatePayload(BaseModel): ...
def graph_to_front_state(runtime: GameRuntimeState) -> GraphFrontStatePayload: ...
```

Rules:

- name falls back to id,
- stats include only numeric values,
- current place comes from the player's `located_at` edge,
- exits come from current place `connects_to` edges,
- targets are same-place character nodes except the player,
- hidden characters are not included because only `located_at` targets are surfaced,
- combat participants use server-computed HP/MP state words.

- [x] **Step 2: Run snapshot tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\wire\test_graph_to_front.py -q
```

Expected GREEN: snapshot tests pass.

## Task 3: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-wire-snapshot.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/wire/graph_to_front.py` builds a minimal public state snapshot from graph runtime.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\wire\test_graph_to_front.py server\tests\llm\context\test_graph_combat_context.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\wire\graph_to_front.py server\tests\wire\test_graph_to_front.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, graph runtime can execute actions and produce a minimal public state payload. The next useful slice is an internal graph `/turn` flow adapter that combines classify output, confirmation, dispatcher, state snapshot, and persistence.
