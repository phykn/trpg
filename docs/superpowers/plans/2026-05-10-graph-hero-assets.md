# Graph Hero Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show graph-mode hero inventory, equipment, skills, and status in the existing hero panel.

**Architecture:** The graph remains the source of truth. Server graph wire derives hero assets from `carries`, `equips`, and `knows_skill` edges; the client adapter maps those fields into the existing legacy-compatible `Hero` display shape.

**Tech Stack:** FastAPI/Pydantic graph wire, Expo TypeScript adapter, pytest, Jest.

---

### Task 1: Server Graph Hero Assets

**Files:**
- Modify: `server/src/wire/graph_to_front.py`
- Modify: `server/tests/wire/test_graph_to_front.py`

- [x] **Step 1: Write the failing test**

Extend the graph front-state test fixture with a carried item, equipped weapon, known skill, and status. Assert `payload.hero.inventory`, `payload.hero.equipment.weapon`, `payload.hero.skills`, and `payload.hero.status`.

- [x] **Step 2: Verify RED**

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\wire\test_graph_to_front.py::test_graph_front_state_builds_hero_assets_from_graph_edges -q
```

- [x] **Step 3: Implement graph hero asset payload**

Add small Pydantic payloads for named equipment and inventory rows. Build them from graph edges only:

- `carries` → inventory rows
- `equips` with `slot` in `weapon | armor | accessory` → equipment slots
- `knows_skill` → skill names
- `character.properties.status` → status strings

- [x] **Step 4: Verify GREEN**

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\wire\test_graph_to_front.py -q
```

### Task 2: Client Adapter Mapping

**Files:**
- Modify: `client/services/wire.ts`
- Modify: `client/services/graphAdapter.ts`
- Modify: `client/services/__tests__/graphAdapter.test.ts`

- [x] **Step 1: Write the failing client assertion**

Add graph hero `equipment`, `inventory`, `skills`, and `status` to the graph adapter test input, then assert the adapted `Hero` carries those values.

- [x] **Step 2: Verify RED**

```powershell
npm test -- graphAdapter.test.ts --runInBand
```

- [x] **Step 3: Implement client mapping**

Add graph hero asset types and map them in `adaptHero`.

- [x] **Step 4: Verify client GREEN**

```powershell
npm test -- graphAdapter.test.ts --runInBand
npx tsc --noEmit
```

### Task 3: Regression

- [x] **Step 1: Run server focused tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\wire\test_graph_to_front.py server\tests\api\test_graph_session_routes.py::test_graph_play_loop_reaches_quest_reward_without_legacy_state -q
```

- [x] **Step 2: Run client tests**

```powershell
npm test -- --runInBand
npm run lint
```

- [x] **Step 3: Commit and push**

```powershell
git add docs\superpowers\plans\2026-05-10-graph-hero-assets.md server\src\wire\graph_to_front.py server\tests\wire\test_graph_to_front.py client\services\wire.ts client\services\graphAdapter.ts client\services\__tests__\graphAdapter.test.ts
git commit -m "feat: show graph hero assets"
git push
```
