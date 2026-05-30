from __future__ import annotations

from typing import Any

from src.game.domain.action import Action
from src.locale.terms import QUEST_ACCEPT_TERMS, QUEST_CONTEXT_TERMS

from .surroundings import dict_entries, entry_ref, has_any, named_entry, player_id


def quest_accept_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    if not looks_like_quest_accept(player_input):
        return None
    quests = [
        quest
        for quest in dict_entries(surroundings.get("quests"))
        if quest.get("status") in {"pending", "abandoned"}
        and isinstance(quest.get("id"), str)
    ]
    quest = named_entry(player_input, quests)
    if quest is None:
        quest = named_giver_quest(player_input, quests)
    if quest is None and len(quests) == 1:
        quest = entry_ref(quests[0])
    if quest is None:
        return None
    return Action(
        verb="transfer",
        what=quest["id"],
        from_=quest_giver_id(quest["id"], quests),
        to=player_id(surroundings),
        how="accept",
    )


def quest_decide_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    for quest in dict_entries(surroundings.get("quests")):
        quest_id = quest.get("id")
        if not isinstance(quest_id, str):
            continue
        for choice in dict_entries(quest.get("choices")):
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


def looks_like_quest_accept(player_input: str) -> bool:
    if not has_any(player_input, QUEST_ACCEPT_TERMS):
        return False
    return has_any(player_input, QUEST_CONTEXT_TERMS)


def named_giver_quest(
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


def quest_giver_id(quest_id: str, quests: list[dict[str, Any]]) -> str | None:
    for quest in quests:
        if quest.get("id") == quest_id and isinstance(quest.get("giver"), str):
            return quest["giver"]
    return None
