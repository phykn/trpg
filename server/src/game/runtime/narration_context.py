from typing import Any

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatTraceEvent
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

from .dispatch import GraphActionDispatchResult
from .memory_context import important_history_payload, recent_dialogue_payload
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
    return {
        "player": _node_ref(after, after.graph.nodes.get(after.progress.player_id)),
        "current_place": _place_payload(after, place),
        "action": action.model_dump(mode="json", by_alias=True, exclude_none=True),
        "dispatch": {
            "kind": dispatch.kind,
            "outcome": dispatch.outcome,
            "applied": dispatch.applied,
        },
        "current_event": {
            "kind": dispatch.kind,
            "outcome": dispatch.outcome,
            "resolved_results": card_texts,
        },
        "resolved_results": card_texts,
        "visible_targets": _visible_character_payloads(
            after,
            place_id,
            exclude_id=after.progress.player_id,
        ),
        "visible_items": _visible_item_payloads(after, place_id),
        "exits": _exit_payloads(after, place_id),
        "recent_log": _recent_log_payload(before, include_gm=False),
        "important_history": important_history_payload(before),
        "recent_dialogue": recent_dialogue_payload(before),
        "combat": _combat_payload(after, dispatch),
    }


def build_input_narration_payload(
    *,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    dialogue_target: dict[str, str | None] | None,
    surroundings: dict[str, Any],
) -> dict[str, Any]:
    return {
        "player_input": player_input,
        "classified_action": action.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        ),
        "dialogue_target": dialogue_target,
        "surroundings": surroundings,
        "recent_log": _recent_log_payload(runtime),
        "important_history": important_history_payload(runtime),
        "recent_dialogue": recent_dialogue_payload(runtime),
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


def _recent_log_payload(
    runtime: GameRuntimeState,
    *,
    include_gm: bool = True,
) -> list[dict[str, str]]:
    return [
        {"kind": entry.kind, "text": entry.text}
        for entry in runtime.log_entries[-4:]
        if hasattr(entry, "text")
        and (include_gm or getattr(entry, "kind", None) != "gm")
    ]


def _combat_payload(
    runtime: GameRuntimeState,
    dispatch: GraphActionDispatchResult,
) -> dict[str, Any] | None:
    if dispatch.kind != "combat":
        return None
    return {
        "outcome": dispatch.outcome,
        "trace": [
            _combat_trace_payload(runtime, event) for event in dispatch.combat_trace
        ],
    }


def _combat_trace_payload(
    runtime: GameRuntimeState,
    event: GraphCombatTraceEvent,
) -> dict[str, Any]:
    actor = runtime.graph.nodes.get(event.actor_id or "")
    target = runtime.graph.nodes.get(event.target_id or "")
    return {
        "kind": event.kind,
        "actor": _node_ref(runtime, actor) if actor is not None else None,
        "target": _node_ref(runtime, target) if target is not None else None,
        "state": event.state,
    }
