from typing import Any

from src.game.domain.action import Action, ActionOutput
from src.locale.lexicon import (
    ABANDON_TERMS,
    ACCEPT_TERMS,
    DECEPTIVE_TERMS,
    DIALOGUE_TERMS,
    HOSTILE_TERMS,
    PART_TERMS,
    RECRUIT_TERMS,
)


def classify_dialogue_shortcut(
    player_input: str,
    surroundings: dict[str, Any],
) -> ActionOutput | None:
    if not _looks_like_dialogue(player_input):
        return None
    target = _find_dialogue_target(player_input, surroundings)
    if target is None:
        return None
    return ActionOutput(
        actions=[
            Action(
                verb="speak",
                to=target["id"],
                how=_dialogue_how(player_input),
            )
        ]
    )


def _looks_like_dialogue(player_input: str) -> bool:
    return any(term in player_input for term in DIALOGUE_TERMS)


def _find_dialogue_target(
    player_input: str,
    surroundings: dict[str, Any],
) -> dict[str, str] | None:
    characters = [
        {"id": entry["id"], "name": entry["name"]}
        for entry in _dicts(surroundings.get("entities"))
        if entry.get("type") in {"npc", "enemy"}
        and isinstance(entry.get("id"), str)
        and isinstance(entry.get("name"), str)
    ]
    for character in characters:
        if character["name"] in player_input:
            return character

    recent = surroundings.get("recent_npc")
    if isinstance(recent, dict) and isinstance(recent.get("id"), str):
        recent_id = recent["id"]
        for character in characters:
            if character["id"] == recent_id:
                return character

    if len(characters) == 1:
        return characters[0]
    return None


def _dialogue_how(player_input: str) -> str:
    if any(term in player_input for term in HOSTILE_TERMS):
        return "hostile"
    if any(term in player_input for term in DECEPTIVE_TERMS):
        return "deceptive"
    if any(term in player_input for term in RECRUIT_TERMS):
        return "recruit"
    if any(term in player_input for term in PART_TERMS):
        return "part"
    if any(term in player_input for term in ACCEPT_TERMS):
        return "accept"
    if any(term in player_input for term in ABANDON_TERMS):
        return "abandon"
    return "friendly"


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]
