from typing import Any

from src.game.domain.action import Action
from src.game.domain.graph import GraphNode
from src.game.domain.memory import RollLogEntry
from src.game.domain.graph.query import location_of

from ...action.dispatch import GraphActionDispatchResult
from ...state import GameRuntimeState
from ...story_context import current_story_payload
from ..combat_view import combat_narration_view
from .events import (
    action_target as _action_target,
    arrival_branch_results as _arrival_branch_results,
    input_current_event as _input_current_event,
    quest_trigger_payload as _quest_trigger_payload,
    result_cards as _result_cards,
    roll_result_card as _roll_result_card,
    story_transition_payload as _story_transition_payload,
    travel_results as _travel_results,
)
from ..memory_context import (
    narrate_recent_exchanges_payload,
    previous_scene_payload,
    subject_memories_payload,
)
from ..payload_contract import compact_narration_payload, narration_action_payload
from .base import place_payload as _place_payload
from .base import world_guidance as _world_guidance
from .knowledge import (
    discoveries_payload as _discoveries_payload,
    revealed_fact_payloads as _revealed_fact_payloads,
)
from .target import target_view as _target_view
from .visibility import scene_anchor as _scene_anchor


def build_action_narration_payload(
    *,
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
) -> dict[str, Any]:
    place_id = location_of(after.graph_index, after.progress.player_id)
    place = after.graph.nodes.get(place_id or "")
    target = _action_target(after, action)
    scene_anchor = _scene_anchor(after)
    current_event = {
        "kind": dispatch.kind,
        "outcome": dispatch.outcome,
        "action": narration_action_payload(action),
        "resolved_results": [
            *card_texts,
            *_travel_results(before, after),
            *_arrival_branch_results(before, after),
        ],
    }
    quest_trigger = _quest_trigger_payload(action, dispatch.kind)
    if quest_trigger is not None:
        current_event["quest_trigger"] = quest_trigger
    story_transition = _story_transition_payload(before, after, action)
    if story_transition is not None:
        current_event["story_transition"] = story_transition
    payload = {
        "world_guidance": _world_guidance(after),
        "current_story": current_story_payload(after),
        "player_input": None,
        "current_place": _place_payload(after, place),
        "current_event": current_event,
        "scene_anchor": scene_anchor,
        "target_view": _target_view(after, target),
        "result_cards": _result_cards(card_texts),
        "previous_scene": previous_scene_payload(after),
        "subject_memories": subject_memories_payload(
            after,
            target=target.id if target is not None else None,
        ),
        "recent_exchanges": narrate_recent_exchanges_payload(
            after,
            target=target.id if target is not None else None,
        ),
        "discoveries": _discoveries_payload(after),
        "combat_view": combat_narration_view(
            after,
            trace=dispatch.combat_trace,
            outcome=dispatch.outcome,
        ),
    }
    return compact_narration_payload(payload)

def build_roll_narration_payload(
    *,
    runtime: GameRuntimeState,
    action: Action,
    pending: dict[str, Any],
    roll_entry: RollLogEntry,
    outcome: str,
    result_texts: list[str] | None = None,
) -> dict[str, Any]:
    target = _action_target(runtime, action)
    check_reason = pending.get("check_reason")
    if not isinstance(check_reason, str):
        check_reason = ""
    player_input = pending.get("player_input")
    resolved_results = result_texts or [
        _roll_result_card(roll_entry, outcome, runtime.progress.locale)
    ]
    current_event = {
        "kind": "roll",
        "outcome": outcome,
        "action": narration_action_payload(action),
        "roll": {
            "check": roll_entry.check,
            "result": roll_entry.result,
            "margin": roll_entry.margin,
        },
        "resolved_results": resolved_results,
    }
    revealed_facts = _revealed_fact_payloads(runtime, target) if outcome == "success" else []
    if revealed_facts:
        current_event["revealed_facts"] = revealed_facts
    if check_reason:
        current_event["check_reason"] = check_reason
    payload = {
        "world_guidance": _world_guidance(runtime),
        "current_story": current_story_payload(runtime),
        "player_input": player_input if isinstance(player_input, str) else None,
        "current_event": current_event,
        "scene_anchor": _scene_anchor(runtime),
        "target_view": _target_view(runtime, target),
        "result_cards": _result_cards(resolved_results),
        "previous_scene": previous_scene_payload(runtime),
        "subject_memories": subject_memories_payload(
            runtime,
            target=target.id if target is not None else None,
        ),
        "recent_exchanges": narrate_recent_exchanges_payload(
            runtime,
            target=target.id if target is not None else None,
        ),
        "discoveries": _discoveries_payload(runtime),
        "combat_view": combat_narration_view(runtime),
    }
    return compact_narration_payload(payload)
def build_input_narration_payload(
    *,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    dialogue_target: GraphNode | None,
) -> dict[str, Any]:
    payload = {
        "world_guidance": _world_guidance(runtime),
        "current_story": current_story_payload(runtime),
        "player_input": player_input,
        "current_event": _input_current_event(runtime, action, dialogue_target),
        "current_place": _place_payload(
            runtime,
            runtime.graph.nodes.get(
                location_of(runtime.graph_index, runtime.progress.player_id) or ""
            ),
        ),
        "scene_anchor": _scene_anchor(runtime),
        "target_view": _target_view(
            runtime,
            dialogue_target,
            player_input=player_input,
        ),
        "result_cards": [],
        "previous_scene": [],
        "subject_memories": subject_memories_payload(
            runtime,
            target=dialogue_target.id if dialogue_target is not None else None,
        )
        if dialogue_target is not None
        else [],
        "recent_exchanges": narrate_recent_exchanges_payload(
            runtime,
            target=dialogue_target.id if dialogue_target is not None else None,
        )
        if dialogue_target is not None
        else [],
        "discoveries": _discoveries_payload(runtime),
        "combat_view": combat_narration_view(runtime),
    }
    return compact_narration_payload(payload)
