# Graph Level Up Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Graph sessions that expose `canLevelUp` must commit level-up choices through graph runtime instead of the legacy entity stream.

**Architecture:** Add a graph runtime level-up function that loads `GameRuntimeState`, applies `plan_level_up`, appends one factual `act` card, saves graph/progress/logs, and returns `graph_to_front_state`. Add `/session/{game_id}/graph/level_up` as a JSON route, then make the client call that route when `runtimeMode === "graph"`; graph preview can return no skill candidates because the current graph route does not ask the weak LLM to invent skills.

**Tech Stack:** Python 3.13 in the root `.venv`, FastAPI, Pydantic v2, pytest, Expo React Native, Jest.

---

### Task 1: Server Graph Level-Up Runtime

**Files:**
- Create: `server/src/game/runtime/level_up.py`
- Modify: `server/src/game/runtime/cards.py`
- Test: `server/tests/game/runtime/test_graph_level_up.py`

- [x] **Step 1: Write failing runtime tests**

Create tests that build a graph with a levelable player, call `run_graph_level_up`, and assert level, xp, log, and front-state updates. Add a second test for insufficient XP.

- [x] **Step 2: Run runtime tests to verify failure**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_level_up.py -q
```

Expected: FAIL because `server/src/game/runtime/level_up.py` does not exist.

- [x] **Step 3: Implement runtime function**

Create `run_graph_level_up(repo, game_id, stat_up, skill_id)` and reject non-null `skill_id` for now. Use `plan_level_up`, `apply_runtime_graph_changes`, `build_graph_level_up_card`, `append_log_entries`, `save_graph`, and `save_progress`.

- [x] **Step 4: Run runtime tests**

Expected: PASS.

### Task 2: API And Client Route

**Files:**
- Modify: `server/src/api/routes/session.py`
- Modify: `server/tests/api/test_graph_session_routes.py`
- Modify: `client/services/api.ts`
- Modify: `client/services/__tests__/api.test.ts`
- Modify: `client/logic/game/useGame.ts`

- [x] **Step 1: Write failing API and client tests**

Add a server route test for `POST /session/{game_id}/graph/level_up`. Add a client API test that `sendGraphLevelUp` posts to `/graph/level_up` and adapts the returned graph state.

- [x] **Step 2: Run tests to verify failure**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py::test_graph_level_up_commits_and_returns_state -q
npm test -- api.test.ts --runInBand
```

Expected: FAIL because the route and client function do not exist.

- [x] **Step 3: Implement route and client branch**

Add the FastAPI route and `sendGraphLevelUp`. In `useGame.openLevelUp`, graph mode should skip legacy skill preview and set `levelUpCandidates` to `[]`. In `commitLevelUp`, graph mode should call `runGraphRequest(() => sendGraphLevelUp(...))`.

- [x] **Step 4: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_level_up.py server\tests\api\test_graph_session_routes.py::test_graph_level_up_commits_and_returns_state -q
npm test -- api.test.ts --runInBand
```

Expected: PASS.

- [x] **Step 5: Run verification**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\ruff.exe check server
npx tsc --noEmit
npm test -- --runInBand
npm run lint
```

Expected: all tests pass; client lint may keep existing warnings only.

- [x] **Step 6: Commit**

```powershell
git add docs\superpowers\plans\2026-05-10-graph-level-up-route.md server\src\game\runtime\level_up.py server\src\game\runtime\cards.py server\src\api\routes\session.py server\tests\game\runtime\test_graph_level_up.py server\tests\api\test_graph_session_routes.py client\services\api.ts client\services\__tests__\api.test.ts client\logic\game\useGame.ts
git commit -m "feat: support graph level up"
```
