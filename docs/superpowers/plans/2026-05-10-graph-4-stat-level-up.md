# Graph 4-Stat Level Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Graph sessions must level up with the graph contract's 4 stats: `body`, `agility`, `mind`, and `presence`.

**Architecture:** Keep legacy level-up on `STR/DEX/CON/INT/WIS/CHA`. Add a graph stat key type for graph-only API and runtime paths, convert seed character stats into graph stats, and make graph client level-up controls send graph stat keys while legacy controls keep sending legacy stat keys.

**Tech Stack:** Python 3.13 in the root `.venv`, FastAPI, Pydantic v2, pytest, Expo React Native, Jest.

---

### Task 1: Server Graph Growth Uses 4 Stats

**Files:**
- Modify: `server/src/game/domain/types.py`
- Modify: `server/src/game/engines/graph_growth.py`
- Modify: `server/src/game/runtime/cards.py`
- Modify: `server/src/game/runtime/level_up.py`
- Modify: `server/src/api/schema.py`
- Modify: `server/src/game/seed/graph_seed.py`
- Modify: `server/src/locale/catalog/stat.toml`
- Test: `server/tests/game/engines/test_graph_growth.py`
- Test: `server/tests/game/runtime/test_graph_level_up.py`
- Test: `server/tests/api/test_graph_session_routes.py`
- Test: `server/tests/game/seed/test_graph_seed.py`

- [x] **Step 1: Write failing server tests**

Change graph growth and runtime tests to call level-up with `body`, assert only `stats.body` changes, and assert graph seed character stats expose only `body`, `agility`, `mind`, and `presence`.

- [x] **Step 2: Run server tests to verify failure**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_growth.py server\tests\game\runtime\test_graph_level_up.py server\tests\api\test_graph_session_routes.py::test_graph_level_up_commits_and_returns_state server\tests\game\seed\test_graph_seed.py::test_build_seed_graph_creates_nodes_edges_and_progress -q
```

Expected: FAIL because graph growth still requires legacy stat keys.

- [x] **Step 3: Implement graph stat key path**

Add `GraphStatKey = Literal["body", "agility", "mind", "presence"]`. Make `plan_level_up` increment one graph stat without a paired stat decrease. Recalculate `max_hp` from `body` and `max_mp` from `mind`. Add graph stat labels to `stat.toml`, use `GraphLevelUpRequest` for `/graph/level_up`, and convert seed `Stats` into graph stats.

- [x] **Step 4: Run focused server tests**

Expected: PASS.

### Task 2: Client Graph Level-Up Sends 4 Stats

**Files:**
- Modify: `client/services/wire.ts`
- Modify: `client/services/__tests__/api.test.ts`
- Modify: `client/components/composer/LevelUpPrompt.tsx`
- Modify: `client/logic/game/useGame.ts`
- Modify: `client/screens/play/Playing.tsx`

- [x] **Step 1: Write failing client test**

Change the graph API test to send `stat_up: "body"` to `sendGraphLevelUp`.

- [x] **Step 2: Run client test to verify failure**

Run:

```powershell
npm test -- api.test.ts --runInBand
```

Expected: TypeScript or test failure until the client wire type supports graph stat keys.

- [x] **Step 3: Implement client graph stat mode**

Add `GraphStatKey` and `LevelUpStatKey` types. `LevelUpPrompt` receives `mode`; graph mode shows `body/agility/mind/presence` without paired stat-down previews, while legacy mode keeps the existing 6-stat pair trade UI. `commitLevelUp` sends graph keys only to `sendGraphLevelUp`.

- [x] **Step 4: Run focused client checks**

Run:

```powershell
npm test -- api.test.ts --runInBand
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
git add docs\superpowers\plans\2026-05-10-graph-4-stat-level-up.md server\src\game\domain\types.py server\src\game\engines\graph_growth.py server\src\game\runtime\cards.py server\src\game\runtime\level_up.py server\src\api\schema.py server\src\game\seed\graph_seed.py server\src\locale\catalog\stat.toml server\tests\game\engines\test_graph_growth.py server\tests\game\runtime\test_graph_level_up.py server\tests\api\test_graph_session_routes.py server\tests\game\seed\test_graph_seed.py client\services\wire.ts client\services\__tests__\api.test.ts client\components\composer\LevelUpPrompt.tsx client\logic\game\useGame.ts client\screens\play\Playing.tsx
git commit -m "feat: use four stats for graph level up"
```
