from __future__ import annotations

from src.game.domain.content import node_value
from src.game.domain.graph import GraphNode
from src.game.domain.graph.query import edges_from, location_of
from src.locale.generated_story import is_generated_current_location_memory

from ...state import GameRuntimeState


def discoveries_payload(runtime: GameRuntimeState) -> dict[str, list[dict[str, str]]]:
    player_id = runtime.progress.player_id
    place_id = location_of(runtime.graph_index, player_id)
    anchors = {player_id}
    if place_id:
        anchors.add(place_id)
    memories: list[dict[str, str]] = []
    clues: list[dict[str, str]] = []
    for anchor_id in anchors:
        for entry in knowledge_payloads_from_anchor(runtime, anchor_id):
            kind = entry.pop("kind", "")
            if kind == "memory":
                memories.append(entry)
            elif kind == "clue":
                clues.append(entry)
    payload: dict[str, list[dict[str, str]]] = {}
    if memories:
        payload["memories"] = memories[-5:]
    if clues:
        payload["clues"] = clues[-5:]
    return payload


def revealed_fact_payloads(
    runtime: GameRuntimeState,
    node: GraphNode | None,
) -> list[dict[str, str]]:
    if node is None:
        return []
    out: list[dict[str, str]] = []
    for edge in edges_from(runtime.graph_index, node.id, "has_knowledge"):
        knowledge = runtime.graph.nodes.get(edge.to_node_id)
        if knowledge is None or knowledge.type != "knowledge":
            continue
        visibility = node_value(runtime.content, knowledge, "visibility")
        reveal_on_success = node_value(
            runtime.content,
            knowledge,
            "reveal_on_success",
        )
        if visibility != "public" and reveal_on_success is not True:
            continue
        payload = knowledge_summary_payload(runtime, knowledge)
        if len(payload) > 1:
            out.append(payload)
    return out


def public_knowledge_payloads(
    runtime: GameRuntimeState,
    node: GraphNode,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for edge in edges_from(runtime.graph_index, node.id, "has_knowledge"):
        knowledge = runtime.graph.nodes.get(edge.to_node_id)
        if knowledge is None or knowledge.type != "knowledge":
            continue
        visibility = node_value(runtime.content, knowledge, "visibility")
        if visibility != "public":
            continue
        payload = knowledge_summary_payload(runtime, knowledge)
        if len(payload) > 1:
            out.append(payload)
    return out


def knowledge_payloads_from_anchor(
    runtime: GameRuntimeState,
    anchor_id: str,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for edge in edges_from(runtime.graph_index, anchor_id, "has_knowledge"):
        knowledge = runtime.graph.nodes.get(edge.to_node_id)
        if knowledge is None or knowledge.type != "knowledge":
            continue
        visibility = node_value(runtime.content, knowledge, "visibility")
        if visibility != "player":
            continue
        kind = node_value(runtime.content, knowledge, "kind")
        if kind not in {"memory", "clue"}:
            continue
        title = node_value(runtime.content, knowledge, "title")
        summary = node_value(runtime.content, knowledge, "summary")
        if is_generated_current_location_memory(
            kind=kind,
            title=title,
            summary=summary,
        ):
            continue
        payload: dict[str, str] = {"id": knowledge.id, "kind": kind}
        if isinstance(title, str) and title:
            payload["title"] = title
        if isinstance(summary, str) and summary:
            payload["summary"] = summary
        if "summary" in payload or "title" in payload:
            out.append(payload)
    return out


def knowledge_summary_payload(
    runtime: GameRuntimeState,
    knowledge: GraphNode,
) -> dict[str, str]:
    payload: dict[str, str] = {"id": knowledge.id}
    title = node_value(runtime.content, knowledge, "title")
    if isinstance(title, str) and title:
        payload["title"] = title
    summary = node_value(runtime.content, knowledge, "summary")
    if isinstance(summary, str) and summary:
        payload["summary"] = summary
    return payload
