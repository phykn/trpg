# Mobile Smoke Function And Fun Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `dev_test` mobile smoke path reliable while making early combat, quest, and reward feedback feel responsive enough to invite another turn.

**Architecture:** Keep server state authoritative. Add deterministic classifier shortcuts only for visible, grounded Korean actions; keep LLM classification as the fallback. Improve play feel through existing action cards, combat narration payloads, and client panels instead of adding a new UX layer.

**Tech Stack:** Python 3.12, FastAPI graph runtime, Pydantic v2, pytest, Expo React Native, Jest.

---

## File Structure

- `server/src/llm/context/classify_view.py` exposes location items alongside visible targets, inventory, skills, and quests.
- `server/src/llm/calls/classify/shortcuts.py` owns deterministic Korean shortcuts for visible attacks, skill attacks, pickup, and combat flee.
- `server/src/llm/calls/classify/grounding.py` validates that location-item pickup is grounded in the current location and player.
- `server/src/game/runtime/cards.py` improves concise action-result cards for combat, quest abandon, flee, and pickup.
- `server/src/game/runtime/combat.py` and `server/src/game/engines/graph_combat.py` remain the combat source of truth; only patch if tests show MP spend or terminal state is not actually applied.
- `client/screens/play/Playing.tsx` must show active quest and quest offer as distinct slots when both exist.
- `client/components/composer/LevelUpPrompt.tsx` adds stable mobile selectors and keeps hit targets usable.
- Tests live next to the existing test buckets under `server/tests/...` and `client/.../__tests__/`.

## Success Criteria

- Natural Korean attacks on visible enemies produce `confirmation_required` before combat starts.
- `훈련 일격으로 훈련용 허수아비를 공격한다` keeps `with="training_strike"` through confirmation and spends MP after confirm.
- `보급 표식을 획득한다` transfers `supply_token` from the current location to the player inventory without opening a roll.
- Quest abandon clears the active quest panel; a re-offered pending quest must appear as an offer, not as an active quest with `포기`.
- Golem combat persists after confirm, and combat flee clears `graph_combat_state`.
- Level-up stat buttons and confirm button can be selected reliably by accessibility label or `testID`.
- Logs/cards name concrete state changes: MP spend, victory/flee, quest abandon, pickup.

---

### Task 1: Deterministic Action Classification

**Files:**
- Modify: `server/src/llm/context/classify_view.py`
- Modify: `server/src/llm/calls/classify/grounding.py`
- Modify: `server/src/llm/calls/classify/runner.py`
- Create: `server/src/llm/calls/classify/shortcuts.py`
- Modify: `server/src/locale/prompts/classify/prompt.ko.md`
- Test: `server/tests/llm/calls/test_classify_action_shortcuts.py`
- Test: `server/tests/llm/calls/test_classify_grounding.py`
- Test: `server/tests/llm/context/test_classify_view.py`

- [ ] **Step 1: Write failing tests**

Cover attack, skill attack, pickup, and combat flee without calling the LLM:

```python
output = await classify(
    _NoCallLLM(),
    ClassifyInput(
        player_input="훈련 일격으로 훈련용 허수아비를 공격한다",
        context=_context(),
    ),
    locale="ko",
)
assert output.actions[0].verb == "attack"
assert output.actions[0].what == ["training_dummy"]
assert output.actions[0].with_ == "training_strike"
```

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/llm/calls/test_classify_action_shortcuts.py -q
```

Expected before implementation: failures because the LLM is called or `location_items` is missing.

- [ ] **Step 2: Expose grounded location items**

Add `location_items` and `can_pick_up` to the classify context, using `items_at(runtime.graph_index, location_id)` and the existing `_item_payload`.

- [ ] **Step 3: Add shortcut module**

Implement `classify_action_shortcut(player_input, grounding_view)` with these rules:

```python
if in_combat and input has 도망/도주:
    return move(how="hasty")
if input has 공격 and a visible enemy name:
    return attack(what=[enemy_id], with_=matching_skill_id_or_none)
if input has 획득/줍/챙 and a location item name:
    return transfer(what=item_id, from_=location_id, to=player_id, how="gift")
```

Only match names already present in grounding view. Return `None` when ambiguous.

- [ ] **Step 4: Wire shortcut before LLM fallback**

In `classify.runner`, call `classify_action_shortcut` after guard and before dialogue shortcut.

- [ ] **Step 5: Verify focused tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/llm/calls/test_classify_action_shortcuts.py server/tests/llm/context/test_classify_view.py::test_classify_context_exposes_items_at_current_location server/tests/llm/calls/test_classify_grounding.py::test_transfer_accepts_current_location_item_pickup -q
```

Expected after implementation: all pass.

---

### Task 2: Server Flow Regressions

**Files:**
- Modify if needed: `server/src/game/runtime/combat.py`
- Modify if needed: `server/src/game/engines/graph_combat.py`
- Modify: `server/src/game/runtime/cards.py`
- Test: `server/tests/game/runtime/test_graph_input.py`
- Test: `server/tests/game/runtime/test_graph_confirmation.py`
- Test: `server/tests/game/runtime/test_graph_combat_dispatch.py`

- [ ] **Step 1: Add end-to-end runtime tests**

Use a fake classifier payload or the shortcut path to prove:

```python
result = await run_graph_input_turn(
    llm,
    repo,
    "game-1",
    "훈련 일격으로 훈련용 허수아비를 공격한다",
)
assert result.status == "confirmation_required"
```

Then confirm and assert MP, outcome, and combat state:

```python
result = await run_graph_confirm(repo, "game-1", pending["id"], "confirm")
assert result.status == "executed"
assert result.runtime.graph.nodes["player_01"].properties["mp"] == expected_mp
assert result.runtime.progress.graph_combat_state is None
```

- [ ] **Step 2: Verify golem persistence and flee**

Add tests that confirm a high-HP enemy keeps `graph_combat_state` after the first confirmed attack, and `Action(verb="move", how="hasty")` clears it with outcome `fled`.

- [ ] **Step 3: Improve action cards for feel**

In `cards.py`, make cards concrete:

- pickup: “당신은 보급 표식을 챙깁니다.”
- skill combat start/exchange: mention skill name and MP cost when available.
- flee: “당신은 전투에서 물러납니다.”
- quest abandon: “당신은 훈련 전투를 포기합니다.”

Do not add long prose; the LLM narration remains optional flavor.

- [ ] **Step 4: Verify tests**

Run:

```powershell
.\.venv\Scripts\python -m pytest server/tests/game/runtime/test_graph_input.py server/tests/game/runtime/test_graph_confirmation.py server/tests/game/runtime/test_graph_combat_dispatch.py -q
```

Expected: all pass.

---

### Task 3: Quest Panel And Level-Up Mobile Controls

**Files:**
- Modify: `client/screens/play/Playing.tsx`
- Modify: `client/components/composer/LevelUpPrompt.tsx`
- Modify or add: `client/screens/play/__tests__/Playing.test.ts`
- Modify or add: `client/components/composer/__tests__/LevelUpPrompt.test.tsx`
- Modify: `client/logic/info-panel/panels.ts` only if the screen composition should reuse the existing slot builder.

- [ ] **Step 1: Write client tests**

Quest display test expectation:

```ts
expect(slots.map((slot) => slot.id)).toContain('quest');
expect(slots.map((slot) => slot.id)).toContain('quest_offer');
```

Level-up selector expectation:

```tsx
getByTestId('level-stat-body').props.onClick?.();
getByTestId('level-confirm').props.onClick?.();
expect(onCommit).toHaveBeenCalledWith('body');
```

- [ ] **Step 2: Split quest slots in Playing**

Replace `buildQuestSlot(quest ?? questOffers[0] ?? null)` with the existing `buildPanelSlots` helper or equivalent logic so active quest and first offer have different slot ids.

- [ ] **Step 3: Add stable test IDs**

Add these props in `LevelUpPrompt`:

- `testID={`level-stat-${k}`}` on stat buttons
- `testID="level-cancel"` on cancel
- `testID="level-confirm"` on confirm

Keep existing Korean accessibility labels.

- [ ] **Step 4: Verify client tests**

Run:

```powershell
npm test -- --runInBand components/composer/__tests__/LevelUpPrompt.test.tsx screens/play/__tests__/Playing.test.ts
```

Expected: all pass.

---

### Task 4: Smoke-Level Verification

**Files:**
- No production changes unless verification exposes a new root cause.
- Optional update: `report_mobile-smoke.md` only if the user asks for a refreshed report.

- [ ] **Step 1: Run server focused suite**

```powershell
.\.venv\Scripts\python -m pytest server/tests/llm/calls/test_classify_action_shortcuts.py server/tests/llm/context/test_classify_view.py server/tests/llm/calls/test_classify_grounding.py server/tests/game/runtime/test_graph_input.py server/tests/game/runtime/test_graph_confirmation.py server/tests/game/runtime/test_graph_combat_dispatch.py -q
```

- [ ] **Step 2: Run client focused suite**

```powershell
cd client
npm test -- --runInBand
```

- [ ] **Step 3: Manual or Playwright smoke**

Use the existing dev server setup from `tester.md` and verify these states:

- Attack input opens server confirmation.
- Confirming dummy attack logs MP spend and victory.
- Golem attack leaves combat panel visible.
- Combat `도주` button clears combat.
- Pickup puts `보급 표식` in inventory.
- Abandon hides active quest.
- Level-up stat and confirm controls are clickable on mobile viewport.

Expected: no horizontal scroll and no blocked modal hit targets at mobile width.

## Self-Review

- Spec coverage: the plan covers every failure and partial failure in `report_mobile-smoke.md`, plus the fun notes about combat feedback, state change, and next-action desire.
- Placeholder scan: no unfinished markers remain.
- Type consistency: action fields use existing `Action` keys: `verb`, `what`, `from_`, `to`, `with_`, `how`.
