# LLM Pipeline Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make graph action streams send engine result and success/failure outcome before narration, remove partial roll outcomes, and align server/client behavior with `docs/plan.md`.

**Architecture:** The server becomes result-first: engine state is committed before narration, stream endpoints emit `result`, then `narration_delta`, then `final`. Response-level `outcome` is computed by Python/runtime code, never by the LLM. The client stores that outcome from `result` and uses it to style temporary streamed narration.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest, Expo React Native, TypeScript, Jest.

---

## File Structure

- Modify `server/src/game/rules/dc.py`: remove `partial_success` branch from roll grade calculation.
- Modify `server/src/game/domain/types.py`: remove `partial_success` from the `Grade` literal.
- Modify `server/src/game/domain/memory.py`: remove `partial` from `RollLogEntry.result`.
- Modify `server/src/game/runtime/roll.py`: map roll grades to `success | fail`, clear pending roll, and continue the stored action.
- Modify `server/src/game/runtime/request_result.py`: add response-level `outcome`.
- Modify `server/src/game/runtime/turn.py`: split action turn into result commit and narration commit.
- Modify `server/src/game/runtime/input.py`: guard pending state before player-log append/classify; adapt stream event names.
- Modify `server/src/game/runtime/confirmation.py`: adapt stream event names and outcome propagation.
- Modify `server/src/game/runtime/session.py` and `server/src/game/runtime/intro.py`: make intro stream use the same result/narration/final event shape.
- Modify `server/src/api/schema.py`: add `outcome` to `GraphActionResponse`; remove or stop using `event_kind`.
- Modify `server/src/api/session_graph_routes.py`: serialize the new stream event types.
- Modify server tests under `server/tests/game/rules`, `server/tests/game/runtime`, `server/tests/api`.
- Modify `client/services/wire.ts`: add response-level `outcome`, remove `eventKind`, remove `partial` roll result.
- Modify `client/services/api.ts`: parse `result`, `narration_delta`, and `final`.
- Modify `client/logic/game/requestRunner.ts`: apply state on `result`, remember outcome, and pass outcome with narration deltas.
- Modify `client/logic/log/types.ts`: remove `partial`.
- Modify `client/components/log/RollResult.tsx`: remove partial tone.
- Modify `client/locale/ko.ts`: remove partial roll label.
- Modify client tests under `client/services/__tests__`, `client/logic/game/__tests__`, and `client/components/log/__tests__`.

## Task 1: Remove Partial Roll Outcomes

**Files:**
- Modify: `server/src/game/rules/dc.py`
- Modify: `server/src/game/domain/types.py`
- Modify: `server/src/game/domain/memory.py`
- Modify: `server/src/game/runtime/roll.py`
- Modify: `server/src/game/rules/config.py`
- Modify: `server/tests/game/rules/test_dc.py`
- Modify: `server/tests/game/runtime/test_graph_roll.py`
- Modify: `client/logic/log/types.ts`
- Modify: `client/components/log/RollResult.tsx`
- Modify: `client/locale/ko.ts`
- Modify: `client/components/log/__tests__/LogItem.test.ts`

- [ ] **Step 1: Update the server grade test first**

In `server/tests/game/rules/test_dc.py`, change `test_compute_grade_normal_branches` to expect failure when missing by 1:

```python
def test_compute_grade_normal_branches():
    # total >= required -> success.
    assert compute_grade(dice=15, total=18, required_roll=15) == "success"
    assert compute_grade(dice=10, total=10, required_roll=10) == "success"
    # Anything below required is failure.
    assert compute_grade(dice=10, total=9, required_roll=10) == "failure"
    assert compute_grade(dice=5, total=5, required_roll=10) == "failure"
```

- [ ] **Step 2: Run the server grade test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\rules\test_dc.py::test_compute_grade_normal_branches -q
```

Expected: FAIL because `compute_grade(dice=10, total=9, required_roll=10)` still returns `partial_success`.

- [ ] **Step 3: Remove partial from server grade calculation and types**

In `server/src/game/rules/dc.py`, change `compute_grade` to:

```python
def compute_grade(dice: int, total: int, required_roll: int) -> Grade:
    # Critical only looks at the raw dice; modifiers cannot create or erase a critical.
    if dice >= RULES.difficulty_class.critical_hit_threshold:
        return "critical_success"
    if dice <= RULES.difficulty_class.critical_miss_threshold:
        return "critical_failure"
    if total >= required_roll:
        return "success"
    return "failure"
```

In `server/src/game/domain/types.py`, remove `"partial_success"` from the `Grade` literal. The resulting grade set should be:

```python
Grade = Literal[
    "critical_success",
    "success",
    "failure",
    "critical_failure",
]
```

In `server/src/game/domain/memory.py`, change the roll result literal to:

```python
result: Literal["success", "fail"]
```

In `server/src/game/runtime/roll.py`, change `_roll_result` to:

```python
def _roll_result(grade: str) -> str:
    if grade in {"critical_success", "success"}:
        return "success"
    return "fail"
```

In `server/src/game/rules/config.py`, remove the `partial_success` entries from grade maps. Leave the other grade keys unchanged.

- [ ] **Step 4: Update roll tests for binary results**

In `server/tests/game/runtime/test_graph_roll.py`, add a focused failure assertion after the existing success test:

```python
async def test_run_graph_roll_one_short_is_fail(tmp_path):
    repo = await _repo(tmp_path)
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="perceive", what="town"))
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=12)
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert logs[0].kind == "roll"
    assert logs[0].roll == 12
    assert logs[0].result == "fail"
```

- [ ] **Step 5: Update client roll types and UI**

In `client/logic/log/types.ts`, change:

```ts
export type RollResult = 'success' | 'fail';
```

In `client/components/log/RollResult.tsx`, remove the `partial` entry from `TONE` so it is:

```ts
const TONE = {
  success: { color: colors.success.fg, label: ko.roll.success, cls: 'text-success-fg' },
  fail:    { color: colors.danger.fg,  label: ko.roll.fail,    cls: 'text-danger-fg'  },
} as const;
```

In `client/locale/ko.ts`, remove the `roll.partial` label from the `roll` catalog.

In `client/components/log/__tests__/LogItem.test.ts`, add an assertion that the source no longer contains a partial tone:

```ts
test('does not include partial roll tone', () => {
  expect(source).not.toContain('partial');
});
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\rules\test_dc.py server\tests\game\runtime\test_graph_roll.py -q
```

Expected: PASS.

From `client/`, run:

```powershell
npm test -- --runInBand components/log/__tests__/LogItem.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add server/src/game/rules/dc.py server/src/game/domain/types.py server/src/game/domain/memory.py server/src/game/runtime/roll.py server/src/game/rules/config.py server/tests/game/rules/test_dc.py server/tests/game/runtime/test_graph_roll.py client/logic/log/types.ts client/components/log/RollResult.tsx client/locale/ko.ts client/components/log/__tests__/LogItem.test.ts
git commit -m "refactor: remove partial roll outcomes"
```

## Task 2: Add Response-Level Outcome

**Files:**
- Modify: `server/src/game/runtime/request_result.py`
- Modify: `server/src/api/schema.py`
- Modify: `server/src/api/session_graph_routes.py`
- Modify: `server/tests/game/runtime/test_request_result.py`
- Modify: `client/services/wire.ts`
- Modify: `client/services/api.ts`
- Modify: `client/services/__tests__/api.test.ts`

- [ ] **Step 1: Write server result outcome tests**

In `server/tests/game/runtime/test_request_result.py`, update the existing result factory tests to assert outcomes:

```python
def test_request_results_include_presentation_outcome():
    runtime = _runtime()
    front_state = graph_to_front_state(runtime)

    assert executed_result(runtime, front_state).outcome == "success"
    assert rejected_result(runtime, front_state, "지금은 할 수 없습니다.").outcome == "failure"
    assert answered_result(runtime, front_state, "주변은 조용합니다.").outcome == "neutral"
    assert cancelled_result(runtime, front_state).outcome == "neutral"
    assert confirmation_required_result(
        runtime,
        front_state,
        {"id": "confirm_1", "kind": "quest_accept"},
    ).outcome == "neutral"
    assert roll_required_result(
        runtime,
        front_state,
        {"id": "roll_1", "kind": "perceive"},
    ).outcome == "neutral"
```

- [ ] **Step 2: Run the server result test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_request_result.py::test_request_results_include_presentation_outcome -q
```

Expected: FAIL because `GraphActionRequestResult` has no `outcome` field yet.

- [ ] **Step 3: Add outcome to request results**

In `server/src/game/runtime/request_result.py`, add:

```python
GraphResultOutcome = Literal["success", "failure", "neutral"]
```

Add `outcome: GraphResultOutcome` to `GraphActionRequestResult`.

Change factory functions to pass outcome:

```python
def executed_result(..., outcome: GraphResultOutcome = "success", ...) -> GraphActionRequestResult:
    return _result(..., status="executed", outcome=outcome, ...)

def rejected_result(...) -> GraphActionRequestResult:
    return _result(..., status="rejected", outcome="failure", ...)

def answered_result(...) -> GraphActionRequestResult:
    return _result(..., status="answered", outcome="neutral", ...)

def roll_required_result(...) -> GraphActionRequestResult:
    return _result(..., status="roll_required", outcome="neutral", ...)

def confirmation_required_result(...) -> GraphActionRequestResult:
    return _result(..., status="confirmation_required", outcome="neutral", ...)

def cancelled_result(...) -> GraphActionRequestResult:
    return _result(..., status="cancelled", outcome="neutral")
```

Update `_result` to require `outcome` and set it on `GraphActionRequestResult`.

Add a dispatch mapping helper in `server/src/game/runtime/request_result.py`:

```python
def outcome_from_dispatch(dispatch: GraphActionDispatchResult) -> GraphResultOutcome:
    if dispatch.kind == "combat":
        if dispatch.outcome == "victory":
            return "success"
        if dispatch.outcome == "defeat":
            return "failure"
        return "neutral"
    if dispatch.kind == "move":
        return "neutral"
    return "success"
```

Use this helper whenever `executed_result(...)` wraps a `GraphActionDispatchResult`, unless a caller explicitly passes a roll-driven outcome.

- [ ] **Step 4: Add API response outcome**

In `server/src/api/schema.py`, change `GraphActionResponse` to:

```python
class GraphActionResponse(BaseModel):
    game_id: str
    state: dict
    status: str | None = None
    outcome: Literal["success", "failure", "neutral"] = "neutral"
    message: str | None = None
    suggestions: list[GraphSuggestionValue] = Field(default_factory=list)
```

In every `GraphActionResponse(...)` construction in `server/src/api/session_graph_routes.py`, pass:

```python
outcome=result.outcome,
```

For level-up, pass `outcome="success"` because a successful level-up applies a player-selected growth.

- [ ] **Step 5: Update client response types**

In `client/services/wire.ts`, add:

```ts
export type GraphResultOutcome = 'success' | 'failure' | 'neutral';
```

Change `GraphActionResponse`:

```ts
export type GraphActionResponse = {
  game_id: string;
  state: GraphFrontState;
  status?: string | null;
  outcome?: GraphResultOutcome | null;
  message?: string | null;
  suggestions?: GraphSuggestion[];
};
```

Change `GraphActionClientResponse`:

```ts
export type GraphActionClientResponse = {
  game_id: string;
  state: FrontState;
  pendingConfirmation: PendingConfirmation | null;
  pendingRoll: PendingRoll | null;
  status?: string | null;
  outcome: GraphResultOutcome;
  message?: string | null;
  suggestions: SuggestionChip[];
};
```

In `client/services/api.ts`, update `adaptGraphActionResponse` to:

```ts
outcome: payload.outcome ?? 'neutral',
```

and remove `eventKind`.

- [ ] **Step 6: Update client API tests**

In `client/services/__tests__/api.test.ts`, change expected payload examples from `event_kind: 'result'` to `outcome: 'success'` where the response is executed, and assert:

```ts
expect(result.outcome).toBe('success');
```

For confirmation-required examples, assert:

```ts
expect(result.outcome).toBe('neutral');
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_request_result.py server\tests\api\test_graph_session_routes.py -q
```

Expected: PASS after updating route expectations.

From `client/`, run:

```powershell
npm test -- --runInBand services/__tests__/api.test.ts
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add server/src/game/runtime/request_result.py server/src/api/schema.py server/src/api/session_graph_routes.py server/tests/game/runtime/test_request_result.py server/tests/api/test_graph_session_routes.py client/services/wire.ts client/services/api.ts client/services/__tests__/api.test.ts
git commit -m "feat: add graph response outcomes"
```

## Task 3: Make Text Input Pending-Safe Before Classify

**Files:**
- Modify: `server/src/game/runtime/input.py`
- Modify: `server/tests/game/runtime/test_graph_input.py`

- [ ] **Step 1: Add tests that pending state blocks classify and player-log append**

In `server/tests/game/runtime/test_graph_input.py`, add tests using the existing fake LLM/client helpers in that file:

```python
async def test_graph_input_pending_confirmation_blocks_before_classify(tmp_path):
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(
            update={
                "pending_confirmation": {
                    "id": "confirm_1",
                    "kind": "attack_start",
                    "title": "공격하시겠습니까?",
                    "body": "공격합니다.",
                    "confirm_label": "공격",
                    "cancel_label": "취소",
                    "target_label": "적",
                    "payload": {"kind": "graph_action", "action": {"verb": "attack", "what": ["enemy_01"]}},
                }
            }
        )
    )
    client = _FakeClassifyClient({"intents": [{"intent": "pass"}]})

    with pytest.raises(GraphConfirmationActive):
        await run_graph_input_turn(client, repo, "game-1", "아무 말")

    assert client.calls == []
    assert await repo.load_log_entries("game-1") == []
```

Add the same test shape for `pending_roll`:

```python
async def test_graph_input_pending_roll_blocks_before_classify(tmp_path):
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(
            update={
                "pending_roll": {
                    "id": "roll_1",
                    "kind": "perceive",
                    "title": "지력 판정이 필요합니다",
                    "body": "주변을 살핍니다.",
                    "stat": "mind",
                    "stat_label": "지력",
                    "required_roll": 13,
                    "payload": {"kind": "graph_action", "action": {"verb": "perceive", "what": "town"}},
                }
            }
        )
    )
    client = _FakeClassifyClient({"intents": [{"intent": "pass"}]})

    with pytest.raises(GraphConfirmationActive):
        await run_graph_input_turn(client, repo, "game-1", "아무 말")

    assert client.calls == []
    assert await repo.load_log_entries("game-1") == []
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_input.py::test_graph_input_pending_confirmation_blocks_before_classify server\tests\game\runtime\test_graph_input.py::test_graph_input_pending_roll_blocks_before_classify -q
```

Expected: FAIL because current input flow appends player log and calls classify first.

- [ ] **Step 3: Add pending guard helper**

In `server/src/game/runtime/input.py`, import `GraphConfirmationActive` from `.confirmation` if it is not already imported.

Add:

```python
def _raise_if_pending_input_blocked(runtime: GameRuntimeState) -> None:
    if runtime.progress.pending_confirmation is not None:
        raise GraphConfirmationActive(
            "a pending_confirmation is already active; call graph confirm instead"
        )
    if runtime.progress.pending_roll is not None:
        raise GraphConfirmationActive(
            "a pending_roll is already active; call graph roll instead"
        )
```

Call it in both `run_graph_input_turn` and `run_graph_input_turn_stream` immediately after `load_runtime_state(...)` and before `_append_player_input_log(...)`.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_input.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/src/game/runtime/input.py server/tests/game/runtime/test_graph_input.py
git commit -m "fix: block graph input while pending"
```

## Task 4: Emit Result Before Narration In Server Streams

**Files:**
- Modify: `server/src/game/runtime/turn.py`
- Modify: `server/src/game/runtime/input.py`
- Modify: `server/src/game/runtime/confirmation.py`
- Modify: `server/src/game/runtime/session.py`
- Modify: `server/src/game/runtime/intro.py`
- Modify: `server/src/api/session_graph_routes.py`
- Modify: `server/tests/api/test_graph_session_routes.py`
- Modify: `server/tests/game/runtime/test_graph_action_turn.py`
- Modify: `server/tests/game/runtime/test_graph_input.py`

- [ ] **Step 1: Update API stream tests to the new event order**

In `server/tests/api/test_graph_session_routes.py`, replace tests expecting `["delta", "delta", "final"]` with expectations like:

```python
assert [event["type"] for event in events] == [
    "result",
    "narration_delta",
    "narration_delta",
    "final",
]
assert events[0]["payload"]["outcome"] in {"success", "neutral", "failure"}
```

For no-narration streams, expect:

```python
assert [event["type"] for event in events] == ["result", "final"]
```

- [ ] **Step 2: Run updated API stream tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py -q
```

Expected: FAIL because streams still emit `delta` before `final`.

- [ ] **Step 3: Split action turn persistence**

In `server/src/game/runtime/turn.py`, split `_finish_graph_action_turn` into two helpers:

```python
async def _commit_graph_action_result(
    repo: GraphRepo,
    game_id: str,
    prepared: _PreparedGraphActionTurn,
) -> GraphActionTurnResult:
    card = prepared.cards[0]
    log_entries = [*prepared.cards]
    next_progress = prepared.after.progress.model_copy(
        update={"next_log_id": card.id + len(log_entries)}
    )
    next_runtime = prepared.after.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*prepared.after.log_entries, *log_entries],
        }
    )
    await prepared.dirty.save(repo, game_id, next_runtime.graph)
    await repo.append_log_entries(game_id, log_entries)
    await repo.save_progress(next_runtime.progress)
    return GraphActionTurnResult(
        runtime=next_runtime,
        dispatch=prepared.dispatch,
        front_state=graph_to_front_state(next_runtime),
    )
```

Then add:

```python
async def _commit_graph_action_narration(
    repo: GraphRepo,
    game_id: str,
    prepared: _PreparedGraphActionTurn,
    result_runtime: GameRuntimeState,
    narration_result: GraphNarrationResult,
) -> GraphActionTurnResult:
    if not narration_result.narration:
        return GraphActionTurnResult(
            runtime=result_runtime,
            dispatch=prepared.dispatch,
            front_state=graph_to_front_state(result_runtime),
            suggestions=narration_result.suggestions,
        )
    entry = GMLogEntry(
        id=result_runtime.progress.next_log_id,
        kind="gm",
        text=narration_result.narration,
    )
    next_progress = result_runtime.progress.model_copy(
        update={"next_log_id": entry.id + 1}
    )
    next_runtime = result_runtime.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*result_runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(game_id, [entry])
    await repo.save_progress(next_runtime.progress)
    next_runtime = await persist_graph_narration_result(
        repo,
        next_runtime,
        narration_result,
        target_id=_action_target_id(prepared.action),
    )
    return GraphActionTurnResult(
        runtime=next_runtime,
        dispatch=prepared.dispatch,
        front_state=graph_to_front_state(next_runtime),
        suggestions=narration_result.suggestions,
    )
```

Update non-stream action turn to prepare, commit result, build narration, then commit narration.

Update stream action turn to:

```python
prepared = _prepare_graph_action_turn(game_id, runtime, action)
result = await _commit_graph_action_result(repo, game_id, prepared)
yield {
    "type": "result",
    "result": executed_result(
        result.runtime,
        result.front_state,
        dispatch=result.dispatch,
        outcome=outcome_from_dispatch(result.dispatch),
    ),
}
stream narration...
final = await _commit_graph_action_narration(...)
yield {
    "type": "final",
    "result": executed_result(
        final.runtime,
        final.front_state,
        dispatch=final.dispatch,
        outcome=outcome_from_dispatch(final.dispatch),
        suggestions=final.suggestions,
    ),
}
```

When yielding narration chunks, use:

```python
yield {"type": "narration_delta", "text": visible}
```

- [ ] **Step 4: Update input and confirmation stream wrappers**

In `server/src/game/runtime/input.py` and `server/src/game/runtime/confirmation.py`, pass through `result`, `narration_delta`, and `final`.

Replace checks of only `"final"` where needed:

```python
if event["type"] == "final":
    result = event["result"]
elif event["type"] == "result":
    yield event
else:
    yield event
```

For narrative input paths that produce narration without engine dispatch, emit a neutral result before narration:

```python
intermediate = GraphActionRequestResult(
    runtime=runtime,
    status="executed",
    outcome="neutral",
    front_state=graph_to_front_state(runtime),
)
yield {"type": "result", "result": intermediate}
```

- [ ] **Step 5: Update intro stream**

In `server/src/game/runtime/session.py`, when `run_graph_intro_request_stream` receives the initial runtime from `intro.py`, wrap it as a `result` event with neutral outcome. Then pass narration chunks as `narration_delta` and final runtime as `final`.

If `intro.py` currently emits `delta`, change it to emit `narration_delta`.

- [ ] **Step 6: Update API stream serializer**

In `server/src/api/session_graph_routes.py`, change `_stream_event`:

```python
def _stream_event(game_id: str, event) -> str:
    if event["type"] in {"result", "final"}:
        result = event["result"]
        response = GraphActionResponse(
            game_id=game_id,
            state=result.front_state.model_dump(mode="json", by_alias=True),
            status=result.status,
            outcome=result.outcome,
            message=result.message,
            suggestions=result.suggestions,
        )
        payload = {
            "type": event["type"],
            "payload": response.model_dump(mode="json"),
        }
    else:
        payload = event
    return json.dumps(payload, ensure_ascii=False) + "\n"
```

- [ ] **Step 7: Run focused server tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py server\tests\game\runtime\test_graph_action_turn.py server\tests\game\runtime\test_graph_input.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add server/src/game/runtime/turn.py server/src/game/runtime/input.py server/src/game/runtime/confirmation.py server/src/game/runtime/session.py server/src/game/runtime/intro.py server/src/api/session_graph_routes.py server/tests/api/test_graph_session_routes.py server/tests/game/runtime/test_graph_action_turn.py server/tests/game/runtime/test_graph_input.py
git commit -m "feat: stream graph results before narration"
```

## Task 5: Continue Pending Roll Actions

**Files:**
- Modify: `server/src/game/runtime/roll.py`
- Modify: `server/tests/game/runtime/test_graph_roll.py`

- [ ] **Step 1: Add roll continuation test**

In `server/tests/game/runtime/test_graph_roll.py`, extend `_graph()` with a second location and connection:

```python
"forest": GraphNode(
    id="forest",
    type="location",
    properties={"name": "Forest"},
),
"connects_to:town:forest": GraphEdge(
    id="connects_to:town:forest",
    type="connects_to",
    from_node_id="town",
    to_node_id="forest",
),
```

Add this test:

```python
async def test_run_graph_roll_continues_stored_action(tmp_path):
    repo = await _repo(tmp_path)
    pending = build_pending_roll(
        _character("player_01").properties,
        Action(verb="move", to="forest"),
    )
    progress = await repo.load_progress("game-1")
    await repo.save_progress(progress.model_copy(update={"pending_roll": pending}))

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=13)
    progress = await repo.load_progress("game-1")
    edges = (await repo.load_graph("game-1")).edges

    assert result.status == "executed"
    assert progress.pending_roll is None
    assert any(
        edge.type == "located_at"
        and edge.from_node_id == "player_01"
        and edge.to_node_id == "forest"
        for edge in edges.values()
    )
```

- [ ] **Step 2: Run the continuation test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_roll.py::test_run_graph_roll_continues_stored_action -q
```

Expected: FAIL because `run_graph_roll` clears pending and logs roll but does not run the stored action.

- [ ] **Step 3: Continue stored action after roll log**

In `server/src/game/runtime/roll.py`, import:

```python
from .turn import run_graph_action_turn_from_runtime
```

After saving the roll log and clearing pending, call:

```python
turn_result = await run_graph_action_turn_from_runtime(
    repo,
    game_id,
    next_runtime,
    action,
    llm=None,
)
return executed_result(
    turn_result.runtime,
    turn_result.front_state,
    dispatch=turn_result.dispatch,
    suggestions=turn_result.suggestions,
    outcome="success" if entry.result == "success" else "failure",
)
```

This means roll success/failure controls response color. The stored action still follows current engine rules.

- [ ] **Step 4: Run focused roll tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_roll.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server/src/game/runtime/roll.py server/tests/game/runtime/test_graph_roll.py
git commit -m "feat: continue actions after pending rolls"
```

## Task 6: Update Client Stream Parser And Temporary Narration Outcome

**Files:**
- Modify: `client/services/api.ts`
- Modify: `client/services/wire.ts`
- Modify: `client/logic/game/requestRunner.ts`
- Modify: `client/logic/game/__tests__/requestRunner.test.ts`
- Modify: `client/services/__tests__/api.test.ts`

- [ ] **Step 1: Update service API stream tests**

In `client/services/__tests__/api.test.ts`, change stream fixture lines from:

```ts
JSON.stringify({ type: 'delta', text: '검이 ' }),
JSON.stringify({ type: 'delta', text: '허공을 가릅니다.' }),
JSON.stringify({ type: 'final', payload: response }),
```

to:

```ts
JSON.stringify({ type: 'result', payload: { ...response, outcome: 'success' } }),
JSON.stringify({ type: 'narration_delta', text: '검이 ' }),
JSON.stringify({ type: 'narration_delta', text: '허공을 가릅니다.' }),
JSON.stringify({ type: 'final', payload: { ...response, outcome: 'success' } }),
```

Assert:

```ts
expect(onNarrationDelta).toHaveBeenCalledWith('검이 ', 'success');
expect(onNarrationDelta).toHaveBeenCalledWith('허공을 가릅니다.', 'success');
expect(result.outcome).toBe('success');
```

- [ ] **Step 2: Change callback types**

In `client/services/api.ts`, change:

```ts
onNarrationDelta?: (text: string) => void;
```

to:

```ts
onNarrationDelta?: (text: string, outcome: GraphResultOutcome) => void;
```

Import `GraphResultOutcome` from `@/services/wire`.

Change stream event type:

```ts
type GraphInputStreamEvent =
  | { type: 'result'; payload?: unknown }
  | { type: 'narration_delta'; text?: unknown }
  | { type: 'final'; payload?: unknown }
  | { type: 'error'; status?: unknown; message?: unknown };
```

Inside `readGraphActionStream`, track:

```ts
let resultOutcome: GraphResultOutcome = 'neutral';
```

On `result`:

```ts
if (event.type === 'result') {
  const payload = event.payload as GraphActionResponse;
  resultOutcome = payload.outcome ?? 'neutral';
  return;
}
```

On `narration_delta`:

```ts
if (event.type === 'narration_delta') {
  if (typeof event.text === 'string' && event.text) {
    options.onNarrationDelta?.(event.text, resultOutcome);
  }
  return;
}
```

- [ ] **Step 3: Update request runner callback and temporary log type**

In `client/logic/game/requestRunner.ts`, change:

```ts
onNarrationDelta: (text: string) => void;
```

to:

```ts
onNarrationDelta: (text: string, outcome: GraphResultOutcome) => void;
```

Import `GraphResultOutcome`.

Change `appendStreamingNarration` signature:

```ts
function appendStreamingNarration(
  runtime: GraphActionRequestRuntime,
  generation: number,
  optimisticEntryCount: number,
  text: string,
  outcome: GraphResultOutcome,
): void
```

When merging the temporary GM entry, include outcome once the log type supports it:

```ts
return mergeEntry(current, {
  id,
  kind: 'gm',
  text: `${existing?.kind === 'gm' ? existing.text : ''}${text}`,
  outcome,
});
```

Update `client/logic/log/types.ts` to keep log outcome local to the log layer:

```ts
export type LogOutcome = 'success' | 'failure' | 'neutral';
export type RollResult = 'success' | 'fail';

export type LogEntry =
  | { id: number; kind: 'gm'; text: string; outcome?: LogOutcome }
  // keep the existing player, system, and roll variants unchanged
```

`GraphResultOutcome` and `LogOutcome` intentionally share the same literal values, so `requestRunner` can pass the API outcome into the log entry without a converter.

- [ ] **Step 4: Update request runner tests**

In `client/logic/game/__tests__/requestRunner.test.ts`, update the fake graph action call to call:

```ts
events.onNarrationDelta('공격이 ', 'success');
events.onNarrationDelta('적중합니다.', 'success');
```

Assert the temporary GM log entry has:

```ts
expect(logEntry).toMatchObject({
  kind: 'gm',
  text: '공격이 적중합니다.',
  outcome: 'success',
});
```

- [ ] **Step 5: Run client tests**

From `client/`, run:

```powershell
npm test -- --runInBand services/__tests__/api.test.ts logic/game/__tests__/requestRunner.test.ts
npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add client/services/api.ts client/services/wire.ts client/logic/game/requestRunner.ts client/logic/game/__tests__/requestRunner.test.ts client/services/__tests__/api.test.ts client/logic/log/types.ts
git commit -m "feat(client): handle result-first graph streams"
```

## Task 7: Render Narration Outcome Color

**Files:**
- Modify: `client/components/log/LogItem.tsx`
- Modify: `client/components/log/__tests__/LogItem.test.ts`
- Modify: `client/design/tokens.js` only if current tone classes cannot express success/failure.

- [ ] **Step 1: Add source-level test for GM outcome styling**

In `client/components/log/__tests__/LogItem.test.ts`, add:

```ts
describe('LogItem gm outcome styling', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'LogItem.tsx'), 'utf8');

  test('uses gm outcome to pick success and failure colors', () => {
    expect(source).toContain('entry.outcome');
    expect(source).toContain('text-success-fg');
    expect(source).toContain('text-danger-fg');
  });
});
```

- [ ] **Step 2: Implement outcome color in `LogItem.tsx`**

In `client/components/log/LogItem.tsx`, add a helper:

```ts
function gmTextClass(entry: Extract<LogEntry, { kind: 'gm' }>): string {
  if (entry.outcome === 'success') return 'text-success-fg';
  if (entry.outcome === 'failure') return 'text-danger-fg';
  return 'text-fg-default';
}
```

Use it on the GM narration text `Text` element:

```tsx
<Text className={`font-serif text-body leading-body ${gmTextClass(entry)}`}>
  {entry.text}
</Text>
```

Keep non-GM log styling unchanged.

- [ ] **Step 3: Run log tests**

From `client/`, run:

```powershell
npm test -- --runInBand components/log/__tests__/LogItem.test.ts
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add client/components/log/LogItem.tsx client/components/log/__tests__/LogItem.test.ts
git commit -m "feat(client): color narration by outcome"
```

## Task 8: Full Verification

**Files:**
- No code edits expected.

- [ ] **Step 1: Run full server tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server\tests -q
```

Expected: PASS.

- [ ] **Step 2: Run server lint for touched areas**

Run:

```powershell
.\.venv\Scripts\ruff.exe check server
```

Expected: PASS.

- [ ] **Step 3: Run client checks**

From `client/`, run:

```powershell
npm run lint
npx tsc --noEmit
npm test -- --runInBand
```

Expected: PASS.

- [ ] **Step 4: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree and branch ahead by implementation commits.
