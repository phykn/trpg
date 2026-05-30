from __future__ import annotations

from typing import Any

from src.game.domain.action import Action, ActionOutput, RefuseReason
from src.locale.render import render
from src.locale.terms import DIALOGUE_GENERIC_TARGETS, DIALOGUE_TERMS

from .surroundings import dict_entries, named_entry
from .text_intents import looks_like_direct_dialogue, looks_like_information_question
from .text_match import dialogue_target_phrases, has_localized_target_names


def single_visible_npc_question_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    if not looks_like_information_question(player_input):
        return None
    targets = [
        entry
        for entry in dict_entries(surroundings.get("entities"))
        if entry.get("type") in {"npc", "enemy"} and isinstance(entry.get("id"), str)
    ]
    if len(targets) != 1:
        return None
    return Action(verb="speak", to=targets[0]["id"], how="friendly")


def named_visible_dialogue_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    if not looks_like_direct_dialogue(player_input):
        return None
    target = named_entry(
        player_input,
        [
            entry
            for entry in dict_entries(surroundings.get("entities"))
            if entry.get("type") in {"npc", "enemy"}
        ],
    )
    if target is None:
        return None
    return Action(verb="speak", to=target["id"], how="friendly")


def missing_dialogue_target_refusal(
    player_input: str,
    surroundings: dict[str, Any],
    *,
    locale: str,
) -> ActionOutput | None:
    if not any(term in player_input for term in DIALOGUE_TERMS):
        return None
    targets = [
        entry
        for entry in dict_entries(surroundings.get("entities"))
        if entry.get("type") in {"npc", "enemy"}
    ]
    if not has_localized_target_names(targets):
        return None
    if named_entry(player_input, targets) is not None:
        return None
    recent = surroundings.get("recent_npc")
    if isinstance(recent, dict) and isinstance(recent.get("name"), str):
        if recent["name"] in player_input:
            return None
    for phrase in dialogue_target_phrases(player_input):
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
