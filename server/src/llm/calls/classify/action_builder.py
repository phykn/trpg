from typing import Any

from src.game.domain.action import Action, ActionCheckHint, ActionOutput, RefuseReason


def build_action_output(
    raw: dict[str, Any], surroundings: dict[str, Any]
) -> ActionOutput:
    if isinstance(raw.get("refuse"), dict):
        return ActionOutput(refuse=RefuseReason.model_validate(raw["refuse"]))

    intents = raw.get("intents")
    if not isinstance(intents, list) or not intents:
        raise ValueError("intent output requires non-empty intents")

    actions = [_build_action(intent, surroundings) for intent in intents]
    checks = [_build_check_hint(intent) for intent in intents]
    return ActionOutput.model_validate(
        {
            "actions": [
                action.model_dump(mode="json", by_alias=True) for action in actions
            ],
            "action_checks": [check.model_dump(mode="json") for check in checks],
        },
        context={"in_combat": bool(surroundings.get("in_combat", False))},
    )


def _build_check_hint(intent: object) -> ActionCheckHint:
    if not isinstance(intent, dict):
        raise ValueError("intent must be an object")
    required = intent.get("check_required") is True
    reason = _optional_str(intent, "check_reason")
    return ActionCheckHint(required=required, reason=reason)


def _build_action(intent: object, surroundings: dict[str, Any]) -> Action:
    if not isinstance(intent, dict):
        raise ValueError("intent must be an object")
    name = _required_str(intent, "intent")

    if name == "move":
        return Action(verb="move", to=_first_str(intent, "destination_id", "target_id"))
    if name == "buy":
        return Action(
            verb="transfer",
            what=_first_str(intent, "item_id", "target_id"),
            from_=_required_str(intent, "merchant_id"),
            to=_player_id(surroundings),
            how="trade",
        )
    if name == "sell":
        return Action(
            verb="transfer",
            what=_first_str(intent, "item_id", "target_id"),
            from_=_player_id(surroundings),
            to=_required_str(intent, "merchant_id"),
            how="trade",
        )
    if name == "pickup":
        return Action(
            verb="transfer",
            what=_required_str(intent, "item_id"),
            from_=_location_id(surroundings),
            to=_player_id(surroundings),
            how="free",
        )
    if name == "give":
        return Action(
            verb="transfer",
            what=_required_str(intent, "item_id"),
            from_=_player_id(surroundings),
            to=_first_str(intent, "target_id", "recipient_id"),
            how="free",
        )
    if name == "steal":
        return Action(
            verb="transfer",
            what=_required_str(intent, "item_id"),
            from_=_first_str(intent, "source_id", "target_id"),
            to=_player_id(surroundings),
            how="steal",
        )
    if name == "loot":
        return Action(
            verb="transfer",
            what=_required_str(intent, "item_id"),
            from_=_first_str(intent, "source_id", "corpse_id"),
            to=_player_id(surroundings),
            how="free",
        )
    if name == "equip":
        return Action(
            verb="transfer",
            what=_required_str(intent, "item_id"),
            to=_optional_str(intent, "slot") or "weapon",
            how="equip",
        )
    if name == "unequip":
        return Action(
            verb="transfer",
            what=_required_str(intent, "item_id"),
            how="unequip",
        )
    if name == "accept_quest":
        return Action(
            verb="transfer",
            what=_required_str(intent, "quest_id"),
            from_=_first_str(intent, "source_id", "target_id"),
            to=_player_id(surroundings),
            how="accept",
        )
    if name == "abandon_quest":
        return Action(
            verb="transfer",
            what=_required_str(intent, "quest_id"),
            from_=_player_id(surroundings),
            to=_first_str(intent, "target_id", "source_id"),
            how="abandon",
        )
    if name == "use":
        return Action(
            verb="use",
            what=_optional_str(intent, "item_id"),
            with_=_optional_str(intent, "skill_id"),
            to=_optional_str(intent, "target_id"),
        )
    if name == "attack":
        return Action(
            verb="attack",
            what=[_first_str(intent, "target_id", "enemy_id")],
            with_=_optional_str(intent, "skill_id"),
            how=_optional_str(intent, "tactic"),
        )
    if name == "cast":
        skill_id = _required_str(intent, "skill_id")
        target_id = _optional_str(intent, "target_id")
        if target_id is not None and _is_attack_target(surroundings, target_id):
            return Action(verb="attack", what=[target_id], with_=skill_id)
        return Action(
            verb="use",
            with_=skill_id,
            to=target_id,
        )
    if name == "flee":
        return Action(verb="move", how="create_distance")
    if name == "talk":
        return Action(
            verb="speak",
            to=_optional_str(intent, "target_id"),
            how=_optional_str(intent, "manner") or "friendly",
        )
    if name == "query":
        return Action(verb="query", what=_optional_str(intent, "topic"))
    if name == "inspect":
        return Action(verb="perceive", what=_optional_str(intent, "target_id"))
    if name == "pass":
        return Action(verb="pass", note=_optional_str(intent, "note"))
    if name == "rest":
        return Action(verb="rest")

    raise ValueError(f"unsupported intent: {name}")


def _player_id(surroundings: dict[str, Any]) -> str:
    for entry in _dicts(surroundings.get("entities")):
        if entry.get("type") == "player" and isinstance(entry.get("id"), str):
            return entry["id"]
    raise ValueError("player id is required")


def _location_id(surroundings: dict[str, Any]) -> str:
    location = surroundings.get("location")
    if isinstance(location, dict) and isinstance(location.get("id"), str):
        return location["id"]
    raise ValueError("location id is required")


def _first_str(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    raise ValueError(f"{keys[0]} is required")


def _required_str(payload: dict[str, Any], key: str) -> str:
    return _first_str(payload, key)


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _is_attack_target(surroundings: dict[str, Any], target_id: str) -> bool:
    for entry in _dicts(surroundings.get("entities")):
        if entry.get("id") != target_id:
            continue
        return entry.get("type") in {"enemy", "monster", "hostile"}
    return bool(surroundings.get("in_combat", False))
