from __future__ import annotations

from typing import Any

from src.game.engines.growth import calc_max_hp, calc_max_mp
from src.game.seed.player import PlayerInput

from .coerce import graph_stats, int_value, mapping, record_id, str_list
from .types import STATIC_CONTENT_KEYS, SeedRecord


def build_player(
    player: PlayerInput,
    races,
    start: dict[str, Any],
    template: dict[str, Any],
) -> SeedRecord:
    player_id = template.get("id", "player_01")
    stats = graph_stats(None)
    location_id = start["start_location"]
    level = int_value(template.get("level"), 1)
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
        "equipment": mapping(template.get("equipment")),
        "inventory": str_list(template.get("inventory")),
        "gold": int_value(template.get("gold"), 0),
        "xp_pool": int_value(template.get("xp_pool"), 0),
        "max_hp": max_hp,
        "max_mp": max_mp,
        "hp": max_hp,
        "mp": max_mp,
        "alive": True,
        "visited_location_ids": [location_id],
    }


def quest_graph_properties(quest: SeedRecord) -> dict[str, Any]:
    properties = node_properties(quest, exclude={"rewards", "triggers"})
    triggers = trigger_graph_properties(quest.get("triggers"))
    if triggers:
        properties["triggers"] = triggers
    rewards = mapping(quest.get("rewards"))
    properties["rewards"] = {
        key: value for key, value in rewards.items() if key != "items"
    }
    return properties


def character_graph_properties(character: SeedRecord) -> dict[str, Any]:
    is_player = character.get("is_player") is True
    properties = node_properties(
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
        properties["stats"] = graph_stats(character.get("stats"))
    return properties


def node_properties(
    record: SeedRecord,
    *,
    exclude: set[str] | None = None,
    source: str = "scenario",
) -> dict[str, Any]:
    skipped = {"id", *STATIC_CONTENT_KEYS, *(exclude or set())}
    return source_properties(record, source=source) | {
        key: value for key, value in record.items() if key not in skipped
    }


def record_properties(
    record: SeedRecord,
    *,
    exclude: set[str] | None = None,
) -> dict[str, Any]:
    skipped = {"id", *(exclude or set())}
    return {key: value for key, value in record.items() if key not in skipped}


def source_properties(record: SeedRecord, *, source: str) -> dict[str, str]:
    return {"source": source, "source_id": record_id(record)}


def trigger_graph_properties(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    triggers: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            triggers.append({key: val for key, val in item.items() if key != "name"})
    return triggers
