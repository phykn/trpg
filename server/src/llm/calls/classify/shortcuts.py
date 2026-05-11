from typing import Any

from src.game.domain.action import Action, ActionOutput
from src.locale.lexicon import ACTION_ATTACK_TERMS, ACTION_FLEE_TERMS, ACTION_PICKUP_TERMS


def classify_action_shortcut(
    player_input: str,
    surroundings: dict[str, Any],
) -> ActionOutput | None:
    if surroundings.get("in_combat") is True and _has_any(player_input, ACTION_FLEE_TERMS):
        return _action_output(
            [Action(verb="move", how="hasty")],
            in_combat=True,
        )

    if _has_any(player_input, ACTION_ATTACK_TERMS):
        attack = _attack_action(player_input, surroundings)
        if attack is not None:
            return _action_output(
                [attack],
                in_combat=surroundings.get("in_combat") is True,
            )

    if _has_any(player_input, ACTION_PICKUP_TERMS):
        pickup = _pickup_action(player_input, surroundings)
        if pickup is not None:
            return _action_output([pickup])

    return None


def _action_output(
    actions: list[Action],
    *,
    in_combat: bool = False,
) -> ActionOutput:
    return ActionOutput.model_validate(
        {"actions": [action.model_dump(mode="json", by_alias=True) for action in actions]},
        context={"in_combat": in_combat},
    )


def _attack_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    target = _named_entry(
        player_input,
        [
            entry
            for entry in _dicts(surroundings.get("entities"))
            if entry.get("type") == "enemy" and entry.get("protected") is not True
        ],
    )
    if target is None:
        return None
    skill = _named_entry(player_input, _dicts(surroundings.get("skills")))
    return Action(
        verb="attack",
        what=[target["id"]],
        with_=skill["id"] if skill is not None else None,
    )


def _pickup_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    item = _named_entry(player_input, _dicts(surroundings.get("location_items")))
    if item is None:
        return None
    location = surroundings.get("location")
    player = _player(surroundings)
    if not isinstance(location, dict) or player is None:
        return None
    location_id = location.get("id")
    if not isinstance(location_id, str):
        return None
    return Action(
        verb="transfer",
        what=item["id"],
        from_=location_id,
        to=player["id"],
        how="gift",
    )


def _player(surroundings: dict[str, Any]) -> dict[str, str] | None:
    for entry in _dicts(surroundings.get("entities")):
        if entry.get("type") != "player":
            continue
        entry_id = entry.get("id")
        if isinstance(entry_id, str):
            return {"id": entry_id}
    return None


def _named_entry(
    player_input: str,
    entries: list[dict[str, Any]],
) -> dict[str, str] | None:
    for entry in entries:
        entry_id = entry.get("id")
        name = entry.get("name")
        if isinstance(entry_id, str) and isinstance(name, str) and name in player_input:
            return {"id": entry_id, "name": name}
    return None


def _has_any(player_input: str, terms: tuple[str, ...]) -> bool:
    return any(term in player_input for term in terms)


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]
