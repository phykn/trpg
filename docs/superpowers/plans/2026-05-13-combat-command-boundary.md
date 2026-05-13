# Combat Command Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 전투 버튼이 최종 `GraphAction`을 만들지 않고 command만 보내며, server가 command를 검증한 뒤 기존 engine용 `Action`으로 바꾼다.

**Architecture:** Client에 `CombatCommand` 타입과 `combat_command` panel action을 추가한다. Server에는 `GraphCombatCommandRequest`와 작은 action builder를 추가하고, 새 `/graph/combat` route가 builder 결과를 기존 `run_graph_action_request` 흐름에 넘긴다.

**Tech Stack:** Expo React Native, TypeScript, Jest, FastAPI, Pydantic, pytest.

---

## File Structure

- Modify `client/services/wire.ts`: client/server wire type `CombatCommand` 추가.
- Modify `client/logic/info-panel/types.ts`: `PanelAction` union에 `combat_command` 추가.
- Modify `client/logic/combat/actions.ts`: combat buttons가 `combatCommand`를 만들게 변경.
- Modify `client/logic/combat/__tests__/actions.test.ts`: combat action shape 테스트 변경.
- Modify `client/services/api.ts`: `sendGraphCombatCommand` 추가.
- Modify `client/services/index.ts`: 새 API export 확인 및 필요 시 추가.
- Modify `client/services/__tests__/api.test.ts`: stream/plain endpoint 호출 테스트 추가.
- Modify `client/logic/game/useGame.ts`: `onCombatCommand` 추가.
- Modify `client/screens/play/Playing.tsx`: `combat_command` action dispatch 추가.
- Modify `server/src/api/schema.py`: `GraphCombatCommandRequest` 추가.
- Create `server/src/game/runtime/combat_command.py`: command를 `Action`으로 바꾸는 server-side builder.
- Modify `server/src/api/routes/session_graph.py`: `/graph/combat`, `/graph/combat/stream` 추가.
- Modify `server/tests/api/test_graph_session_routes.py`: route happy path와 invalid state 테스트 추가.

---

### Task 1: Client Combat Command Types And Buttons

**Files:**
- Modify: `client/services/wire.ts`
- Modify: `client/logic/info-panel/types.ts`
- Modify: `client/logic/combat/actions.ts`
- Test: `client/logic/combat/__tests__/actions.test.ts`

- [ ] **Step 1: Update the failing combat action test**

Replace `client/logic/combat/__tests__/actions.test.ts` with:

```ts
import { buildCombatActions } from '../actions';
import type { CombatBadge } from '../types';

describe('buildCombatActions', () => {
  test('builds four combat command actions for the first live enemy', () => {
    const combat: CombatBadge = {
      round: 2,
      turnLabel: '전투 중',
      playerHearts: { current: 3, maximum: 3 },
      enemyHearts: { current: 2, maximum: 3 },
      enemies: [{ id: 'enemy_01', name: '늑대', alive: true }],
    };

    const actions = buildCombatActions(combat);

    expect(actions).toEqual([
      expect.objectContaining({
        kind: 'combat_command',
        label: '공격',
        combatCommand: { command: 'attack', target_id: 'enemy_01' },
        textFallback: '늑대를 공격합니다',
      }),
      expect.objectContaining({
        kind: 'combat_command',
        label: '기술',
        combatCommand: { command: 'skill', target_id: 'enemy_01' },
        textFallback: '기술을 사용합니다',
      }),
      expect.objectContaining({
        kind: 'combat_command',
        label: '방어',
        combatCommand: { command: 'defend' },
        textFallback: '방어합니다',
      }),
      expect.objectContaining({
        kind: 'combat_command',
        label: '도주',
        combatCommand: { command: 'flee' },
        textFallback: '도망칩니다',
      }),
    ]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\code\trpg\client
npm test -- --runInBand logic/combat/__tests__/actions.test.ts
```

Expected: FAIL because `buildCombatActions` still returns `kind: 'graph_action'` and `graphAction`.

- [ ] **Step 3: Add `CombatCommand` wire type**

In `client/services/wire.ts`, add after `GraphRollRequest`:

```ts
export type CombatCommand =
  | { command: 'attack'; target_id: string }
  | { command: 'skill'; target_id: string }
  | { command: 'defend' }
  | { command: 'flee' };
```

- [ ] **Step 4: Extend `PanelAction`**

In `client/logic/info-panel/types.ts`, update imports and union:

```ts
import type { CombatCommand, GraphAction, QuestAction } from '@/services/wire';

export type PanelAction =
  | { kind: 'text'; label: string; text: string; confirm?: ConfirmInfo }
  | { kind: 'graph_action'; label: string; graphAction: GraphAction; textFallback?: string; confirm?: ConfirmInfo }
  | { kind: 'combat_command'; label: string; combatCommand: CombatCommand; textFallback?: string; confirm?: ConfirmInfo }
  | { kind: 'quest_action'; label: string; questAction: QuestAction; confirm?: ConfirmInfo };
```

- [ ] **Step 5: Change combat buttons to command actions**

In `client/logic/combat/actions.ts`, replace each `graph_action` item with `combat_command`:

```ts
return [
  {
    kind: 'combat_command',
    label: ko.combat.attack,
    combatCommand: { command: 'attack', target_id: targetId },
    textFallback: compose.attack(target.name),
  },
  {
    kind: 'combat_command',
    label: ko.combat.skill,
    combatCommand: { command: 'skill', target_id: targetId },
    textFallback: ko.combat.skillFallback,
  },
  {
    kind: 'combat_command',
    label: ko.combat.defend,
    combatCommand: { command: 'defend' },
    textFallback: compose.defend(),
  },
  {
    kind: 'combat_command',
    label: ko.combat.flee,
    combatCommand: { command: 'flee' },
    textFallback: compose.flee(),
  },
];
```

- [ ] **Step 6: Run combat action test**

Run:

```powershell
cd D:\code\trpg\client
npm test -- --runInBand logic/combat/__tests__/actions.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add client/services/wire.ts client/logic/info-panel/types.ts client/logic/combat/actions.ts client/logic/combat/__tests__/actions.test.ts
git commit -m "feat(client): send combat commands from buttons"
```

---

### Task 2: Client API And Game Dispatch

**Files:**
- Modify: `client/services/api.ts`
- Modify: `client/services/index.ts`
- Modify: `client/logic/game/useGame.ts`
- Modify: `client/screens/play/Playing.tsx`
- Test: `client/services/__tests__/api.test.ts`

- [ ] **Step 1: Add failing API test**

In `client/services/__tests__/api.test.ts`, add `sendGraphCombatCommand` to the require destructuring:

```ts
const {
  getGraphSessionById,
  getGraphLevelUpOptions,
  initGraphSession,
  listProfiles,
  requestGraphIntro,
  rollGraphPending,
  sendGraphAction,
  sendGraphCombatCommand,
  sendGraphInput,
  sendGraphLevelUp,
} = require('../api') as typeof import('../api');
```

Add this test inside `describe('graph API helpers', () => { ... })`:

```ts
test('posts combat commands to the graph combat endpoint', async () => {
  fetch.mockResolvedValueOnce(
    streamResponse([
      JSON.stringify({
        type: 'final',
        payload: {
          game_id: 'game-1',
          state: graphState(),
          status: 'executed',
          message: null,
        },
      }),
    ]),
  );

  const result = await sendGraphCombatCommand('game-1', {
    command: 'attack',
    target_id: 'enemy_01',
  });

  expect(fetch).toHaveBeenCalledWith(
    'https://api.example.test/session/game-1/graph/combat/stream',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ command: 'attack', target_id: 'enemy_01' }),
    }),
  );
  expect(result.status).toBe('executed');
});
```

- [ ] **Step 2: Run API test to verify it fails**

Run:

```powershell
cd D:\code\trpg\client
npm test -- --runInBand services/__tests__/api.test.ts
```

Expected: FAIL because `sendGraphCombatCommand` is not exported.

- [ ] **Step 3: Implement API helper**

In `client/services/api.ts`, import `CombatCommand` from wire and add:

```ts
export async function sendGraphCombatCommand(
  gameId: string,
  command: CombatCommand,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  return requestGraphActionWithOptionalStream(
    'sendGraphCombatCommand',
    `/session/${gameId}/graph/combat/stream`,
    `/session/${gameId}/graph/combat`,
    command,
    options,
  );
}
```

- [ ] **Step 4: Export API helper**

Check `client/services/index.ts`. If it exports from `./api`, no change is needed. If it names exports explicitly, add `sendGraphCombatCommand`.

- [ ] **Step 5: Add `onCombatCommand` to `useGame`**

In `client/logic/game/useGame.ts`, import `sendGraphCombatCommand` and `CombatCommand`.

Add callback near `onGraphAction`:

```ts
const onCombatCommand = React.useCallback(
  (command: CombatCommand, label?: string) => {
    if (!gameId || pendingConfirmation || pendingRoll) return;
    void runGraphActionRequest(
      (signal, events) =>
        sendGraphCombatCommand(gameId, command, {
          signal,
          onNarrationDelta: events.onNarrationDelta,
        }),
    );
  },
  [gameId, pendingConfirmation, pendingRoll, runGraphActionRequest],
);
```

Return it from `useGame` alongside `onGraphAction`.

- [ ] **Step 6: Dispatch combat command panel actions**

In `client/screens/play/Playing.tsx`, destructure `onCombatCommand` from `game`.

Update `runAction`:

```ts
if (action.kind === 'text') {
  onSend(action.text);
} else if (action.kind === 'graph_action') {
  onGraphAction(action.graphAction, action.label);
} else if (action.kind === 'combat_command') {
  onCombatCommand(action.combatCommand, action.label);
} else {
  onQuestAction(action.questAction.kind, action.questAction.quest_id, action.label);
}
```

- [ ] **Step 7: Run client tests**

Run:

```powershell
cd D:\code\trpg\client
npm test -- --runInBand services/__tests__/api.test.ts logic/combat/__tests__/actions.test.ts
npx tsc --noEmit
```

Expected: tests PASS and TypeScript PASS.

- [ ] **Step 8: Commit**

```powershell
git add client/services/api.ts client/services/index.ts client/logic/game/useGame.ts client/screens/play/Playing.tsx client/services/__tests__/api.test.ts
git commit -m "feat(client): call combat command endpoint"
```

---

### Task 3: Server Combat Command Builder

**Files:**
- Modify: `server/src/api/schema.py`
- Create: `server/src/game/runtime/combat_command.py`
- Test: `server/tests/game/runtime/test_combat_command.py`

- [ ] **Step 1: Write failing builder tests**

Create `server/tests/game/runtime/test_combat_command.py`:

```python
import pytest

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.combat_command import (
    CombatCommandError,
    build_combat_command_action,
)
from src.game.runtime.state import GameRuntimeState


def _runtime() -> GameRuntimeState:
    progress = GameProgress(
        game_id="game-1",
        player_id="player_01",
        locale="ko",
        graph_combat_state=GraphCombatState(
            player_id="player_01",
            location_id="loc_01",
            active_enemy_id="enemy_01",
            enemy_ids=["enemy_01"],
            participant_ids=["player_01", "enemy_01"],
            sides={"player_01": "player", "enemy_01": "enemy"},
            player_hearts=3,
            enemy_hearts=2,
            round=1,
            outcome="ongoing",
            trace=[],
        ),
    )
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(id="player_01", type="character"),
                "enemy_01": GraphNode(id="enemy_01", type="character"),
            }
        ),
        progress=progress,
    )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"command": "attack", "target_id": "enemy_01"}, Action(verb="attack", what="enemy_01")),
        ({"command": "skill", "target_id": "enemy_01"}, Action(verb="cast", to="enemy_01", how="auto")),
        ({"command": "defend"}, Action(verb="pass", how="defend")),
        ({"command": "flee"}, Action(verb="move", how="flee")),
    ],
)
def test_build_combat_command_action(payload, expected):
    assert build_combat_command_action(_runtime(), payload) == expected


def test_rejects_when_not_in_combat():
    runtime = _runtime()
    runtime = runtime.model_copy(
        update={
            "progress": runtime.progress.model_copy(update={"graph_combat_state": None})
        }
    )

    with pytest.raises(CombatCommandError, match="combat is not active"):
        build_combat_command_action(runtime, {"command": "defend"})


def test_rejects_wrong_target():
    with pytest.raises(CombatCommandError, match="target is not active enemy"):
        build_combat_command_action(
            _runtime(),
            {"command": "attack", "target_id": "enemy_02"},
        )
```

- [ ] **Step 2: Run builder tests to verify failure**

Run:

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_combat_command.py -q
```

Expected: FAIL because `combat_command.py` does not exist.

- [ ] **Step 3: Add schema model**

In `server/src/api/schema.py`, add:

```python
class GraphCombatCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal["attack", "skill", "defend", "flee"]
    target_id: str | None = None
    think: bool = False
```

- [ ] **Step 4: Implement command builder**

Create `server/src/game/runtime/combat_command.py`:

```python
from typing import Any

from src.game.domain.action import Action

from .state import GameRuntimeState


class CombatCommandError(ValueError):
    pass


def build_combat_command_action(
    runtime: GameRuntimeState,
    payload: dict[str, Any],
) -> Action:
    state = runtime.progress.graph_combat_state
    if state is None or state.outcome != "ongoing":
        raise CombatCommandError("combat is not active")

    command = payload.get("command")
    target_id = payload.get("target_id")
    if command in ("attack", "skill"):
        if not isinstance(target_id, str) or not target_id:
            raise CombatCommandError("target_id is required")
        if target_id not in state.enemy_ids:
            raise CombatCommandError("target is not active enemy")
    elif command in ("defend", "flee"):
        target_id = None
    else:
        raise CombatCommandError("unsupported combat command")

    if command == "attack":
        return Action(verb="attack", what=target_id)
    if command == "skill":
        return Action(verb="cast", to=target_id, how="auto")
    if command == "defend":
        return Action(verb="pass", how="defend")
    return Action(verb="move", how="flee")
```

- [ ] **Step 5: Run builder tests**

Run:

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_combat_command.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add server/src/api/schema.py server/src/game/runtime/combat_command.py server/tests/game/runtime/test_combat_command.py
git commit -m "feat(server): build actions from combat commands"
```

---

### Task 4: Server Combat Command Routes

**Files:**
- Modify: `server/src/api/routes/session_graph.py`
- Test: `server/tests/api/test_graph_session_routes.py`

- [ ] **Step 1: Add route tests**

In `server/tests/api/test_graph_session_routes.py`, add:

```python
@pytest.mark.asyncio
async def test_graph_combat_rejects_when_not_in_combat(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/combat",
            json={"command": "defend"},
        )

    assert response.status_code == 422
    assert "combat is not active" in response.text


@pytest.mark.asyncio
async def test_graph_combat_stream_rejects_when_not_in_combat(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/combat/stream",
            json={"command": "defend"},
        )

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert "combat is not active" in response.text
```

- [ ] **Step 2: Run route tests to verify failure**

Run:

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server/tests/api/test_graph_session_routes.py::test_graph_combat_rejects_when_not_in_combat server/tests/api/test_graph_session_routes.py::test_graph_combat_stream_rejects_when_not_in_combat -q
```

Expected: FAIL with 404 route not found.

- [ ] **Step 3: Import schema and builder**

In `server/src/api/routes/session_graph.py`, import:

```python
from src.game.runtime.combat_command import (
    CombatCommandError,
    build_combat_command_action,
)
```

Add `GraphCombatCommandRequest` to the `from ..schema import (...)` list.

- [ ] **Step 4: Add plain route**

Add after `/graph/turn/stream`:

```python
@router.post("/session/{game_id}/graph/combat", response_model=GraphActionResponse)
async def session_graph_combat(
    game_id: str,
    body: GraphCombatCommandRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        runtime = await load_runtime_state(graph_repo, game_id, scenario_repo)
        action = build_combat_command_action(
            runtime,
            body.model_dump(exclude={"think"}),
        )
        with force_think(_request_thinking(body.think)):
            result = await run_graph_action_request(
                graph_repo,
                game_id,
                action,
                llm=llm,
                scenario_repo=scenario_repo,
            )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphConfirmationActive as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (CombatCommandError, GraphConfirmationError, GraphActionTurnError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    return GraphActionResponse(
        game_id=game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
        status=result.status,
        message=result.message,
        suggestions=result.suggestions,
    )
```

- [ ] **Step 5: Add stream route**

Add after the plain route:

```python
@router.post("/session/{game_id}/graph/combat/stream")
async def session_graph_combat_stream(
    game_id: str,
    body: GraphCombatCommandRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> StreamingResponse:
    async def source():
        runtime = await load_runtime_state(graph_repo, game_id, scenario_repo)
        action = build_combat_command_action(
            runtime,
            body.model_dump(exclude={"think"}),
        )
        with force_think(_request_thinking(body.think)):
            async for event in run_graph_action_request_stream(
                graph_repo,
                game_id,
                action,
                llm=llm,
                scenario_repo=scenario_repo,
            ):
                yield event

    return _graph_action_streaming_response(game_id, source)
```

- [ ] **Step 6: Extend streaming error mapping**

In `_graph_action_streaming_response`, add `CombatCommandError` to the 422 error tuple:

```python
        except (
            CombatCommandError,
            GraphInputError,
            GraphConfirmationError,
            GraphActionTurnError,
            GraphRollError,
        ) as e:
            yield _stream_error(422, str(e))
```

- [ ] **Step 7: Run route tests**

Run:

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server/tests/api/test_graph_session_routes.py::test_graph_combat_rejects_when_not_in_combat server/tests/api/test_graph_session_routes.py::test_graph_combat_stream_rejects_when_not_in_combat -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add server/src/api/routes/session_graph.py server/tests/api/test_graph_session_routes.py
git commit -m "feat(server): add combat command routes"
```

---

### Task 5: Full Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused client tests**

```powershell
cd D:\code\trpg\client
npm test -- --runInBand logic/combat/__tests__/actions.test.ts services/__tests__/api.test.ts
```

Expected: PASS.

- [ ] **Step 2: Run client typecheck**

```powershell
cd D:\code\trpg\client
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 3: Run focused server tests**

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_combat_command.py server/tests/api/test_graph_session_routes.py -q
```

Expected: PASS.

- [ ] **Step 4: Search for forbidden combat button JSON**

```powershell
cd D:\code\trpg
rg -n "graphAction: \\{ verb: 'attack'|graphAction: \\{ verb: 'cast'|graphAction: \\{ verb: 'pass'|graphAction: \\{ verb: 'move'" client\logic\combat client\components\combat
```

Expected: no matches.

- [ ] **Step 5: Commit verification-only doc note if needed**

If implementation changed the design, update:

```powershell
git add docs/superpowers/specs/2026-05-13-combat-command-boundary-design.md docs/superpowers/plans/2026-05-13-combat-command-boundary.md
git commit -m "docs: align combat command plan"
```

If no docs changed, skip this commit.
