from __future__ import annotations

from src.locale.terms import (
    DIALOGUE_QUESTION_TERMS,
    DIALOGUE_TARGET_PARTICLES,
    DIALOGUE_TERMS,
    INSPECT_TERMS,
    LOOT_TERMS,
)

from .surroundings import has_any


def looks_like_dialogue(player_input: str) -> bool:
    return has_any(player_input, DIALOGUE_TERMS) or has_any(
        player_input,
        DIALOGUE_TARGET_PARTICLES,
    )


def looks_like_direct_dialogue(player_input: str) -> bool:
    return has_any(player_input, DIALOGUE_TERMS) or "「" in player_input


def looks_like_information_question(player_input: str) -> bool:
    return "?" in player_input or has_any(player_input, DIALOGUE_QUESTION_TERMS)


def looks_like_inspect(player_input: str) -> bool:
    return has_any(player_input, INSPECT_TERMS)


def looks_like_loot(player_input: str) -> bool:
    return any(term in player_input for term in LOOT_TERMS)
