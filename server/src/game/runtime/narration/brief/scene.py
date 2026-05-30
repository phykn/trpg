"""Top-level narration brief selection and non-combat brief builders."""

from typing import Any

from .coerce import as_dict, as_dicts, as_strings
from .combat import build_combat_narration_brief
from .context import (
    append_player_input,
    current_place_detail_lines,
    event_fact_lines,
    looks_like_dialogue_input,
    place_name,
    recent_context_lines,
    target_name,
    target_public_knowledge_lines,
)
from .rendering import brief


def build_narration_brief(payload: dict[str, Any]) -> str:
    event = as_dict(payload.get("engine_event"))
    if as_dict(event.get("story_transition")):
        return _story_transition_brief(payload, event)
    if event.get("kind") == "combat":
        return build_combat_narration_brief(payload)
    if event.get("kind") == "roll":
        return _roll_brief(payload, event)
    return _action_brief(payload, event)


def _story_transition_brief(
    payload: dict[str, Any],
    event: dict[str, Any],
) -> str:
    transition = as_dict(event.get("story_transition"))
    completed = ", ".join(
        item["name"] for item in as_dicts(transition.get("completed_quests"))
    )
    chapter = as_dict(transition.get("opened_chapter")).get("name")
    quest = as_dict(transition.get("next_quest")).get("name")
    next_text = " / ".join(
        value for value in (chapter, quest) if isinstance(value, str) and value
    )
    lines = recent_context_lines(payload, include_recent=False)
    lines.extend(
        [
            brief("scene.transition"),
            brief("place", value=place_name(payload)),
        ]
    )
    if completed:
        lines.append(brief("completed", value=completed))
    choice_result = _choice_result_line(transition)
    if choice_result:
        lines.append(brief("choice_result", value=choice_result))
    if next_text:
        lines.append(brief("next", value=next_text))
    handoff = transition.get("handoff")
    if isinstance(handoff, str) and handoff:
        lines.append(brief("handoff", value=handoff))
    append_player_input(lines, payload)
    return "\n".join(lines)


def _choice_result_line(transition: dict[str, Any]) -> str:
    choice_result = as_dict(transition.get("choice_result"))
    choice = as_dict(choice_result.get("choice")).get("label")
    gained_items = ", ".join(
        item["name"]
        for item in as_dicts(choice_result.get("gained_items"))
        if isinstance(item.get("name"), str) and item["name"]
    )
    parts = []
    if isinstance(choice, str) and choice:
        parts.append(brief("choice", value=choice))
    if gained_items:
        parts.append(brief("gained_items", value=gained_items))
    return " / ".join(parts)


def _roll_brief(payload: dict[str, Any], event: dict[str, Any]) -> str:
    outcome = event.get("outcome")
    result = (
        brief("outcome.success")
        if outcome == "success"
        else brief("outcome.failure")
    )
    lines = recent_context_lines(payload)
    lines.extend(
        [
            brief("scene.roll"),
            brief("place", value=place_name(payload)),
            brief("target", value=target_name(payload)),
        ]
    )
    revealed_facts = event_fact_lines(event) if outcome == "success" else []
    target_facts = (
        target_public_knowledge_lines(payload)
        if outcome == "success" and not revealed_facts
        else []
    )
    if revealed_facts:
        lines.append(brief("revealed_facts"))
        lines.extend(f"- {fact}" for fact in revealed_facts)
    elif target_facts:
        lines.append(brief("target_info"))
        lines.extend(f"- {fact}" for fact in target_facts)
    lines.append(brief("result", value=result))
    resolved = as_strings(event.get("resolved_results"))
    if resolved:
        lines.append(brief("confirmed_inline", value=" / ".join(resolved)))
    append_player_input(lines, payload)
    return "\n".join(lines)


def _action_brief(payload: dict[str, Any], event: dict[str, Any]) -> str:
    kind = event.get("kind")
    lines = [] if kind == "move" else recent_context_lines(payload)
    is_dialogue_like = kind == "dialogue" or looks_like_dialogue_input(payload)
    lines.extend(
        [
            brief(
                "scene.action",
                kind=kind
                if isinstance(kind, str) and kind
                else brief("scene.action_default"),
            ),
            brief("place", value=place_name(payload)),
        ]
    )
    if kind == "move" or is_dialogue_like:
        place_lines = current_place_detail_lines(payload)
        if place_lines:
            lines.append(brief("current_place"))
            lines.extend(f"- {line}" for line in place_lines)
    target = target_name(payload)
    if target:
        lines.append(brief("target", value=target))
        if kind == "dialogue" or looks_like_dialogue_input(payload):
            lines.append(brief("dialogue_responder", value=target))
    target_facts = target_public_knowledge_lines(payload)
    if target_facts:
        lines.append(brief("target_info"))
        lines.extend(f"- {fact}" for fact in target_facts)
    resolved = as_strings(event.get("resolved_results"))
    if resolved:
        lines.append(brief("confirmed_inline", value=" / ".join(resolved)))
    append_player_input(lines, payload)
    return "\n".join(lines)
