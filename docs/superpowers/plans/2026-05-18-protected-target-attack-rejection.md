# Protected Target Attack Rejection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize target field naming to `target`, then complete the first theory-driven gameplay slice: attacks against `protected=true` targets are visibly blocked, preserve fiction continuity, preserve player agency, and have focused evidence.

**Architecture:** First remove the legacy target-id public/data-contract name across client, API, LLM classify intents, combat traces, memory payloads, and tests so the system has one target field. Then keep the existing classify -> runtime -> graph_narrate flow and add a narrow optional `target` to classifier refusal metadata so protected-target refusals can still carry the in-fiction target into rejection narration.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, FastAPI server runtime, graph-native game state, Korean locale TOML prompts/catalogs.

---

## Required Reading

Before touching code, read:

- `docs/research/THEORY.md`
- `docs/superpowers/specs/2026-05-18-theory-driven-runtime-improvement-design.md`
- `server/AGENTS.md`

Do not read `THEORY_LOOP.md` for this implementation slice unless you are changing the theory itself.

## Slice Acceptance Check

ExposedTransitionValidity:
The protected target remains visible but not attackable. The public rejection says the target is protected, the attack cannot proceed now, and a different approach such as talking or observing is available.

FictionContinuity:
The target remains in the scene and remains protected. Rejection narration receives the target view and must not imply the target was hit, injured, killed, moved, or newly hostile.

AgencyContinuity:
The player's attack attempt is preserved as the player input and as an action-rejected event. The output should leave grounded next choices open instead of silently ignoring the attack.

Evidence:
Focused pytest coverage must prove context affordances, classifier refusal target preservation, runtime rejection payload, public reason text, and fallback log text.

## File Structure

Modify:

- `client/services/wire.ts`
  - Rename combat command legacy target fields to `target`.
- `client/logic/combat/actions.ts`
  - Emit `target` in combat command payloads.
- `server/src/api/schema.py`
  - Rename `GraphCombatCommandRequest` legacy target field to `target`.
- `server/src/game/domain/combat.py`
  - Rename combat trace/action legacy target fields to `target`.
- `server/src/game/domain/memory.py`
  - Rename memory/dialogue legacy target fields to `target`.
- `server/src/llm/calls/classify/action_builder.py`
  - Read classify intent targets from `target`.
- `server/src/locale/prompts/_kernel.ko.md`
  - Document `target` as the target id field.
- `server/src/locale/prompts/classify/prompt.ko.md`
  - Replace classify intent contract and examples with `target`.
- Runtime and engine modules that consume combat trace, combat command, memory,
  narration, or classify target fields.
- `server/src/game/domain/action.py`
  - Add optional `target` to `RefuseReason`.
- `server/src/llm/calls/classify/shortcuts.py`
  - Populate `RefuseReason.target` for protected target attack refusals.
- `server/src/game/runtime/flow/input.py`
  - Pass `output.refuse.target` into refused-input handling.
  - Build the rejection narration action with `to=target` when present.
- `server/src/locale/catalog/log.toml`
  - Strengthen `log.error.protected_target` in Korean and English.
- `server/src/locale/prompts/graph_narrate/prompt.ko.md`
  - Make action-rejected target handling explicit.

Test:

- `server/tests/game/domain/test_action_contract.py`
- `server/tests/llm/calls/test_classify_in_combat_plumbing.py`
- `server/tests/game/runtime/test_graph_input.py`
- Existing coverage in `server/tests/llm/context/test_classify_view.py`
- Existing coverage in `server/tests/llm/calls/test_classify_grounding.py`

No new files are needed.

## Task 0: Normalize Target Field Contract

**Files:**

- Modify: `client/services/wire.ts`
- Modify: `client/logic/combat/actions.ts`
- Modify: `client/logic/combat/__tests__/actions.test.ts`
- Modify: `client/services/__tests__/api.test.ts`
- Modify: `server/src/api/schema.py`
- Modify: `server/src/game/domain/combat.py`
- Modify: `server/src/game/domain/memory.py`
- Modify: `server/src/llm/calls/classify/action_builder.py`
- Modify: `server/src/locale/prompts/_kernel.ko.md`
- Modify: `server/src/locale/prompts/classify/prompt.ko.md`
- Modify: runtime, engine, narration, and tests found by searching for the legacy target-id spelling.

- [ ] **Step 1: Write failing contract tests for `target`**

Update existing tests so new public/data contracts use `target` only:

```python
# server/tests/llm/calls/test_classify_action_builder.py
output = build_action_output(
    {"intents": [{"intent": "attack", "target": "goblin_01"}]},
    _surroundings(),
)
assert output.actions is not None
assert output.actions[0].what == ["goblin_01"]
```

```python
# server/tests/game/runtime/test_combat_command.py
action = build_combat_command_action(
    _runtime(),
    {"command": "precise", "target": "enemy_01"},
)
assert action.what == "enemy_01"
```

```typescript
// client/logic/combat/__tests__/actions.test.ts
expect(action.combatCommand).toEqual({
  command: 'precise',
  target: 'enemy_01',
});
```

Also update `server/tests/llm/calls/test_classify_prompt.py` so it asserts:

```python
assert '"intent":"use","skill_id":"minor_heal_01","target":"player_01"' in text
old_target_field = "target" + "_id"
assert old_target_field not in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/llm/calls/test_classify_action_builder.py server/tests/game/runtime/test_combat_command.py server/tests/llm/calls/test_classify_prompt.py -q
```

From `client/` run:

```powershell
npm test -- --runInBand logic/combat/__tests__/actions.test.ts services/__tests__/api.test.ts
```

Expected:

- Server tests fail where code still expects the legacy target field.
- Client tests fail where payloads still emit the legacy target field.

- [ ] **Step 3: Rename the contract mechanically**

Apply a repo-scoped mechanical rename for this contract:

```powershell
$paths = @('server','client','agency','docs/superpowers')
$legacyTargetField = 'target' + '_id'
Get-ChildItem -Path $paths -Recurse -File |
  Where-Object { $_.FullName -notmatch '\\node_modules\\|\\.pytest_cache\\|\\__pycache__\\' } |
  ForEach-Object {
    $path = $_.FullName
    $text = Get-Content -Raw -LiteralPath $path
    if ($text -match $legacyTargetField) {
      $new = $text -replace $legacyTargetField, 'target'
      if ($new -ne $text) { Set-Content -LiteralPath $path -Value $new -NoNewline }
    }
  }
```

Then inspect the diff before continuing:

```powershell
git diff --stat
rg -n $legacyTargetField server client agency docs/superpowers -S
```

Expected:

- The search returns no legacy target-field hits under those paths.
- The diff is a mechanical field rename, not unrelated cleanup.

- [ ] **Step 4: Fix compile/runtime fallout from the rename**

Follow test failures only. Typical expected fixes:

- `GraphCombatTraceEvent.target`
- `GraphCombatAction.target`
- `GraphCombatCommandRequest.target`
- `DialoguePair.target`
- `Memory.target`
- `narrate_recent_dialogue_payload(..., target=...)`
- prompt examples using `"target"`
- TypeScript `CombatCommand` union members with `target`

Do not add compatibility aliases for the legacy target field. The point of this slice is to
remove the double contract.

- [ ] **Step 5: Verify no old target contract remains**

Run:

```powershell
rg -n $legacyTargetField server client agency docs/superpowers -S
```

Expected: no output.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/llm/calls/test_classify_action_builder.py server/tests/game/runtime/test_combat_command.py server/tests/llm/calls/test_classify_prompt.py server/tests/game/runtime/test_memory_context.py server/tests/game/runtime/test_combat_narration_view.py -q
```

From `client/` run:

```powershell
npm test -- --runInBand logic/combat/__tests__/actions.test.ts services/__tests__/api.test.ts
```

Expected: all selected tests pass.

## Task 1: Preserve Protected Refusal Target

**Files:**

- Modify: `server/tests/game/domain/test_action_contract.py`
- Modify: `server/tests/llm/calls/test_classify_in_combat_plumbing.py`
- Modify: `server/src/game/domain/action.py`
- Modify: `server/src/llm/calls/classify/shortcuts.py`

- [ ] **Step 1: Add failing domain and classify shortcut tests**

In `server/tests/game/domain/test_action_contract.py`, update `test_action_output_refuse_only` to assert optional target metadata:

```python
def test_action_output_refuse_only():
    out = ActionOutput(
        refuse={
            "category": "out_of_game",
            "message_hint": "범위 밖",
            "target": "npc_01",
        }
    )
    assert out.actions is None
    assert out.refuse is not None
    assert out.refuse.target == "npc_01"
```

In `server/tests/llm/calls/test_classify_in_combat_plumbing.py`, add this constant near the imports:

```python
PROTECTED_TARGET_REASON = (
    "보호받는 대상이라 지금은 공격할 수 없습니다. "
    "대화하거나 주변을 살피면 다른 방법을 찾을 수 있습니다."
)
```

Then update both protected shortcut tests:

```python
    assert out.refuse.message_hint == PROTECTED_TARGET_REASON
    assert out.refuse.target == "protected_guard"
```

Apply that replacement in:

- `test_protected_target_attack_shortcut_returns_refusal`
- `test_single_protected_target_attack_shortcut_returns_refusal_without_name`

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/domain/test_action_contract.py::test_action_output_refuse_only server/tests/llm/calls/test_classify_in_combat_plumbing.py::test_protected_target_attack_shortcut_returns_refusal server/tests/llm/calls/test_classify_in_combat_plumbing.py::test_single_protected_target_attack_shortcut_returns_refusal_without_name -q
```

Expected:

- `test_action_output_refuse_only` fails because `target` is forbidden or absent.
- The two classify shortcut tests fail because the message is still `"그 대상은 공격할 수 없습니다."` and `target` is absent.

- [ ] **Step 3: Add `target` to `RefuseReason`**

In `server/src/game/domain/action.py`, change `RefuseReason` to:

```python
class RefuseReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RefuseCategory
    message_hint: str = Field(min_length=1, max_length=120)
    target: str | None = Field(default=None, min_length=1)
```

- [ ] **Step 4: Populate target metadata in protected shortcut**

In `server/src/llm/calls/classify/shortcuts.py`, update `_protected_attack_refusal` return block to:

```python
    return ActionOutput(
        refuse=RefuseReason(
            category="meta_breaking",
            message_hint=render("log.error.protected_target", locale),
            target=target["id"],
        )
    )
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/domain/test_action_contract.py::test_action_output_refuse_only server/tests/llm/calls/test_classify_in_combat_plumbing.py::test_protected_target_attack_shortcut_returns_refusal server/tests/llm/calls/test_classify_in_combat_plumbing.py::test_single_protected_target_attack_shortcut_returns_refusal_without_name -q
```

Expected:

- The domain test passes.
- The two classify tests still fail until Task 2 updates the localized public reason.

## Task 2: Strengthen Public Protected Reason

**Files:**

- Modify: `server/src/locale/catalog/log.toml`
- Modify: `server/tests/llm/calls/test_classify_in_combat_plumbing.py`
- Modify: `server/tests/game/runtime/test_graph_input.py`

- [ ] **Step 1: Update failing runtime expectation**

In `server/tests/game/runtime/test_graph_input.py`, add this constant near the imports or near `_FakeLLM`:

```python
PROTECTED_TARGET_REASON = (
    "보호받는 대상이라 지금은 공격할 수 없습니다. "
    "대화하거나 주변을 살피면 다른 방법을 찾을 수 있습니다."
)
```

In `test_graph_input_protected_target_attack_is_clear_rejection`, replace:

```python
    assert logs[-1].text == "그 대상은 공격할 수 없습니다."
```

with:

```python
    assert logs[-1].text == PROTECTED_TARGET_REASON
    assert "보호받는 대상" in logs[-1].text
    assert "대화하거나 주변을 살피면" in logs[-1].text
```

Keep these existing assertions:

```python
    assert result.status == "rejected"
    assert "공격" in logs[-1].text
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert logs[0].text == "goblin_01을 공격한다"
```

- [ ] **Step 2: Run focused tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/llm/calls/test_classify_in_combat_plumbing.py::test_protected_target_attack_shortcut_returns_refusal server/tests/llm/calls/test_classify_in_combat_plumbing.py::test_single_protected_target_attack_shortcut_returns_refusal_without_name server/tests/game/runtime/test_graph_input.py::test_graph_input_protected_target_attack_is_clear_rejection -q
```

Expected:

- All failures point to the old protected-target localized text.

- [ ] **Step 3: Update localized protected target reason**

In `server/src/locale/catalog/log.toml`, replace:

```toml
[log."error.protected_target"]
ko = "그 대상은 공격할 수 없습니다."
en = "That target cannot be attacked."
```

with:

```toml
[log."error.protected_target"]
ko = "보호받는 대상이라 지금은 공격할 수 없습니다. 대화하거나 주변을 살피면 다른 방법을 찾을 수 있습니다."
en = "That target is protected and cannot be attacked right now. Talk or look around to find another approach."
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/llm/calls/test_classify_in_combat_plumbing.py::test_protected_target_attack_shortcut_returns_refusal server/tests/llm/calls/test_classify_in_combat_plumbing.py::test_single_protected_target_attack_shortcut_returns_refusal_without_name server/tests/game/runtime/test_graph_input.py::test_graph_input_protected_target_attack_is_clear_rejection -q
```

Expected: all three tests pass.

## Task 3: Preserve Target in Rejection Narration Payload

**Files:**

- Modify: `server/tests/game/runtime/test_graph_input.py`
- Modify: `server/src/game/runtime/flow/input.py`
- Modify: `server/src/locale/prompts/graph_narrate/prompt.ko.md`

- [ ] **Step 1: Add failing payload assertions**

In `server/tests/game/runtime/test_graph_input.py`, extend `test_graph_input_protected_target_attack_is_clear_rejection` after `logs = await repo.load_log_entries("game-1")`:

```python
    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    payload = json.loads(narrate_call["messages"][1]["content"])
```

Then add these assertions after the existing log assertions:

```python
    assert payload["player_input"] == "goblin_01을 공격한다"
    assert payload["current_event"]["kind"] == "action_rejected"
    assert payload["current_event"]["outcome"] == "action_rejected"
    assert payload["current_event"]["resolved_results"] == [PROTECTED_TARGET_REASON]
    assert payload["result_cards"] == [{"text": PROTECTED_TARGET_REASON}]
    assert payload["target_view"]["id"] == "goblin_01"
    assert payload["current_event"]["target"]["id"] == "goblin_01"
    assert payload["current_event"]["action"] == {
        "verb": "pass",
        "to": "goblin_01",
    }
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_graph_input.py::test_graph_input_protected_target_attack_is_clear_rejection -q
```

Expected:

- The test fails because `target_view` is missing or `None`.
- The action is currently `{"verb": "pass"}` without `"to": "goblin_01"`.

- [ ] **Step 3: Pass refusal target through runtime**

In `server/src/game/runtime/flow/input.py`, update the two call sites that handle `output.refuse`.

In `run_graph_input_turn`, replace:

```python
        return await _run_graph_refused_input(
            client,
            repo,
            runtime,
            player_input,
            output.refuse.message_hint,
        )
```

with:

```python
        return await _run_graph_refused_input(
            client,
            repo,
            runtime,
            player_input,
            output.refuse.message_hint,
            target=output.refuse.target,
        )
```

In `run_graph_input_turn_stream`, replace:

```python
        async for event in _run_graph_refused_input_stream(
            client,
            repo,
            runtime,
            player_input,
            output.refuse.message_hint,
        ):
```

with:

```python
        async for event in _run_graph_refused_input_stream(
            client,
            repo,
            runtime,
            player_input,
            output.refuse.message_hint,
            target=output.refuse.target,
        ):
```

- [ ] **Step 4: Add target parameters to refused helpers**

In `server/src/game/runtime/flow/input.py`, change `_run_graph_refused_input` signature and action construction to:

```python
async def _run_graph_refused_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    public_reason: str,
    *,
    target: str | None = None,
) -> GraphActionRequestResult:
    action = Action(verb="pass", to=target)
    engine_diag("input:refused", reason=public_reason)
    return await _run_graph_rejected_reason_input(
        client,
        repo,
        runtime,
        player_input,
        action,
        public_reason,
    )
```

Change `_run_graph_refused_input_stream` signature and action construction to:

```python
async def _run_graph_refused_input_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    public_reason: str,
    *,
    target: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    action = Action(verb="pass", to=target)
    engine_diag("input:refused", reason=public_reason)
    async for event in _run_graph_rejected_reason_input_stream(
        client,
        repo,
        runtime,
        player_input,
        action,
        public_reason,
    ):
        yield event
```

- [ ] **Step 5: Make rejection prompt target handling explicit**

In `server/src/locale/prompts/graph_narrate/prompt.ko.md`, under `## 행동 거부`, after:

```markdown
`payload.current_event.outcome`이 `action_rejected`이면 행동이 자연스럽게 멈추는 장면만 씁니다.
```

add:

```markdown
`payload.target_view`나 `payload.current_event.target`이 있으면 그 대상에게 시도한 행동이 막힌 것으로 씁니다. 공격, 강제 제압, 탈취 같은 행동이 거부된 경우 성공, 부상, 사망, 관계 악화를 만들지 말고, 제약 때문에 멈춘 장면과 다른 접근 여지만 남깁니다.
```

- [ ] **Step 6: Run focused runtime test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_graph_input.py::test_graph_input_protected_target_attack_is_clear_rejection -q
```

Expected: the test passes.

## Task 4: Verify Existing Grounding and Context Evidence

**Files:**

- Read-only verification for:
  - `server/tests/llm/context/test_classify_view.py`
  - `server/tests/llm/calls/test_classify_grounding.py`

- [ ] **Step 1: Run classify context protected candidate test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/llm/context/test_classify_view.py::test_classify_context_exposes_transfer_and_protected_candidates -q
```

Expected: pass.

This verifies:

- protected target appears in `identity.visible_targets`
- protected target keeps `"protected": True`
- protected target is excluded from `affordances.can_attack`

- [ ] **Step 2: Run grounding protected rejection test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/llm/calls/test_classify_grounding.py::test_attack_rejects_protected_visible_target -q
```

Expected: pass.

This verifies:

- even if an attack action names a protected visible target, grounding rejects it
- the lower-level transition guard remains intact

## Task 5: Run Slice Verification Set

**Files:**

- All modified files from Tasks 1-3.

- [ ] **Step 1: Run focused slice tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/game/domain/test_action_contract.py::test_action_output_refuse_only server/tests/llm/calls/test_classify_in_combat_plumbing.py::test_protected_target_attack_shortcut_returns_refusal server/tests/llm/calls/test_classify_in_combat_plumbing.py::test_single_protected_target_attack_shortcut_returns_refusal_without_name server/tests/llm/context/test_classify_view.py::test_classify_context_exposes_transfer_and_protected_candidates server/tests/llm/calls/test_classify_grounding.py::test_attack_rejects_protected_visible_target server/tests/game/runtime/test_graph_input.py::test_graph_input_protected_target_attack_is_clear_rejection -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run nearby classify/runtime tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/llm/calls/test_classify_in_combat_plumbing.py server/tests/game/runtime/test_graph_input.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run lint for touched server code**

Run:

```powershell
.\.venv\Scripts\ruff.exe check server/src/game/domain/action.py server/src/game/domain/combat.py server/src/game/domain/memory.py server/src/api/schema.py server/src/llm/calls/classify/action_builder.py server/src/llm/calls/classify/shortcuts.py server/src/game/runtime/flow/input.py server/src/game/runtime/action/combat_command.py server/tests/game/domain/test_action_contract.py server/tests/llm/calls/test_classify_action_builder.py server/tests/llm/calls/test_classify_in_combat_plumbing.py server/tests/game/runtime/test_graph_input.py server/tests/game/runtime/test_combat_command.py
```

Expected: no lint errors.

- [ ] **Step 4: Record slice completion check in final response**

Use this exact structure in the implementation final response:

```text
ExposedTransitionValidity: protected targets remain visible, are excluded from can_attack, and produce a public protection reason with a repair path.
FictionContinuity: rejection narration receives the protected target view and does not receive state changes implying a hit or injury.
AgencyContinuity: the player's attack input is preserved, the rejection is explicit, and the reason leaves talk/observe alternatives open.
Evidence: list the exact pytest and ruff commands run.
```

## Task 6: Commit the Slice

**Files:**

- Stage only the files changed by this slice.

- [ ] **Step 1: Check worktree state**

Run:

```powershell
git status --short
```

Expected:

- Existing unrelated changes such as `AGENTS.md`, `THEORY_LOOP.md`, and `docs/research/` may still be present.
- Only slice files should be staged in the next step.

- [ ] **Step 2: Stage slice files**

Run:

```powershell
git add -- client/logic/combat/__tests__/actions.test.ts client/logic/combat/actions.ts client/services/__tests__/api.test.ts client/services/wire.ts server/src/api/schema.py server/src/game/domain/action.py server/src/game/domain/combat.py server/src/game/domain/memory.py server/src/llm/calls/classify/action_builder.py server/src/llm/calls/classify/shortcuts.py server/src/game/runtime/flow/input.py server/src/game/runtime/action/combat_command.py server/src/locale/catalog/log.toml server/src/locale/prompts/_kernel.ko.md server/src/locale/prompts/classify/prompt.ko.md server/src/locale/prompts/graph_narrate/prompt.ko.md server/tests/game/domain/test_action_contract.py server/tests/game/runtime/test_combat_command.py server/tests/llm/calls/test_classify_action_builder.py server/tests/llm/calls/test_classify_in_combat_plumbing.py server/tests/llm/calls/test_classify_prompt.py server/tests/game/runtime/test_graph_input.py
```

- [ ] **Step 3: Commit**

Run:

```powershell
git commit -m "Improve protected target attack rejection"
```

Expected: commit succeeds.

## Self-Review

Spec coverage:

- ExposedTransitionValidity is covered by context, grounding, public reason, and runtime rejection tests.
- FictionContinuity is covered by target preservation into `target_view` and prompt instruction forbidding invented attack success.
- AgencyContinuity is covered by player input preservation and a public reason with alternate approaches.
- Evidence is covered by the focused pytest and ruff commands in Task 5.

Placeholder scan:

- This plan contains no forbidden placeholder markers or unspecified test-writing steps.

Type consistency:

- `RefuseReason.target` is optional and defaults to `None`, so existing refusal outputs remain valid.
- Runtime passes `target` only through refused-input paths.
- Rejection narration still receives an `Action`; it is `pass` with optional `to`, which keeps existing action validation untouched.
