from __future__ import annotations

from typing import Any

from src.game.domain.content import node_label
from src.game.domain.graph import GraphNode
from src.game.domain.graph.query import edges_from, location_of
from src.game.domain.quest import quest_choices, quest_ready_to_decide
from src.game.runtime.state import GameRuntimeState


def active_quest(runtime: GameRuntimeState) -> dict[str, Any] | None:
    quest_id = runtime.progress.active_quest_id
    node = runtime.graph.nodes.get(quest_id or "")
    if node is None or node.type != "quest":
        return None
    payload: dict[str, Any] = {
        "id": node.id,
        "name": node_label(runtime.content, node),
    }
    location_targets = quest_location_targets(node)
    if location_targets:
        payload["location_targets"] = location_targets
    location_routes = quest_location_routes(runtime, node, location_targets)
    if location_routes:
        payload["location_routes"] = location_routes
    choices = quest_choice_payloads(node) if quest_ready_to_decide(node) else []
    if choices:
        payload["choices"] = choices
    return payload


def available_quests(
    runtime: GameRuntimeState,
    visible_targets: list[dict[str, Any]],
    current_active_quest: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if current_active_quest is not None:
        return []
    visible_by_id = {
        target["id"]: target
        for target in visible_targets
        if isinstance(target.get("id"), str)
        and isinstance(target.get("name"), str)
        and target.get("type") in {"npc", "enemy"}
    }
    out: list[dict[str, Any]] = []
    for node in runtime.graph.nodes.values():
        if node.type != "quest":
            continue
        status = node.properties.get("status")
        if status not in {"pending", "abandoned"}:
            continue
        giver_id = node.properties.get("giver")
        if not isinstance(giver_id, str) or giver_id not in visible_by_id:
            continue
        giver = visible_by_id[giver_id]
        out.append(
            {
                "id": node.id,
                "name": node_label(runtime.content, node),
                "status": status,
                "giver": giver_id,
                "giver_name": giver["name"],
            }
        )
    return out


def quest_ids(
    runtime: GameRuntimeState,
    current_available_quests: list[dict[str, Any]] | None = None,
) -> list[str]:
    ids = [runtime.progress.active_quest_id] if runtime.progress.active_quest_id else []
    ids.extend(
        quest["id"]
        for quest in (current_available_quests or [])
        if isinstance(quest.get("id"), str)
    )
    return ids


def quest_choice_ids(runtime: GameRuntimeState) -> list[str]:
    quest_id = runtime.progress.active_quest_id
    node = runtime.graph.nodes.get(quest_id or "")
    if node is None or node.type != "quest":
        return []
    if not quest_ready_to_decide(node):
        return []
    return [choice["id"] for choice in quest_choice_payloads(node)]


def quest_location_targets(node: GraphNode) -> list[str]:
    out: list[str] = []
    raw = node.properties.get("triggers")
    if not isinstance(raw, list):
        return out
    for trigger in raw:
        if not isinstance(trigger, dict):
            continue
        if trigger.get("type") != "location_enter":
            continue
        target = trigger.get("target")
        if isinstance(target, str):
            out.append(target)
    return list(dict.fromkeys(out))


def quest_location_routes(
    runtime: GameRuntimeState,
    node: GraphNode,
    location_targets: list[str],
) -> list[dict[str, str]]:
    graph = runtime.graph_index
    current_id = location_of(graph, runtime.progress.player_id)
    if current_id is None:
        return []
    out: list[dict[str, str]] = []
    for target_id in location_targets:
        target = graph.nodes.get(target_id)
        if target is None or target.type != "location":
            continue
        next_exit_id = (
            target_id
            if any(
                edge.to_node_id == target_id
                for edge in edges_from(graph, current_id, "connects_to")
            )
            else first_step_toward_location(graph, current_id, target_id)
        )
        if next_exit_id is None:
            continue
        next_exit = graph.nodes.get(next_exit_id)
        if next_exit is None or next_exit.type != "location":
            continue
        out.append(
            {
                "target_id": target_id,
                "target_name": node_label(runtime.content, target),
                "next_exit_id": next_exit_id,
                "next_exit_name": node_label(runtime.content, next_exit),
            }
        )
    return out


def first_step_toward_location(
    graph,
    current_id: str,
    target_id: str,
) -> str | None:
    queue: list[tuple[str, str | None]] = [(current_id, None)]
    visited = {current_id}
    while queue:
        location_id, first_step = queue.pop(0)
        for edge in edges_from(graph, location_id, "connects_to"):
            if edge.to_node_id in visited:
                continue
            step = first_step or edge.to_node_id
            if edge.to_node_id == target_id:
                return step
            visited.add(edge.to_node_id)
            queue.append((edge.to_node_id, step))
    return None


def quest_choice_payloads(node: GraphNode) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for choice_id, choice in quest_choices(node).items():  # ssot-allow: quest choice attribute map
        label = choice.get("label")
        out.append(
            {
                "id": choice_id,
                "label": label if isinstance(label, str) and label else choice_id,
            }
        )
    return out
