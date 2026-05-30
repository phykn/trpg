"""Shared context extraction for narration briefs."""

from typing import Any

from src.locale.terms import (
    DIALOGUE_REQUEST_TERMS,
    DIALOGUE_TARGET_PARTICLES,
    DIALOGUE_TERMS,
)

from .coerce import as_dict, as_dicts, as_strings, clip, dedupe
from .rendering import brief


def append_player_input(lines: list[str], payload: dict[str, Any]) -> None:
    player_input = player_input_text(payload)
    if player_input != brief("none"):
        lines.append(brief("player_input", value=player_input))


def recent_context_lines(
    payload: dict[str, Any],
    *,
    include_recent: bool = True,
) -> list[str]:
    lines: list[str] = []
    context = as_dict(payload.get("reference_context"))
    world_guidance = context.get("world_guidance")
    if isinstance(world_guidance, str) and world_guidance:
        lines.append(brief("world_guidance"))
        lines.append(f"- {clip(world_guidance)}")
    current_story = _current_story_lines(context)
    if current_story:
        lines.append(brief("current_story"))
        lines.extend(f"- {text}" for text in current_story)
    if not include_recent:
        return lines
    previous = as_dicts(context.get("previous_scene"))
    memories = as_dicts(context.get("subject_memories"))
    exchanges = as_dicts(context.get("recent_exchanges"))
    discoveries = as_dict(context.get("discoveries"))

    previous_scene = [
        clip(summary)
        for item in previous
        if isinstance(summary := item.get("summary"), str) and summary
    ]
    if previous_scene:
        lines.append(brief("previous_scene"))
        lines.extend(f"- {text}" for text in previous_scene)

    subject_memories = [
        clip(content)
        for item in memories
        if isinstance(content := item.get("content"), str) and content
    ]
    if subject_memories:
        lines.append(brief("subject_memories"))
        lines.extend(f"- {text}" for text in subject_memories)

    discovery_lines = _discovery_lines(discoveries)
    if discovery_lines:
        lines.append(brief("discoveries"))
        lines.extend(f"- {text}" for text in discovery_lines)

    recent_exchanges = []
    for item in exchanges:
        player = item.get("player")
        narrator = item.get("narrator")
        player_text = player if isinstance(player, str) and player else ""
        narrator_text = narrator if isinstance(narrator, str) and narrator else ""
        cues = [
            text
            for cue in as_dicts(item.get("cues"))
            if isinstance(text := cue.get("text"), str) and text
        ]
        if player_text or narrator_text or cues:
            recent_exchanges.append((player_text, narrator_text, cues))
    if recent_exchanges:
        lines.append(brief("recent_exchanges"))
        for player, narrator, cues in recent_exchanges:
            if player:
                lines.append(f"- {brief('player', value=clip(player))}")
            if narrator:
                lines.append(f"- {brief('gm', value=clip(narrator))}")
            for cue in cues:
                lines.append(f"- {brief('cue', value=clip(cue))}")
    return lines


def current_place_detail_lines(payload: dict[str, Any]) -> list[str]:
    scene = as_dict(payload.get("scene_state"))
    place = as_dict(scene.get("current_place"))
    out: list[str] = []
    description = place.get("description")
    if isinstance(description, str) and description:
        out.append(clip(description))
    for trait in as_strings(place.get("traits"))[:3]:
        out.append(clip(trait))
    return dedupe(out)


def player_input_text(payload: dict[str, Any]) -> str:
    request = as_dict(payload.get("user_request"))
    value = request.get("player_input")
    return value if isinstance(value, str) and value else brief("none")


def looks_like_dialogue_input(payload: dict[str, Any]) -> bool:
    player_input = player_input_text(payload)
    return any(term in player_input for term in DIALOGUE_TARGET_PARTICLES) or any(
        term in player_input
        for term in (*DIALOGUE_TERMS, *DIALOGUE_REQUEST_TERMS)
    )


def place_name(payload: dict[str, Any]) -> str:
    scene = as_dict(payload.get("scene_state"))
    place = as_dict(scene.get("current_place"))
    if not place:
        anchor = as_dict(scene.get("scene_anchor"))
        place = as_dict(anchor.get("location"))
    value = place.get("name")
    return value if isinstance(value, str) and value else brief("unknown")


def target_name(payload: dict[str, Any]) -> str:
    scene = as_dict(payload.get("scene_state"))
    target = as_dict(scene.get("target_view"))
    value = target.get("name")
    return value if isinstance(value, str) and value else ""


def target_public_knowledge_lines(payload: dict[str, Any]) -> list[str]:
    scene = as_dict(payload.get("scene_state"))
    target = as_dict(scene.get("target_view"))
    out: list[str] = []
    for item in as_dicts(target.get("public_knowledge")):
        title = item.get("title")
        summary = item.get("summary")
        if not isinstance(summary, str) or not summary:
            continue
        if isinstance(title, str) and title:
            out.append(clip(f"{title}: {summary}"))
        else:
            out.append(clip(summary))
    return dedupe(out)


def event_fact_lines(event: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in as_dicts(event.get("revealed_facts")):
        title = item.get("title")
        summary = item.get("summary")
        if not isinstance(summary, str) or not summary:
            continue
        if isinstance(title, str) and title:
            out.append(clip(f"{title}: {summary}"))
        else:
            out.append(clip(summary))
    return dedupe(out)


def _current_story_lines(context: dict[str, Any]) -> list[str]:
    story = as_dict(context.get("current_story"))
    chapter = as_dict(story.get("chapter"))
    quest = as_dict(story.get("active_quest"))
    lines: list[str] = []
    chapter_line = _story_item_line(chapter)
    if chapter_line:
        lines.append(brief("chapter", value=chapter_line))
    for guidance in _story_guidance_lines(chapter):
        lines.append(brief("chapter_guidance", value=guidance))
    quest_line = _story_item_line(quest)
    if quest_line:
        lines.append(brief("active_quest", value=quest_line))
    return lines


def _discovery_lines(discoveries: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in ("clues", "memories"):
        for item in as_dicts(discoveries.get(key)):
            title = item.get("title")
            summary = item.get("summary")
            if isinstance(title, str) and title and isinstance(summary, str) and summary:
                lines.append(clip(f"{title}: {summary}"))
            elif isinstance(summary, str) and summary:
                lines.append(clip(summary))
            elif isinstance(title, str) and title:
                lines.append(clip(title))
    return dedupe(lines)


def _story_item_line(item: dict[str, Any]) -> str:
    name = item.get("name")
    if not isinstance(name, str) or not name:
        return ""
    description = item.get("description")
    if isinstance(description, str) and description:
        return clip(f"{name} - {description}")
    return clip(name)


def _story_guidance_lines(item: dict[str, Any]) -> list[str]:
    guidance = item.get("guidance")
    if isinstance(guidance, str):
        return [clip(guidance)] if guidance.strip() else []
    if isinstance(guidance, list):
        return [
            clip(value)
            for value in guidance[:12]
            if isinstance(value, str) and value.strip()
        ]
    return []
