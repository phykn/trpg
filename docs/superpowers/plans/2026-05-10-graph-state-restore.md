# Graph State Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let graph sessions survive client refresh by exposing and using a graph-native state restore route.

**Architecture:** Keep legacy `GET /session/{game_id}/state` unchanged. Add `GET /session/{game_id}/graph/state` that loads graph runtime state and returns the same graph front payload used by graph init/turn responses. The client first tries the legacy restore path for old saves, then falls back to graph restore and adapts the graph payload into the existing display state.

**Tech Stack:** FastAPI, graph runtime loader, Expo TypeScript services, pytest, TypeScript.

---

## Task 1: Server Route

- [x] **Step 1: Write failing API tests**

Add tests for `GET /session/{game_id}/graph/state` returning graph front state and for a missing game returning 404.

- [x] **Step 2: Verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py::test_graph_state_route_restores_graph_session -q
```

Expected: FAIL with 404 because the route does not exist.

- [x] **Step 3: Implement route**

Use `load_runtime_state(graph_repo, game_id)` and `graph_to_front_state(runtime)`. Do not touch legacy state loading.

- [x] **Step 4: Verify GREEN**

Run the focused API tests. Expected: PASS.

## Task 2: Client Restore Fallback

- [x] **Step 1: Add graph restore service**

Add `getGraphSessionById(gameId)` in `client/services/api.ts` and adapt the graph state at the service boundary.

- [x] **Step 2: Use fallback in `useGame.refresh`**

If legacy `getSessionById` returns `null`, call `getGraphSessionById` before dropping the stored id.

- [x] **Step 3: Verify client**

Run:

```powershell
cd client
npx tsc --noEmit
npm test -- --runInBand
```

Expected: TypeScript and Jest pass.

## Task 3: Final Checks

- [x] **Step 1: Run server tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

- [x] **Step 2: Commit**

Commit the restore route and client fallback on `codex/graph-client-integration`.
