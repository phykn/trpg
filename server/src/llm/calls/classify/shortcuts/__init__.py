from __future__ import annotations

from typing import Any

from src.game.domain.action import Action, ActionOutput
from src.locale.terms import (
    ACTION_ATTACK_TERMS,
    ACTION_CREATE_DISTANCE_TERMS,
    ACTION_PICKUP_TERMS,
)

from .combat import attack_action, protected_attack_refusal
from .dialogue import (
    missing_dialogue_target_refusal,
    named_visible_dialogue_action,
    single_visible_npc_question_action,
)
from .inventory import corpse_loot_action, pickup_action
from .movement import (
    active_quest_location_move_action,
    open_generated_move_action,
    visible_exit_move_action,
)
from .payload import action_output
from .quest import quest_accept_action, quest_decide_action
from .surroundings import has_any
from .text_intents import looks_like_loot

__all__ = ["classify_action_shortcut"]


def classify_action_shortcut(
    player_input: str,
    surroundings: dict[str, Any],
    *,
    locale: str = "ko",
) -> ActionOutput | None:
    quest = quest_accept_action(player_input, surroundings)
    if quest is not None:
        return action_output([quest])

    decision = quest_decide_action(player_input, surroundings)
    if decision is not None:
        return action_output([decision])

    named_dialogue = named_visible_dialogue_action(player_input, surroundings)
    if named_dialogue is not None:
        return action_output([named_dialogue])

    single_npc_question = single_visible_npc_question_action(
        player_input,
        surroundings,
    )
    if single_npc_question is not None:
        return action_output([single_npc_question])

    quest_move = active_quest_location_move_action(player_input, surroundings)
    if quest_move is not None:
        return action_output([quest_move])

    exit_move = visible_exit_move_action(player_input, surroundings)
    if exit_move is not None:
        return action_output([exit_move])

    open_move = open_generated_move_action(player_input)
    if open_move is not None:
        return action_output([open_move])

    if surroundings.get("in_combat") is True and has_any(
        player_input, ACTION_CREATE_DISTANCE_TERMS
    ):
        return action_output(
            [Action(verb="move", how="flee")],
            in_combat=True,
        )

    if has_any(player_input, ACTION_ATTACK_TERMS):
        protected = protected_attack_refusal(player_input, surroundings, locale=locale)
        if protected is not None:
            return protected
        attack = attack_action(player_input, surroundings)
        if attack is not None:
            return action_output(
                [attack],
                in_combat=surroundings.get("in_combat") is True,
            )

    if has_any(player_input, ACTION_PICKUP_TERMS):
        loot = corpse_loot_action(player_input, surroundings)
        if loot is not None:
            return action_output([loot])
        pickup = pickup_action(player_input, surroundings)
        if pickup is not None:
            return action_output([pickup])
    if looks_like_loot(player_input):
        loot = corpse_loot_action(player_input, surroundings)
        if loot is not None:
            return action_output([loot])

    missing_dialogue = missing_dialogue_target_refusal(
        player_input,
        surroundings,
        locale=locale,
    )
    if missing_dialogue is not None:
        return missing_dialogue

    return None
