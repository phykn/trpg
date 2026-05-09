# Graph Natural Language Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let graph-native sessions accept player text, classify it into one grounded `Action`, and send it through the graph confirmation-aware request layer.

**Architecture:** Build a minimal graph-derived `surroundings` payload for the existing classify agent. The graph input flow converts one classified `Verb` back into an `Action` and delegates to `run_graph_action_request`. This slice adds a separate JSON route and does not replace legacy `/session/{game_id}/turn`.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice adds:

- graph surroundings for classify grounding,
- graph natural-language turn adapter,
- `POST /session/{game_id}/graph/input`.

This slice does not add:

- narration streaming,
- multi-action execution,
- query answer flow,
- client UI changes.

Weak LLM safety rule: graph input accepts exactly one classified action. Refuse or multi-action output returns an error instead of guessing.

## File Structure

- `server/src/llm/context/graph_surroundings.py`
  - Minimal graph-derived classify context.
- `server/src/game/runtime/input.py`
  - Natural-language graph turn adapter.
- `server/src/api/schema.py`
  - Graph input request model.
- `server/src/api/routes/session.py`
  - Graph input route.
- `server/tests/llm/context/test_graph_surroundings.py`
  - Context tests for visible location, exits, NPCs, inventory, and combat flag.
- `server/tests/game/runtime/test_graph_input.py`
  - Adapter tests using fake LLM output.
- `server/tests/api/test_graph_session_routes.py`
  - Route test for natural-language attack confirmation.

## Task 1: Context And Runtime Tests

**Files:**
- Create: `server/tests/llm/context/test_graph_surroundings.py`
- Create: `server/tests/game/runtime/test_graph_input.py`

- [x] **Step 1: Write failing tests**

Add tests that assert:

- graph surroundings expose current location, exits as `connection`, visible NPCs, and inventory,
- graph input classifies one text command and creates attack confirmation,
- graph input rejects multi-action classify output.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\context\test_graph_surroundings.py server\tests\game\runtime\test_graph_input.py -q
```

Expected RED: graph surroundings/input modules do not exist.

## Task 2: API Test

**Files:**
- Modify: `server/tests/api/test_graph_session_routes.py`

- [x] **Step 1: Add failing route test**

Use a fake LLM that returns one attack action and assert `POST /session/{game_id}/graph/input` returns `pendingConfirmation`.

- [x] **Step 2: Run test to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py -q
```

Expected RED: graph input route does not exist.

## Task 3: Implementation

**Files:**
- Create: `server/src/llm/context/graph_surroundings.py`
- Create: `server/src/game/runtime/input.py`
- Modify: `server/src/api/schema.py`
- Modify: `server/src/api/routes/session.py`

- [x] **Step 1: Build graph surroundings**

Expose only grounded ids that classify can use: current location, visible characters, visible exits, inventory, equipment, skills, and `in_combat`.

- [x] **Step 2: Build graph input adapter**

Call `classify`, reject refuse/multi-action output, convert the single `Verb` to `Action`, and call `run_graph_action_request`.

- [x] **Step 3: Wire API route**

Add `POST /session/{game_id}/graph/input` with `player_input` and `think` fields. `think` is accepted for API symmetry but classify still runs with its existing retry runner behavior.

## Task 4: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-natural-language-input.md`

- [x] **Step 1: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\context\test_graph_surroundings.py server\tests\game\runtime\test_graph_input.py server\tests\api\test_graph_session_routes.py -q
```

- [x] **Step 2: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\llm\context\graph_surroundings.py server\src\game\runtime\input.py server\src\api\schema.py server\src\api\routes\session.py server\tests\llm\context\test_graph_surroundings.py server\tests\game\runtime\test_graph_input.py server\tests\api\test_graph_session_routes.py
```

- [x] **Step 3: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

## Stop Point

After this slice, graph sessions can accept text for simple grounded actions. The next useful slice is graph query flow, because `query` must answer from graph facts without mutating time.
