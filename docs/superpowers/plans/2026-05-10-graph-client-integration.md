# Graph Client Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the client use graph session APIs while keeping the existing single-screen UI stable.

**Architecture:** The server graph response is not the same shape as the legacy `FrontState`. Add a client-side graph wire type and a small adapter that converts graph state into the existing display model with safe defaults. `useGame` will call graph init/input/confirm routes, while the visual components continue to receive the model they already understand.

**Tech Stack:** Expo React Native, TypeScript, Jest, `expo/fetch`, root repository branch `codex/graph-client-integration`.

---

## Design

Use the graph API by default for new sessions:

- start: `POST /session/graph/init`
- input: `POST /session/{game_id}/graph/input`
- confirm/cancel: `POST /session/{game_id}/graph/confirm`
- restore: keep using `GET /session/{game_id}/state` until a graph restore route exists; if restore fails for graph sessions, starting a new game remains available.

The adapter maps graph display fields into the old UI shape:

- graph hero resources become `hero.hp`, `hero.hpMax`, `hero.mp`, `hero.mpMax`;
- graph stats become stat rows using client-owned Korean labels;
- graph place exits and visible targets become a minimal `storyGraph`;
- graph combat participants become `CombatBadgePayload`;
- graph `pendingConfirmation` becomes a new client state slot and modal;
- graph log entries remain server-composed log entries.

## Files

- Modify `client/services/wire.ts` for graph wire types and confirmation request/response shapes.
- Modify `client/services/api.ts` to add graph REST functions.
- Create `client/services/graphAdapter.ts` for graph state conversion.
- Create `client/services/__tests__/graphAdapter.test.ts` for adapter behavior.
- Modify `client/services/index.ts` to export new service helpers.
- Modify `client/logic/game/useGame.ts` to use graph init/input/confirm and store `pendingConfirmation`.
- Modify `client/screens/play/Playing.tsx` to render the server confirmation modal before composer/roll input.
- Modify `client/locale/ko.ts` only for client-owned fallback labels if needed.

## Task 1: Graph Adapter

- [x] **Step 1: Write failing adapter tests**

Test that a graph response with hero resources, current place, exits, targets, log, combat, and pending confirmation becomes a legacy-compatible `FrontState`.

- [x] **Step 2: Verify RED**

Run:

```powershell
cd client
npm test -- graphAdapter.test.ts --runInBand
```

Expected: FAIL because `graphAdapter.ts` does not exist.

- [x] **Step 3: Implement adapter**

Create `client/services/graphAdapter.ts` with `adaptGraphState(payload: GraphFrontState): FrontState`.

- [x] **Step 4: Verify GREEN**

Run the same Jest command. Expected: PASS.

## Task 2: Graph Services

- [x] **Step 1: Write type-level service contract through compile usage**

Add graph wire types and functions for init, input, and confirm. Use the adapter at service boundary so callers receive `SessionPayload` or `GraphActionClientResponse`.

- [x] **Step 2: Run TypeScript**

Run:

```powershell
cd client
npx tsc --noEmit
```

Expected: any missing type fields are reported.

- [x] **Step 3: Fix types**

Keep graph-only raw types inside `services/`. Do not leak raw graph changes or raw action payloads to UI.

## Task 3: useGame And Confirmation UI

- [x] **Step 1: Connect graph routes**

Change new sessions to call graph init. Change normal text input to graph input. Add `pendingConfirmation` state and `onConfirmPending`.

- [x] **Step 2: Render confirmation modal**

Use existing `ConfirmDialog`. Labels come from server `pendingConfirmation`, with client fallback only when a field is missing.

- [x] **Step 3: Run focused client tests**

Run:

```powershell
cd client
npm test -- --runInBand
```

Expected: existing Jest tests and new adapter tests pass.

## Task 4: Verification

- [x] **Step 1: Run TypeScript**

```powershell
cd client
npx tsc --noEmit
```

- [x] **Step 2: Run lint**

```powershell
cd client
npm run lint
```

- [x] **Step 3: Run server tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

- [x] **Step 4: Browser check if a dev server is practical**

If the app can start without missing local env, run `npm run web` and inspect the graph start/confirm flow in a browser.

Skipped in this run because `client/.env` and `server/.env.dev` are not present in the workspace.
