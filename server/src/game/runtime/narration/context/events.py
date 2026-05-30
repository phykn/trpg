from typing import Any

from src.game.domain.action import Action
from src.game.domain.content import node_label, node_text
from src.game.domain.graph import GraphNode
from src.game.domain.graph.query import edges_from, inventory_of, location_of
from src.game.domain.memory import RollLogEntry
from src.game.domain.quest import quest_choices
from src.locale.render import render

from ...action_refs import first_ref
from ...state import GameRuntimeState
from ..payload_contract import narration_action_payload
from .base import item_payload as _item_payload
from .base import node_ref as _node_ref
from .target import target_view as _target_view


def input_current_event(
    runtime: GameRuntimeState,
    action: Action,
    dialogue_target: GraphNode | None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "kind": "dialogue" if dialogue_target is not None else "input",
        "target": _target_view(runtime, dialogue_target),
        "action": narration_action_payload(action),
        "outcome": (
            "player_addresses_target"
            if dialogue_target is not None
            else "player_action_pending_narration"
        ),
    }
    if dialogue_target is not None:
        event["dialogue_expectation"] = {
            "npc_reply": "expected",
            "direct_speech": "prefer_one_short_utterance",
        }
    return event


def quest_trigger_payload(action: Action, kind: str) -> dict[str, str] | None:
    if kind == "move":
        target = first_ref(action.to) or first_ref(action.what)
        if target is not None:
            return {"type": "location_enter"}
    return None


def story_transition_payload(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    completed_quests = _changed_nodes_by_status(
        before,
        after,
        node_type="quest",
        to_status="completed",
    )
    opened_chapters = _changed_nodes_by_status(
        before,
        after,
        node_type="chapter",
        to_status="active",
    )
    next_quests = _changed_nodes_by_status(
        before,
        after,
        node_type="quest",
        to_status="pending",
    )
    if not completed_quests and not opened_chapters and not next_quests:
        return None
    payload: dict[str, Any] = {"style": "lead_not_solution"}
    choice_result = _choice_result_payload(before, after, action)
    if choice_result is not None:
        payload["choice_result"] = choice_result
    if completed_quests:
        payload["completed_quests"] = completed_quests
    if opened_chapters:
        payload["opened_chapter"] = opened_chapters[0]
    if next_quests:
        next_quest = next_quests[0]
        payload["next_quest"] = next_quest
    handoff = _transition_handoff_for_completed(after, completed_quests)
    if handoff is None and next_quests:
        handoff = _transition_handoff(after, next_quests[0]["id"])
    if handoff:
        payload["handoff"] = handoff
    return payload


def result_cards(card_texts: list[str]) -> list[dict[str, str]]:
    return [{"text": text} for text in card_texts if text]


def roll_result_card(roll_entry: RollLogEntry, outcome: str, locale: str) -> str:
    key = (
        "runtime.roll.result.success"
        if outcome == "success"
        else "runtime.roll.result.failure"
    )
    return render(key, locale, check=roll_entry.check)


def action_target(runtime: GameRuntimeState, action: Action) -> GraphNode | None:
    target = first_ref(action.what) or first_ref(action.to)
    return runtime.graph.nodes.get(target or "")


def _choice_result_payload(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    if action.verb != "decide":
        return None
    quest_id = first_ref(action.what) or first_ref(action.to)
    if quest_id is None:
        return None
    quest = after.graph.nodes.get(quest_id)
    if quest is None or quest.type != "quest":
        return None

    payload: dict[str, Any] = {"quest": _node_ref(after, quest)}
    choice_id = action.how
    if choice_id is not None:
        choice = quest_choices(quest).get(choice_id)
        label = choice.get("label") if isinstance(choice, dict) else None
        payload["choice"] = {
            "id": choice_id,
            "label": label if isinstance(label, str) and label else choice_id,
        }
    gained_items = _gained_inventory_items(before, after)
    if gained_items:
        payload["gained_items"] = gained_items
    return payload if len(payload) > 1 else None


def _gained_inventory_items(
    before: GameRuntimeState,
    after: GameRuntimeState,
) -> list[dict[str, Any]]:
    before_items = set(inventory_of(before.graph_index, before.progress.player_id))
    after_items = inventory_of(after.graph_index, after.progress.player_id)
    out: list[dict[str, Any]] = []
    for item_id in after_items:
        if item_id in before_items:
            continue
        item = after.graph.nodes.get(item_id)
        if item is not None and item.type == "item":
            out.append(_item_payload(after, item))
    return out


def _changed_nodes_by_status(
    before: GameRuntimeState,
    after: GameRuntimeState,
    *,
    node_type: str,
    to_status: str,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for node_id, after_node in after.graph.nodes.items():  # ssot-allow: attribute-only status diff
        if after_node.type != node_type:
            continue
        before_node = before.graph.nodes.get(node_id)
        if before_node is None or before_node.type != node_type:
            continue
        if before_node.properties.get("status") == to_status:
            continue
        if after_node.properties.get("status") != to_status:
            continue
        out.append({"id": node_id, "name": node_label(after.content, after_node)})
    return out


def _transition_handoff(runtime: GameRuntimeState, quest_id: str) -> str | None:
    quest = runtime.graph.nodes.get(quest_id)
    if quest is None or quest.type != "quest":
        return None
    return node_text(runtime.content, quest, "handoff")


def _transition_handoff_for_completed(
    runtime: GameRuntimeState,
    completed_quests: list[dict[str, str]],
) -> str | None:
    for quest in completed_quests:
        handoff = _transition_handoff(runtime, quest["id"])
        if handoff:
            return handoff
    return None


def arrival_branch_results(
    before: GameRuntimeState,
    after: GameRuntimeState,
) -> list[str]:
    before_place_id = location_of(before.graph_index, before.progress.player_id)
    after_place_id = location_of(after.graph_index, after.progress.player_id)
    if before_place_id == after_place_id or after_place_id is None:
        return []
    place = after.graph.nodes.get(after_place_id)
    if place is None or place.type != "location":
        return []
    return [
        text
        for branch in _dicts(place.properties.get("arrival_branches"))
        if (text := _arrival_branch_text(after, branch))
    ]


def travel_results(
    before: GameRuntimeState,
    after: GameRuntimeState,
) -> list[str]:
    before_place_id = location_of(before.graph_index, before.progress.player_id)
    after_place_id = location_of(after.graph_index, after.progress.player_id)
    if (
        before_place_id is None
        or after_place_id is None
        or before_place_id == after_place_id
    ):
        return []
    for edge in edges_from(after.graph_index, before_place_id, "connects_to"):
        if edge.to_node_id != after_place_id:
            continue
        text = edge.properties.get("travel_text")
        if isinstance(text, str) and text:
            return [text]
    return []


def _arrival_branch_text(
    runtime: GameRuntimeState,
    branch: dict[str, Any],
) -> str:
    property_name = branch.get("inventory_item_property")
    if not isinstance(property_name, str) or not property_name:
        return ""
    if _player_inventory_has_truthy_item_property(runtime, property_name):
        text = branch.get("text")
    else:
        text = branch.get("else_text")
    return text if isinstance(text, str) and text else ""


def _player_inventory_has_truthy_item_property(
    runtime: GameRuntimeState,
    property_name: str,
) -> bool:
    for item_id in inventory_of(runtime.graph_index, runtime.progress.player_id):
        item = runtime.graph.nodes.get(item_id)
        if item is not None and item.properties.get(property_name) is True:
            return True
    return False


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
