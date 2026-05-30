from __future__ import annotations

from typing import Any

from src.game.domain.content import runtime_content_from_records
from src.game.domain.graph import EdgeType, Graph, GraphEdge, GraphNode, NodeType
from src.game.domain.progress import GameProgress
from src.game.seed.player import PlayerInput

from .coerce import (
    dict_list,
    equipped_items,
    mapping,
    optional_str,
    record_id,
    str_list,
)
from .edges import (
    add_action_edge,
    add_effect_edge,
    add_knowledge_edges,
    add_quest_target_edge,
    add_slot_edge,
)
from .properties import (
    build_player,
    character_graph_properties,
    node_properties,
    quest_graph_properties,
    record_properties,
)
from .types import SeedGraphBundle, SeedRecords

__all__ = ["SeedGraphBundle", "build_seed_graph"]


def build_seed_graph(
    *,
    profile_name: str,
    player: PlayerInput,
    races: SeedRecords,
    locations: SeedRecords,
    items: SeedRecords,
    skills: SeedRecords,
    npcs: SeedRecords,
    quests: SeedRecords,
    chapters: SeedRecords,
    start: dict[str, Any],
    template: dict[str, Any],
    game_id: str,
    locale: str = "ko",
    world_guidance: str = "",
    effects: SeedRecords | None = None,
    statuses: SeedRecords | None = None,
    slots: SeedRecords | None = None,
    factions: SeedRecords | None = None,
    actions: SeedRecords | None = None,
    knowledge: SeedRecords | None = None,
    dialogue_styles: SeedRecords | None = None,
    mbti: SeedRecords | None = None,
) -> SeedGraphBundle:
    player_record = build_player(player, races, start, template)
    characters = {**npcs, record_id(player_record): player_record}
    effect_records = effects or {}
    status_records = statuses or {}
    slot_records = slots or {}
    faction_records = factions or {}
    action_records = actions or {}
    knowledge_records = knowledge or {}
    dialogue_style_records = dialogue_styles or {}
    mbti_records = mbti or {}

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
            record_id(character),
            "character",
            character_graph_properties(character),
        )
    for item in items.values():
        add_node(record_id(item), "item", node_properties(item))
    for location in locations.values():
        add_node(
            record_id(location),
            "location",
            node_properties(location, exclude={"items", "connections"}),
        )
    for quest in quests.values():
        add_node(
            record_id(quest),
            "quest",
            quest_graph_properties(quest),
        )
    for skill in skills.values():
        add_node(record_id(skill), "skill", node_properties(skill))
    for effect in effect_records.values():
        add_node(
            record_id(effect),
            "effect",
            node_properties(effect),
        )
    for status in status_records.values():
        add_node(
            record_id(status),
            "status",
            node_properties(status),
        )
    for slot in slot_records.values():
        add_node(
            record_id(slot),
            "slot",
            node_properties(slot),
        )
    for faction in faction_records.values():
        add_node(
            record_id(faction),
            "faction",
            node_properties(faction, exclude={"relations"}),
        )
    for action in action_records.values():
        add_node(
            record_id(action),
            "action",
            node_properties(action),
        )
    for knowledge_record in knowledge_records.values():
        add_node(
            record_id(knowledge_record),
            "knowledge",
            node_properties(knowledge_record),
        )
    for dialogue_style in dialogue_style_records.values():
        add_node(
            record_id(dialogue_style),
            "dialogue_style",
            node_properties(dialogue_style),
        )
    for mbti_record in mbti_records.values():
        add_node(
            record_id(mbti_record),
            "mbti",
            node_properties(mbti_record),
        )
    for race in races.values():
        add_node(
            record_id(race),
            "race",
            node_properties(race, exclude={"racial_skills"}),
        )
    for chapter in chapters.values():
        add_node(
            record_id(chapter),
            "chapter",
            node_properties(chapter, exclude={"quests"}),
        )

    for character in characters.values():
        character_id = record_id(character)
        if location_id := optional_str(character.get("location")):
            add_edge("located_at", character_id, location_id)
        if race_id := optional_str(character.get("race")):
            add_edge("belongs_to_race", character_id, race_id)
        equipped_item_ids = {
            item_id for _, item_id in equipped_items(mapping(character.get("equipment")))
        }
        for slot, item_id in equipped_items(mapping(character.get("equipment"))):
            add_edge("equips", character_id, item_id, {"slot": slot})
        for item_id in str_list(character.get("inventory")):
            if item_id in equipped_item_ids:
                continue
            add_edge("carries", character_id, item_id)
        for skill_id in str_list(character.get("learned_skills")):
            add_edge(
                "knows_skill",
                character_id,
                skill_id,
                {"source": "learned", "tier": 1},
                edge_id=f"knows_skill:learned:{character_id}:{skill_id}",
            )
        for companion_id in str_list(character.get("companions")):
            add_edge("has_companion", character_id, companion_id)
        for target, affinity in mapping(character.get("relations")).items():
            if isinstance(target, str) and isinstance(affinity, int):
                add_edge("relation", character_id, target, {"affinity": affinity})
        if faction_id := optional_str(character.get("faction")):
            if faction_id in faction_records:
                add_edge("member_of_faction", character_id, faction_id)
        if dialogue_style_id := optional_str(character.get("dialogue_style")):
            if dialogue_style_id in dialogue_style_records:
                add_edge("uses_dialogue_style", character_id, dialogue_style_id)
        if mbti_id := optional_str(character.get("mbti")):
            if mbti_id in mbti_records:
                add_edge("has_mbti", character_id, mbti_id)
        add_knowledge_edges(add_edge, character, knowledge_records)

    for location in locations.values():
        location_id = record_id(location)
        add_knowledge_edges(add_edge, location, knowledge_records)
        for item_id in str_list(location.get("items")):
            add_edge("located_at", item_id, location_id)
        for connection in dict_list(location.get("connections")):
            target = optional_str(connection.get("target"))
            if target is None:
                continue
            add_edge(
                "connects_to",
                location_id,
                target,
                record_properties(connection, exclude={"target"}),
            )

    for quest in quests.values():
        quest_id = record_id(quest)
        giver_id = optional_str(quest.get("giver"))
        if giver_id is not None:
            add_edge("gives_quest", giver_id, quest_id)
        for trigger in dict_list(quest.get("triggers")):
            add_quest_target_edge(edges, trigger, quest_id, "success")
        for trigger in dict_list(quest.get("fail_triggers")):
            add_quest_target_edge(edges, trigger, quest_id, "failure")
        for item_id in str_list(mapping(quest.get("rewards")).get("items")):
            add_edge("reward_of", item_id, quest_id)

    for race in races.values():
        race_id = record_id(race)
        for skill_id in str_list(race.get("racial_skills")):
            add_edge("grants_skill", race_id, skill_id)

    for item in items.values():
        add_effect_edge(add_edge, item, "item", effect_records)
        add_slot_edge(add_edge, item, slot_records)
        add_knowledge_edges(add_edge, item, knowledge_records)
    for skill in skills.values():
        add_action_edge(add_edge, skill, action_records)

    for chapter in chapters.values():
        chapter_id = record_id(chapter)
        for quest_id in str_list(chapter.get("quests")):
            add_edge("part_of_chapter", quest_id, chapter_id)

    for faction in faction_records.values():
        faction_id = record_id(faction)
        for target, relation in mapping(faction.get("relations")).items():
            if not isinstance(target, str) or target not in faction_records:
                continue
            properties = {"relation": relation} if isinstance(relation, str) else {}
            add_edge("faction_relation", faction_id, target, properties)

    progress = GameProgress(
        game_id=game_id,
        player_id=record_id(player_record),
        profile_id=profile_name,
        locale=locale,
        active_subject_id=start.get("active_subject"),
        active_quest_id=start.get("active_quest"),
        intro_text=optional_str(start.get("intro_text")),
    )
    content = runtime_content_from_records(
        world_guidance=world_guidance,
        races=races,
        locations=locations,
        items=items,
        skills=skills,
        effects=effect_records,
        statuses=status_records,
        slots=slot_records,
        factions=faction_records,
        actions=action_records,
        knowledge=knowledge_records,
        dialogue_styles=dialogue_style_records,
        mbti=mbti_records,
        characters=npcs,
        quests=quests,
        chapters=chapters,
    )
    return SeedGraphBundle(
        graph=Graph(nodes=nodes, edges=edges),
        progress=progress,
        content=content,
    )
