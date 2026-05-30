from __future__ import annotations

from typing import Any

from src.game.domain.action import Action
from src.locale.generated_story import (
    GENERATED_OPEN_MOVE_TARGET_TERMS,
    GENERATED_OPEN_MOVE_TERMS,
)
from src.locale.terms import QUEST_TRAVEL_TERMS

from .surroundings import dict_entries, has_any
from .text_intents import looks_like_dialogue, looks_like_inspect


def active_quest_location_move_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    if not looks_like_quest_travel(player_input):
        return None
    if looks_like_dialogue(player_input):
        return None
    if looks_like_inspect(player_input):
        return None
    exits = {
        entry["id"]
        for entry in dict_entries(surroundings.get("entities"))
        if entry.get("type") == "connection" and isinstance(entry.get("id"), str)
    }
    if not exits:
        return None
    targets: list[str] = []
    for quest in dict_entries(surroundings.get("quests")):
        if not isinstance(quest.get("id"), str):
            continue
        for target in quest.get("location_targets", []):
            if isinstance(target, str) and target in exits:
                targets.append(target)
        for route in dict_entries(quest.get("location_routes")):
            target_name = route.get("target_name")
            next_exit_id = route.get("next_exit_id")
            if not isinstance(next_exit_id, str) or next_exit_id not in exits:
                continue
            if (
                isinstance(target_name, str)
                and target_name
                and target_name in player_input
            ):
                targets.append(next_exit_id)
    targets = list(dict.fromkeys(targets))
    if len(targets) != 1:
        return None
    return Action(verb="move", to=targets[0])


def visible_exit_move_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    if not has_any(player_input, GENERATED_OPEN_MOVE_TERMS):
        return None
    if looks_like_dialogue(player_input) or looks_like_inspect(player_input):
        return None
    targets: list[str] = []
    for entry in dict_entries(surroundings.get("entities")):
        if entry.get("type") != "connection":
            continue
        entry_id = entry.get("id")
        name = entry.get("name")
        if isinstance(entry_id, str) and isinstance(name, str) and name in player_input:
            targets.append(entry_id)
    targets = list(dict.fromkeys(targets))
    if len(targets) != 1:
        return None
    return Action(verb="move", to=targets[0])


def open_generated_move_action(player_input: str) -> Action | None:
    if not has_any(player_input, GENERATED_OPEN_MOVE_TERMS):
        return None
    if not has_any(player_input, GENERATED_OPEN_MOVE_TARGET_TERMS):
        return None
    if looks_like_dialogue(player_input) or looks_like_inspect(player_input):
        return None
    return Action(verb="move", note="generated_open_move")


def looks_like_quest_travel(player_input: str) -> bool:
    return has_any(player_input, QUEST_TRAVEL_TERMS)
