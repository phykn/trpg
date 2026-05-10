# Legacy Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the old relational/SSE play path so the app has one supported dev runtime: graph session REST + graph save repo + local scenario data.

**Architecture:** Cut from the outside inward. First commit the current graph-client cleanup, then remove public legacy routes and client generated legacy schema, then delete unmounted legacy server code and tests after graph equivalents cover the behaviors we still want. The graph runtime remains the source of truth; anything that only exists to serve `/session/init`, `/turn`, `/roll`, `/intro`, `/level_up_preview`, or `PendingCheck` is legacy.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest, ruff, Expo React Native, Jest, TypeScript, root `.venv`.

---

## Current State

The branch already contains a first cleanup pass:

- Client play path uses graph REST helpers only.
- `RollPrompt`, `handleStreamEvent`, and legacy stream helpers are deleted.
- Server routes are split into `session_graph.py` and `session_legacy.py`.
- Weak-LLM graph fixes are included for visible enemy grounding, graph confirmation camelCase, and `attack.with` weapon handling.

Do not start deeper deletion until this checkpoint is committed. It is already a coherent unit and has passed:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check server
cd client; npm test -- --runInBand
cd client; npx tsc --noEmit
cd client; npm run lint
```

`npm run lint` currently has one existing warning in `client/components/story-graph/StoryGraphCanvas.web.tsx`; it is not part of legacy removal.

---

## Target End State

Keep:

- `server/src/api/routes/session_graph.py`
- graph repos and graph runtime under `server/src/game/runtime/`
- graph engines under `server/src/game/engines/graph_*`
- graph wire payload under `server/src/wire/graph_to_front.py`
- client `services/api.ts` graph helpers
- client manual graph contract in `services/wire.ts`

Delete or stop exporting:

- `server/src/api/routes/session_legacy.py`
- legacy mounted routes: `/session/init`, `/session/{game_id}/turn`, `/roll`, `/confirm`, `/intro`, `/level_up_preview`, `/level_up`
- `server/src/api/sse.py`
- legacy wire SSE payload exports: `PendingCheckPayload`, `JudgePayload`, `NarrativeDeltaPayload`, `SuggestionsPayload`, `DonePayload`, combat SSE event payloads if no graph code imports them
- client generated legacy schema artifacts if no remaining client code imports them: `client/services/wire.gen.d.ts`, `client/services/wire.schema.json`, `client/scripts/gen-wire-types.cjs`, `client/package.json` `gen` script
- legacy flow tests and code that only exercise relational `GameState` turn/roll/SSE behavior

Keep for now unless a later graph replacement exists:

- domain models that graph runtime still imports
- LLM classify and narrate call modules used by graph input/narration
- general graph seed, graph persistence, graph combat, graph quest, graph growth tests

---

### Task 0: Commit The Current Cleanup Checkpoint

**Files:**

- Stage all current tracked graph cleanup changes.
- Do not stage unrelated untracked logs: `brainstorm-server.err.log`, `brainstorm-server.log`.

- [ ] **Step 1: Verify current status**

```powershell
git status --short
```

Expected: current graph cleanup changes are listed, plus untracked brainstorm logs.

- [ ] **Step 2: Stage only intended source changes**

```powershell
git add client server docs/superpowers/plans/2026-05-10-legacy-removal.md
git status --short
```

Expected: source files are staged; brainstorm logs remain untracked.

- [ ] **Step 3: Commit checkpoint**

```powershell
git commit -m "refactor: remove client legacy play path"
```

Expected: commit succeeds.

- [ ] **Step 4: Push checkpoint**

```powershell
git push -u origin codex/legacy-cleanup
```

Expected: push succeeds.

---

### Task 1: Unmount Legacy HTTP Routes

**Files:**

- Modify: `server/src/api/routes/session.py`
- Modify or delete: `server/tests/api/test_level_up_routes.py`
- Modify or delete: `server/tests/api/test_pending_check_roll_flow.py`
- Modify: `server/README.md`
- Modify: `server/AGENTS.md`

- [ ] **Step 1: Write failing API route absence test**

Create or extend `server/tests/api/test_legacy_routes_removed.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from run_api import build_app
from src.db.graph_local_fs import LocalFsGraphRepo
from tests._fakes import make_default_storage, make_save_repo, make_scenario_repo


class _NoopLLM:
    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        return {"answer": "{}", "think": ""}


def _build_test_app(tmp_path):
    save_repo, _ = make_save_repo()
    scenario_repo, _ = make_scenario_repo(make_default_storage())
    return build_app(
        llm=_NoopLLM(),
        basic_auth_user="t",
        basic_auth_pass="t",
        save_repo=save_repo,
        scenario_repo=scenario_repo,
        graph_repo=LocalFsGraphRepo(str(tmp_path / "graph")),
        cors_origins=[],
    )


def _client(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        auth=("t", "t"),
        timeout=30.0,
    )


@pytest.mark.asyncio
async def test_legacy_session_routes_are_not_mounted(tmp_path):
    app = _build_test_app(tmp_path)

    async with _client(app) as client:
        init_response = await client.post("/session/init", json={})
        turn_response = await client.post("/session/game-1/turn", json={})
        roll_response = await client.post("/session/game-1/roll", json={})
        intro_response = await client.post("/session/game-1/intro", json={})
        preview_response = await client.get("/session/game-1/level_up_preview")
        level_up_response = await client.post("/session/game-1/level_up", json={})

    assert init_response.status_code == 404
    assert turn_response.status_code == 404
    assert roll_response.status_code == 404
    assert intro_response.status_code == 404
    assert preview_response.status_code == 404
    assert level_up_response.status_code == 404


@pytest.mark.asyncio
async def test_graph_session_routes_remain_mounted(tmp_path):
    app = _build_test_app(tmp_path)

    async with _client(app) as client:
        response = await client.post(
            "/session/graph/init",
            json={
                "profile": "default",
                "player": {"name": "테스터", "race_id": "human", "gender": "female"},
            },
        )

    assert response.status_code == 200, response.text
```

Do not test these with a loop. A loop hides which removed route regressed when the assertion fails.

- [ ] **Step 2: Run red test**

```powershell
.venv\Scripts\python.exe -m pytest server\tests\api\test_legacy_routes_removed.py::test_legacy_session_routes_are_not_mounted -q
```

Expected: fails because at least one of the old routes is still mounted.

- [ ] **Step 3: Unmount legacy router**

Change `server/src/api/routes/session.py` to:

```python
"""Session route aggregate."""

from fastapi import APIRouter

from . import session_graph

router = APIRouter()
router.include_router(session_graph.router)
```

- [ ] **Step 4: Run route removal test**

```powershell
.venv\Scripts\python.exe -m pytest server\tests\api\test_legacy_routes_removed.py -q
```

Expected: both tests pass.

- [ ] **Step 5: Remove legacy API tests**

Delete API tests whose only purpose is the old HTTP/SSE surface:

```powershell
git rm server\tests\api\test_level_up_routes.py
git rm server\tests\api\test_pending_check_roll_flow.py
```

Keep `server/tests/api/test_graph_session_routes.py`.

- [ ] **Step 6: Update route docs**

In `server/README.md`, replace the session route table with graph routes only:

```markdown
| Method | Path | Purpose |
|---|---|---|
| POST | `/session/graph/init` | Create a graph game |
| GET | `/session/{game_id}/graph/state` | Load graph game state |
| POST | `/session/{game_id}/graph/input` | Classify free text and execute graph action |
| POST | `/session/{game_id}/graph/turn` | Execute explicit graph action |
| POST | `/session/{game_id}/graph/confirm` | Resolve pending graph confirmation |
| POST | `/session/{game_id}/graph/level_up` | Apply graph level-up |
```

In `server/AGENTS.md`, remove the SSE event contract as active route guidance. If the file keeps a short historical note, it must say the route is removed and must not instruct future work to maintain it.

- [ ] **Step 7: Run route tests**

```powershell
.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py server\tests\api\test_legacy_routes_removed.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```powershell
git add server/src/api/routes/session.py server/tests/api server/README.md server/AGENTS.md
git commit -m "refactor: unmount legacy session routes"
```

---

### Task 2: Remove Client Generated Legacy Wire Surface

**Files:**

- Modify: `client/logic/subject/types.ts`
- Modify: `client/logic/quest/types.ts`
- Modify: `client/logic/log/types.ts`
- Modify: `client/logic/story-graph/types.ts`
- Delete: `client/services/wire.gen.d.ts`
- Delete: `client/services/wire.schema.json`
- Delete: `client/scripts/gen-wire-types.cjs`
- Modify: `client/package.json`
- Modify: `client/package-lock.json`
- Modify: `client/AGENTS.md`
- Modify: `client/README.md`

- [ ] **Step 1: Confirm remaining generated imports**

```powershell
rg "wire\.gen" client -n
```

Expected before change: hits in `client/logic/log/types.ts`, `client/logic/subject/types.ts`, `client/logic/quest/types.ts`, `client/logic/story-graph/types.ts`, the generated script, and docs.

- [ ] **Step 2: Replace `client/logic/log/types.ts`**

Remove the `wire.gen` import and define the rendered log union locally:

```ts
export type RollResult = 'success' | 'partial' | 'fail';

export type LogEntry =
  | { id: number; kind: 'gm'; text: string }
  | { id: number; kind: 'player'; text: string }
  | { id: number; kind: 'act'; text: string }
  | {
      id: number;
      kind: 'roll';
      check: string;
      roll: number;
      margin: number;
      result: RollResult;
      bonus_breakdown?: { label: string; value: number }[];
    };
```

- [ ] **Step 3: Replace `client/logic/subject/types.ts`**

```ts
import type { Equipment, InventoryItem, Stat } from '@/logic/hero/types';

// Only hp/hpMax is exposed for subjects. mp/mpMax is intentionally absent.
export type Subject = {
  name: string;
  alive: boolean;
  role: string;
  raceJob: string;
  gender: string;
  trust: number;
  known: string[];
  level: number;
  hp: number;
  hpMax: number;
  stats: Stat[];
  equipment: Equipment;
  inventory: InventoryItem[];
  skills: string[];
};
```

- [ ] **Step 4: Replace `client/logic/quest/types.ts`**

```ts
export type DifficultyBadge = {
  label: string;
  tone?: 'neutral' | 'good' | 'exp' | 'accent' | 'bad' | null;
};

export type Quest = {
  id: string;
  title: string;
  summary: string;
  giver: string;
  difficulty: DifficultyBadge;
  goals: string[];
  progressLabel: string;
  rewards: { gold: number; exp: number };
  status: 'pending' | 'active' | 'completed' | 'failed';
  actions: ('accept' | 'abandon')[];
};
```

- [ ] **Step 5: Replace generated imports in `client/logic/story-graph/types.ts`**

Remove the `wire.gen` import, replace `export type RiskBadge = RiskBadgePayload;`, and add local display payloads:

```ts
export type RiskBadge = {
  label: string;
  tone: 'good' | 'neutral' | 'bad';
};

export type PlaceSurrounding = {
  name: string;
  blurb: string;
  difficulty?: string | null;
  risk: RiskBadge;
};

export type PlaceTarget = {
  name: string;
  level: number;
  raceJob: string;
  gender: string;
  blurb: string;
  trust: number;
};

export type Place = {
  name: string;
  description: string;
  dayPhase: string;
  weather: string[];
  surroundings: PlaceSurrounding[];
  targets: PlaceTarget[];
  risk: RiskBadge;
};
```

Delete these old alias lines at the bottom of the file:

```ts
export type PlaceSurrounding = PlaceSurroundingPayload;
export type PlaceTarget = PlaceTargetPayload;
export type Place = PlacePayload;
```

- [ ] **Step 6: Remove generated files and gen script**

```powershell
git rm client\services\wire.gen.d.ts
git rm client\services\wire.schema.json
git rm client\scripts\gen-wire-types.cjs
```

Remove the `gen` script from `client/package.json`, then remove the unused generator dependency:

```powershell
cd client
npm uninstall json-schema-to-typescript
```

- [ ] **Step 7: Run client typecheck**

```powershell
cd client
npx tsc --noEmit
```

Expected: no TypeScript errors.

- [ ] **Step 8: Run client tests**

```powershell
cd client
npm test -- --runInBand
```

Expected: all tests pass.

- [ ] **Step 9: Search for removed surface**

```powershell
rg "wire\.gen|PendingCheck|pendingCheck|StreamEvent|RollPrompt|handleStreamEvent" client -n
```

Expected: no hits, except historical docs if intentionally kept.

- [ ] **Step 10: Commit**

```powershell
git add client
git commit -m "refactor: remove client generated legacy wire types"
```

---

### Task 3: Remove Legacy API Schemas And SSE Helpers

**Files:**

- Modify: `server/src/api/schema.py`
- Delete: `server/src/api/sse.py`
- Delete: `server/src/api/routes/session_legacy.py`
- Modify: `server/src/api/routes/session.py`
- Modify: tests that import removed schemas

- [ ] **Step 1: Search active imports**

```powershell
rg "TurnRequest|RollRequest|LevelUpPreviewResponse|LevelUpRequest|streaming_response|session_legacy|api\.sse" server -n
```

Expected: hits in schemas, legacy route, and legacy API tests before deletion.

- [ ] **Step 2: Delete unmounted legacy route and SSE helper**

```powershell
git rm server\src\api\routes\session_legacy.py
git rm server\src\api\sse.py
```

- [ ] **Step 3: Prune legacy request/response models**

In `server/src/api/schema.py`, delete models only used by old routes:

```python
class QuestActionRequest(BaseModel): ...
class TurnRequest(BaseModel): ...
class RollRequest(BaseModel): ...
class LevelUpPreviewResponse(BaseModel): ...
class LevelUpRequest(BaseModel): ...
```

Keep graph models:

```python
class InitRequest(BaseModel): ...
class InitResponse(BaseModel): ...
class ConfirmRequest(BaseModel): ...
class GraphTurnRequest(BaseModel): ...
class GraphInputRequest(BaseModel): ...
class GraphLevelUpRequest(BaseModel): ...
class GraphActionResponse(BaseModel): ...
```

- [ ] **Step 4: Run import-focused tests**

```powershell
.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py -q
.venv\Scripts\ruff.exe check server\src\api server\tests\api
```

Expected: pass.

- [ ] **Step 5: Confirm no API legacy imports remain**

```powershell
rg "TurnRequest|RollRequest|LevelUpPreviewResponse|LevelUpRequest|streaming_response|session_legacy|api\.sse" server/src server/tests/api -n
```

Expected: no hits.

- [x] **Step 6: Commit**

```powershell
git add server/src/api server/tests/api
git commit -m "refactor: remove legacy session API surface"
```

---

### Task 4: Replace Or Delete Legacy Flow Test Coverage

**Files:**

- Review: `server/tests/game/flow/`
- Review: `server/tests/wire/test_pending_check.py`
- Review: `server/tests/test_pending_check_kind.py`
- Review: `server/tests/game/domain/test_pending_check_verb_fields.py`
- Keep as graph replacements: `server/tests/api/test_graph_session_routes.py`
- Keep as graph replacements: `server/tests/game/runtime/`

- [x] **Step 1: Categorize legacy flow tests**

```powershell
rg "run_turn|run_roll|run_intro|run_level_up|PendingCheck|GameState" server\tests\game\flow server\tests\wire server\tests\game\domain server\tests -n
```

Use these categories:

- delete: behavior only existed for old dice/SSE UI
- already covered: behavior is covered by `test_graph_turn_attack_returns_confirmation_without_starting_combat`, `test_graph_confirm_confirm_executes_pending_attack`, `test_graph_play_loop_reaches_quest_reward_without_legacy_state`, or a focused graph runtime test
- keep temporarily: shared domain behavior still used by graph

- [x] **Step 2: Verify graph replacements already pass**

```powershell
.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py server\tests\game\runtime -q
```

Expected: pass. These tests cover graph session init, movement, attack confirmation, confirmation resolution, combat progress, flee, item use, equipment, quest reward, and level-up.

- [x] **Step 3: Delete flow tests that have no graph future**

After replacements pass:

```powershell
git rm server\tests\game\flow\test_roll.py
git rm server\tests\wire\test_pending_check.py
git rm server\tests\test_pending_check_kind.py
```

Continue deleting files only after `rg` confirms they test removed APIs or `PendingCheck`.

- [x] **Step 4: Run server test suite**

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Expected: all remaining tests pass.

- [x] **Step 5: Commit**

```powershell
git add server/tests
git commit -m "test: remove legacy flow coverage"
```

---

### Task 5: Delete Legacy Runtime Code

**Files:**

- Delete or prune: `server/src/game/flow/`
- Delete or prune: `server/src/wire/emit.py`
- Delete or prune: `server/src/wire/to_front.py`
- Delete or prune: `server/src/wire/models/pending_check.py`
- Delete or prune: `server/src/wire/models/judge.py`
- Delete or prune: `server/src/wire/models/narrative_delta.py`
- Delete or prune: `server/src/wire/models/suggestions.py`
- Delete or prune: `server/src/wire/models/done.py`
- Modify: `server/src/wire/__init__.py`
- Modify: `server/src/wire/models/__init__.py`
- Modify: `server/src/wire/export.py`

- [x] **Step 1: Search production imports**

```powershell
rg "src\.game\.flow|from src\.wire\.to_front|from src\.wire\.emit|PendingCheckPayload|JudgePayload|NarrativeDeltaPayload|SuggestionsPayload|DonePayload" server\src -n
```

Expected before deletion: imports from legacy-only modules.

- [x] **Step 2: Remove legacy-only modules with no production imports**

Delete modules only after imports are gone:

```powershell
git rm server\src\wire\emit.py
git rm server\src\wire\models\pending_check.py
git rm server\src\wire\models\judge.py
git rm server\src\wire\models\narrative_delta.py
git rm server\src\wire\models\suggestions.py
git rm server\src\wire\models\done.py
```

Do not delete `server/src/wire/models/hero.py`, `quest.py`, or related display models until graph wire no longer imports them.

- [x] **Step 3: Prune wire exports**

In `server/src/wire/models/__init__.py`, remove deleted model imports and names from `__all__`.

In `server/src/wire/__init__.py`, remove deleted exports.

In `server/src/wire/export.py`, either delete the file if no client generation remains, or reduce `_MODELS` to graph-supported models only.

- [x] **Step 4: Delete legacy flow package after imports are gone**

```powershell
rg "src\.game\.flow|game\.flow" server\src server\tests -n
```

If only historical docs remain, delete:

```powershell
git rm -r server\src\game\flow
```

- [x] **Step 5: Run focused import tests**

```powershell
.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py server\tests\game\runtime server\tests\wire -q
.venv\Scripts\ruff.exe check server
```

Expected: pass.

- [x] **Step 6: Commit**

```powershell
git add server/src server/tests
git commit -m "refactor: delete legacy flow runtime"
```

---

### Task 6: Clean Persistence Legacy Only If Graph No Longer Needs It

**Files:**

- Review: `server/src/db/repo.py`
- Review: `server/src/db/local_fs.py`
- Review: `server/src/db/supabase.py`
- Review: `server/src/db/store.py`
- Review: `server/src/db/_schema.py`
- Review: `server/src/db/factory.py`
- Review: `server/tests/db/`

- [x] **Step 1: Find SaveRepo usage**

```powershell
rg "SaveRepo|build_save_repo|LocalFsSaveRepo|SupabaseSaveRepo|save_repo|GameState" server\src server\tests -n
```

- [x] **Step 2: Remove app startup construction if unused**

If no route depends on `SaveRepo`, update `server/run_api.py`:

```python
from src.db.factory import build_graph_repo, build_scenario_repo
```

and remove `save_repo` from `build_app(...)`, `create_app()`, and `app.state`.

- [x] **Step 3: Remove factory branch**

If tests no longer instantiate `LocalFsSaveRepo`, remove `build_save_repo()` from `server/src/db/factory.py`.

- [x] **Step 4: Delete relational save adapters**

Removed the `SaveRepo` protocol, app wiring, Supabase save adapter, LocalFs save
adapter, and relational `_schema.py`. Kept `local_fs.py`, `supabase.py`, and
`store.py` because graph runtime still uses them for scenario storage or local
graph JSONL helpers.

```powershell
git rm server\src\db\local_fs.py
git rm server\src\db\supabase.py
git rm server\src\db\store.py
```

Keep scenario repo code if graph scenario loading still uses it.

- [x] **Step 5: Run DB and graph tests**

```powershell
.venv\Scripts\python.exe -m pytest server\tests\db server\tests\game\runtime server\tests\api\test_graph_session_routes.py -q
.venv\Scripts\ruff.exe check server
```

Passed: `87 passed`; `ruff check server` and `ruff check agency\qa` passed.

- [x] **Step 6: Commit**

```powershell
git add server/src/db server/run_api.py server/tests/db
git commit -m "refactor: remove relational save repo"
```

---

### Task 7: Update Documentation To Graph-Only Dev Runtime

**Files:**

- Modify: `AGENTS.md`
- Modify: `server/AGENTS.md`
- Modify: `client/AGENTS.md`
- Modify: `README.md`
- Modify: `server/README.md`
- Modify: `client/README.md`
- Modify: `docs/05-interfaces.md`

- [x] **Step 1: Search stale terms**

```powershell
rg "legacy|SSE|PendingCheck|RollPrompt|/session/init|/turn|/roll|SaveRepo|GameState|wire.gen" AGENTS.md README.md server client docs -n
```

- [x] **Step 2: Rewrite active guidance**

Use these replacement rules:

- active runtime: graph REST
- save runtime: `GraphRepo`
- client state: `FrontState` from `client/services/wire.ts`
- scenario in dev: local scenario repo
- LLM in dev: local OpenAI-compatible server

Do not describe removed code as if it still exists. Historical plan files under `docs/superpowers/plans/` may keep old references.

- [x] **Step 3: Run doc sanity search**

```powershell
rg "PendingCheck|RollPrompt|wire.gen|/session/init|/session/\{id\}/turn|/session/\{id\}/roll" AGENTS.md README.md server\README.md client\README.md client\AGENTS.md server\AGENTS.md docs\05-interfaces.md -n
```

Expected: no active-doc hits. `/session/{id}/graph/turn` is active and allowed.

- [x] **Step 4: Commit**

```powershell
git add AGENTS.md README.md server/AGENTS.md server/README.md client/AGENTS.md client/README.md docs/05-interfaces.md
git commit -m "docs: describe graph-only runtime"
```

---

### Task 8: Final Verification And Browser Smoke

**Files:**

- No planned code edits.

- [x] **Step 1: Run full server tests**

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Passed: `647 passed` after removing the final PendingCheck-only tests.

- [x] **Step 2: Run server lint**

```powershell
.venv\Scripts\ruff.exe check server
```

Passed.

- [x] **Step 3: Run client checks**

```powershell
cd client
npm test -- --runInBand
npx tsc --noEmit
npm run lint
```

Passed: Jest `6 passed / 12 tests`; `tsc --noEmit` passed; `npm run lint` had the existing `StoryGraphCanvas.web.tsx` hook dependency warning and no errors.

- [x] **Step 4: Run SSOT guard**

Use PowerShell equivalent on Windows if `bash server/scripts/check_relational_ssot.sh` hits CRLF:

```powershell
$searchDirs = @('server/src/game/flow', 'server/src/llm/context', 'server/src/wire')
$patterns = @(
  '\.inventory_ids\b',
  '\.racial_skill_ids\b',
  '\.learned_skill_ids\b',
  '\.connections\b',
  '\.item_ids\b',
  '\.quest_ids\b',
  '\.companions\b',
  '\.triggers\[',
  'state\.characters\.items\(\)',
  'state\.characters\.values\(\)'
)
$violations = @()
foreach ($pattern in $patterns) {
  foreach ($dir in $searchDirs) {
    if (!(Test-Path $dir)) { continue }
    $matches = rg -n --glob '*.py' --pcre2 $pattern $dir 2>$null
    foreach ($line in $matches) {
      if ($line -match '#\s*ssot-allow') { continue }
      $violations += $line
    }
  }
}
if ($violations.Count -gt 0) {
  $violations | ForEach-Object { $_ }
  exit 1
}
Write-Output 'relational SSOT guard: clean.'
```

Expected: clean.

- [x] **Step 5: Browser smoke**

With `python run_api.py` running from `server/` and `npm run web` running from `client/`, verify in `http://127.0.0.1:8081/`:

- start dev test scenario
- talk to NPC
- attack dummy
- see attack confirmation modal
- confirm attack
- see combat panel
- finish combat if quick enough
- level up if XP allows

Passed on `http://127.0.0.1:8081/` with API running from the root `.venv`: existing dev test game talked to the guide, defeated the training dummy, showed recommendation chips, opened level-up, raised `몸`, and applied level 1.

- [x] **Step 6: Final legacy search**

```powershell
rg "session_legacy|streaming_response|PendingCheck|RollPrompt|handleStreamEvent|wire.gen|/session/init|/roll|/turn|SaveRepo|LocalFsSaveRepo|SupabaseSaveRepo" server client AGENTS.md README.md -n
```

Expected: no active-code hits. If docs mention historical plans, leave only under `docs/superpowers/plans/`.

Passed after pruning graph progress leftovers: no active `PendingCheck`, `SaveRepo`, `session_legacy`, SSE stream helper, generated wire type, or removed route implementation remains. Expected `/session/{game_id}/graph/turn` route and tests remain.

- [x] **Step 7: Commit and push**

```powershell
git status --short
git push
```

Expected: branch is pushed.

---

## Stop Conditions

Stop and ask before proceeding if any of these happens:

- A graph runtime feature has no replacement for a user-visible legacy behavior the user still wants.
- Removing `GameState`/`SaveRepo` would also remove scenario loading needed by graph dev.
- Full pytest drops too much coverage without graph replacements.
- The browser smoke cannot reach combat or level-up after fixes.

## Recommended Execution Order

Run tasks in order. Do not jump to deleting `server/src/game/flow/` first. The safe order is:

1. checkpoint current branch
2. remove public legacy routes
3. remove client generated legacy schema
4. remove legacy API schemas/SSE helper
5. replace or delete legacy flow tests
6. delete legacy runtime code
7. clean persistence if graph does not need relational adapters
8. update docs and run final browser smoke
