from typing import Any

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import EdgeType, Graph, GraphEdge, GraphNode, NodeType
from src.game.domain.progress import GameProgress
from src.game.engines.growth import calc_max_hp, calc_max_mp
from src.game.rules.config import RULES
from src.game.domain.content import RuntimeContent, runtime_content_from_records
from src.game.seed.player import PlayerInput


SeedRecord = dict[str, Any]
SeedRecords = dict[str, SeedRecord]

_STATIC_CONTENT_KEYS = frozenset(
    {
        "name",
        "title",
        "description",
        "summary",
        "role",
        "job",
        "gender",
        "memorable",
        "memories",
        "disposition",
        "props",
    }
)


class SeedGraphBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: Graph
    progress: GameProgress
    content: RuntimeContent


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
    support_effects: SeedRecords | None = None,
    statuses: SeedRecords | None = None,
    factions: SeedRecords | None = None,
    action_categories: SeedRecords | None = None,
    knowledge: SeedRecords | None = None,
    dialogue_styles: SeedRecords | None = None,
    mbti: SeedRecords | None = None,
) -> SeedGraphBundle:
    player_record = _build_player(player, races, start, template)
    characters = {**npcs, _record_id(player_record): player_record}
    support_effect_records = support_effects or {}
    status_records = statuses or {}
    faction_records = factions or {}
    action_category_records = action_categories or {}
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
            _record_id(character),
            "character",
            _character_graph_properties(character),
        )
    for item in items.values():
        add_node(_record_id(item), "item", _node_properties(item))
    for location in locations.values():
        add_node(
            _record_id(location),
            "location",
            _node_properties(location, exclude={"item_ids", "connections"}),
        )
    for quest in quests.values():
        add_node(
            _record_id(quest),
            "quest",
            _quest_graph_properties(quest),
        )
    for skill in skills.values():
        add_node(_record_id(skill), "skill", _node_properties(skill))
    for support_effect in support_effect_records.values():
        add_node(
            _record_id(support_effect),
            "support_effect",
            _node_properties(support_effect),
        )
    for status in status_records.values():
        add_node(
            _record_id(status),
            "status",
            _node_properties(status),
        )
    for faction in faction_records.values():
        add_node(
            _record_id(faction),
            "faction",
            _node_properties(faction, exclude={"relations"}),
        )
    for action_category in action_category_records.values():
        add_node(
            _record_id(action_category),
            "action_category",
            _node_properties(action_category),
        )
    for knowledge_record in knowledge_records.values():
        add_node(
            _record_id(knowledge_record),
            "knowledge",
            _node_properties(knowledge_record),
        )
    for dialogue_style in dialogue_style_records.values():
        add_node(
            _record_id(dialogue_style),
            "dialogue_style",
            _node_properties(dialogue_style),
        )
    for mbti_record in mbti_records.values():
        add_node(
            _record_id(mbti_record),
            "mbti",
            _node_properties(mbti_record),
        )
    for race in races.values():
        add_node(
            _record_id(race),
            "race",
            _node_properties(race, exclude={"racial_skill_ids"}),
        )
    for chapter in chapters.values():
        add_node(
            _record_id(chapter),
            "chapter",
            _node_properties(chapter, exclude={"quest_ids"}),
        )

    for character in characters.values():
        character_id = _record_id(character)
        if location_id := _optional_str(character.get("location_id")):
            add_edge("located_at", character_id, location_id)
        if race_id := _optional_str(character.get("race_id")):
            add_edge("belongs_to_race", character_id, race_id)
        equipped_item_ids = {
            item_id
            for _, item_id in _equipped_items(_mapping(character.get("equipment")))
        }
        for slot, item_id in _equipped_items(_mapping(character.get("equipment"))):
            add_edge("equips", character_id, item_id, {"slot": slot})
        for item_id in _str_list(character.get("inventory_ids")):
            if item_id in equipped_item_ids:
                continue
            add_edge("carries", character_id, item_id)
        for skill_id in _str_list(character.get("racial_skill_ids")):
            add_edge(
                "knows_skill",
                character_id,
                skill_id,
                {"source": "racial", "tier": 1},
                edge_id=f"knows_skill:racial:{character_id}:{skill_id}",
            )
        for skill_id in _str_list(character.get("learned_skill_ids")):
            add_edge(
                "knows_skill",
                character_id,
                skill_id,
                {"source": "learned", "tier": 1},
                edge_id=f"knows_skill:learned:{character_id}:{skill_id}",
            )
        for companion_id in _str_list(character.get("companions")):
            add_edge("has_companion", character_id, companion_id)
        for target_id, affinity in _mapping(character.get("relations")).items():
            if isinstance(target_id, str) and isinstance(affinity, int):
                add_edge("relation", character_id, target_id, {"affinity": affinity})
        if faction_id := _optional_str(character.get("faction_id")):
            if faction_id in faction_records:
                add_edge("member_of_faction", character_id, faction_id)
        if dialogue_style_id := _optional_str(character.get("dialogue_style_id")):
            if dialogue_style_id in dialogue_style_records:
                add_edge("uses_dialogue_style", character_id, dialogue_style_id)
        if mbti_id := _optional_str(character.get("mbti")):
            if mbti_id in mbti_records:
                add_edge("has_mbti", character_id, mbti_id)
        _add_knowledge_edges(add_edge, character, knowledge_records)

    for location in locations.values():
        location_id = _record_id(location)
        _add_knowledge_edges(add_edge, location, knowledge_records)
        for item_id in _str_list(location.get("item_ids")):
            add_edge("located_at", item_id, location_id)
        for connection in _dict_list(location.get("connections")):
            target_id = _optional_str(connection.get("target_id"))
            if target_id is None:
                continue
            add_edge(
                "connects_to",
                location_id,
                target_id,
                _record_properties(connection, exclude={"target_id"}),
            )

    for quest in quests.values():
        quest_id = _record_id(quest)
        giver_id = _optional_str(quest.get("giver_id"))
        if giver_id is not None:
            add_edge("gives_quest", giver_id, quest_id)
        for trigger in _dict_list(quest.get("triggers")):
            _add_quest_target_edge(edges, trigger, quest_id, "success")
        for trigger in _dict_list(quest.get("fail_triggers")):
            _add_quest_target_edge(edges, trigger, quest_id, "failure")
        for item_id in _str_list(_mapping(quest.get("rewards")).get("items")):
            add_edge("reward_of", item_id, quest_id)

    for race in races.values():
        race_id = _record_id(race)
        for skill_id in _str_list(race.get("racial_skill_ids")):
            add_edge("grants_skill", race_id, skill_id)

    for item in items.values():
        _add_support_effect_edge(add_edge, item, "item", support_effect_records)
        _add_status_edges(add_edge, item, "item", status_records)
        _add_knowledge_edges(add_edge, item, knowledge_records)
    for skill in skills.values():
        _add_support_effect_edge(add_edge, skill, "skill", support_effect_records)
        _add_status_edges(add_edge, skill, "skill", status_records)
        _add_action_category_edge(add_edge, skill, action_category_records)

    for chapter in chapters.values():
        chapter_id = _record_id(chapter)
        for quest_id in _str_list(chapter.get("quest_ids")):
            add_edge("part_of_chapter", quest_id, chapter_id)

    for faction in faction_records.values():
        faction_id = _record_id(faction)
        for target_id, relation in _mapping(faction.get("relations")).items():
            if not isinstance(target_id, str) or target_id not in faction_records:
                continue
            properties = {"relation": relation} if isinstance(relation, str) else {}
            add_edge("faction_relation", faction_id, target_id, properties)

    progress = GameProgress(
        game_id=game_id,
        player_id=_record_id(player_record),
        profile_id=profile_name,
        locale=locale,
        active_subject_id=start.get("active_subject_id"),
        active_quest_id=start.get("active_quest_id"),
    )
    content = runtime_content_from_records(
        races=races,
        locations=locations,
        items=items,
        skills=skills,
        support_effects=support_effect_records,
        statuses=status_records,
        factions=faction_records,
        action_categories=action_category_records,
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


def _build_player(
    player: PlayerInput,
    races: SeedRecords,
    start: dict[str, Any],
    template: dict[str, Any],
) -> SeedRecord:
    player_id = template.get("id", "player_01")
    stats = _graph_stats(template.get("stats"))
    chosen_race = races[player.race_id]
    location_id = start["start_location_id"]
    level = _int_value(template.get("level"), 1)
    max_hp = calc_max_hp(level, stats["body"])
    max_mp = calc_max_mp(level, stats["mind"])
    return {
        **template,
        "id": player_id,
        "name": player.name,
        "is_player": True,
        "race_id": player.race_id,
        "gender": player.gender,
        "level": level,
        "stats": stats,
        "location_id": location_id,
        "equipment": _mapping(template.get("equipment")),
        "inventory_ids": _str_list(template.get("inventory_ids")),
        "gold": _int_value(template.get("gold"), 0),
        "xp_pool": _int_value(template.get("xp_pool"), 0),
        "racial_skill_ids": _str_list(chosen_race.get("racial_skill_ids")),
        "revive_coins": RULES.death.revive_coins,
        "max_hp": max_hp,
        "max_mp": max_mp,
        "hp": max_hp,
        "mp": max_mp,
        "alive": True,
        "visited_location_ids": [location_id],
    }


def _quest_graph_properties(quest: SeedRecord) -> dict[str, Any]:
    properties = _node_properties(quest, exclude={"giver_id", "rewards", "triggers"})
    triggers = _trigger_graph_properties(quest.get("triggers"))
    if triggers:
        properties["triggers"] = triggers
    rewards = _mapping(quest.get("rewards"))
    properties["rewards"] = {
        key: value for key, value in rewards.items() if key != "items"
    }
    return properties


def _add_support_effect_edge(
    add_edge,
    record: SeedRecord,
    source_type: str,
    support_effects: SeedRecords,
) -> None:
    effect_id = _optional_str(record.get("effect_template"))
    if effect_id is None or effect_id not in support_effects:
        return
    source_id = _record_id(record)
    add_edge(
        "uses_support_effect",
        source_id,
        effect_id,
        {"source_type": source_type},
    )


def _add_status_edges(
    add_edge,
    record: SeedRecord,
    source_type: str,
    statuses: SeedRecords,
) -> None:
    source_id = _record_id(record)
    for status_id in _str_list(record.get("status_ids")):
        if status_id not in statuses:
            continue
        add_edge(
            "applies_status",
            source_id,
            status_id,
            {"source_type": source_type},
        )


def _add_action_category_edge(
    add_edge,
    skill: SeedRecord,
    action_categories: SeedRecords,
) -> None:
    action_category_id = _optional_str(skill.get("action_category_id"))
    if action_category_id is None or action_category_id not in action_categories:
        return
    add_edge("uses_action_category", _record_id(skill), action_category_id)


def _add_knowledge_edges(
    add_edge,
    record: SeedRecord,
    knowledge: SeedRecords,
) -> None:
    source_id = _record_id(record)
    for knowledge_id in _str_list(record.get("knowledge_ids")):
        if knowledge_id not in knowledge:
            continue
        add_edge("has_knowledge", source_id, knowledge_id)


def _character_graph_properties(character: SeedRecord) -> dict[str, Any]:
    is_player = character.get("is_player") is True
    properties = _node_properties(
        character,
        exclude={
            "location_id",
            "equipment",
            "inventory_ids",
            "relations",
            "faction_id",
            "dialogue_style_id",
            "racial_skill_ids",
            "learned_skill_ids",
            "companions",
        },
        source="runtime" if is_player else "scenario",
    )
    if is_player:
        for key in ("name", "gender"):
            value = character.get(key)
            if value is not None:
                properties[key] = value
    properties.setdefault("alive", True)
    properties.setdefault("status", [])
    properties.setdefault("level", 0)
    properties["stats"] = _graph_stats(character.get("stats"))
    return properties


def _add_quest_target_edge(
    edges: dict[str, GraphEdge],
    trigger: SeedRecord,
    quest_id: str,
    outcome: str,
) -> None:
    target_id = _optional_str(trigger.get("target_id"))
    trigger_id = _optional_str(trigger.get("id"))
    if target_id is None or trigger_id is None:
        return
    prefix = "target_of" if outcome == "success" else "target_of:fail"
    edge_id = f"{prefix}:{trigger_id}:{target_id}:{quest_id}"
    edges[edge_id] = GraphEdge(
        id=edge_id,
        type="target_of",
        from_node_id=target_id,
        to_node_id=quest_id,
        properties=_record_properties(trigger, exclude={"target_id"})
        | {"outcome": outcome},
    )


def _node_properties(
    record: SeedRecord,
    *,
    exclude: set[str] | None = None,
    source: str = "scenario",
) -> dict[str, Any]:
    skipped = {"id", *_STATIC_CONTENT_KEYS, *(exclude or set())}
    return _source_properties(record, source=source) | {
        key: value for key, value in record.items() if key not in skipped
    }


def _record_properties(
    record: SeedRecord,
    *,
    exclude: set[str] | None = None,
) -> dict[str, Any]:
    skipped = {"id", *(exclude or set())}
    return {key: value for key, value in record.items() if key not in skipped}


def _source_properties(record: SeedRecord, *, source: str) -> dict[str, str]:
    record_id = _record_id(record)
    return {"source": source, "source_id": record_id}


def _trigger_graph_properties(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    triggers: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            triggers.append({key: val for key, val in item.items() if key != "name"})
    return triggers


def _record_id(record: SeedRecord) -> str:
    value = record.get("id")
    if not isinstance(value, str) or not value:
        raise ValueError("seed record requires a non-empty id")
    return value


def _graph_stats(value: object) -> dict[str, int]:
    raw = _mapping(value)
    defaults = {"body": 10, "agility": 10, "mind": 10, "presence": 10}
    return {key: _int_value(raw.get(key), default) for key, default in defaults.items()}


def _equipped_items(equipment: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (slot, item_id)
        for slot, item_id in equipment.items()
        if isinstance(slot, str) and isinstance(item_id, str) and item_id
    ]


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: object) -> list[SeedRecord]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_value(value: object, default: int) -> int:
    return value if isinstance(value, int) else default
