# Graph-Sliced LLM Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broad log/world payloads with graph-sliced classify and narrate contexts, preserve the player's raw input, pass enough local graph evidence to both LLM calls, hide raw GM narration and internal combat enum values, and restore structured recommendation chips plus compact memory summaries.

**Architecture:** Add explicit context projection builders between `GameRuntimeState` and LLM prompts. `classify` receives a compact action-disambiguation view. `graph_narrate` receives a narration view centered on the current event, target, result cards, related memories, recent dialogue summaries, and a presentation-safe combat view. Suggestions become a backward-compatible structured wire type: old strings still work, new chips render labels and send `input_text`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, existing graph runtime modules under `server/src/game/runtime`, existing OpenAI-compatible LLM adapters, Expo React Native client with TypeScript wire adapters.

---

## Current Problem

`classify` and `graph_narrate` currently receive overlapping context through `build_graph_surroundings`, `important_history_payload`, `recent_dialogue_payload`, and `build_input_narration_payload`. This leaks full location descriptions, raw GM narration, broad inventory and skill lists, raw combat states such as `hurt` or `critical`, and high-importance memories that may be unrelated to the current turn.

The fix is not a larger prompt. The fix is a smaller contract with evidence selected from graph relationships.

## Target Contracts

`classify` gets the action-resolution view:

```json
{
  "player_input": "어제 만난 상인에게 말을 겁니다",
  "mode": "exploration",
  "identity": {
    "location": {"id": "loc_town", "name": "마을 광장"},
    "visible_targets": [{"id": "npc_merchant", "name": "로엔", "type": "npc"}],
    "exits": [{"id": "loc_shop", "name": "잡화점"}],
    "inventory": [{"id": "item_coin", "name": "동화 주머니"}],
    "equipment": [],
    "skills": [{"id": "skill_persuade", "name": "설득"}],
    "active_quest": {"id": "quest_missing", "name": "사라진 장부"}
  },
  "affordances": {
    "can_speak_to": ["npc_merchant"],
    "can_attack": [],
    "can_move_to": ["loc_shop"],
    "can_use": ["item_coin"],
    "can_accept_or_abandon_quest": ["quest_missing"]
  },
  "references": {
    "last_npc": {"id": "npc_merchant", "name": "로엔"},
    "last_target": null,
    "last_item": null,
    "recent_dialogue": [{"turn": 3, "player": "장부를 봤나요?", "summary": "로엔이 장부를 어제 잃어버렸다고 말했습니다."}]
  },
  "budget": {
    "visible_targets_omitted": 0,
    "exits_omitted": 0,
    "inventory_omitted": 0,
    "skills_omitted": 0
  }
}
```

`graph_narrate` gets the prose-generation view:

```json
{
  "player_input": "어제 만난 상인에게 말을 겁니다",
  "current_event": {"kind": "dialogue", "target": {"id": "npc_merchant", "name": "로엔"}, "outcome": "player_addresses_target"},
  "scene_anchor": {"location": {"id": "loc_town", "name": "마을 광장"}, "visible_names": ["로엔", "잡화점"]},
  "target_view": {"id": "npc_merchant", "name": "로엔", "type": "character", "known_role": "상인"},
  "result_cards": [],
  "related_memory": [{"turn": 3, "target": "npc_merchant", "summary": "로엔이 장부를 어제 잃어버렸다고 말했습니다.", "importance": 3}],
  "recent_dialogue": [{"turn": 3, "player": "장부를 봤나요?", "summary": "로엔이 장부를 어제 잃어버렸다고 말했습니다."}],
  "combat_view": null,
  "budget": {
    "visible_names_omitted": 0,
    "related_memory_omitted": 0,
    "recent_dialogue_omitted": 0,
    "result_cards_omitted": 0
  }
}
```

Forbidden by default for both contracts:

- Raw GM narration text from prior turns
- Full location, NPC, item, or world descriptions
- Full important-history lists
- Raw combat enum values such as `critical`, `hurt`, `healthy`, `downed`, `player_attacked`, `enemy_pressed`, `forced_end`
- HP, MP, damage, and other hidden numeric combat traces

## Implementation Tasks

### 1. Add Focused Classify Context

- [ ] Create `server/src/llm/context/classify_view.py`.

  The builder should return a plain JSON-serializable `dict` because the existing LLM call path already passes dict payloads through Pydantic request models. Keep budgets local and visible.

  Use these constants:

  ```python
  MAX_CLASSIFY_VISIBLE_TARGETS = 8
  MAX_CLASSIFY_EXITS = 6
  MAX_CLASSIFY_INVENTORY = 10
  MAX_CLASSIFY_SKILLS = 8
  MAX_CLASSIFY_RECENT_DIALOGUE = 5
  ```

  Public entry point:

  ```python
  def build_classify_context_view(runtime: GameRuntimeState, player_input: str) -> dict[str, Any]:
      place_id = location_of(runtime.graph_index, runtime.progress.player_id)
      location = runtime.graph.nodes.get(place_id or "")
      visible_targets = _visible_targets(runtime)[:MAX_CLASSIFY_VISIBLE_TARGETS]
      exits = _exits(runtime)[:MAX_CLASSIFY_EXITS]
      inventory = _inventory(runtime)[:MAX_CLASSIFY_INVENTORY]
      skills = _skills(runtime)[:MAX_CLASSIFY_SKILLS]
      recent_dialogue = classify_recent_dialogue_payload(runtime, limit=MAX_CLASSIFY_RECENT_DIALOGUE)

      return {
          "player_input": player_input,
          "mode": "combat" if runtime.progress.graph_combat_state is not None else "exploration",
          "identity": {
              "location": _node_ref(location),
              "visible_targets": visible_targets,
              "exits": exits,
              "inventory": inventory,
              "equipment": _equipment(runtime),
              "skills": skills,
              "active_quest": _active_quest(runtime),
          },
          "affordances": {
              "can_speak_to": [target["id"] for target in visible_targets if target["type"] in {"npc", "enemy"}],
              "can_attack": _attackable_ids(runtime, visible_targets),
              "can_move_to": [exit_["id"] for exit_ in exits],
              "can_use": [item["id"] for item in inventory],
              "can_accept_or_abandon_quest": _quest_ids(runtime),
          },
          "references": {
              "last_npc": last_entity_ref(runtime, entity_types={"character"}),
              "last_target": last_entity_ref(runtime),
              "last_item": last_entity_ref(runtime, entity_types={"item"}),
              "recent_dialogue": recent_dialogue,
          },
          "budget": {
              "visible_targets_omitted": max(0, len(_visible_targets(runtime)) - MAX_CLASSIFY_VISIBLE_TARGETS),
              "exits_omitted": max(0, len(_exits(runtime)) - MAX_CLASSIFY_EXITS),
              "inventory_omitted": max(0, len(_inventory(runtime)) - MAX_CLASSIFY_INVENTORY),
              "skills_omitted": max(0, len(_skills(runtime)) - MAX_CLASSIFY_SKILLS),
          },
      }
  ```

  The helper implementation must select graph neighbors from the current player location and player-owned nodes. It must not read `runtime.turn_log` except through the memory helper described in task 3.

- [ ] Modify `server/src/game/runtime/input.py`.

  Replace the classify call payload:

  ```python
  surroundings=build_graph_surroundings(runtime),
  history=important_history_payload(runtime),
  recent_dialogue=recent_dialogue_payload(runtime),
  ```

  with:

  ```python
  context=build_classify_context_view(runtime, player_input),
  ```

  If `ClassifyInput` currently requires `surroundings`, `history`, or `recent_dialogue`, update that request model so `context` is the authoritative field and the removed fields are no longer sent by runtime code.

- [ ] Modify `server/src/llm/calls/classify/schema.py`.

  Replace the current `ClassifyInput` fields with:

  ```python
  class ClassifyInput(BaseModel):
      player_input: str
      context: dict[str, Any]
  ```

- [ ] Modify `server/src/llm/calls/classify/runner.py`.

  The LLM should receive `input_.model_dump_json()` with `context`, but grounding and the dialogue shortcut can use an internal adapter so they do not need to understand every nested contract field in the first pass:

  ```python
  grounding_view = classify_context_to_grounding_view(input_.context)
  in_combat = input_.context.get("mode") == "combat"
  ```

  Then use `grounding_view` where the runner currently uses `input_.surroundings`:

  ```python
  dialogue = classify_dialogue_shortcut(input_.player_input, grounding_view)
  if dialogue is not None:
      return validate_grounded_output(dialogue, grounding_view)

  def parse(answer: str) -> ActionOutput:
      output = validate_action_output_json(answer, in_combat=in_combat)
      return validate_grounded_output(output, grounding_view)
  ```

- [ ] Add `classify_context_to_grounding_view` in `server/src/llm/context/classify_view.py`.

  This adapter is internal. It should not be sent to the LLM. It preserves the existing validator shape until `server/src/llm/calls/classify/grounding.py` is rewritten around `context` directly.

  ```python
  def classify_context_to_grounding_view(context: dict[str, Any]) -> dict[str, Any]:
      identity = context.get("identity") if isinstance(context.get("identity"), dict) else {}
      references = context.get("references") if isinstance(context.get("references"), dict) else {}
      visible_targets = _dicts(identity.get("visible_targets"))
      exits = _dicts(identity.get("exits"))
      inventory = _dicts(identity.get("inventory"))
      skills = _dicts(identity.get("skills"))

      grounding_targets = [
          {
              **target,
              "type": target["type"] if target.get("type") in {"npc", "enemy"} else "npc",
          }
          for target in visible_targets
          if isinstance(target.get("id"), str) and isinstance(target.get("name"), str)
      ]

      return {
          "in_combat": context.get("mode") == "combat",
          "location": identity.get("location") or {},
          "entities": [
              *grounding_targets,
              *[
                  {"id": exit_["id"], "name": exit_["name"], "type": "connection"}
                  for exit_ in exits
                  if isinstance(exit_.get("id"), str) and isinstance(exit_.get("name"), str)
              ],
          ],
          "inventory": inventory,
          "equipment": identity.get("equipment") or {},
          "skills": skills,
          "merchants": [],
          "corpses": [],
          "recent_npc": references.get("last_npc"),
      }
  ```

- [ ] Update `server/tests/llm/calls/test_classify_history.py`.

  Rename it to `test_classify_schema.py` or replace its contents in place. The new tests should assert that the schema carries only `player_input` and `context`:

  ```python
  def test_classify_input_carries_focused_context():
      context = {
          "mode": "exploration",
          "identity": {"location": {"id": "town", "name": "마을"}},
          "affordances": {},
          "references": {},
          "budget": {},
      }
      input_ = ClassifyInput(player_input="상인에게 말을 겁니다", context=context)

      assert input_.player_input == "상인에게 말을 겁니다"
      assert input_.context == context
      assert set(input_.model_dump()) == {"player_input", "context"}
  ```

- [ ] Update `server/tests/llm/calls/test_classify_in_combat_plumbing.py` and `server/tests/llm/calls/test_classify_dialogue_shortcut.py`.

  Replace every construction that passes `surroundings=` with a helper-backed context. Add this helper to each touched test file:

  ```python
  def _classify_test_context(surroundings: dict) -> dict:
      return {
          "mode": "combat" if surroundings.get("in_combat") else "exploration",
          "identity": {
              "location": surroundings.get("location") or {},
              "visible_targets": [
                  entity
                  for entity in surroundings.get("entities", [])
                  if entity.get("type") in {"npc", "enemy"}
              ],
              "exits": [
                  {"id": entity["id"], "name": entity["name"]}
                  for entity in surroundings.get("entities", [])
                  if entity.get("type") == "connection"
              ],
              "inventory": surroundings.get("inventory", []),
              "equipment": surroundings.get("equipment", {}),
              "skills": surroundings.get("skills", []),
              "active_quest": None,
          },
          "affordances": {},
          "references": {"last_npc": surroundings.get("recent_npc"), "recent_dialogue": []},
          "budget": {},
      }
  ```

  Then construct inputs like this:

  ```python
  ClassifyInput(player_input=player_input, context=_classify_test_context(surroundings))
  ```

  This keeps the old test scenarios while forcing them through the new public request model.

- [ ] Update developer scripts that construct `ClassifyInput`.

  Replace `surroundings=` construction in:

  - `server/scripts/smoke_classify.py`
  - `server/scripts/smoke_move.py`
  - `server/scripts/classify_stress.py`

  For scripts that already define a static surroundings dict, reuse the same `_classify_test_context(surroundings)` adapter shape used in the tests. Do not keep compatibility fields on `ClassifyInput` just for scripts.

- [ ] Modify `server/src/locale/prompts/classify/prompt.ko.md`.

  Replace the old surroundings/history contract with:

  ```md
  ## 입력 컨텍스트
  - `context.player_input`: 플레이어 원문입니다.
  - `context.identity`: 현재 장소, 눈앞 대상, 이동 후보, 소지품, 장비, 기술, 활성 퀘스트입니다.
  - `context.affordances`: 현재 그래프에서 가능한 말걸기, 공격, 이동, 사용, 퀘스트 조작 후보입니다.
  - `context.references`: 최근 지칭 대상입니다. "그 사람", "아까 그 상인" 같은 표현을 해소할 때만 사용합니다.
  - `context.budget`: 잘린 후보 수입니다. 생략된 후보가 있으면 모호성을 낮게 확신하지 마십시오.

  이전 GM 나레이션, 전체 장소 설명, 전투 수치, 중요 기억 전체 목록은 제공되지 않습니다. 제공된 후보 안에서만 판정하십시오.
  ```

- [ ] Add `server/tests/llm/context/test_classify_view.py`.

  Required tests:

  ```python
  def test_classify_context_excludes_gm_narration_and_descriptions():
      runtime = _runtime(gm_log_text="GM 원문이 여기 들어가면 실패합니다.")

      context = build_classify_context_view(runtime, "상인에게 말을 겁니다")
      payload = json.dumps(context, ensure_ascii=False)

      assert "GM 원문이 여기 들어가면 실패합니다." not in payload
      assert "description" not in payload
      assert context["player_input"] == "상인에게 말을 겁니다"
  ```

  ```python
  def test_classify_context_tracks_omitted_candidates():
      runtime = _runtime(visible_character_count=10, inventory_count=12, skill_count=9)

      context = build_classify_context_view(runtime, "주변을 살핍니다")

      assert len(context["identity"]["visible_targets"]) == 8
      assert len(context["identity"]["inventory"]) == 10
      assert len(context["identity"]["skills"]) == 8
      assert context["budget"]["visible_targets_omitted"] == 2
      assert context["budget"]["inventory_omitted"] == 2
      assert context["budget"]["skills_omitted"] == 1
  ```

- [ ] Update `server/tests/game/runtime/test_graph_input.py`.

  Replace the tests that assert `history` and full `recent_dialogue` are passed to classify. The new assertions should check:

  ```python
  classify_request = captured_requests[0]
  assert classify_request.context["player_input"] == player_input
  assert "history" not in classify_request.model_dump(exclude_none=True)
  assert "recent_dialogue" not in classify_request.model_dump(exclude_none=True)
  assert classify_request.context["references"]["recent_dialogue"]
  ```

- [ ] Run:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest server/tests/llm/context/test_classify_view.py server/tests/llm/calls/test_classify_history.py server/tests/llm/calls/test_classify_in_combat_plumbing.py server/tests/llm/calls/test_classify_dialogue_shortcut.py server/tests/game/runtime/test_graph_input.py -q
  .\.venv\Scripts\python.exe server/scripts/smoke_move.py
  ```

  Expected result after implementation: all selected tests pass and no classify payload test asserts raw history transport.

### 2. Add Narrate Context Views and Remove Raw GM Log

- [ ] Modify `server/src/game/runtime/narration_context.py`.

  Keep the public functions `build_intro_narration_payload`, `build_action_narration_payload`, and `build_input_narration_payload`, but make input/action payloads use the same explicit shape:

  ```python
  def build_input_narration_payload(
      runtime: GameRuntimeState,
      *,
      player_input: str,
      action: Action | None,
      dialogue_target: GraphNode | None,
  ) -> dict[str, Any]:
      return {
          "player_input": player_input,
          "current_event": _input_current_event(action, dialogue_target),
          "scene_anchor": _scene_anchor(runtime),
          "target_view": _target_view(dialogue_target),
          "result_cards": [],
          "related_memory": related_memory_payload(runtime, action=action, target=dialogue_target),
          "recent_dialogue": narrate_recent_dialogue_payload(runtime),
          "combat_view": combat_narration_view(runtime),
          "budget": _narrate_budget(runtime, action=action, target=dialogue_target),
      }
  ```

  For action turns, keep the existing public signature and make `current_event` include the server action result rather than the old broad `recent_log` block. Explicit action endpoints do not have a raw typed sentence, so use `player_input: None` there.

  ```python
  def build_action_narration_payload(
      *,
      before: GameRuntimeState,
      after: GameRuntimeState,
      action: Action,
      dispatch: GraphActionDispatchResult,
      card_texts: list[str],
  ) -> dict[str, Any]:
      target = _action_target(after, action)
      return {
          "player_input": None,
          "current_event": _action_current_event(action, dispatch, card_texts),
          "scene_anchor": _scene_anchor(after),
          "target_view": _target_view(target),
          "result_cards": _result_cards(card_texts),
          "related_memory": related_memory_payload(after, action=action, target=target),
          "recent_dialogue": narrate_recent_dialogue_payload(after),
          "combat_view": combat_narration_view(after, trace=dispatch.combat_trace, outcome=dispatch.outcome),
          "budget": _narrate_budget(after, action=action, target=target),
      }
  ```

  `_recent_log_payload` should no longer be called by input/action narration builders. It may remain only if intro or legacy tests still need it.

- [ ] Modify `_graph_input_narration_messages` in `server/src/game/runtime/input.py`.

  Stop passing `surroundings` into `build_input_narration_payload`. The narration builder should derive the minimal scene anchor directly. Current code builds `dialogue_target` as a dict; change that local value to the actual `GraphNode | None` so the narration builder receives the same target type as action narration.

- [ ] Update `server/src/locale/prompts/graph_narrate/prompt.ko.md`.

  Add this contract:

  ```md
  ## 우선순위
  1. `payload.current_event`와 `payload.player_input`을 기준으로 이번 턴만 서술합니다.
  2. `payload.target_view`, `payload.result_cards`, `payload.combat_view`는 이번 턴 결과를 보강하는 근거입니다.
  3. `payload.related_memory`와 `payload.recent_dialogue`는 연속성을 위한 요약입니다. 이전 문장을 반복하지 마십시오.
  4. `payload.scene_anchor.visible_names`는 배경 고정용 이름 목록입니다. 모든 이름을 나열하지 마십시오.

  이전 GM 원문은 제공되지 않습니다. 같은 나레이션을 반복하지 말고, 플레이어 원문에 직접 반응하십시오.
  ```

- [ ] Update `server/tests/game/runtime/test_graph_narration_context.py`.

  Required assertions:

  ```python
  payload = build_input_narration_payload(
      runtime,
      player_input="로엔에게 장부를 묻습니다",
      action=None,
      dialogue_target=merchant,
  )
  encoded = json.dumps(payload, ensure_ascii=False)

  assert payload["player_input"] == "로엔에게 장부를 묻습니다"
  assert "recent_log" not in payload
  assert "GM 원문" not in encoded
  assert payload["current_event"]["kind"] == "dialogue"
  assert payload["target_view"]["id"] == merchant.id
  ```

- [ ] Run:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_graph_narration_context.py server/tests/game/runtime/test_graph_input.py server/tests/game/runtime/test_graph_action_turn.py -q
  ```

  Expected result after implementation: input and action narration tests pass without asserting `recent_log`.

### 3. Replace Importance-Only Memory with Related Compact Memory

- [ ] Modify `server/src/game/runtime/memory_context.py`.

  Keep old helpers only if other callers still need them, but add the new public helpers:

  ```python
  MAX_NARRATE_RELATED_MEMORY = 8
  MAX_RECENT_DIALOGUE = 5
  ```

  ```python
  def classify_recent_dialogue_payload(runtime: GameRuntimeState, *, limit: int = MAX_RECENT_DIALOGUE) -> list[dict[str, Any]]:
      return [
          {"turn": pair.turn, "player": pair.player, "summary": pair.narrator}
          for pair in runtime.recent_dialogue[-limit:]
      ]
  ```

  ```python
  def narrate_recent_dialogue_payload(runtime: GameRuntimeState, *, limit: int = MAX_RECENT_DIALOGUE) -> list[dict[str, Any]]:
      return classify_recent_dialogue_payload(runtime, limit=limit)
  ```

  `importance` is currently a 1-3 value. Relevance decides membership first; importance only breaks ties or keeps the strongest general memory when there is room.

  ```python
  def related_memory_payload(
      runtime: GameRuntimeState,
      *,
      action: Action | None,
      target: GraphNode | None,
      limit: int = MAX_NARRATE_RELATED_MEMORY,
  ) -> list[dict[str, Any]]:
      related_ids = _related_ids(runtime, action=action, target=target)
      ranked = sorted(
          runtime.turn_log,
          key=lambda entry: (
              0 if entry.target in related_ids else 1,
              -entry.importance,
              -entry.turn,
          ),
      )
      return [
          {
              "turn": entry.turn,
              "target": entry.target,
              "summary": entry.summary,
              "importance": entry.importance,
          }
          for entry in ranked
          if entry.target in related_ids or entry.importance >= 3
      ][:limit]
  ```

  `_related_ids` should include:

  - Current location id
  - Action `target_id`, `from_id`, `to_id`, `item_id`, `skill_id` when present
  - Dialogue target id
  - Active quest id and quest participant ids when already available in runtime state
  - Combat participant ids when `runtime.progress.graph_combat_state` exists

- [ ] Add tests to `server/tests/game/runtime/test_memory_context.py`.

  Required cases:

  ```python
  def test_related_memory_prefers_relevance_before_importance():
      runtime = _runtime()
      runtime.turn_log.append(TurnLogEntry(turn=1, target="unrelated", summary="중요하지만 이번 장면과 무관합니다.", importance=3))
      runtime.turn_log.append(TurnLogEntry(turn=2, target="npc_merchant", summary="상인이 장부를 잃어버렸습니다.", importance=2))

      payload = related_memory_payload(runtime, action=None, target=runtime.graph.nodes["npc_merchant"], limit=1)

      assert payload == [{"turn": 2, "target": "npc_merchant", "summary": "상인이 장부를 잃어버렸습니다.", "importance": 2}]
  ```

  ```python
  def test_recent_dialogue_is_limited_and_does_not_pull_turn_log():
      runtime = _runtime(dialogue_count=7)
      runtime.turn_log.append(TurnLogEntry(turn=99, target="npc_merchant", summary="중요 기억", importance=3))

      payload = classify_recent_dialogue_payload(runtime)

      assert len(payload) == 5
      assert all(set(item) == {"turn", "player", "summary"} for item in payload)
      assert "중요 기억" not in json.dumps(payload, ensure_ascii=False)
  ```

- [ ] Update tests that currently assert twenty importance summaries. The replacement assertion is:

  ```python
  assert len(payload["related_memory"]) <= 8
  assert all("summary" in item for item in payload["related_memory"])
  ```

- [ ] Run:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_memory_context.py server/tests/game/runtime/test_graph_input.py server/tests/game/runtime/test_graph_narration_context.py -q
  ```

  Expected result after implementation: no test depends on twenty global importance summaries for classify or narrate.

### 4. Convert Combat Trace into Presentation-Safe Combat View

- [ ] Create `server/src/game/runtime/combat_narration_view.py`.

  Public entry point:

  ```python
  def combat_narration_view(
      runtime: GameRuntimeState,
      *,
      trace: list[GraphCombatTraceEvent] | None = None,
      outcome: str | None = None,
  ) -> dict[str, Any] | None:
      state = runtime.progress.graph_combat_state
      events = trace if trace is not None else (state.trace if state is not None else [])
      if not events:
          return None

      return {
          "kind": "combat_exchange",
          "round": state.round if state is not None else None,
          "player_action": state.last_action if state is not None else None,
          "outcome": outcome or (state.outcome if state is not None else None),
          "events": [_event_view(runtime, event) for event in events],
          "tone": _combat_tone(runtime),
      }
  ```

  Action narration must pass `dispatch.combat_trace` into this function. That keeps the current exchange available even when a terminal result clears `after.progress.graph_combat_state`, and it prevents narration from receiving the full accumulated combat trace. The `state.trace` fallback is only for contexts that do not have a dispatch object.

  Event view should map raw states to prose-safe labels:

  ```python
  COMBAT_CONDITION_LABELS = {
      "healthy": "버티고 있음",
      "hurt": "흔들림",
      "critical": "위태로움",
      "downed": "쓰러짐",
  }
  ```

  Raw `event.kind` values should map to natural motion labels:

  ```python
  COMBAT_MOTION_LABELS = {
      "combat_started": "교전이 시작됨",
      "player_attacked": "공격을 시도함",
      "player_cast": "기술을 사용함",
      "player_defended": "방어 자세를 취함",
      "player_fled": "거리를 벌림",
      "enemy_pressed": "압박함",
      "enemy_defeated": "상대가 쓰러짐",
      "player_downed": "플레이어가 쓰러짐",
      "forced_end": "교전이 멈춤",
  }
  ```

  The returned payload must not include `kind` from the raw trace event, `state`, HP, damage, or enum-style condition words.

- [ ] Add training/nonlethal tone selection.

  `_combat_tone(runtime)` should return:

  ```python
  {"lethality": "nonlethal", "style": "training"}
  ```

  when the encounter or current opponent has graph metadata indicating sparring, training, tutorial, or nonlethal combat. Otherwise return:

  ```python
  {"lethality": "dangerous", "style": "adventure"}
  ```

  Use existing graph node properties only. Do not add hidden defaults to env or scenario loading.

- [ ] Modify `server/src/game/runtime/narration_context.py` to call `combat_narration_view` instead of `_combat_trace_payload`.

- [ ] Update `server/src/locale/prompts/graph_narrate/prompt.ko.md`.

  Add:

  ```md
  `payload.combat_view`는 플레이어에게 보여줄 수 있는 전투 요약입니다. 내부 상태명, 수치, 피해량을 만들지 마십시오. `tone.lethality`가 `nonlethal`이면 훈련이나 대련처럼 쓰고, 살상 위협처럼 과장하지 마십시오.
  ```

- [ ] Update `server/tests/game/runtime/test_graph_narration_context.py`.

  Replace raw trace assertions:

  ```python
  combat = payload["combat_view"]
  encoded = json.dumps(combat, ensure_ascii=False)

  assert combat["kind"] == "combat_exchange"
  assert "events" in combat
  assert "hurt" not in encoded
  assert "critical" not in encoded
  assert "healthy" not in encoded
  assert "downed" not in encoded
  assert "player_attacked" not in encoded
  assert "enemy_pressed" not in encoded
  assert "damage" not in encoded
  assert "hp" not in encoded.lower()
  ```

  Add a terminal-combat assertion:

  ```python
  terminal_payload = build_action_narration_payload(
      before=runtime,
      after=runtime.model_copy(update={"progress": runtime.progress.model_copy(update={"graph_combat_state": None})}),
      action=Action(verb="attack", what="guard_01"),
      dispatch=GraphActionDispatchResult(
          runtime=runtime,
          kind="combat",
          applied=1,
          changed_node_ids=["guard_01"],
          changed_edge_ids=[],
          removed_edge_ids=[],
          outcome="victory",
          combat_trace=[GraphCombatTraceEvent(kind="enemy_defeated", actor_id="player_01", target_id="guard_01", state="downed")],
      ),
      card_texts=["전투가 끝납니다."],
  )

  assert terminal_payload["combat_view"]["outcome"] == "victory"
  assert terminal_payload["combat_view"]["events"]
  assert "enemy_defeated" not in json.dumps(terminal_payload["combat_view"], ensure_ascii=False)
  ```

- [ ] Run:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_graph_narration_context.py server/tests/game/runtime/test_graph_action_turn.py -q
  ```

  Expected result after implementation: combat payload tests pass and raw enum strings are absent.

### 5. Restore Structured Recommendation Chips with Backward Compatibility

- [ ] Create `server/src/game/runtime/suggestions.py`.

  This keeps suggestion parsing out of the API layer and avoids importing `server/src/api/schema.py` from runtime code.

  ```python
  class GraphSuggestion(BaseModel):
      label: str
      input_text: str
      intent: str | None = None
      action: dict[str, Any] | None = None
  ```

  Also add:

  ```python
  GraphSuggestionValue = str | GraphSuggestion
  ```

  Move suggestion cleanup into this file:

  ```python
  def normalize_suggestion(value: object) -> GraphSuggestionValue | None:
      if isinstance(value, str):
          text = value.strip()
          return text or None
      if isinstance(value, dict):
          label = str(value.get("label", "")).strip()
          input_text = str(value.get("input_text", "")).strip()
          if not label or not input_text:
              return None
          return GraphSuggestion(
              label=label,
              input_text=input_text,
              intent=str(value["intent"]).strip() if value.get("intent") else None,
              action=value.get("action") if isinstance(value.get("action"), dict) else None,
          )
      return None
  ```

- [ ] Modify `server/src/game/runtime/narration_result.py`.

  Import `GraphSuggestionValue` and `normalize_suggestion` from `server/src/game/runtime/suggestions.py`. Change:

  ```python
  suggestions: list[str] = Field(default_factory=list)
  ```

  to:

  ```python
  suggestions: list[GraphSuggestionValue] = Field(default_factory=list)
  ```

  Keep the existing max count and max string length behavior for string suggestions. For structured suggestions, trim `label` and `input_text`; cap `label` at 32 characters and `input_text` at the existing `_MAX_SUGGESTION_CHARS`.

- [ ] Modify `server/src/api/schema.py`.

  Import `GraphSuggestionValue` and change both `InitResponse` and `GraphActionResponse`:

  ```python
  suggestions: list[GraphSuggestionValue] = Field(default_factory=list)
  ```

  Keep string support so old LLM output and existing snapshots do not break.

- [ ] Update `server/src/locale/prompts/graph_narrate/prompt.ko.md`.

  Require structured suggestions in the metadata block:

  ```md
  `suggestions`는 2~4개입니다. 각 항목은 `{ "label": "짧은 칩 문구", "input_text": "플레이어가 직접 입력할 자연문", "intent": "talk", "action": null }` 형태입니다.
  - `label`: 칩에 짧게 보일 문구입니다.
  - `input_text`: 칩을 눌렀을 때 플레이어 입력창에 들어갈 자연문입니다.
  - `intent`: `talk`, `move`, `inspect`, `use`, `combat`, `quest` 중 하나입니다.
  - `action`: 지금은 항상 `null`입니다.
  ```

- [ ] Modify client types in `client/services/wire.ts`.

  Add:

  ```ts
  export type GraphSuggestion =
    | string
    | {
        label: string;
        input_text: string;
        intent?: string | null;
        action?: Record<string, unknown> | null;
      };
  ```

  Then update every client response or session type that carries suggestions:

  ```ts
  export type SessionPayload = {
    game_id: string;
    state: FrontState;
    suggestions?: GraphSuggestion[];
  };

  export type GraphSessionPayload = {
    game_id: string;
    state: GraphFrontState;
    suggestions?: GraphSuggestion[];
  };

  export type GraphActionResponse = {
    game_id: string;
    state: GraphFrontState;
    status?: string | null;
    message?: string | null;
    suggestions?: GraphSuggestion[];
  };
  ```

  `GraphActionClientResponse` should use normalized chips, not server wire values:

  ```ts
  suggestions: SuggestionChip[];
  ```

- [ ] Modify `client/services/api.ts`.

  Change `adaptSuggestions` to return chip view models:

  ```ts
  export type SuggestionChip = {
    label: string;
    inputText: string;
    intent?: string | null;
  };
  ```

  Normalization:

  ```ts
  function normalizeSuggestion(value: GraphSuggestion): SuggestionChip | null {
    if (typeof value === "string") {
      const text = value.trim();
      return text ? { label: text, inputText: text } : null;
    }
    const label = value.label.trim();
    const inputText = value.input_text.trim();
    if (!label || !inputText) return null;
    return { label, inputText, intent: value.intent ?? null };
  }
  ```

- [ ] Modify `client/logic/game/useGame.ts`, `client/logic/game/requestRunner.ts`, `client/components/composer/Composer.tsx`, and any child chip component.

  State should be `SuggestionChip[]`. Chip text should render `suggestion.label`. Chip press should send `suggestion.inputText`.

  Required press behavior:

  ```tsx
  onPress={() => sendText(suggestion.inputText)}
  ```

- [ ] Modify `client/services/storage.ts`.

  Change `loadSuggestions` and `storeSuggestions` from `string[]` to `SuggestionChip[]`. When loading existing local storage, accept both old strings and new objects:

  ```ts
  function normalizeStoredSuggestion(value: unknown): SuggestionChip | null {
    if (typeof value === "string") {
      const text = value.trim();
      return text ? { label: text, inputText: text } : null;
    }
    if (!value || typeof value !== "object") return null;
    const item = value as { label?: unknown; inputText?: unknown };
    if (typeof item.label !== "string" || typeof item.inputText !== "string") return null;
    const label = item.label.trim();
    const inputText = item.inputText.trim();
    return label && inputText ? { label, inputText } : null;
  }
  ```

  Keep `client/services/graphAdapter.ts` deriving the same Korean fallback text, but update its exported return type to `SuggestionChip[]` or normalize its returned strings immediately in `adaptSuggestions`. All public paths that set `suggestions` in `useGame.ts`, `requestRunner.ts`, storage, and API adapters must end at `SuggestionChip[]`.

- [ ] Add or update client tests if the project already has a test harness for adapters.

  Existing Jest tests under `client/services/__tests__` and `client/components/composer/__tests__` should be updated. The API adapter test that currently expects `['북문으로 이동합니다']` should expect:

  ```ts
  [{ label: '북문으로 이동합니다', inputText: '북문으로 이동합니다' }]
  ```

  Add one adapter test for a structured server suggestion:

  ```ts
  expect(result.suggestions).toEqual([
    { label: '북문으로', inputText: '북문으로 이동합니다', intent: 'move' },
  ]);
  ```

- [ ] Run:

  ```powershell
  cd client
  npx tsc --noEmit
  npm test -- --runInBand
  ```

  `client/package.json` currently has no `typecheck` script, so use `npx tsc --noEmit` directly.

### 6. Add Payload Guard Tests

- [ ] Add guard tests that serialize payloads and reject forbidden fields.

  Create `server/tests/game/runtime/test_llm_context_guards.py`:

  ```python
  FORBIDDEN_CONTEXT_TOKENS = [
      "recent_log",
      "GM 원문",
      "combat_started",
      "player_attacked",
      "player_cast",
      "player_defended",
      "player_fled",
      "enemy_pressed",
      "enemy_defeated",
      "player_downed",
      "forced_end",
      "critical",
      "hurt",
      "healthy",
      "downed",
      "\"hp\"",
      "\"damage\"",
  ]
  ```

  Test classify:

  ```python
  def test_classify_context_forbidden_tokens():
      runtime = _runtime(with_combat=True)
      payload = json.dumps(build_classify_context_view(runtime, "공격합니다"), ensure_ascii=False)

      for token in FORBIDDEN_CONTEXT_TOKENS:
          assert token not in payload
  ```

  Test narrate:

  ```python
  def test_narrate_context_forbidden_tokens():
      runtime = _runtime(with_combat=True)
      payload = json.dumps(
          build_input_narration_payload(
              runtime,
              player_input="대련을 계속합니다",
              action=None,
              dialogue_target=None,
          ),
          ensure_ascii=False,
      )

      for token in FORBIDDEN_CONTEXT_TOKENS:
          assert token not in payload
  ```

- [ ] Add a size sanity guard.

  The exact byte budget is not a product guarantee, but this catches accidental world dumps:

  ```python
  def test_context_payloads_stay_compact():
      runtime = _runtime(visible_character_count=20, inventory_count=25, skill_count=20, dialogue_count=20)

      classify_payload = json.dumps(build_classify_context_view(runtime, "말을 겁니다"), ensure_ascii=False)
      narrate_payload = json.dumps(
          build_input_narration_payload(runtime, player_input="말을 겁니다", action=None, dialogue_target=None),
          ensure_ascii=False,
      )

      assert len(classify_payload) < 12000
      assert len(narrate_payload) < 12000
  ```

- [ ] Run:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest server/tests/game/runtime/test_llm_context_guards.py -q
  ```

  Expected result after implementation: guard tests pass and protect the core design constraints.

### 7. Manual QA Round

- [ ] Start the API and web client from existing commands.

  ```powershell
  cd server
  ..\.venv\Scripts\python.exe run_api.py
  ```

  In a separate shell:

  ```powershell
  cd client
  npm run web
  ```

- [ ] Use Playwright with mobile viewport against `http://localhost:8081/`.

  Required flow:

  1. Start or load a Korean scenario.
  2. Send a direct Korean input that refers to a visible NPC.
  3. Press a recommendation chip.
  4. Enter a follow-up reference such as `아까 그 사람에게 다시 물어봅니다`.
  5. Trigger or continue training combat if the scenario exposes it.

- [ ] Observe and record in root `report.md`:

  - Whether LLM narration repeats the previous GM prose.
  - Whether chip text is short and chip press sends the longer natural input.
  - Whether classify resolves references without broad history.
  - Whether combat prose avoids raw states and excessive lethal tone in training contexts.
  - Whether any additional tests are needed after this round.

## Final Verification

Run the server tests touched by this work:

```powershell
.\.venv\Scripts\python.exe -m pytest server/tests/llm/context/test_classify_view.py server/tests/game/runtime/test_memory_context.py server/tests/game/runtime/test_graph_input.py server/tests/game/runtime/test_graph_narration_context.py server/tests/game/runtime/test_graph_action_turn.py server/tests/game/runtime/test_llm_context_guards.py -q
```

Run the client check:

```powershell
cd client
npx tsc --noEmit
npm test -- --runInBand
```

Run a smoke classify sanity check:

```powershell
.\.venv\Scripts\python.exe server/scripts/smoke_classify.py
```

## Expected Outcome

After implementation:

- `classify` receives player input, local graph candidates, affordances, and compact references only.
- `graph_narrate` receives player input, current event, scene anchor, target/result view, relevant memories, recent dialogue summaries, and a safe combat view.
- Previous GM raw prose is not transported to either LLM call by default.
- Recommendation chips support `{label, input_text, intent, action}` while preserving old string suggestions.
- Memory is selected first by graph relevance and only then by importance.
- Combat narration receives player-safe labels and tone hints, not internal engine enums or numeric traces.
