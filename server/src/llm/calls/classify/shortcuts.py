from typing import Any

from src.game.domain.action import Action, ActionOutput, RefuseReason
from src.locale.terms import (
    ABANDON_TERMS,
    ACCEPT_TERMS,
    ACTION_ATTACK_TERMS,
    ACTION_CREATE_DISTANCE_TERMS,
    ACTION_PICKUP_TERMS,
    DECEPTIVE_TERMS,
    DIALOGUE_TERMS,
    HOSTILE_TERMS,
    LOOT_TERMS,
    META_BREAKING_TERMS,
    PART_TERMS,
    QUEST_ACCEPT_TERMS,
    QUEST_CONTEXT_TERMS,
    RECRUIT_TERMS,
)
from src.locale.render import render


def classify_guard(player_input: str, *, locale: str = "ko") -> ActionOutput | None:
    lowered = player_input.lower()
    if any(term.lower() in lowered for term in META_BREAKING_TERMS):
        return ActionOutput(
            refuse=RefuseReason(
                category="meta_breaking",
                message_hint=render(
                    "runtime.classify.refuse_meta_breaking",
                    locale,
                ),
            )
        )
    return None


def classify_action_shortcut(
    player_input: str,
    surroundings: dict[str, Any],
    *,
    locale: str = "ko",
) -> ActionOutput | None:
    quest = _quest_accept_action(player_input, surroundings)
    if quest is not None:
        return _action_output([quest])

    decision = _quest_decide_action(player_input, surroundings)
    if decision is not None:
        return _action_output([decision])

    quest_move = _active_quest_location_move_action(player_input, surroundings)
    if quest_move is not None:
        return _action_output([quest_move])

    if surroundings.get("in_combat") is True and _has_any(
        player_input, ACTION_CREATE_DISTANCE_TERMS
    ):
        return _action_output(
            [Action(verb="move", how="flee")],
            in_combat=True,
        )

    if _has_any(player_input, ACTION_ATTACK_TERMS):
        protected = _protected_attack_refusal(player_input, surroundings, locale=locale)
        if protected is not None:
            return protected
        attack = _attack_action(player_input, surroundings)
        if attack is not None:
            return _action_output(
                [attack],
                in_combat=surroundings.get("in_combat") is True,
            )

    if _has_any(player_input, ACTION_PICKUP_TERMS):
        loot = _corpse_loot_action(player_input, surroundings)
        if loot is not None:
            return _action_output([loot])
        pickup = _pickup_action(player_input, surroundings)
        if pickup is not None:
            return _action_output([pickup])
    if _looks_like_loot(player_input):
        loot = _corpse_loot_action(player_input, surroundings)
        if loot is not None:
            return _action_output([loot])

    return None


def _quest_accept_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    if not _looks_like_quest_accept(player_input):
        return None
    quests = [
        quest
        for quest in _dicts(surroundings.get("quests"))
        if quest.get("status") in {"pending", "abandoned"}
        and isinstance(quest.get("id"), str)
    ]
    quest = _named_entry(player_input, quests)
    if quest is None:
        quest = _named_giver_quest(player_input, quests)
    if quest is None and len(quests) == 1:
        quest = _entry_ref(quests[0])
    if quest is None:
        return None
    return Action(
        verb="transfer",
        what=quest["id"],
        from_=_quest_giver_id(quest["id"], quests),
        to=_player_id(surroundings),
        how="accept",
    )


def _quest_decide_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    for quest in _dicts(surroundings.get("quests")):
        quest_id = quest.get("id")
        if not isinstance(quest_id, str):
            continue
        for choice in _dicts(quest.get("choices")):
            choice_id = choice.get("id")
            label = choice.get("label")
            if (
                isinstance(choice_id, str)
                and isinstance(label, str)
                and label
                and label in player_input
            ):
                return Action(verb="decide", what=quest_id, how=choice_id)
    return None


def _active_quest_location_move_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    if not _looks_like_quest_travel(player_input):
        return None
    exits = {
        entry["id"]
        for entry in _dicts(surroundings.get("entities"))
        if entry.get("type") == "connection" and isinstance(entry.get("id"), str)
    }
    if not exits:
        return None
    targets: list[str] = []
    for quest in _dicts(surroundings.get("quests")):
        if not isinstance(quest.get("id"), str):
            continue
        for target in quest.get("location_targets", []):
            if isinstance(target, str) and target in exits:
                targets.append(target)
    targets = list(dict.fromkeys(targets))
    if len(targets) != 1:
        return None
    return Action(verb="move", to=targets[0])


def _looks_like_quest_accept(player_input: str) -> bool:
    if not _has_any(player_input, QUEST_ACCEPT_TERMS):
        return False
    return _has_any(player_input, QUEST_CONTEXT_TERMS)


def _looks_like_quest_travel(player_input: str) -> bool:
    return _has_any(player_input, ("출항", "항해", "떠나", "떠납", "건너"))


def _named_giver_quest(
    player_input: str,
    quests: list[dict[str, Any]],
) -> dict[str, str] | None:
    for quest in quests:
        quest_id = quest.get("id")
        giver_name = quest.get("giver_name")
        if (
            isinstance(quest_id, str)
            and isinstance(giver_name, str)
            and giver_name in player_input
        ):
            return {"id": quest_id, "name": giver_name}
    return None


def _quest_giver_id(quest_id: str, quests: list[dict[str, Any]]) -> str | None:
    for quest in quests:
        if quest.get("id") == quest_id and isinstance(quest.get("giver"), str):
            return quest["giver"]
    return None


def _player_id(surroundings: dict[str, Any]) -> str | None:
    player = _player(surroundings)
    return player["id"] if player is not None else None


def _protected_attack_refusal(
    player_input: str,
    surroundings: dict[str, Any],
    *,
    locale: str,
) -> ActionOutput | None:
    protected_targets = [
        entry
        for entry in _dicts(surroundings.get("entities"))
        if entry.get("type") in {"npc", "enemy"} and entry.get("protected") is True
    ]
    target = _named_entry(player_input, protected_targets)
    if target is None and len(protected_targets) == 1:
        has_attackable_target = any(
            entry.get("type") in {"npc", "enemy"}
            and entry.get("protected") is not True
            for entry in _dicts(surroundings.get("entities"))
        )
        if not has_attackable_target:
            target = _entry_ref(protected_targets[0])
    if target is None:
        return None
    return ActionOutput(
        refuse=RefuseReason(
            category="invalid_transition",
            message_hint=render("log.error.protected_target", locale),
            target=target["id"],
        )
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


def _action_output(
    actions: list[Action],
    *,
    in_combat: bool = False,
) -> ActionOutput:
    return ActionOutput.model_validate(
        {
            "actions": [
                action.model_dump(mode="json", by_alias=True) for action in actions
            ]
        },
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
            if entry.get("type") in {"npc", "enemy"}
            and entry.get("protected") is not True
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
        how="free",
    )


def _corpse_loot_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    corpse = _named_entry(player_input, _dicts(surroundings.get("corpses")))
    corpses = _dicts(surroundings.get("corpses"))
    if corpse is None and len(corpses) == 1:
        corpse = _entry_ref(corpses[0])
    if corpse is None:
        return None

    corpse_payload = next(
        (
            entry
            for entry in corpses
            if isinstance(entry.get("id"), str) and entry.get("id") == corpse["id"]
        ),
        None,
    )
    if corpse_payload is None:
        return None
    inventory = _dicts(corpse_payload.get("inventory"))
    item = _named_entry(player_input, inventory)
    if item is None and len(inventory) == 1:
        item = _entry_ref(inventory[0])
    player = _player(surroundings)
    if item is None or player is None:
        return None
    return Action(
        verb="transfer",
        what=item["id"],
        from_=corpse["id"],
        to=player["id"],
        how="free",
    )


def _player(surroundings: dict[str, Any]) -> dict[str, str] | None:
    for entry in _dicts(surroundings.get("entities")):
        if entry.get("type") != "player":
            continue
        entry_id = entry.get("id")
        if isinstance(entry_id, str):
            return {"id": entry_id}
    return None


def _looks_like_dialogue(player_input: str) -> bool:
    return any(term in player_input for term in DIALOGUE_TERMS)


def _looks_like_loot(player_input: str) -> bool:
    return any(term in player_input for term in LOOT_TERMS)


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


def _entry_ref(entry: dict[str, Any]) -> dict[str, str] | None:
    entry_id = entry.get("id")
    name = entry.get("name")
    if isinstance(entry_id, str) and isinstance(name, str):
        return {"id": entry_id, "name": name}
    return None


def _has_any(player_input: str, terms: tuple[str, ...]) -> bool:
    return any(term in player_input for term in terms)


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]
