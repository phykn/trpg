# Graph Runtime Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared runtime apply wrapper that applies `GraphChange` batches atomically to `GameRuntimeState`.

**Architecture:** Keep domain graph mutation in `game.domain.graph.apply_graph_change`; the runtime wrapper only parses a batch, applies changes to a copied graph, tracks touched ids, and returns a copied `GameRuntimeState`. If one change fails, the original runtime remains unchanged.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers applying graph changes to an in-memory runtime.

It does not persist graph changes to Supabase or LocalFs, does not wire live `/turn`, and does not update progress fields.

## File Structure

- `server/src/game/runtime/apply.py`
  - New runtime-level graph change apply wrapper.
- `server/src/game/runtime/__init__.py`
  - Re-export the wrapper for runtime call sites.
- `server/tests/game/runtime/test_runtime_apply.py`
  - Unit tests for atomic application, touched ids, raw dict parsing, and failure behavior.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that a graph runtime apply wrapper exists.

## Task 1: Runtime Apply Tests

**Files:**
- Create: `server/tests/game/runtime/test_runtime_apply.py`

- [x] **Step 1: Write failing runtime apply tests**

Create tests that assert:

- a batch of raw dict changes returns a new runtime with the changed graph,
- the original runtime graph is unchanged,
- touched node and edge ids are reported,
- invalid later changes raise `GraphRuntimeApplyError`,
- when a later change fails, no partial graph is returned and the original runtime stays unchanged.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_runtime_apply.py -q
```

Expected RED: `src.game.runtime.apply` does not exist.

## Task 2: Runtime Apply Wrapper

**Files:**
- Create: `server/src/game/runtime/apply.py`
- Modify: `server/src/game/runtime/__init__.py`

- [x] **Step 1: Implement runtime apply wrapper**

Implement:

- `GraphRuntimeApplyError(ValueError)`
- `GraphRuntimeApplyResult(BaseModel)`
- `apply_runtime_graph_changes(runtime, changes)`

Rules:

- accept both parsed `GraphChange` objects and raw dict changes,
- parse raw dicts with `parse_graph_change`,
- apply every change with `apply_graph_change`,
- catch validation and graph invariant failures and raise `GraphRuntimeApplyError`,
- return `GraphRuntimeApplyResult(runtime=<new runtime>, applied=<count>, changed_node_ids=[...], changed_edge_ids=[...])`,
- never mutate the input `runtime`.

- [x] **Step 2: Re-export runtime apply symbols**

Add exports in `server/src/game/runtime/__init__.py`:

```python
from .apply import (
    GraphRuntimeApplyError,
    GraphRuntimeApplyResult,
    apply_runtime_graph_changes,
)
```

- [x] **Step 3: Run runtime apply tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_runtime_apply.py -q
```

Expected GREEN: runtime apply tests pass.

## Task 3: Roadmap And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-runtime-apply.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/game/runtime/apply.py` applies graph change batches atomically to runtime state.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_runtime_apply.py server\tests\game\engines\test_graph_move.py server\tests\game\engines\test_graph_transfer.py server\tests\game\engines\test_graph_item_use.py server\tests\game\engines\test_graph_quest.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\runtime\apply.py server\src\game\runtime\__init__.py server\tests\game\runtime\test_runtime_apply.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, graph-native planners have a shared runtime apply wrapper. The next slice should handle rest planning, because it mainly updates progress time and character resources without requiring combat/death-save migration.
