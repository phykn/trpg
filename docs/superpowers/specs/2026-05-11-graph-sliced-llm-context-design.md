# Graph-Sliced LLM Context Design

## Goal

LLM context must be sufficient, but not broad. The graph is the source of truth, so each LLM call receives a purpose-built graph projection instead of recent-log dumps, full surroundings, or full world state.

This design covers three sequential changes:

1. Split classify and narrate context contracts.
2. Structure suggestions without changing the chip UI.
3. Filter memory and combat state through user-facing views.

## Non-Goals

- Do not let LLMs decide success, damage, rewards, quest completion, or graph changes.
- Do not send raw GM narration logs to classify or narrate.
- Do not solve English UI support in this pass.
- Do not replace graph engine rules with prompt rules.

## Current Failure

The current input narration path can send recent GM text through `recent_log`. When the next player input is short, such as `테스트 가이드에게 말을 겁니다`, that GM text is more detailed than the current action and the LLM repeats it.

Combat narration can receive raw trace state such as `critical`. The model then copies the internal enum into player-facing prose.

Both failures come from the same boundary problem: LLM context is not yet a strict graph-query view.

## Context Rules

All LLM context builders use allowlists. If a field is not listed in the context schema, it is not sent.

Raw log entries are forbidden by default. Player input is preserved exactly. Previous context enters only through summaries or graph-derived fields.

Internal ids may appear only in structured fields. Player-facing prose fields use localized names or short localized state phrases.

Every context view has count budgets. If more candidates exist, the builder keeps the most relevant entries and sets an omitted counter for that slice, such as `visible_targets_omitted`.

## ClassifyContextView

Classify only chooses `Action`. It needs candidate sets for grounding and reference resolution, not narrative detail.

Schema:

```json
{
  "player_input": "테스트 가이드에게 허수아비 훈련 방법을 물어봅니다.",
  "mode": "normal",
  "identity": {
    "location": {"id": "test_hub", "name": "테스트 허브"},
    "visible_targets": [
      {"id": "guide_01", "name": "테스트 가이드", "type": "npc", "role": "훈련 안내"},
      {"id": "dummy_01", "name": "훈련용 허수아비", "type": "enemy", "role": "훈련 대상"}
    ],
    "exits": [
      {"id": "prep_room", "name": "준비실"}
    ],
    "inventory": [
      {"id": "focus_charm", "name": "집중 부적", "kind": "trigger"}
    ],
    "equipment": {
      "weapon": null,
      "armor": null,
      "accessory": {"id": "focus_charm", "name": "집중 부적"}
    },
    "skills": [],
    "active_quest": null
  },
  "affordances": {
    "can_speak_to": ["guide_01"],
    "can_attack": ["dummy_01"],
    "can_move_to": ["prep_room"],
    "can_use": ["focus_charm"],
    "can_accept_or_abandon_quest": []
  },
  "references": {
    "last_npc": {"id": "guide_01", "name": "테스트 가이드"},
    "last_target": {"id": "dummy_01", "name": "훈련용 허수아비"},
    "last_item": null,
    "recent_dialogue": [
      {"player": "테스트 가이드에게 말을 겁니다", "summary": "가이드는 반응했지만 구체적인 설명은 하지 않았습니다."}
    ]
  },
  "budget": {
    "visible_targets_omitted": 0,
    "exits_omitted": 0,
    "inventory_omitted": 0,
    "skills_omitted": 0
  }
}
```

Budgets:

| Slice | Limit | Selection |
|---|---:|---|
| `visible_targets` | 8 | same-location visible characters, active subject first, then active quest targets, then stable graph order |
| `exits` | 6 | same-location `connects_to`, stable graph order |
| `inventory` | 10 | equipped and usable items first, then stable graph order |
| `skills` | 8 | available skills only, combat-usable first in combat |
| `recent_dialogue` | 5 | newest dialogue summaries only |

Classify forbidden fields:

- GM narration text
- full location or NPC descriptions
- HP and MP numbers
- combat trace
- raw log entries
- full important-history list

## NarrateContextView

Narrate writes visible prose for an already resolved event. It needs the current event and a small amount of scene grounding.

Schema:

```json
{
  "player_input": "테스트 가이드에게 허수아비 훈련 방법을 물어봅니다.",
  "current_event": {
    "kind": "dialogue",
    "intent": "ask_training_method",
    "target": {"id": "guide_01", "name": "테스트 가이드"},
    "focus": "NPC가 질문에 짧게 답하고 다음 행동 힌트를 줍니다."
  },
  "scene_anchor": {
    "location": {"id": "test_hub", "name": "테스트 허브"},
    "visible_names": ["테스트 가이드", "훈련용 허수아비", "준비실"]
  },
  "target_view": {
    "id": "guide_01",
    "name": "테스트 가이드",
    "type": "npc",
    "role": "훈련 안내",
    "description": "훈련 절차를 안내하는 테스트 NPC입니다."
  },
  "result_cards": [],
  "related_memory": [
    {"summary": "허수아비는 훈련 대상입니다.", "importance": 2}
  ],
  "recent_dialogue": [
    {"player": "테스트 가이드에게 말을 겁니다", "summary": "가이드는 반응했지만 구체적인 설명은 하지 않았습니다."}
  ],
  "combat_view": null,
  "budget": {
    "visible_names_omitted": 0,
    "related_memory_omitted": 0,
    "recent_dialogue_omitted": 0,
    "result_cards_omitted": 0
  }
}
```

Budgets:

| Slice | Limit | Selection |
|---|---:|---|
| `visible_names` | 5 | target, active subject, active quest targets, exits, then stable graph order |
| `related_memory` | 8 | target/location/quest related entries, importance desc, recency desc |
| `recent_dialogue` | 5 | same target first, then newest |
| `result_cards` | 4 | engine cards from this request only |

Narrate forbidden fields:

- GM narration text
- full surroundings
- full inventory
- full visible target detail
- internal enum values
- HP and MP numbers
- damage amounts
- full important-history list

## Slice Mapping

| Slice | Purpose | Used By | Fields |
|---|---|---|---|
| Identity | Resolve names and ids | classify, narrate | `id`, `name`, `type`, `role` |
| Affordance | Pick legal action candidates | classify | `can_speak_to`, `can_attack`, `can_move_to`, `can_use`, quest action candidates |
| Event | Center the current turn | narrate | `kind`, `intent`, `target`, `outcome`, `result_cards` |
| Narrative | Write visible prose without inventing facts | narrate | localized short descriptions, visible names, related summaries |
| Memory | Resolve references and preserve continuity | classify, narrate | summaries only, agent-specific limits |
| Combat | Describe combat without exposing rules | narrate | user-facing condition and pressure labels |

## Candidate Selection

The builder must not decide relevance by prompt wording alone. It queries graph relations in this order:

1. Current player location.
2. Nodes directly referenced by `Action.what`, `Action.from`, `Action.to`, or `Action.with`.
3. `progress.active_subject_id`.
4. Active quest giver, targets, requirements, and rewards.
5. Combat participants.
6. Same-location visible characters, visible items, exits.
7. Player inventory, equipment, and known skills.

Classify receives candidate arrays because it must compare options. Narrate receives target-focused views because it should not choose game actions.

## Memory Selection

Stored dialogue and history stay append-only, but context builders filter them.

Classify uses memory only for reference resolution. It receives `references.last_npc`, `references.last_target`, `references.last_item`, and up to five `references.recent_dialogue` summaries.

Narrate receives up to eight related memory summaries. Related means at least one of these matches the current event: target id, location id, quest id, active subject id, or combat participant id.

Importance decides ties after relevance. Importance alone does not force an entry into context.

## CombatNarrationView

Combat trace is converted before it reaches the LLM.

Example:

```json
{
  "kind": "combat_exchange",
  "round": 2,
  "player_action": "attack",
  "outcome": "ongoing",
  "events": [
    {
      "actor": "주인공",
      "target": "훈련용 허수아비",
      "motion": "공격이 상대의 균형을 무너뜨립니다.",
      "target_condition": "거의 버티지 못하는 상태"
    },
    {
      "actor": "훈련용 허수아비",
      "target": "주인공",
      "motion": "상대가 거리를 좁혀 압박합니다.",
      "target_condition": "다쳤지만 움직일 수 있는 상태"
    }
  ],
  "tone": ["training", "nonlethal"]
}
```

Forbidden combat payload values:

- `critical`, `hurt`, `healthy`, `downed`
- raw `player_attacked`, `enemy_pressed`, `forced_end`
- HP numbers
- damage numbers

The engine may still store internal states. The LLM sees localized condition labels.

## Suggestion Structure

Suggestions will move from `string[]` to structured entries after the context split lands.

```json
{
  "label": "훈련 방법을 다시 묻습니다",
  "input_text": "테스트 가이드에게 허수아비 훈련 방법을 다시 물어봅니다.",
  "intent": "dialogue.ask_training_method",
  "action": null
}
```

Client UI still renders chips from `label`. Pressing a chip sends `input_text` until direct structured `action` execution is implemented.

String suggestions remain supported during migration. The client adapts old strings into `{label, input_text}`.

## Implementation Plan

Phase 1: Context split.

- Add `ClassifyContextView` and `NarrateContextView` builders.
- Remove GM raw text from narrate input.
- Preserve player input exactly.
- Add budget fields and tests for omitted counts.

Phase 2: Combat view.

- Convert combat trace into `CombatNarrationView`.
- Add tests that forbidden internal tokens do not appear in narrate payload.
- Add training/nonlethal tone hints from graph properties.

Phase 3: Memory filtering.

- Add target/location/quest related memory selection.
- Stop passing the same 20-entry history payload to every agent.
- Keep append-only storage unchanged.

Phase 4: Structured suggestions.

- Extend API schema with structured suggestions.
- Keep string fallback.
- Update client chip handling to use `label` and send `input_text`.

## Tests

- Classify payload contains multiple visible candidates and no GM raw narration.
- Classify payload enforces candidate budgets and reports omitted counts.
- Narrate payload preserves `player_input` and has no GM raw narration.
- Narrate payload contains `current_event` for dialogue turns.
- Narrate payload uses target-focused views rather than full surroundings.
- Combat narrate payload contains no internal enum strings or HP numbers.
- Memory context includes only relevant summaries for the current target/location/quest.
- Suggestion migration keeps old `string[]` responses working.
- Mobile QA reproduces no intro-repeat after `테스트 가이드에게 말을 겁니다`.

## Acceptance Criteria

- The recommendation chip dialogue no longer repeats the intro GM paragraph.
- Direct input and chip input both preserve the player text that caused the turn.
- `graph_narrate` receives no raw GM log text.
- `classify` receives enough candidates to ground actions but no narrative prose dump.
- Combat narration cannot expose internal trace enums.
- Context builder tests make payload size and forbidden fields enforceable.
