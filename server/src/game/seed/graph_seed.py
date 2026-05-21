from typing import Any

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import EdgeType, Graph, GraphEdge, GraphNode, NodeType
from src.game.domain.progress import GameProgress
from src.game.engines.growth import calc_max_hp, calc_max_mp
from src.game.domain.content import RuntimeContent, runtime_content_from_records
from src.game.seed.player import PlayerInput


SeedRecord = dict[str, Any]
SeedRecords = dict[str, SeedRecord]

_STATIC_CONTENT_KEYS = frozenset(
    {
        "name",
        "title",
        "description",
        "background",
        "summary",
        "role",
        "gender",
        "memorable",
        "memories",
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
    effects: SeedRecords | None = None,
    statuses: SeedRecords | None = None,
    slots: SeedRecords | None = None,
    factions: SeedRecords | None = None,
    actions: SeedRecords | None = None,
    knowledge: SeedRecords | None = None,
    dialogue_styles: SeedRecords | None = None,
    mbti: SeedRecords | None = None,
) -> SeedGraphBundle:
    player_record = _build_player(player, races, start, template)
    characters = {**npcs, _record_id(player_record): player_record}
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
            _node_properties(location, exclude={"items", "connections"}),
        )
    for quest in quests.values():
        add_node(
            _record_id(quest),
            "quest",
            _quest_graph_properties(quest),
        )
    for skill in skills.values():
        add_node(_record_id(skill), "skill", _node_properties(skill))
    for effect in effect_records.values():
        add_node(
            _record_id(effect),
            "effect",
            _node_properties(effect),
        )
    for status in status_records.values():
        add_node(
            _record_id(status),
            "status",
            _node_properties(status),
        )
    for slot in slot_records.values():
        add_node(
            _record_id(slot),
            "slot",
            _node_properties(slot),
        )
    for faction in faction_records.values():
        add_node(
            _record_id(faction),
            "faction",
            _node_properties(faction, exclude={"relations"}),
        )
    for action in action_records.values():
        add_node(
            _record_id(action),
            "action",
            _node_properties(action),
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
            _node_properties(race, exclude={"racial_skills"}),
        )
    for chapter in chapters.values():
        add_node(
            _record_id(chapter),
            "chapter",
            _node_properties(chapter, exclude={"quests"}),
        )

    for character in characters.values():
        character_id = _record_id(character)
        if location_id := _optional_str(character.get("location")):
            add_edge("located_at", character_id, location_id)
        if race_id := _optional_str(character.get("race")):
            add_edge("belongs_to_race", character_id, race_id)
        equipped_item_ids = {
            item_id
            for _, item_id in _equipped_items(_mapping(character.get("equipment")))
        }
        for slot, item_id in _equipped_items(_mapping(character.get("equipment"))):
            add_edge("equips", character_id, item_id, {"slot": slot})
        for item_id in _str_list(character.get("inventory")):
            if item_id in equipped_item_ids:
                continue
            add_edge("carries", character_id, item_id)
        for skill_id in _str_list(character.get("learned_skills")):
            add_edge(
                "knows_skill",
                character_id,
                skill_id,
                {"source": "learned", "tier": 1},
                edge_id=f"knows_skill:learned:{character_id}:{skill_id}",
            )
        for companion_id in _str_list(character.get("companions")):
            add_edge("has_companion", character_id, companion_id)
        for target, affinity in _mapping(character.get("relations")).items():
            if isinstance(target, str) and isinstance(affinity, int):
                add_edge("relation", character_id, target, {"affinity": affinity})
        if faction_id := _optional_str(character.get("faction")):
            if faction_id in faction_records:
                add_edge("member_of_faction", character_id, faction_id)
        if dialogue_style_id := _optional_str(character.get("dialogue_style")):
            if dialogue_style_id in dialogue_style_records:
                add_edge("uses_dialogue_style", character_id, dialogue_style_id)
        if mbti_id := _optional_str(character.get("mbti")):
            if mbti_id in mbti_records:
                add_edge("has_mbti", character_id, mbti_id)
        _add_knowledge_edges(add_edge, character, knowledge_records)

    for location in locations.values():
        location_id = _record_id(location)
        _add_knowledge_edges(add_edge, location, knowledge_records)
        for item_id in _str_list(location.get("items")):
            add_edge("located_at", item_id, location_id)
        for connection in _dict_list(location.get("connections")):
            target = _optional_str(connection.get("target"))
            if target is None:
                continue
            add_edge(
                "connects_to",
                location_id,
                target,
                _record_properties(connection, exclude={"target"}),
            )

    for quest in quests.values():
        quest_id = _record_id(quest)
        giver_id = _optional_str(quest.get("giver"))
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
        for skill_id in _str_list(race.get("racial_skills")):
            add_edge("grants_skill", race_id, skill_id)

    for item in items.values():
        _add_effect_edge(add_edge, item, "item", effect_records)
        _add_slot_edge(add_edge, item, slot_records)
        _add_knowledge_edges(add_edge, item, knowledge_records)
    for skill in skills.values():
        _add_action_edge(add_edge, skill, action_records)

    for chapter in chapters.values():
        chapter_id = _record_id(chapter)
        for quest_id in _str_list(chapter.get("quests")):
            add_edge("part_of_chapter", quest_id, chapter_id)

    for faction in faction_records.values():
        faction_id = _record_id(faction)
        for target, relation in _mapping(faction.get("relations")).items():
            if not isinstance(target, str) or target not in faction_records:
                continue
            properties = {"relation": relation} if isinstance(relation, str) else {}
            add_edge("faction_relation", faction_id, target, properties)

    progress = GameProgress(
        game_id=game_id,
        player_id=_record_id(player_record),
        profile_id=profile_name,
        locale=locale,
        active_subject_id=start.get("active_subject"),
        active_quest_id=start.get("active_quest"),
        intro_text=_optional_str(start.get("intro_text")),
    )
    content = runtime_content_from_records(
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


def _build_player(
    player: PlayerInput,
    races: SeedRecords,
    start: dict[str, Any],
    template: dict[str, Any],
) -> SeedRecord:
    player_id = template.get("id", "player_01")
    stats = _graph_stats(None)
    location_id = start["start_location"]
    level = _int_value(template.get("level"), 1)
    max_hp = calc_max_hp(level, stats["body"])
    max_mp = calc_max_mp(level, stats["mind"])
    return {
        **template,
        "id": player_id,
        "name": player.name,
        "is_player": True,
        "race": player.race_id,
        "gender": player.gender,
        "level": level,
        "stats": stats,
        "location": location_id,
        "equipment": _mapping(template.get("equipment")),
        "inventory": _str_list(template.get("inventory")),
        "gold": _int_value(template.get("gold"), 0),
        "xp_pool": _int_value(template.get("xp_pool"), 0),
        "max_hp": max_hp,
        "max_mp": max_mp,
        "hp": max_hp,
        "mp": max_mp,
        "alive": True,
        "visited_location_ids": [location_id],
    }


def _quest_graph_properties(quest: SeedRecord) -> dict[str, Any]:
    properties = _node_properties(quest, exclude={"giver", "rewards", "triggers"})
    triggers = _trigger_graph_properties(quest.get("triggers"))
    if triggers:
        properties["triggers"] = triggers
    rewards = _mapping(quest.get("rewards"))
    properties["rewards"] = {
        key: value for key, value in rewards.items() if key != "items"
    }
    return properties


def _add_effect_edge(
    add_edge,
    record: SeedRecord,
    source_type: str,
    effects: SeedRecords,
) -> None:
    effect_id = _optional_str(record.get("effect"))
    if effect_id is None or effect_id not in effects:
        return
    source_id = _record_id(record)
    add_edge(
        "uses_effect",
        source_id,
        effect_id,
        {"source_type": source_type},
    )


def _add_slot_edge(
    add_edge,
    item: SeedRecord,
    slots: SeedRecords,
) -> None:
    slot_id = _optional_str(item.get("slot"))
    if slot_id is None or slot_id not in slots:
        return
    add_edge("uses_slot", _record_id(item), slot_id)


def _add_action_edge(
    add_edge,
    skill: SeedRecord,
    actions: SeedRecords,
) -> None:
    action = _optional_str(skill.get("action"))
    if action is None or action not in actions:
        return
    add_edge("uses_action", _record_id(skill), action)


def _add_knowledge_edges(
    add_edge,
    record: SeedRecord,
    knowledge: SeedRecords,
) -> None:
    source_id = _record_id(record)
    for knowledge_id in _str_list(record.get("knowledge")):
        if knowledge_id not in knowledge:
            continue
        add_edge("has_knowledge", source_id, knowledge_id)


def _character_graph_properties(character: SeedRecord) -> dict[str, Any]:
    is_player = character.get("is_player") is True
    properties = _node_properties(
        character,
        exclude={
            "location",
            "equipment",
            "inventory",
            "relations",
            "faction",
            "dialogue_style",
            "learned_skills",
            "companions",
            *(() if is_player else ("stats",)),
        },
        source="runtime" if is_player else "scenario",
    )
    properties["is_player"] = is_player
    if is_player:
        for key in ("name", "gender"):
            value = character.get(key)
            if value is not None:
                properties[key] = value
    properties.setdefault("alive", True)
    properties.setdefault("level", 0)
    if is_player:
        properties["stats"] = _graph_stats(character.get("stats"))
    return properties


def _add_quest_target_edge(
    edges: dict[str, GraphEdge],
    trigger: SeedRecord,
    quest_id: str,
    outcome: str,
) -> None:
    target = _optional_str(trigger.get("target"))
    trigger_id = _optional_str(trigger.get("id"))
    if target is None or trigger_id is None:
        return
    prefix = "target_of" if outcome == "success" else "target_of:fail"
    edge_id = f"{prefix}:{trigger_id}:{target}:{quest_id}"
    edges[edge_id] = GraphEdge(
        id=edge_id,
        type="target_of",
        from_node_id=target,
        to_node_id=quest_id,
        properties=_record_properties(trigger, exclude={"target"})
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
