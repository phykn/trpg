import re
from typing import Any

from src.game.domain.action import Action, ActionOutput, RefuseReason
from src.locale.generated_story import (
    GENERATED_OPEN_MOVE_TARGET_TERMS,
    GENERATED_OPEN_MOVE_TERMS,
)
from src.locale.terms import (
    ACTION_ATTACK_TERMS,
    ACTION_CREATE_DISTANCE_TERMS,
    ACTION_PICKUP_TERMS,
    DIALOGUE_GENERIC_TARGETS,
    DIALOGUE_QUESTION_TERMS,
    DIALOGUE_TARGET_PARTICLES,
    DIALOGUE_TERMS,
    INSPECT_TERMS,
    LOOT_TERMS,
    QUEST_ACCEPT_TERMS,
    QUEST_CONTEXT_TERMS,
    QUEST_TRAVEL_TERMS,
)
from src.locale.render import render


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

    named_dialogue = _named_visible_dialogue_action(player_input, surroundings)
    if named_dialogue is not None:
        return _action_output([named_dialogue])

    single_npc_question = _single_visible_npc_question_action(
        player_input,
        surroundings,
    )
    if single_npc_question is not None:
        return _action_output([single_npc_question])

    quest_move = _active_quest_location_move_action(player_input, surroundings)
    if quest_move is not None:
        return _action_output([quest_move])

    exit_move = _visible_exit_move_action(player_input, surroundings)
    if exit_move is not None:
        return _action_output([exit_move])

    open_move = _open_generated_move_action(player_input)
    if open_move is not None:
        return _action_output([open_move])

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

    missing_dialogue = _missing_dialogue_target_refusal(
        player_input,
        surroundings,
        locale=locale,
    )
    if missing_dialogue is not None:
        return missing_dialogue

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
    if _looks_like_dialogue(player_input):
        return None
    if _looks_like_inspect(player_input):
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
        for route in _dicts(quest.get("location_routes")):
            target_name = route.get("target_name")
            next_exit_id = route.get("next_exit_id")
            if not isinstance(next_exit_id, str) or next_exit_id not in exits:
                continue
            if isinstance(target_name, str) and target_name and target_name in player_input:
                targets.append(next_exit_id)
    targets = list(dict.fromkeys(targets))
    if len(targets) != 1:
        return None
    return Action(verb="move", to=targets[0])


def _looks_like_quest_accept(player_input: str) -> bool:
    if not _has_any(player_input, QUEST_ACCEPT_TERMS):
        return False
    return _has_any(player_input, QUEST_CONTEXT_TERMS)


def _looks_like_quest_travel(player_input: str) -> bool:
    return _has_any(player_input, QUEST_TRAVEL_TERMS)


def _visible_exit_move_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    if not _has_any(player_input, GENERATED_OPEN_MOVE_TERMS):
        return None
    if _looks_like_dialogue(player_input) or _looks_like_inspect(player_input):
        return None
    targets: list[str] = []
    for entry in _dicts(surroundings.get("entities")):
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


def _open_generated_move_action(player_input: str) -> Action | None:
    if not _has_any(player_input, GENERATED_OPEN_MOVE_TERMS):
        return None
    if not _has_any(player_input, GENERATED_OPEN_MOVE_TARGET_TERMS):
        return None
    if _looks_like_dialogue(player_input) or _looks_like_inspect(player_input):
        return None
    return Action(verb="move", note="generated_open_move")


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


def _single_visible_npc_question_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    if not _looks_like_information_question(player_input):
        return None
    targets = [
        entry
        for entry in _dicts(surroundings.get("entities"))
        if entry.get("type") in {"npc", "enemy"} and isinstance(entry.get("id"), str)
    ]
    if len(targets) != 1:
        return None
    return Action(verb="speak", to=targets[0]["id"], how="friendly")


def _named_visible_dialogue_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    if not _looks_like_direct_dialogue(player_input):
        return None
    target = _named_entry(
        player_input,
        [
            entry
            for entry in _dicts(surroundings.get("entities"))
            if entry.get("type") in {"npc", "enemy"}
        ],
    )
    if target is None:
        return None
    return Action(verb="speak", to=target["id"], how="friendly")


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


def _missing_dialogue_target_refusal(
    player_input: str,
    surroundings: dict[str, Any],
    *,
    locale: str,
) -> ActionOutput | None:
    if not _has_any(player_input, DIALOGUE_TERMS):
        return None
    targets = [
        entry
        for entry in _dicts(surroundings.get("entities"))
        if entry.get("type") in {"npc", "enemy"}
    ]
    if not _has_localized_target_names(targets):
        return None
    if _named_entry(player_input, targets) is not None:
        return None
    recent = surroundings.get("recent_npc")
    if isinstance(recent, dict) and isinstance(recent.get("name"), str):
        if recent["name"] in player_input:
            return None
    for phrase in _dialogue_target_phrases(player_input):
        if phrase not in DIALOGUE_GENERIC_TARGETS:
            return ActionOutput(
                refuse=RefuseReason(
                    category="invalid_transition",
                    message_hint=render(
                        "runtime.classify.refuse_missing_target",
                        locale,
                    ),
                )
            )
    return None


def _has_localized_target_names(entries: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(entry.get("name"), str) and _has_hangul(entry["name"])
        for entry in entries
    )


def _has_hangul(text: str) -> bool:
    return any(0xAC00 <= ord(char) <= 0xD7A3 for char in text)


def _dialogue_target_phrases(player_input: str) -> list[str]:
    particle = "|".join(re.escape(term) for term in DIALOGUE_TARGET_PARTICLES)
    hangul_range = f"{chr(0xAC00)}-{chr(0xD7A3)}"
    return [
        match.group(1).strip()
        for match in re.finditer(
            rf"([0-9A-Za-z{hangul_range} ]{{1,32}})(?:{particle})",
            player_input,
        )
        if match.group(1).strip()
    ]


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
    return _has_any(player_input, DIALOGUE_TERMS) or _has_any(
        player_input,
        DIALOGUE_TARGET_PARTICLES,
    )


def _looks_like_direct_dialogue(player_input: str) -> bool:
    return _has_any(player_input, DIALOGUE_TERMS) or "「" in player_input


def _looks_like_information_question(player_input: str) -> bool:
    return "?" in player_input or _has_any(player_input, DIALOGUE_QUESTION_TERMS)


def _looks_like_inspect(player_input: str) -> bool:
    return _has_any(player_input, INSPECT_TERMS)


def _looks_like_loot(player_input: str) -> bool:
    return any(term in player_input for term in LOOT_TERMS)


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
