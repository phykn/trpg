from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from src.game.domain.entities import (
    Chapter,
    Character,
    Equipment,
    Item,
    Location,
    Quest,
    Race,
    Skill,
    Stats,
)
from src.game.domain.graph import EdgeType, Graph, GraphEdge, GraphNode, NodeType
from src.game.domain.progress import GameProgress
from src.game.engines.growth import calc_max_hp, calc_max_mp
from src.game.rules.config import RULES
from src.game.seed.player import PlayerInput


class SeedGraphBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: Graph
    progress: GameProgress


def build_seed_graph(
    *,
    profile_name: str,
    player: PlayerInput,
    races: dict[str, Race],
    locations: dict[str, Location],
    items: dict[str, Item],
    skills: dict[str, Skill],
    npcs: dict[str, Character],
    quests: dict[str, Quest],
    chapters: dict[str, Chapter],
    start: dict[str, Any],
    template: dict[str, Any],
    game_id: str,
    locale: str = "ko",
) -> SeedGraphBundle:
    del profile_name

    player_char = _build_player(player, races, start, template)
    characters = {**npcs, player_char.id: player_char}

    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}

    def add_node(
        node_id: str,
        node_type: NodeType,
        properties: dict[str, Any],
    ) -> None:
        nodes[node_id] = GraphNode(id=node_id, type=node_type, properties=properties)

    def add_edge(
        edge_type: EdgeType,
        from_node_id: str,
        to_node_id: str,
        properties: dict[str, Any] | None = None,
        *,
        edge_id: str | None = None,
    ) -> None:
        resolved_id = edge_id or f"{edge_type}:{from_node_id}:{to_node_id}"
        edges[resolved_id] = GraphEdge(
            id=resolved_id,
            type=edge_type,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            properties=properties or {},
        )

    for character in characters.values():
        add_node(
            character.id,
            "character",
            _character_graph_properties(character),
        )
    for item in items.values():
        add_node(item.id, "item", item.model_dump(mode="json"))
    for location in locations.values():
        add_node(
            location.id,
            "location",
            location.model_dump(mode="json", exclude={"item_ids", "connections"}),
        )
    for quest in quests.values():
        add_node(
            quest.id,
            "quest",
            _quest_graph_properties(quest),
        )
    for skill in skills.values():
        add_node(skill.id, "skill", skill.model_dump(mode="json"))
    for race in races.values():
        add_node(
            race.id,
            "race",
            race.model_dump(mode="json", exclude={"racial_skill_ids"}),
        )
    for chapter in chapters.values():
        add_node(
            chapter.id,
            "chapter",
            chapter.model_dump(mode="json", exclude={"quest_ids"}),
        )

    for character in characters.values():
        if character.location_id:
            add_edge("located_at", character.id, character.location_id)
        if character.race_id:
            add_edge("belongs_to_race", character.id, character.race_id)
        equipped_item_ids = {
            item_id for _, item_id in character.equipment.equipped_items()
        }
        for slot, item_id in character.equipment.equipped_items():
            add_edge("equips", character.id, item_id, {"slot": slot})
        for item_id in character.inventory_ids:
            if item_id in equipped_item_ids:
                continue
            add_edge("carries", character.id, item_id)
        for skill_id in character.racial_skill_ids:
            add_edge(
                "knows_skill",
                character.id,
                skill_id,
                {"source": "racial"},
                edge_id=f"knows_skill:racial:{character.id}:{skill_id}",
            )
        for skill_id in character.learned_skill_ids:
            add_edge(
                "knows_skill",
                character.id,
                skill_id,
                {"source": "learned"},
                edge_id=f"knows_skill:learned:{character.id}:{skill_id}",
            )
        for companion_id in character.companions:
            add_edge("has_companion", character.id, companion_id)
        for target_id, affinity in character.relations.items():
            add_edge("relation", character.id, target_id, {"affinity": affinity})

    for location in locations.values():
        for item_id in location.item_ids:
            add_edge("located_at", item_id, location.id)
        for connection in location.connections:
            add_edge(
                "connects_to",
                location.id,
                connection.target_id,
                connection.model_dump(
                    mode="json",
                    exclude={"target_id"},
                    exclude_none=True,
                ),
            )

    for quest in quests.values():
        add_edge("gives_quest", quest.giver_id, quest.id)
        for trigger in quest.triggers:
            add_edge(
                "target_of",
                trigger.target_id,
                quest.id,
                trigger.model_dump(mode="json", exclude={"target_id"})
                | {"outcome": "success"},
                edge_id=f"target_of:{trigger.id}:{trigger.target_id}:{quest.id}",
            )
        for trigger in quest.fail_triggers:
            add_edge(
                "target_of",
                trigger.target_id,
                quest.id,
                trigger.model_dump(mode="json", exclude={"target_id"})
                | {"outcome": "failure"},
                edge_id=f"target_of:fail:{trigger.id}:{trigger.target_id}:{quest.id}",
            )
        for item_id in quest.rewards.items:
            add_edge("reward_of", item_id, quest.id)

    for race in races.values():
        for skill_id in race.racial_skill_ids:
            add_edge("grants_skill", race.id, skill_id)

    for chapter in chapters.values():
        for quest_id in chapter.quest_ids:
            add_edge("part_of_chapter", quest_id, chapter.id)

    progress = GameProgress(
        game_id=game_id,
        player_id=player_char.id,
        locale=locale,
        active_subject_id=start.get("active_subject_id"),
        active_quest_id=start.get("active_quest_id"),
    )
    return SeedGraphBundle(graph=Graph(nodes=nodes, edges=edges), progress=progress)


def _build_player(
    player: PlayerInput,
    races: dict[str, Race],
    start: dict[str, Any],
    template: dict[str, Any],
) -> Character:
    player_id = template.get("id", "player_01")
    stats = Stats()
    chosen_race = races[player.race_id]
    location_id = start["start_location_id"]

    player_char = Character(
        id=player_id,
        name=player.name,
        is_player=True,
        race_id=player.race_id,
        gender=player.gender,
        level=int(template.get("level", 1)),
        stats=stats,
        location_id=location_id,
        equipment=Equipment.model_validate(template.get("equipment", {})),
        inventory_ids=list(template.get("inventory_ids", [])),
        gold=int(template.get("gold", 0)),
        xp_pool=int(template.get("xp_pool", 0)),
        racial_skill_ids=list(chosen_race.racial_skill_ids),
        revive_coins=RULES.death.revive_coins,
    )
    player_char.max_hp = calc_max_hp(player_char.level, stats.CON)
    player_char.max_mp = calc_max_mp(player_char.level, stats.INT)
    player_char.hp = player_char.max_hp
    player_char.mp = player_char.max_mp
    player_char.visited_location_ids.add(location_id)
    return player_char


def _quest_graph_properties(quest: Quest) -> dict[str, Any]:
    properties = quest.model_dump(mode="json", exclude={"giver_id", "rewards"})
    properties["rewards"] = quest.rewards.model_dump(
        mode="json",
        exclude={"items"},
    )
    return properties


def _character_graph_properties(character: Character) -> dict[str, Any]:
    properties = character.model_dump(
        mode="json",
        exclude={
            "location_id",
            "equipment",
            "inventory_ids",
            "relations",
            "racial_skill_ids",
            "learned_skill_ids",
            "companions",
        },
    )
    properties["stats"] = _graph_stats(character.stats)
    return properties


def _graph_stats(stats: Stats) -> dict[str, int]:
    return {
        "body": (stats.STR + stats.CON) // 2,
        "agility": stats.DEX,
        "mind": (stats.INT + stats.WIS) // 2,
        "presence": stats.CHA,
    }
