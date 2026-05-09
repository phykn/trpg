from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph_query import characters_at, edges_from, location_of
from src.game.domain.memory import LogEntry
from src.game.runtime.state import GameRuntimeState
from src.llm.context.graph_combat import hp_state, mp_state
from src.wire.models import PendingConfirmationPayload


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class GraphResourcePayload(_CamelModel):
    current: int
    maximum: int
    state: str


class GraphHeroPayload(_CamelModel):
    id: str
    name: str
    resources: dict[Literal["hp", "mp"], GraphResourcePayload]
    stats: dict[str, int]


class GraphPlaceLinkPayload(_CamelModel):
    id: str
    name: str
    description: str


class GraphPlaceTargetPayload(_CamelModel):
    id: str
    name: str
    hp: GraphResourcePayload


class GraphPlacePayload(_CamelModel):
    id: str
    name: str
    description: str
    exits: list[GraphPlaceLinkPayload]
    targets: list[GraphPlaceTargetPayload]


class GraphCombatParticipantPayload(_CamelModel):
    id: str
    name: str
    side: Literal["player", "enemy"]
    hp: GraphResourcePayload
    mp: GraphResourcePayload | None = None


class GraphCombatPayload(_CamelModel):
    round: int
    outcome: Literal["ongoing", "victory", "defeat", "fled"]
    participants: list[GraphCombatParticipantPayload]


class GraphFrontStatePayload(_CamelModel):
    hero: GraphHeroPayload
    place: GraphPlacePayload | None
    combat: GraphCombatPayload | None
    pending_confirmation: PendingConfirmationPayload | None
    log: list[LogEntry]


def graph_to_front_state(runtime: GameRuntimeState) -> GraphFrontStatePayload:
    graph = runtime.graph
    player_id = runtime.progress.player_id
    player = _require_node(graph, player_id, "character")
    return GraphFrontStatePayload(
        hero=_hero_payload(player),
        place=_place_payload(graph, player_id),
        combat=_combat_payload(runtime),
        pending_confirmation=_pending_confirmation_payload(
            runtime.progress.pending_confirmation
        ),
        log=list(runtime.log_entries),
    )


def _hero_payload(player: GraphNode) -> GraphHeroPayload:
    return GraphHeroPayload(
        id=player.id,
        name=_name(player),
        resources={
            "hp": _resource(player, "hp", "max_hp"),
            "mp": _resource(player, "mp", "max_mp"),
        },
        stats=_stats(player),
    )


def _place_payload(graph: Graph, player_id: str) -> GraphPlacePayload | None:
    location_id = location_of(graph, player_id)
    if location_id is None:
        return None
    location = graph.nodes.get(location_id)
    if location is None or location.type != "location":
        return None

    exits: list[GraphPlaceLinkPayload] = []
    for edge in edges_from(graph, location_id, "connects_to"):
        target = graph.nodes.get(edge.to_node_id)
        if target is None or target.type != "location":
            continue
        exits.append(_place_link(target))

    targets: list[GraphPlaceTargetPayload] = []
    for character_id in characters_at(graph, location_id):
        if character_id == player_id:
            continue
        target = _require_node(graph, character_id, "character")
        targets.append(
            GraphPlaceTargetPayload(
                id=target.id,
                name=_name(target),
                hp=_resource(target, "hp", "max_hp"),
            )
        )

    return GraphPlacePayload(
        id=location.id,
        name=_name(location),
        description=_optional_str(location.properties.get("description")) or "",
        exits=exits,
        targets=targets,
    )


def _combat_payload(runtime: GameRuntimeState) -> GraphCombatPayload | None:
    state = runtime.progress.graph_combat_state
    if state is None:
        return None

    participants: list[GraphCombatParticipantPayload] = []
    for participant_id in state.participant_ids:
        node = _require_node(runtime.graph, participant_id, "character")
        side = state.sides[participant_id]
        participants.append(
            GraphCombatParticipantPayload(
                id=node.id,
                name=_name(node),
                side=side,
                hp=_resource(node, "hp", "max_hp"),
                mp=_optional_resource(node, "mp", "max_mp"),
            )
        )

    return GraphCombatPayload(
        round=state.round,
        outcome=state.outcome,
        participants=participants,
    )


def _pending_confirmation_payload(
    pending: dict[str, object] | None,
) -> PendingConfirmationPayload | None:
    if pending is None:
        return None
    return PendingConfirmationPayload.model_validate(
        {
            "id": pending.get("id"),
            "kind": pending.get("kind"),
            "title": pending.get("title"),
            "body": pending.get("body"),
            "confirm_label": pending.get("confirm_label"),
            "cancel_label": pending.get("cancel_label"),
            "target_label": pending.get("target_label"),
        }
    )


def _place_link(location: GraphNode) -> GraphPlaceLinkPayload:
    return GraphPlaceLinkPayload(
        id=location.id,
        name=_name(location),
        description=_optional_str(location.properties.get("description")) or "",
    )


def _resource(
    node: GraphNode,
    current_key: Literal["hp", "mp"],
    max_key: Literal["max_hp", "max_mp"],
) -> GraphResourcePayload:
    current = _int_prop(node, current_key)
    maximum = _int_prop(node, max_key)
    state = (
        hp_state(current, maximum)
        if current_key == "hp"
        else mp_state(current, maximum)
    )
    return GraphResourcePayload(
        current=current,
        maximum=maximum,
        state=state or "drained",
    )


def _optional_resource(
    node: GraphNode,
    current_key: Literal["hp", "mp"],
    max_key: Literal["max_hp", "max_mp"],
) -> GraphResourcePayload | None:
    current = node.properties.get(current_key)
    maximum = node.properties.get(max_key)
    if not isinstance(current, int) or not isinstance(maximum, int) or maximum <= 0:
        return None
    return _resource(node, current_key, max_key)


def _require_node(graph: Graph, node_id: str, node_type: str) -> GraphNode:
    node = graph.nodes.get(node_id)
    if node is None:
        raise ValueError(f"missing node: {node_id}")
    if node.type != node_type:
        raise ValueError(f"node {node_id} is not {node_type}")
    return node


def _int_prop(node: GraphNode, key: str) -> int:
    value = node.properties.get(key)
    if not isinstance(value, int):
        raise ValueError(f"missing numeric property {node.id}.{key}")
    return value


def _stats(node: GraphNode) -> dict[str, int]:
    raw = node.properties.get("stats", {})
    if not isinstance(raw, dict):
        return {}
    return {
        key: value
        for key, value in sorted(raw.items())
        if isinstance(key, str) and isinstance(value, int)
    }


def _name(node: GraphNode) -> str:
    return _optional_str(node.properties.get("name")) or node.id


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
