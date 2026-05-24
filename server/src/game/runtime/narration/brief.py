from typing import Any

from src.locale.render import render
from src.locale.terms import (
    DIALOGUE_REQUEST_TERMS,
    DIALOGUE_TARGET_PARTICLES,
    DIALOGUE_TERMS,
)

_LOCALE = "ko"


def _brief(key: str, **vars: object) -> str:
    return render(f"runtime.narration.brief.{key}", _LOCALE, **vars)


def build_narration_brief(payload: dict[str, Any]) -> str:
    event = _dict(payload.get("engine_event"))
    if _dict(event.get("story_transition")):
        return _story_transition_brief(payload, event)
    if event.get("kind") == "combat":
        return build_combat_narration_brief(payload)
    if event.get("kind") == "roll":
        return _roll_brief(payload, event)
    return _action_brief(payload, event)


def build_combat_narration_brief(payload: dict[str, Any]) -> str:
    event = _dict(payload.get("engine_event"))
    combat = _dict(payload.get("combat_view"))
    lines = _recent_context_lines(payload)
    lines.extend([_brief("scene.combat"), _brief("place", value=_place_name(payload))])
    target = _combat_target(combat) or _target_name(payload)
    if target:
        lines.append(_brief("target", value=target))
    lines.extend(
        [
            _brief("action", value=_combat_action(combat, event)),
            _brief("result", value=_combat_result(combat)),
        ]
    )
    outcome = combat.get("outcome")
    if isinstance(outcome, str) and outcome:
        lines.append(_brief("combat_state", value=outcome))
    facts = _combat_facts(event, combat, payload)
    if facts:
        lines.append(_brief("confirmed"))
        lines.extend(f"- {fact}" for fact in facts)
    _append_player_input(lines, payload)
    return "\n".join(lines)


def _story_transition_brief(
    payload: dict[str, Any],
    event: dict[str, Any],
) -> str:
    transition = _dict(event.get("story_transition"))
    completed = ", ".join(
        item["name"] for item in _dicts(transition.get("completed_quests"))
    )
    chapter = _dict(transition.get("opened_chapter")).get("name")
    quest = _dict(transition.get("next_quest")).get("name")
    next_text = " / ".join(
        value for value in (chapter, quest) if isinstance(value, str) and value
    )
    lines = _recent_context_lines(payload, include_recent=False)
    lines.extend(
        [
            _brief("scene.transition"),
            _brief("place", value=_place_name(payload)),
        ]
    )
    if completed:
        lines.append(_brief("completed", value=completed))
    if next_text:
        lines.append(_brief("next", value=next_text))
    handoff = transition.get("handoff")
    if isinstance(handoff, str) and handoff:
        lines.append(_brief("handoff", value=handoff))
    _append_player_input(lines, payload)
    return "\n".join(lines)


def _combat_action(combat: dict[str, Any], event: dict[str, Any]) -> str:
    value = combat.get("player_action")
    if isinstance(value, str) and value:
        return value
    action = _dict(event.get("action"))
    verb = action.get("verb")
    labels = {
        "attack": _brief("combat_action.attack"),
        "defend": _brief("combat_action.defend"),
        "move": _brief("combat_action.move"),
        "speak": _brief("combat_action.speak"),
        "pass": _brief("combat_action.pass"),
    }
    return (
        labels.get(verb, _brief("combat_action.default"))
        if isinstance(verb, str)
        else _brief("combat_action.default")
    )


def _combat_result(combat: dict[str, Any]) -> str:
    value = combat.get("exchange_result_label")
    if isinstance(value, str) and value:
        return value
    result = combat.get("exchange_result")
    if result == "success":
        return _brief("outcome.success")
    if result == "failure":
        return _brief("outcome.failure")
    return _brief("outcome.neutral")


def _combat_target(combat: dict[str, Any]) -> str:
    for event in _dicts(combat.get("events")):
        target = _dict(event.get("target"))
        name = target.get("name")
        if isinstance(name, str) and name:
            return name
    return ""


def _combat_facts(
    event: dict[str, Any],
    combat: dict[str, Any],
    payload: dict[str, Any],
) -> list[str]:
    facts = _strings(event.get("resolved_results"))
    for item in _dicts(combat.get("events"))[:3]:
        line = _combat_event_fact(item)
        if line:
            facts.append(line)
    effect = _dict(combat.get("effect"))
    effect_name = effect.get("name")
    if isinstance(effect_name, str) and effect_name:
        facts.append(_brief("effect", value=effect_name))
    for status in _dicts(combat.get("statuses"))[:3]:
        status_name = status.get("name")
        if isinstance(status_name, str) and status_name:
            facts.append(_brief("status", value=status_name))
    cards = [
        text
        for item in _dicts(payload.get("result_cards"))
        if isinstance(text := item.get("text"), str) and text
    ]
    return _dedupe([*facts, *cards])


def _combat_event_fact(event: dict[str, Any]) -> str:
    actor = _dict(event.get("actor")).get("name")
    target = _dict(event.get("target")).get("name")
    motion = event.get("motion")
    result = event.get("result_label")
    condition = event.get("target_condition")
    parts = [
        value
        for value in (actor, motion, target, result, condition)
        if isinstance(value, str) and value
    ]
    return " / ".join(parts)


def _roll_brief(payload: dict[str, Any], event: dict[str, Any]) -> str:
    outcome = event.get("outcome")
    result = (
        _brief("outcome.success")
        if outcome == "success"
        else _brief("outcome.failure")
    )
    lines = _recent_context_lines(payload)
    lines.extend(
        [
            _brief("scene.roll"),
            _brief("place", value=_place_name(payload)),
            _brief("target", value=_target_name(payload)),
        ]
    )
    revealed_facts = _event_fact_lines(event) if outcome == "success" else []
    target_facts = (
        _target_public_knowledge_lines(payload)
        if outcome == "success" and not revealed_facts
        else []
    )
    if revealed_facts:
        lines.append(_brief("revealed_facts"))
        lines.extend(f"- {fact}" for fact in revealed_facts)
    elif target_facts:
        lines.append(_brief("target_info"))
        lines.extend(f"- {fact}" for fact in target_facts)
    lines.append(_brief("result", value=result))
    resolved = _strings(event.get("resolved_results"))
    if resolved:
        lines.append(_brief("confirmed_inline", value=" / ".join(resolved)))
    _append_player_input(lines, payload)
    return "\n".join(lines)


def _action_brief(payload: dict[str, Any], event: dict[str, Any]) -> str:
    kind = event.get("kind")
    lines = [] if kind == "move" else _recent_context_lines(payload)
    is_dialogue_like = kind == "dialogue" or _looks_like_dialogue_input(payload)
    lines.extend(
        [
            _brief(
                "scene.action",
                kind=kind
                if isinstance(kind, str) and kind
                else _brief("scene.action_default"),
            ),
            _brief("place", value=_place_name(payload)),
        ]
    )
    if kind == "move" or is_dialogue_like:
        place_lines = _current_place_detail_lines(payload)
        if place_lines:
            lines.append(_brief("current_place"))
            lines.extend(f"- {line}" for line in place_lines)
    target = _target_name(payload)
    if target:
        lines.append(_brief("target", value=target))
        if kind == "dialogue" or _looks_like_dialogue_input(payload):
            lines.append(_brief("dialogue_responder", value=target))
    target_facts = _target_public_knowledge_lines(payload)
    if target_facts:
        lines.append(_brief("target_info"))
        lines.extend(f"- {fact}" for fact in target_facts)
    resolved = _strings(event.get("resolved_results"))
    if resolved:
        lines.append(_brief("confirmed_inline", value=" / ".join(resolved)))
    _append_player_input(lines, payload)
    return "\n".join(lines)


def _append_player_input(lines: list[str], payload: dict[str, Any]) -> None:
    player_input = _player_input(payload)
    if player_input != _brief("none"):
        lines.append(_brief("player_input", value=player_input))


def _recent_context_lines(
    payload: dict[str, Any],
    *,
    include_recent: bool = True,
) -> list[str]:
    lines: list[str] = []
    context = _dict(payload.get("reference_context"))
    world_guidance = context.get("world_guidance")
    if isinstance(world_guidance, str) and world_guidance:
        lines.append(_brief("world_guidance"))
        lines.append(f"- {_clip(world_guidance)}")
    current_story = _current_story_lines(context)
    if current_story:
        lines.append(_brief("current_story"))
        lines.extend(f"- {text}" for text in current_story)
    if not include_recent:
        return lines
    previous = _dicts(context.get("previous_scene"))
    exchanges = _dicts(context.get("recent_exchanges"))

    previous_scene = [
        _clip(summary)
        for item in previous
        if isinstance(summary := item.get("summary"), str) and summary
    ]
    if previous_scene:
        lines.append(_brief("previous_scene"))
        lines.extend(f"- {text}" for text in previous_scene)

    recent_exchanges = []
    for item in exchanges:
        player = item.get("player")
        narrator = item.get("narrator")
        player_text = player if isinstance(player, str) and player else ""
        narrator_text = narrator if isinstance(narrator, str) and narrator else ""
        cues = [
            text
            for cue in _dicts(item.get("cues"))
            if isinstance(text := cue.get("text"), str) and text
        ]
        if player_text or narrator_text or cues:
            recent_exchanges.append((player_text, narrator_text, cues))
    if recent_exchanges:
        lines.append(_brief("recent_exchanges"))
        for player, narrator, cues in recent_exchanges:
            if player:
                lines.append(f"- {_brief('player', value=_clip(player))}")
            if narrator:
                lines.append(f"- {_brief('gm', value=_clip(narrator))}")
            for cue in cues:
                lines.append(f"- {_brief('cue', value=_clip(cue))}")
    return lines


def _current_story_lines(context: dict[str, Any]) -> list[str]:
    story = _dict(context.get("current_story"))
    chapter = _dict(story.get("chapter"))
    quest = _dict(story.get("active_quest"))
    lines: list[str] = []
    chapter_line = _story_item_line(chapter)
    if chapter_line:
        lines.append(_brief("chapter", value=chapter_line))
    for guidance in _story_guidance_lines(chapter):
        lines.append(_brief("chapter_guidance", value=guidance))
    quest_line = _story_item_line(quest)
    if quest_line:
        lines.append(_brief("active_quest", value=quest_line))
    return lines


def _current_place_detail_lines(payload: dict[str, Any]) -> list[str]:
    scene = _dict(payload.get("scene_state"))
    place = _dict(scene.get("current_place"))
    out: list[str] = []
    description = place.get("description")
    if isinstance(description, str) and description:
        out.append(_clip(description))
    for trait in _strings(place.get("traits"))[:3]:
        out.append(_clip(trait))
    return _dedupe(out)


def _story_item_line(item: dict[str, Any]) -> str:
    name = item.get("name")
    if not isinstance(name, str) or not name:
        return ""
    description = item.get("description")
    if isinstance(description, str) and description:
        return _clip(f"{name} - {description}")
    return _clip(name)


def _story_guidance_lines(item: dict[str, Any]) -> list[str]:
    guidance = item.get("guidance")
    if isinstance(guidance, str):
        return [_clip(guidance)] if guidance.strip() else []
    if isinstance(guidance, list):
        return [
            _clip(value)
            for value in guidance[:12]
            if isinstance(value, str) and value.strip()
        ]
    return []


def _player_input(payload: dict[str, Any]) -> str:
    request = _dict(payload.get("user_request"))
    value = request.get("player_input")
    return value if isinstance(value, str) and value else _brief("none")


def _looks_like_dialogue_input(payload: dict[str, Any]) -> bool:
    player_input = _player_input(payload)
    return any(term in player_input for term in DIALOGUE_TARGET_PARTICLES) or any(
        term in player_input
        for term in (*DIALOGUE_TERMS, *DIALOGUE_REQUEST_TERMS)
    )


def _place_name(payload: dict[str, Any]) -> str:
    scene = _dict(payload.get("scene_state"))
    place = _dict(scene.get("current_place"))
    if not place:
        anchor = _dict(scene.get("scene_anchor"))
        place = _dict(anchor.get("location"))
    value = place.get("name")
    return value if isinstance(value, str) and value else _brief("unknown")


def _target_name(payload: dict[str, Any]) -> str:
    scene = _dict(payload.get("scene_state"))
    target = _dict(scene.get("target_view"))
    value = target.get("name")
    return value if isinstance(value, str) and value else ""


def _target_public_knowledge_lines(payload: dict[str, Any]) -> list[str]:
    scene = _dict(payload.get("scene_state"))
    target = _dict(scene.get("target_view"))
    out: list[str] = []
    for item in _dicts(target.get("public_knowledge")):
        title = item.get("title")
        summary = item.get("summary")
        if not isinstance(summary, str) or not summary:
            continue
        if isinstance(title, str) and title:
            out.append(_clip(f"{title}: {summary}"))
        else:
            out.append(_clip(summary))
    return _dedupe(out)


def _event_fact_lines(event: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in _dicts(event.get("revealed_facts")):
        title = item.get("title")
        summary = item.get("summary")
        if not isinstance(summary, str) or not summary:
            continue
        if isinstance(title, str) and title:
            out.append(_clip(f"{title}: {summary}"))
        else:
            out.append(_clip(summary))
    return _dedupe(out)


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _dedupe(values: list[str]) -> list[str]:
    out = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _clip(value: str) -> str:
    return " ".join(value.split())
