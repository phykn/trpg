import re
from typing import Any

from src.game.domain.action import Action
from src.game.domain.content import node_label, node_text, node_value
from src.game.domain.graph import GraphNode
from src.game.domain.graph_character import graph_character_kind, is_visible_character
from src.game.domain.graph_query import (
    characters_at,
    edges_from,
    inventory_of,
    items_at,
    location_of,
)
from src.locale.render import render

from .combat_narration_view import combat_narration_view
from .dispatch import GraphActionDispatchResult
from .memory_context import (
    narrate_recent_dialogue_payload,
    related_memory_payload,
)
from .state import GameRuntimeState


def build_intro_narration_payload(runtime: GameRuntimeState) -> dict[str, Any]:
    graph = runtime.graph_index
    player_id = runtime.progress.player_id
    place_id = location_of(graph, player_id)
    place = graph.nodes.get(place_id or "")
    player = graph.nodes.get(player_id)
    return {
        "player": _node_ref(runtime, player),
        "place": _place_payload(runtime, place),
        "visible_targets": _visible_character_payloads(
            runtime,
            place_id,
            exclude_id=player_id,
        ),
        "visible_items": _visible_item_payloads(runtime, place_id),
        "exits": _exit_payloads(runtime, place_id),
        "inventory": _inventory_payloads(runtime, player_id),
    }


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
    return {
        "player_input": None,
        "current_place": _node_ref(after, place),
        "current_event": {
            "kind": dispatch.kind,
            "outcome": dispatch.outcome,
            "action": action.model_dump(mode="json", by_alias=True, exclude_none=True),
            "resolved_results": card_texts,
        },
        "scene_anchor": scene_anchor,
        "target_view": _target_view(after, target),
        "result_cards": _result_cards(card_texts),
        "related_memory": related_memory_payload(
            after,
            action=action,
            target=target,
        ),
        "recent_dialogue": narrate_recent_dialogue_payload(after),
        "combat_view": combat_narration_view(
            after,
            trace=dispatch.combat_trace,
            outcome=dispatch.outcome,
        ),
        "budget": _narrate_budget(after),
    }


def build_input_narration_payload(
    *,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    dialogue_target: GraphNode | None,
) -> dict[str, Any]:
    return {
        "player_input": player_input,
        "current_event": _input_current_event(runtime, action, dialogue_target),
        "scene_anchor": _scene_anchor(runtime),
        "target_view": _target_view(
            runtime,
            dialogue_target,
            player_input=player_input,
        ),
        "result_cards": [],
        "related_memory": related_memory_payload(
            runtime,
            action=action,
            target=dialogue_target,
        ),
        "recent_dialogue": narrate_recent_dialogue_payload(runtime),
        "combat_view": combat_narration_view(runtime),
        "budget": _narrate_budget(runtime),
    }


def _place_payload(
    runtime: GameRuntimeState,
    node: GraphNode | None,
) -> dict[str, str] | None:
    if node is None or node.type != "location":
        return None
    payload = {"id": node.id, "name": node_label(runtime.content, node)}
    description = node_text(runtime.content, node, "description")
    if description:
        payload["description"] = description
    return payload


def _visible_character_payloads(
    runtime: GameRuntimeState,
    place_id: str | None,
    *,
    exclude_id: str,
) -> list[dict[str, str]]:
    if place_id is None:
        return []
    out: list[dict[str, str]] = []
    for character_id in characters_at(runtime.graph_index, place_id):
        if character_id == exclude_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character" or not is_visible_character(node):
            continue
        out.append(
            {
                "id": node.id,
                "name": node_label(runtime.content, node),
                "type": graph_character_kind(node),
            }
        )
    return out


def _visible_item_payloads(
    runtime: GameRuntimeState,
    place_id: str | None,
) -> list[dict[str, str]]:
    if place_id is None:
        return []
    out: list[dict[str, str]] = []
    for item_id in items_at(runtime.graph_index, place_id):
        item = runtime.graph.nodes.get(item_id)
        if item is None or item.type != "item":
            continue
        out.append(_item_payload(runtime, item))
    return out


def _exit_payloads(
    runtime: GameRuntimeState,
    place_id: str | None,
) -> list[dict[str, str]]:
    if place_id is None:
        return []
    out: list[dict[str, str]] = []
    for edge in edges_from(runtime.graph_index, place_id, "connects_to"):
        target = runtime.graph.nodes.get(edge.to_node_id)
        if target is not None and target.type == "location":
            out.append({"id": target.id, "name": node_label(runtime.content, target)})
    return out


def _inventory_payloads(
    runtime: GameRuntimeState,
    player_id: str,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item_id in inventory_of(runtime.graph_index, player_id):
        item = runtime.graph.nodes.get(item_id)
        if item is not None and item.type == "item":
            out.append(_item_payload(runtime, item))
    return out


def _item_payload(runtime: GameRuntimeState, item: GraphNode) -> dict[str, str]:
    kind = node_value(runtime.content, item, "kind") or node_value(
        runtime.content,
        item,
        "type",
    )
    return {
        "id": item.id,
        "name": node_label(runtime.content, item),
        "kind": kind if isinstance(kind, str) and kind else "item",
    }


def _node_ref(runtime: GameRuntimeState, node: GraphNode | None) -> dict[str, str]:
    if node is None:
        return {"id": "", "name": render("runtime.none", runtime.progress.locale)}
    return {"id": node.id, "name": node_label(runtime.content, node)}


def _scene_anchor(runtime: GameRuntimeState) -> dict[str, Any]:
    graph = runtime.graph_index
    player_id = runtime.progress.player_id
    place_id = location_of(graph, player_id)
    place = runtime.graph.nodes.get(place_id or "")
    visible_names = [
        entry["name"]
        for entry in [
            *_visible_character_payloads(runtime, place_id, exclude_id=player_id),
            *_visible_item_payloads(runtime, place_id),
            *_exit_payloads(runtime, place_id),
        ][:5]
    ]
    return {
        "location": _node_ref(runtime, place),
        "visible_names": visible_names,
    }


def _target_view(
    runtime: GameRuntimeState,
    node: GraphNode | None,
    *,
    player_input: str | None = None,
) -> dict[str, Any] | None:
    if node is None:
        return None
    payload = _node_ref(runtime, node)
    payload["type"] = node.type
    role = node_value(runtime.content, node, "role")
    if isinstance(role, str) and role:
        payload["known_role"] = role
    tone_hint = node_text(runtime.content, node, "tone_hint")
    if tone_hint:
        payload["tone_hint"] = tone_hint
    hints = _string_list_value(runtime, node, "hints")
    if hints:
        payload["known_hints"] = hints[:3]
    available_items = _mentioned_inventory_payloads(runtime, node, player_input)
    if available_items:
        payload["available_items"] = available_items
    return payload


def _mentioned_inventory_payloads(
    runtime: GameRuntimeState,
    node: GraphNode,
    player_input: str | None,
) -> list[dict[str, Any]]:
    if node.type != "character" or not player_input:
        return []
    out: list[dict[str, Any]] = []
    for item_id in inventory_of(runtime.graph_index, node.id):
        item = runtime.graph.nodes.get(item_id)
        if item is None or item.type != "item":
            continue
        if not _item_mentioned(
            player_input, node_label(runtime.content, item), item.id
        ):
            continue
        payload: dict[str, Any] = _item_payload(runtime, item)
        price = node_value(runtime.content, item, "price")
        if isinstance(price, int | float):
            payload["price"] = price
        out.append(payload)
    return out


def _item_mentioned(player_input: str, item_name: str, item_id: str) -> bool:
    normalized_input = _normalize_for_match(player_input)
    normalized_name = _normalize_for_match(item_name)
    if normalized_name and normalized_name in normalized_input:
        return True
    normalized_id = _normalize_for_match(item_id)
    if normalized_id and normalized_id in normalized_input:
        return True
    name_tokens = [
        _normalize_for_match(token)
        for token in re.split(r"\s+", item_name)
        if len(_normalize_for_match(token)) >= 2
    ]
    return sum(1 for token in name_tokens if token in normalized_input) >= 2


def _normalize_for_match(text: str) -> str:
    hangul_range = f"{chr(0xAC00)}-{chr(0xD7A3)}"
    return re.sub(rf"[^0-9A-Za-z{hangul_range}]+", "", text).lower()


def _string_list_value(
    runtime: GameRuntimeState,
    node: GraphNode,
    key: str,
) -> list[str]:
    value = node_value(runtime.content, node, key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _input_current_event(
    runtime: GameRuntimeState,
    action: Action,
    dialogue_target: GraphNode | None,
) -> dict[str, Any]:
    return {
        "kind": "dialogue" if dialogue_target is not None else "input",
        "target": _target_view(runtime, dialogue_target),
        "action": action.model_dump(mode="json", by_alias=True, exclude_none=True),
        "outcome": (
            "player_addresses_target"
            if dialogue_target is not None
            else "player_action_pending_narration"
        ),
    }


def _result_cards(card_texts: list[str]) -> list[dict[str, str]]:
    return [{"text": text} for text in card_texts if text]


def _narrate_budget(runtime: GameRuntimeState) -> dict[str, int]:
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    visible_count = (
        len(
            _visible_character_payloads(
                runtime, place_id, exclude_id=runtime.progress.player_id
            )
        )
        + len(_visible_item_payloads(runtime, place_id))
        + len(_exit_payloads(runtime, place_id))
    )
    return {
        "visible_names_omitted": max(0, visible_count - 5),
        "related_memory_omitted": 0,
        "recent_dialogue_omitted": max(0, len(runtime.recent_dialogue) - 5),
        "result_cards_omitted": 0,
    }


def _action_target(runtime: GameRuntimeState, action: Action) -> GraphNode | None:
    target_id = _single(action.what) or _single(action.to)
    return runtime.graph.nodes.get(target_id or "")


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None
