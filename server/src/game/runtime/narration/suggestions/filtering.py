from __future__ import annotations

from src.locale.ko.suggestion_text import ko_abandon, ko_accept, ko_surroundings

from ...state import GameRuntimeState
from .intro import build_intro_suggestions
from .model import GraphSuggestion
from .normalize import normalize_text
from .refs import (
    has_quest_status,
    input_mentions_any,
    inspect_target_refs,
    mentions_any,
    mentions_current_place,
    recent_player_inputs,
    usable_refs,
    visible_character_refs,
    visible_clue_refs,
    visible_exit_refs,
)


def next_turn_suggestions(
    runtime: GameRuntimeState,
    narration_suggestions: list[GraphSuggestion],
) -> list[GraphSuggestion]:
    grounded = filter_grounded_suggestions(runtime, narration_suggestions)
    if grounded:
        return grounded
    fallback = build_intro_suggestions(runtime)
    filtered_fallback = filter_grounded_suggestions(runtime, fallback)
    return filtered_fallback or fallback


def filter_grounded_suggestions(
    runtime: GameRuntimeState,
    suggestions: list[GraphSuggestion],
) -> list[GraphSuggestion]:
    can_accept_quest = has_quest_status(runtime, {"locked", "pending"})
    can_abandon_quest = has_quest_status(runtime, {"active"})
    recent_inputs = recent_player_inputs(runtime)
    out: list[GraphSuggestion] = []
    for suggestion in suggestions:
        if not is_grounded_suggestion(runtime, suggestion):
            continue
        if normalize_text(suggestion.input_text) in recent_inputs:
            continue
        if suggestion.intent != "quest":
            out.append(suggestion)
            continue
        text = f"{suggestion.label} {suggestion.input_text}".lower()
        wants_accept = ko_accept() in text or "accept" in text
        wants_abandon = ko_abandon() in text or "abandon" in text
        if wants_accept and not can_accept_quest:
            continue
        if wants_abandon and not can_abandon_quest:
            continue
        out.append(suggestion)
    return out


def is_grounded_suggestion(
    runtime: GameRuntimeState,
    suggestion: GraphSuggestion,
) -> bool:
    if suggestion.intent is None:
        return False
    intent = suggestion.intent.strip().lower()
    if intent == "move":
        return mentions_any(suggestion, visible_exit_refs(runtime))
    if intent == "talk":
        return mentions_any(suggestion, visible_character_refs(runtime))
    if intent == "use":
        return mentions_any(suggestion, usable_refs(runtime))
    if intent == "combat":
        return runtime.progress.graph_combat_state is not None
    if intent == "inspect":
        return is_grounded_inspect_suggestion(runtime, suggestion)
    if intent == "quest":
        return True
    return False


def is_grounded_inspect_suggestion(
    runtime: GameRuntimeState,
    suggestion: GraphSuggestion,
) -> bool:
    raw_text = suggestion.input_text
    text = normalize_text(raw_text)
    if mentions_any(suggestion, visible_clue_refs(runtime)):
        return False
    if normalize_text(ko_surroundings()) in text:
        return True
    return input_mentions_any(suggestion, inspect_target_refs(runtime)) or (
        mentions_current_place(runtime, raw_text)
    )
