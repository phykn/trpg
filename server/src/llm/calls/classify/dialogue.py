from typing import Any

from src.game.domain.action import Action, ActionOutput


_DIALOGUE_TERMS = (
    "\ub9d0",
    "\ubb3b",
    "\ubb3c\uc5b4",
    "\ub300\ud654",
    "\uc778\uc0ac",
    "\uc9c8\ubb38",
    "\ub300\ub2f5",
)
_HOSTILE_TERMS = (
    "\ud611\ubc15",
    "\uc704\ud611",
    "\ud654\ub0b4",
    "\uc801\ub300",
    "\ub530\uc838",
    "\ub3c4\ubc1c",
)
_DECEPTIVE_TERMS = (
    "\uac70\uc9d3",
    "\uc18d\uc774",
    "\uc18d\uc5ec",
    "\uae30\ub9cc",
)
_RECRUIT_TERMS = (
    "\ub3d9\ub8cc",
    "\ud569\ub958",
    "\ud568\uaed8",
    "\uac19\uc774",
)
_PART_TERMS = (
    "\ud5e4\uc5b4",
    "\uac01\uc790",
    "\ub5a0\ub098",
    "\uadf8\ub9cc",
)
_ACCEPT_TERMS = ("\uc218\ub77d", "\ubc1b\uc544\ub4e4")
_ABANDON_TERMS = ("\ud3ec\uae30", "\uac70\uc808", "\ucde8\uc18c")


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
    return any(term in player_input for term in _DIALOGUE_TERMS)


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
    if any(term in player_input for term in _HOSTILE_TERMS):
        return "hostile"
    if any(term in player_input for term in _DECEPTIVE_TERMS):
        return "deceptive"
    if any(term in player_input for term in _RECRUIT_TERMS):
        return "recruit"
    if any(term in player_input for term in _PART_TERMS):
        return "part"
    if any(term in player_input for term in _ACCEPT_TERMS):
        return "accept"
    if any(term in player_input for term in _ABANDON_TERMS):
        return "abandon"
    return "friendly"


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]
