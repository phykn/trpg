# Graph Quest Offers Wire Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Graph wire state must separate active quest state from visible quest offers.

**Architecture:** Keep the existing `quest` field as the active quest slot for compatibility. Add `questOffers` to graph wire state, populate it from visible `locked`/`pending` quest givers, and make the client adapter use `quest ?? questOffers[0]` until the panel grows a dedicated offers UI.

**Tech Stack:** Python 3.13 in the root `.venv`, Pydantic v2, pytest, Expo React Native, Jest.

---

### Task 1: Server Wire Split

**Files:**
- Modify: `server/src/wire/graph_to_front.py`
- Test: `server/tests/wire/test_graph_to_front.py`

- [x] **Step 1: Write failing server tests**

Change the visible offer test to expect `payload.quest is None` and `payload.quest_offers[0].id == "quest_01"`. Keep the active quest test expecting `payload.quest.id`.

- [x] **Step 2: Run server test to verify failure**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\wire\test_graph_to_front.py::test_graph_front_state_builds_visible_quest_offer -q
```

Expected: FAIL because offers still use `quest`.

- [x] **Step 3: Implement split**

Add `quest_offers: list[QuestPayload]` to `GraphFrontStatePayload`. Make `_quest_payload` return active quests only. Add `_quest_offer_payloads` for visible `locked`/`pending` quests.

- [x] **Step 4: Run focused server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\wire\test_graph_to_front.py -q
```

Expected: PASS.

### Task 2: Client Adapter Compatibility

**Files:**
- Modify: `client/services/wire.ts`
- Modify: `client/services/graphAdapter.ts`
- Test: `client/services/__tests__/graphAdapter.test.ts`
- Test: `client/services/__tests__/api.test.ts`

- [x] **Step 1: Write failing client test**

Add `questOffers: [quest]` and `quest: null` in the graph adapter test, then assert the existing `FrontState.quest` still shows the offer.

- [x] **Step 2: Run client test to verify failure**

Run:

```powershell
npm test -- graphAdapter.test.ts --runInBand
```

Expected: FAIL until adapter reads `questOffers`.

- [x] **Step 3: Implement adapter**

Add `questOffers` to `GraphFrontState`. In `adaptGraphState`, set `quest: state.quest ?? state.questOffers[0] ?? null`. In `buildStoryGraph`, render `state.quest` and all `state.questOffers`.

- [x] **Step 4: Run focused client tests**

Run:

```powershell
npm test -- graphAdapter.test.ts api.test.ts --runInBand
npx tsc --noEmit
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
git add docs\superpowers\plans\2026-05-10-graph-quest-offers-wire.md server\src\wire\graph_to_front.py server\tests\wire\test_graph_to_front.py client\services\wire.ts client\services\graphAdapter.ts client\services\__tests__\graphAdapter.test.ts client\services\__tests__\api.test.ts
git commit -m "feat: split graph quest offers from active quest"
```
