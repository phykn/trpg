# Graph System Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist graph action results as system cards so the graph front state can render them through the existing log/card UI.

**Architecture:** Keep graph facts as the source of truth. After a confirmed mutating graph action succeeds, build one `ActLogEntry` from the committed graph result, append it through `GraphRepo`, bump `progress.next_log_id`, and include `log` in `graph_to_front_state`. Query answers and pending confirmations do not create cards.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice adds:

- graph action result card text,
- persisted graph log entries,
- graph front-state `log`.

This slice does not add:

- LLM narration,
- SSE events for graph routes,
- client UI rewiring.

## File Structure

- `server/src/game/runtime/cards.py`
  - Builds one `ActLogEntry` for a confirmed graph action.
- `server/src/game/runtime/turn.py`
  - Appends card logs after successful graph action execution.
- `server/src/game/runtime/confirmation.py`
  - Confirm uses the same confirmed-action executor.
- `server/src/wire/graph_to_front.py`
  - Adds `log`.
- `server/tests/game/runtime/test_graph_action_turn.py`
  - Persists card tests.
- `server/tests/game/runtime/test_graph_confirmation.py`
  - Confirm-created card test.
- `server/tests/wire/test_graph_to_front.py`
  - Front `log` test.

## Task 1: Card Tests

**Files:**
- Modify: `server/tests/game/runtime/test_graph_action_turn.py`
- Modify: `server/tests/game/runtime/test_graph_confirmation.py`
- Modify: `server/tests/wire/test_graph_to_front.py`

- [x] **Step 1: Write failing tests**

Assert that:

- a move action appends one `act` card and bumps `next_log_id`,
- confirm attack appends one `act` card,
- graph front state includes `log`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_turn.py server\tests\game\runtime\test_graph_confirmation.py server\tests\wire\test_graph_to_front.py -q
```

Expected RED: graph front state has no log and graph actions do not append log entries.

## Task 2: Implementation

**Files:**
- Create: `server/src/game/runtime/cards.py`
- Modify: `server/src/game/runtime/turn.py`
- Modify: `server/src/game/runtime/confirmation.py`
- Modify: `server/src/wire/graph_to_front.py`

- [x] **Step 1: Build action card text**

Use committed graph facts and Korean 합니다체 text. Keep it short and factual.

- [x] **Step 2: Append card in confirmed executor**

`run_graph_action_turn` appends one card after graph/progress save and then saves `progress.next_log_id + 1`.

- [x] **Step 3: Reuse executor from confirm**

`run_graph_confirm(..., "confirm")` clears pending, then executes through the same confirmed-action helper so card behavior is identical.

- [x] **Step 4: Expose log in graph front state**

Add `log` to `GraphFrontStatePayload`.

## Task 3: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-system-cards.md`

- [x] **Step 1: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_turn.py server\tests\game\runtime\test_graph_confirmation.py server\tests\wire\test_graph_to_front.py server\tests\api\test_graph_session_routes.py -q
```

- [x] **Step 2: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\runtime\cards.py server\src\game\runtime\turn.py server\src\game\runtime\confirmation.py server\src\wire\graph_to_front.py server\tests\game\runtime\test_graph_action_turn.py server\tests\game\runtime\test_graph_confirmation.py server\tests\wire\test_graph_to_front.py
```

- [x] **Step 3: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

## Stop Point

After this slice, graph routes can show factual system cards from committed graph results. LLM narration remains a later layer.
