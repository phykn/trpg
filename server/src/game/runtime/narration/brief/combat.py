"""Combat-specific narration brief construction."""

from typing import Any

from .coerce import as_dict, as_dicts, as_strings, dedupe
from .context import append_player_input, place_name, recent_context_lines, target_name
from .rendering import brief


def build_combat_narration_brief(payload: dict[str, Any]) -> str:
    event = as_dict(payload.get("engine_event"))
    combat = as_dict(payload.get("combat_view"))
    lines = recent_context_lines(payload)
    lines.extend([brief("scene.combat"), brief("place", value=place_name(payload))])
    target = _combat_target(combat) or target_name(payload)
    if target:
        lines.append(brief("target", value=target))
    lines.extend(
        [
            brief("action", value=_combat_action(combat, event)),
            brief("result", value=_combat_result(combat)),
        ]
    )
    outcome = combat.get("outcome")
    if isinstance(outcome, str) and outcome:
        lines.append(brief("combat_state", value=outcome))
    facts = _combat_facts(event, combat, payload)
    if facts:
        lines.append(brief("confirmed"))
        lines.extend(f"- {fact}" for fact in facts)
    append_player_input(lines, payload)
    return "\n".join(lines)


def _combat_action(combat: dict[str, Any], event: dict[str, Any]) -> str:
    value = combat.get("player_action")
    if isinstance(value, str) and value:
        return value
    action = as_dict(event.get("action"))
    verb = action.get("verb")
    labels = {
        "attack": brief("combat_action.attack"),
        "defend": brief("combat_action.defend"),
        "move": brief("combat_action.move"),
        "speak": brief("combat_action.speak"),
        "pass": brief("combat_action.pass"),
    }
    return (
        labels.get(verb, brief("combat_action.default"))
        if isinstance(verb, str)
        else brief("combat_action.default")
    )


def _combat_result(combat: dict[str, Any]) -> str:
    value = combat.get("exchange_result_label")
    if isinstance(value, str) and value:
        return value
    result = combat.get("exchange_result")
    if result == "success":
        return brief("outcome.success")
    if result == "failure":
        return brief("outcome.failure")
    return brief("outcome.neutral")


def _combat_target(combat: dict[str, Any]) -> str:
    for event in as_dicts(combat.get("events")):
        target = as_dict(event.get("target"))
        name = target.get("name")
        if isinstance(name, str) and name:
            return name
    return ""


def _combat_facts(
    event: dict[str, Any],
    combat: dict[str, Any],
    payload: dict[str, Any],
) -> list[str]:
    facts = as_strings(event.get("resolved_results"))
    for item in as_dicts(combat.get("events"))[:3]:
        line = _combat_event_fact(item)
        if line:
            facts.append(line)
    effect = as_dict(combat.get("effect"))
    effect_name = effect.get("name")
    if isinstance(effect_name, str) and effect_name:
        facts.append(brief("effect", value=effect_name))
    for status in as_dicts(combat.get("statuses"))[:3]:
        status_name = status.get("name")
        if isinstance(status_name, str) and status_name:
            facts.append(brief("status", value=status_name))
    cards = [
        text
        for item in as_dicts(payload.get("result_cards"))
        if isinstance(text := item.get("text"), str) and text
    ]
    return dedupe([*facts, *cards])


def _combat_event_fact(event: dict[str, Any]) -> str:
    actor = as_dict(event.get("actor")).get("name")
    target = as_dict(event.get("target")).get("name")
    motion = event.get("motion")
    result = event.get("result_label")
    condition = event.get("target_condition")
    parts = [
        value
        for value in (actor, motion, target, result, condition)
        if isinstance(value, str) and value
    ]
    return " / ".join(parts)
