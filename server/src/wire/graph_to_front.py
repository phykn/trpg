from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph_query import (
    characters_at,
    edges_from,
    edges_to,
    location_of,
    nodes_of_type,
)
from src.game.domain.memory import LogEntry
from src.game.engines.growth import xp_for_next_level
from src.game.runtime.state import GameRuntimeState
from src.llm.context.graph_combat import hp_state, mp_state
from src.wire.labels import difficulty_badge
from src.wire.models import (
    DifficultyBadge,
    PendingConfirmationPayload,
    QuestPayload,
    QuestRewards,
)


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
    level: int
    gold: int
    exp: int
    exp_max: int
    can_level_up: bool
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
    quest: QuestPayload | None
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
        quest=_quest_payload(runtime),
        place=_place_payload(graph, player_id),
        combat=_combat_payload(runtime),
        pending_confirmation=_pending_confirmation_payload(
            runtime.progress.pending_confirmation
        ),
        log=list(runtime.log_entries),
    )


def _quest_payload(runtime: GameRuntimeState) -> QuestPayload | None:
    graph = runtime.graph
    active_quest_id = runtime.progress.active_quest_id
    if active_quest_id is not None:
        quest = graph.nodes.get(active_quest_id)
        if quest is not None and quest.type == "quest":
            return _build_quest_payload(graph, quest)

    active = _first_quest_with_status(graph, "active")
    if active is not None:
        return _build_quest_payload(graph, active)

    location_id = location_of(graph, runtime.progress.player_id)
    if location_id is None:
        return None
    visible_characters = set(characters_at(graph, location_id))
    for edge in graph.edges.values():
        if edge.type != "gives_quest" or edge.from_node_id not in visible_characters:
            continue
        quest = graph.nodes.get(edge.to_node_id)
        if quest is None or quest.type != "quest":
            continue
        if _quest_status(quest) in {"locked", "pending"}:
            return _build_quest_payload(graph, quest)
    return None


def _first_quest_with_status(graph: Graph, status: str) -> GraphNode | None:
    for quest in nodes_of_type(graph, "quest"):
        if _quest_status(quest) == status:
            return quest
    return None


def _build_quest_payload(graph: Graph, quest: GraphNode) -> QuestPayload:
    status = _quest_status(quest)
    display_status = (
        status
        if status in {"pending", "active", "completed", "failed"}
        else "pending"
    )
    actions: list[Literal["accept", "abandon"]] = []
    if status in {"locked", "pending"}:
        actions.append("accept")
    elif status == "active":
        actions.append("abandon")

    tier = _optional_str(quest.properties.get("difficulty")) or "normal"
    badge = difficulty_badge(tier)
    goals = _quest_goals(quest)
    done, total = _quest_progress(quest)
    return QuestPayload(
        id=quest.id,
        title=_optional_str(quest.properties.get("title")) or quest.id,
        summary=_optional_str(quest.properties.get("summary")) or "",
        giver=_quest_giver_name(graph, quest.id),
        difficulty=DifficultyBadge(label=badge["label"], tone=badge["tone"]),
        goals=goals,
        progress_label=_progress_label(done, total),
        rewards=_quest_rewards(quest),
        status=display_status,
        actions=actions,
    )


def _quest_status(quest: GraphNode) -> str:
    status = quest.properties.get("status")
    return status if isinstance(status, str) else "locked"


def _quest_goals(quest: GraphNode) -> list[str]:
    raw = quest.properties.get("triggers", [])
    if not isinstance(raw, list):
        return []
    goals: list[str] = []
    for trigger in raw:
        if not isinstance(trigger, dict):
            continue
        name = trigger.get("name")
        if isinstance(name, str) and name:
            goals.append(name)
    return goals


def _quest_progress(quest: GraphNode) -> tuple[int, int]:
    raw_goals = quest.properties.get("triggers", [])
    raw_met = quest.properties.get("triggers_met", [])
    total = len(raw_goals) if isinstance(raw_goals, list) else 0
    if not isinstance(raw_met, list):
        return 0, total
    return sum(1 for item in raw_met[:total] if item is True), total


def _progress_label(done: int, total: int) -> str:
    if total == 0:
        return ""
    if done >= total:
        return "✓"
    return f"{done}/{total}"


def _quest_rewards(quest: GraphNode) -> QuestRewards:
    raw = quest.properties.get("rewards", {})
    if not isinstance(raw, dict):
        return QuestRewards(gold=0, exp=0)
    gold = raw.get("gold")
    exp = raw.get("exp")
    return QuestRewards(
        gold=gold if isinstance(gold, int) else 0,
        exp=exp if isinstance(exp, int) else 0,
    )


def _quest_giver_name(graph: Graph, quest_id: str) -> str:
    for edge in edges_to(graph, quest_id, "gives_quest"):
        giver = graph.nodes.get(edge.from_node_id)
        if giver is not None:
            return _name(giver)
    return ""


def _hero_payload(player: GraphNode) -> GraphHeroPayload:
    level = _int_prop_default(player, "level", 1)
    exp = _int_prop_default(player, "xp_pool", 0)
    exp_max = xp_for_next_level(level)
    return GraphHeroPayload(
        id=player.id,
        name=_name(player),
        level=level,
        gold=_int_prop_default(player, "gold", 0),
        exp=exp,
        exp_max=exp_max,
        can_level_up=exp >= exp_max,
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


def _int_prop_default(node: GraphNode, key: str, default: int) -> int:
    value = node.properties.get(key)
    return value if isinstance(value, int) else default


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
