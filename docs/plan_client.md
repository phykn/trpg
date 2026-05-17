# Runtime Contract Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the server and client with `docs/plan.md` for roll streaming, combat tactics, combat skill support, level-up choices, and public-state boundaries.

**Architecture:** The server remains the source of truth for graph facts and exposes only public runtime state through wire payloads. The client renders server-composed text verbatim, uses public payloads to build UI controls, and sends explicit combat commands without interpreting hidden graph data.

**Tech Stack:** FastAPI, Pydantic v2, pytest, Expo, React Native, TypeScript, Jest.

---

## Scope

This is now a server/client integration plan, not a client-only plan. The file stays at `docs/plan_client.md` because it started as the client implementation plan, but the execution scope includes the server public combat payload required for correct client behavior.

In scope:

- Add public combat skill support payload from server to client.
- Let client show actual skill-name combat buttons when server says they are usable.
- Keep combat UI to situation-based maximum 3 buttons.
- Remove legacy public combat commands from the new server/client path.
- Use roll stream by default and apply stream `result` state immediately.
- Remove client-owned `think` request fields.
- Remove client `cast` graph action type.
- Accept server level-up choices as-is, including stat growth.
- Keep raw action, hidden graph, pending action source, and reward budget out of client state.

Out of scope:

- Item support buttons in combat.
- New combat skill engine behavior beyond wiring the existing support engine.
- New endpoint groups.
- Client-side graph interpretation.
- Legacy compatibility branches, except natural-language input aliases at the server input-normalization boundary described in `docs/plan.md`.

## Legacy Policy

No legacy command or action shape should remain in the implemented server/client runtime path.

- Client must not type, build, send, or test legacy combat commands: `attack`, `skill`, `defend`, `flee`.
- Client must not type, build, send, or test legacy graph action verb `cast`.
- Server combat command schema should accept only v1 tactic commands: `precise`, `guarded`, `reckless`, `create_distance`, `talk`.
- Server command builder should not keep compatibility branches for legacy combat commands after this migration.
- Server may still accept player natural-language aliases such as “스킬”, “마법”, “공격”, or “도망” only at the classify/input-normalization boundary, then convert them into canonical actions/tactics before resolver/engine code.
- Tests should assert that the new public server/client command path uses v1 tactics only.

## Current Gaps

- Server combat engine already supports skill support through `GraphCombatAction.support_id/support_kind`, but `GraphCombatPayload` does not expose usable combat supports.
- Server combat command schema still accepts legacy command names and does not accept explicit `support_id`/`support_kind` from client.
- Client combat UI shows legacy `attack/skill/defend/flee` actions instead of v1 tactics and real skill names.
- Client `rollGraphPending` posts to `/graph/roll` instead of `/graph/roll/stream`.
- Client stream parser does not surface `result` payload state before `final`.
- Client request bodies still send `think: false` in several places even though this product direction is “client does not use thinking mode.”
- Client `GraphAction.verb` still includes legacy `cast`.
- Client `GraphLevelUpGrowth` is missing `{ kind: 'stat'; stat: ... }`.

## File Map

Server:

- `server/src/wire/models.py` defines public wire payloads.
- `server/src/wire/graph/combat.py` builds combat payloads.
- `server/src/api/schema.py` defines REST request schemas.
- `server/src/game/runtime/action/combat_command.py` converts public combat commands into canonical runtime actions.
- `server/tests/wire/test_graph_front_state.py` or a new focused wire test covers combat payload shape.
- `server/tests/api/test_graph_session_routes.py` covers explicit support command routing.
- `server/tests/game/runtime/test_graph_combat.py` or existing combat runtime tests cover support validation if needed.
- `server/src/locale/catalog/runtime.toml` contains one player-facing `스킬` string that should become `기술`.

Client:

- `client/services/wire.ts` defines server/client TypeScript wire contracts.
- `client/services/api.ts` owns all API calls and stream parsing.
- `client/services/graphAdapter.ts` adapts server graph front state into UI state.
- `client/services/suggestions.ts` normalizes suggestion chips and must continue dropping raw `action`.
- `client/logic/game/useGame.ts` owns graph runtime state.
- `client/logic/game/requestRunner.ts` owns in-flight stream behavior.
- `client/logic/combat/types.ts` defines combat UI state.
- `client/logic/combat/actions.ts` builds combat buttons.
- `client/components/combat/CombatStrip.tsx` renders the combat strip.
- `client/locale/ko.ts` owns client-side Korean labels.
- Existing client tests live under `client/**/__tests__`.

## Task 1: Server Combat Support Payload

**Files:**

- Modify: `server/src/wire/models.py`
- Modify: `server/src/wire/graph/combat.py`
- Test: add or update focused server wire combat tests

- [ ] Add a public support payload model.

Expected shape:

```py
class GraphCombatSupportPayload(_CamelModel):
    id: str
    kind: Literal["skill"]
    name: str
    tactic: Literal["precise", "guarded", "reckless", "create_distance", "talk"]
    mp_cost: int
    usable: bool = True
```

`kind` is intentionally only `"skill"` for this task. Item support remains out of scope.

- [ ] Add `available_supports: list[GraphCombatSupportPayload] = Field(default_factory=list)` to `GraphCombatPayload`.

- [ ] Build `available_supports` from the player’s `knows_skill` edges in `server/src/wire/graph/combat.py`.

Rules:

- Include only skill nodes known by the player.
- Include only supports whose `action` maps to a v1 combat tactic:
  - `attack` -> `precise`
  - `defend` -> `guarded`
  - `flee` -> `create_distance`
  - `social` -> `talk`
  - direct `precise`, `guarded`, `reckless`, `create_distance`, `talk` stay as themselves.
- Include only currently usable skills where player MP is at least `mp_cost`.
- Use server-side names from graph/content; client must not reconstruct names.
- Sort by stable graph edge order or skill id so tests are deterministic.

Example expected JSON key after Pydantic aliasing:

```json
{
  "availableSupports": [
    {
      "id": "skill_gen_attack_abc",
      "kind": "skill",
      "name": "그림자 찌르기",
      "tactic": "precise",
      "mpCost": 2,
      "usable": true
    }
  ]
}
```

- [ ] Write a failing test that creates a combat state with one known attack skill and enough MP, then asserts `availableSupports[0]` is present with camelCase keys.

- [ ] Write a failing test that creates a known skill with `mp_cost` above current MP and asserts it is not included.

- [ ] Run the focused server test.

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server\tests\wire\test_graph_front_state.py -q
```

Expected: PASS after implementation.

## Task 2: Server Explicit Combat Support Command

**Files:**

- Modify: `server/src/api/schema.py`
- Modify: `server/src/game/runtime/action/combat_command.py`
- Test: `server/tests/api/test_graph_session_routes.py`

- [ ] Extend `GraphCombatCommandRequest` with explicit support fields.

Expected schema:

```py
support_id: str | None = None
support_kind: Literal["skill"] | None = None
```

- [ ] Validate the pair at the API schema or command builder boundary.

Rules:

- `support_id` and `support_kind` must both be present or both absent.
- `support_kind` only allows `"skill"`.
- `support_id` is passed through to existing engine validation. Do not trust client ownership or MP claims.

- [ ] Update `build_combat_command_action`.

Mapping:

- `precise` -> `Action(verb="attack", what=target_id, how="precise", with_=support_id)`
- `reckless` -> `Action(verb="attack", what=target_id, how="reckless", with_=support_id)`
- `talk` -> `Action(verb="speak", to=target_id, with_=support_id)` if supported by `Action`; if `Action` does not use `with_` for speak in combat, map to an attack/pass action only after confirming engine support.
- `guarded` -> `Action(verb="pass", how="guarded", with_=support_id)` if supported; otherwise keep support off guarded until engine supports it.
- `create_distance` -> `Action(verb="move", how="create_distance", with_=support_id)` if supported.

Implementation note: inspect `server/src/game/runtime/action/combat.py` before editing. If it only reads `action.with_` for `attack`, first extend `_combat_action_from_action` to pass support for `speak`, `pass`, and `move` when in combat. Keep the change surgical.

- [ ] Remove server compatibility for legacy combat commands in this request schema and command builder.

Legacy commands to remove from `GraphCombatCommandRequest` and `build_combat_command_action`:

```text
attack
skill
defend
flee
```

The accepted public command set after this task is:

```text
precise
guarded
reckless
create_distance
talk
```

- [ ] Add a route test that posts a `precise` command with `support_id/support_kind` and verifies the request reaches the combat engine without schema rejection.

- [ ] Add a route or unit test that sends only `support_id` without `support_kind` and expects HTTP 422.

- [ ] Add a route or unit test that sends legacy `command: "skill"` and expects HTTP 422.

- [ ] Run focused tests.

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py -q
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime -q
```

Expected: PASS after implementation.

## Task 3: Server Locale Cleanup

**Files:**

- Modify: `server/src/locale/catalog/runtime.toml`
- Test: existing locale or runtime tests

- [ ] Change the player-facing Korean level-up MP description from `스킬 사용 여유가 1 오릅니다.` to `기술 사용 여유가 1 오릅니다.`

- [ ] Search for remaining unintended player-facing `스킬`.

```powershell
cd D:\code\trpg
rg -n "스킬" server\src\locale server\src\wire server\src\game
```

Expected: no unintended player-facing `스킬` remains. Prompt text that explicitly accepts user synonyms may remain only if it is intentionally about input synonyms.

## Task 4: Client Wire Type Alignment

**Files:**

- Modify: `client/services/wire.ts`

- [ ] Add `GraphCombatSupport` and expose it from `GraphCombatState`.

Expected TypeScript shape:

```ts
export type GraphCombatSupport = {
  id: string;
  kind: 'skill';
  name: string;
  tactic: 'precise' | 'guarded' | 'reckless' | 'create_distance' | 'talk';
  mpCost: number;
  usable: boolean;
};
```

- [ ] Update `CombatCommand` to include only v1 tactic commands and optional support fields.

Expected command shape:

```ts
type CombatSupportCommandFields = {
  support_id?: string;
  support_kind?: 'skill';
};

export type CombatCommand =
  | ({ command: 'precise'; target_id: string } & CombatSupportCommandFields)
  | ({ command: 'reckless'; target_id: string } & CombatSupportCommandFields)
  | ({ command: 'talk'; target_id: string } & CombatSupportCommandFields)
  | ({ command: 'guarded' } & CombatSupportCommandFields)
  | ({ command: 'create_distance' } & CombatSupportCommandFields);
```

Do not keep legacy `attack`, `skill`, `defend`, or `flee` variants in the client type.

- [ ] Add `availableSupports: GraphCombatSupport[]` to `GraphCombatState`.

- [ ] Add combat outcomes `escaped`, `surrendered`, and `combat_stopped`.

- [ ] Add `escapeReady: boolean` and `enemyPressure: number`.

- [ ] Add stat growth:

```ts
| { kind: 'stat'; stat: 'body' | 'agility' | 'mind' | 'presence' }
```

- [ ] Remove `think` from client request types.

Expected:

```ts
export type ConfirmRequest = {
  confirmation_id: string;
  decision: 'confirm' | 'cancel';
};

export type GraphRollRequest = {
  roll_id: string;
};

export type GraphLevelUpRequest = {
  growth: GraphLevelUpGrowth;
};
```

- [ ] Remove `cast` from `GraphAction.verb`.

- [ ] Verify no direct client `cast` action remains.

```powershell
cd D:\code\trpg
rg -n "verb: 'cast'|\"cast\"" client
```

Expected: no client action construction uses `cast`.

- [ ] Verify no legacy combat command construction remains.

```powershell
cd D:\code\trpg
rg -n "command: 'attack'|command: 'skill'|command: 'defend'|command: 'flee'" client
```

Expected: no client code constructs these commands.

- [ ] Run typecheck.

```powershell
cd D:\code\trpg\client
npx tsc --noEmit
```

Expected: PASS after dependent tasks are complete.

## Task 5: Client Combat Adapter

**Files:**

- Modify: `client/logic/combat/types.ts`
- Modify: `client/services/graphAdapter.ts`
- Test: `client/services/__tests__/graphAdapter.test.ts`

- [ ] Add support fields to `CombatBadge`.

Expected shape:

```ts
export type CombatSupport = {
  id: string;
  kind: 'skill';
  name: string;
  tactic: 'precise' | 'guarded' | 'reckless' | 'create_distance' | 'talk';
  mpCost: number;
  usable: boolean;
};
```

`CombatBadge` should include:

```ts
outcome: GraphCombatState['outcome'];
escapeReady: boolean;
enemyPressure: number;
availableSupports: CombatSupport[];
```

- [ ] Map server `combat.availableSupports` through `adaptCombat`.

- [ ] Default missing `availableSupports` to `[]` for compatibility.

- [ ] Add tests for:
  - `availableSupports` mapping.
  - missing `availableSupports` maps to `[]`.
  - `escapeReady`, `enemyPressure`, and new outcomes map through.

- [ ] Run focused tests.

```powershell
cd D:\code\trpg\client
npm test -- --runInBand services/__tests__/graphAdapter.test.ts
```

Expected: PASS.

## Task 6: Client Combat 3-Slot Actions

**Files:**

- Modify: `client/logic/combat/actions.ts`
- Modify: `client/components/combat/CombatStrip.tsx`
- Modify: `client/locale/ko.ts`
- Test: `client/logic/combat/__tests__/actions.test.ts`

- [ ] Replace default legacy combat buttons with max 3 situation-based slots.

Rules:

- Slot 1, attack slot: use the first usable support with tactic `precise`; otherwise `precise`.
- Slot 2, defense slot: use the first usable support with tactic `guarded`; otherwise `guarded`.
- Slot 3, situation slot:
  - if `escapeReady`, use `create_distance` with label meaning “빠져나가기”;
  - else if usable support with tactic `create_distance`, use that skill;
  - else if `enemyPressure > 0` or enemy hearts current is `<= 1`, use `talk`;
  - else if usable support with tactic `reckless`, use that skill;
  - else use `create_distance`.

- [ ] Skill buttons must show `support.name`, not a generic `기술` label.

- [ ] Skill buttons send command with `support_id` and `support_kind: 'skill'`.

Example action for an attack support:

```ts
{
  kind: 'combat_command',
  label: '그림자 찌르기',
  combatCommand: {
    command: 'precise',
    target_id: 'enemy_01',
    support_id: 'skill_gen_attack_abc',
    support_kind: 'skill',
  },
  textFallback: '그림자 찌르기를 사용합니다',
}
```

- [ ] Plain fallback actions send tactic commands only.

Examples:

```ts
{ command: 'precise', target_id: targetId }
{ command: 'guarded' }
{ command: 'create_distance' }
{ command: 'talk', target_id: targetId }
```

- [ ] Add client labels to `ko.combat`:
  - `precise`
  - `guarded`
  - `reckless`
  - `createDistance`
  - `escape`
  - `talk`
  - `pressure`

- [ ] Update `CombatStrip` so action buttons wrap or size correctly with 3 buttons and skill names.

UI constraints:

- Maximum 3 buttons.
- No nested cards.
- No long instructional rule text.
- Use short status chips for `escapeReady` and `enemyPressure`.

- [ ] Tests:
  - no support -> `precise`, `guarded`, `create_distance`.
  - attack support -> first button is support name with `support_id`.
  - guarded support -> second button is support name.
  - `escapeReady` -> third button is `create_distance` with escape label.
  - `enemyPressure > 0` -> third button is `talk`.
  - output length never exceeds 3.

- [ ] Run focused tests.

```powershell
cd D:\code\trpg\client
npm test -- --runInBand logic/combat/__tests__/actions.test.ts
```

Expected: PASS.

## Task 7: Client Roll Stream and Result State

**Files:**

- Modify: `client/services/api.ts`
- Modify: `client/logic/game/requestRunner.ts`
- Modify: `client/logic/game/useGame.ts`
- Test: `client/services/__tests__/api.test.ts`
- Test: `client/logic/game/__tests__/requestRunner.test.ts`

- [ ] Change `rollGraphPending` to use stream first and plain endpoint as fallback.

Expected call:

```ts
return requestGraphActionWithOptionalStream(
  'rollGraphPending',
  `/session/${gameId}/graph/roll/stream`,
  `/session/${gameId}/graph/roll`,
  body,
  options,
);
```

- [ ] Add `onResult?: (response: GraphActionClientResponse) => void` to API request options.

- [ ] In `readGraphActionStream`, adapt `result.payload` and call `onResult` before later narration delta callbacks.

- [ ] Keep `resultOutcome` behavior so narration deltas receive the result outcome.

- [ ] In `requestRunner`, pass `onResult` through request events.

- [ ] In `onResult`, apply state immediately after checking generation and active game id.

- [ ] Keep suggestions update at `final` only.

- [ ] Remove client `think` fields from:
  - `sendGraphInput`
  - `confirmGraphAction`
  - `rollGraphPending`
  - `sendGraphLevelUp`

- [ ] Update `useGame` call sites to stop passing `think: false`.

- [ ] Tests:
  - roll stream endpoint is called first.
  - roll stream falls back to plain endpoint on 404.
  - `result` callback fires before `narration_delta`.
  - request runner applies result state immediately.
  - request runner ignores stale result game id.
  - final response still updates suggestions.

- [ ] Run focused tests.

```powershell
cd D:\code\trpg\client
npm test -- --runInBand services/__tests__/api.test.ts logic/game/__tests__/requestRunner.test.ts
```

Expected: PASS.

## Task 8: Level-Up Choice Compatibility

**Files:**

- Modify: `client/components/composer/LevelUpPrompt.tsx`
- Test: `client/components/composer/__tests__/LevelUpPrompt.test.ts`

- [ ] Keep displaying server `label` and `description` verbatim.

- [ ] Ensure `{ kind: 'stat'; stat: 'body' | 'agility' | 'mind' | 'presence' }` passes through `onCommit` unchanged.

- [ ] Keep fallback choices limited to max HP and max MP for “options failed to load” safety only.

- [ ] Add a test that a stat choice renders with its server label and commits the exact growth object.

- [ ] Run focused test.

```powershell
cd D:\code\trpg\client
npm test -- --runInBand components/composer/__tests__/LevelUpPrompt.test.ts
```

Expected: PASS.

## Task 9: Public State Boundary Tests

**Files:**

- Modify: `client/services/suggestions.ts` only if needed
- Test: `client/services/__tests__/graphAdapter.test.ts`
- Test: `client/services/__tests__/localeBoundary.test.ts` if text ownership needs coverage

- [ ] Ensure `GraphSuggestion.action` continues to be dropped.

Expected normalized suggestion:

```ts
normalizeGraphSuggestion({
  label: '북문으로',
  input_text: '북문으로 이동합니다',
  intent: 'move',
  action: { verb: 'move', to: 'north_gate' },
})
```

returns:

```ts
{ label: '북문으로', inputText: '북문으로 이동합니다', intent: 'move' }
```

- [ ] Search for client state additions that would expose hidden graph internals.

```powershell
cd D:\code\trpg
rg -n "pending.*action|raw.*action|rewardBudget|xpAward|hidden_at|connects_to" client
```

Expected: no client state exposes these internals.

- [ ] Search for unintended client-owned `스킬`.

```powershell
cd D:\code\trpg
rg -n "스킬" client
```

Expected: no new client-owned `스킬`; use `기술` for player-facing labels.

## Task 10: Full Verification

- [ ] Run server focused lint and tests.

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest server\tests\game server\tests\api server\tests\wire -q
.\.venv\Scripts\ruff.exe check server\src server\tests
```

Expected: PASS.

- [ ] Run full Python test suite if focused tests pass.

```powershell
cd D:\code\trpg
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: PASS.

- [ ] Run client verification.

```powershell
cd D:\code\trpg\client
npm run lint
npx tsc --noEmit
npm test -- --runInBand
```

Expected: PASS.

- [ ] Optional manual web check.

```powershell
cd D:\code\trpg\client
npm run web
```

Manual checks:

- pending roll uses streaming narration and clears pending at result state.
- combat strip shows at most 3 buttons.
- usable combat skills appear as skill-name buttons.
- skill buttons send `support_id/support_kind`.
- level-up stat choices render server labels and commit exact growth.
- server-composed log/message text is not rewritten by client.

## Completion Criteria

- [ ] Server exposes `combat.availableSupports` for usable combat skills only.
- [ ] Server accepts explicit combat skill support commands and validates them through existing engine logic.
- [ ] Server public combat command schema rejects legacy `attack`, `skill`, `defend`, and `flee` commands.
- [ ] Client combat UI uses situation-based maximum 3 buttons.
- [ ] Client skill combat buttons show actual skill names.
- [ ] Client sends skill support metadata only when a server-provided support is chosen.
- [ ] Client uses `/graph/roll/stream` by default with `/graph/roll` fallback.
- [ ] Client applies stream `result` state immediately and suggestions at `final`.
- [ ] Client no longer sends `think` fields.
- [ ] Client no longer allows `cast` as a graph action verb.
- [ ] Client no longer types or sends legacy combat commands.
- [ ] Level-up stat growth is type-safe and passed through unchanged.
- [ ] Raw action, hidden graph data, pending action source, and reward budget stay out of client state.
- [ ] Server and client verification commands pass.
