from __future__ import annotations

from typing import Any

from src.game.domain.entities import (
    Chapter,
    Character,
    Connection,
    Equipment,
    Item,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Race,
    Skill,
)
from src.game.domain.graph import Graph, GraphEdge
from src.game.domain.state import GameState
from src.game.runtime.state import GameRuntimeState


def runtime_to_legacy_state(
    runtime: GameRuntimeState,
    *,
    profile_name: str,
) -> GameState:
    graph = runtime.graph
    characters = _characters_from_graph(graph)
    items = _nodes_as(graph, "item", Item)
    locations = _nodes_as(graph, "location", Location, defaults={"item_ids": []})
    races = _nodes_as(graph, "race", Race, defaults={"racial_skill_ids": []})
    skills = _nodes_as(graph, "skill", Skill)
    quests = _quests_from_graph(graph)
    chapters = _nodes_as(graph, "chapter", Chapter, defaults={"quest_ids": []})

    _restore_character_edges(graph, characters)
    _restore_location_edges(graph, locations)
    _restore_quest_edges(graph, quests)
    _restore_race_edges(graph, races)
    _restore_chapter_edges(graph, chapters)

    progress = runtime.progress
    return GameState(
        game_id=progress.game_id,
        profile=profile_name,
        locale=progress.locale,
        characters=characters,
        items=items,
        locations=locations,
        races=races,
        skills=skills,
        quests=quests,
        chapters=chapters,
        campaigns={},
        player_id=progress.player_id,
        active_subject_id=progress.active_subject_id,
        active_quest_id=progress.active_quest_id,
        turn_count=progress.turn_count,
        pending_check=progress.pending_check,
        pending_confirmation=progress.pending_confirmation,
        combat_state=progress.combat_state,
        previous_phase_signal=progress.previous_phase_signal,
        turn_log=list(runtime.turn_log),
        recent_dialogue=list(runtime.recent_dialogue),
        log_entries=list(runtime.log_entries),
        next_log_id=progress.next_log_id,
    )


def _nodes_as(
    graph: Graph,
    node_type: str,
    model_cls: type,
    *,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = {}
    for node in graph.nodes.values():
        if node.type != node_type:
            continue
        data = dict(defaults or {}) | dict(node.properties)
        out[node.id] = model_cls.model_validate(data)
    return out


def _characters_from_graph(graph: Graph) -> dict[str, Character]:
    return _nodes_as(
        graph,
        "character",
        Character,
        defaults={
            "equipment": Equipment().model_dump(mode="json"),
            "inventory_ids": [],
            "relations": {},
            "racial_skill_ids": [],
            "learned_skill_ids": [],
            "companions": [],
        },
    )


def _quests_from_graph(graph: Graph) -> dict[str, Quest]:
    return _nodes_as(
        graph,
        "quest",
        Quest,
        defaults={
            "giver_id": "",
            "triggers": [],
            "fail_triggers": [],
            "rewards": QuestRewards().model_dump(mode="json"),
        },
    )


def _edges(graph: Graph, edge_type: str) -> list[GraphEdge]:
    return sorted(
        (edge for edge in graph.edges.values() if edge.type == edge_type),
        key=lambda edge: edge.id,
    )


def _restore_character_edges(
    graph: Graph,
    characters: dict[str, Character],
) -> None:
    for edge in _edges(graph, "located_at"):
        if graph.nodes[edge.from_node_id].type == "character":
            characters[edge.from_node_id].location_id = edge.to_node_id
    for edge in _edges(graph, "belongs_to_race"):
        if edge.from_node_id in characters:
            characters[edge.from_node_id].race_id = edge.to_node_id
    for edge in _edges(graph, "carries"):
        if edge.from_node_id in characters:
            characters[edge.from_node_id].inventory_ids.append(edge.to_node_id)
    for edge in _edges(graph, "equips"):
        if edge.from_node_id not in characters:
            continue
        slot = edge.properties.get("slot")
        if isinstance(slot, str):
            setattr(characters[edge.from_node_id].equipment, slot, edge.to_node_id)
            if edge.to_node_id not in characters[edge.from_node_id].inventory_ids:
                characters[edge.from_node_id].inventory_ids.append(edge.to_node_id)
    for edge in _edges(graph, "knows_skill"):
        if edge.from_node_id not in characters:
            continue
        source = edge.properties.get("source")
        if source == "racial":
            characters[edge.from_node_id].racial_skill_ids.append(edge.to_node_id)
        else:
            characters[edge.from_node_id].learned_skill_ids.append(edge.to_node_id)
    for edge in _edges(graph, "has_companion"):
        if edge.from_node_id in characters:
            characters[edge.from_node_id].companions.append(edge.to_node_id)
    for edge in _edges(graph, "relation"):
        if edge.from_node_id not in characters:
            continue
        affinity = edge.properties.get("affinity")
        if isinstance(affinity, int):
            characters[edge.from_node_id].relations[edge.to_node_id] = affinity


def _restore_location_edges(
    graph: Graph,
    locations: dict[str, Location],
) -> None:
    for edge in _edges(graph, "located_at"):
        if graph.nodes[edge.from_node_id].type == "item":
            locations[edge.to_node_id].item_ids.append(edge.from_node_id)
    for edge in _edges(graph, "connects_to"):
        if edge.from_node_id not in locations:
            continue
        locations[edge.from_node_id].connections.append(
            Connection.model_validate(
                {"target_id": edge.to_node_id} | dict(edge.properties)
            )
        )


def _restore_quest_edges(
    graph: Graph,
    quests: dict[str, Quest],
) -> None:
    for edge in _edges(graph, "gives_quest"):
        if edge.to_node_id in quests:
            quests[edge.to_node_id].giver_id = edge.from_node_id
    for edge in _edges(graph, "target_of"):
        if edge.to_node_id not in quests:
            continue
        data = {
            key: value
            for key, value in edge.properties.items()
            if key != "outcome"
        }
        trigger = QuestTrigger.model_validate(
            data | {"target_id": edge.from_node_id}
        )
        if edge.properties.get("outcome") == "failure":
            quests[edge.to_node_id].fail_triggers.append(trigger)
        else:
            quests[edge.to_node_id].triggers.append(trigger)
    for edge in _edges(graph, "reward_of"):
        if edge.to_node_id in quests:
            quests[edge.to_node_id].rewards.items.append(edge.from_node_id)


def _restore_race_edges(graph: Graph, races: dict[str, Race]) -> None:
    for edge in _edges(graph, "grants_skill"):
        if edge.from_node_id in races:
            races[edge.from_node_id].racial_skill_ids.append(edge.to_node_id)


def _restore_chapter_edges(graph: Graph, chapters: dict[str, Chapter]) -> None:
    for edge in _edges(graph, "part_of_chapter"):
        if edge.to_node_id in chapters:
            chapters[edge.to_node_id].quest_ids.append(edge.from_node_id)
