from __future__ import annotations

from src.locale.ko.suggestion_text import (
    TARGETLESS_GENERIC_SUGGESTIONS,
    TARGETLESS_TALK_LABELS,
    TARGET_PARTICLES,
)

from .model import GraphSuggestion


def normalize_suggestion(value: object) -> GraphSuggestion | None:
    if isinstance(value, GraphSuggestion):
        label = value.label.strip()
        input_text = value.input_text.strip()
        if not label or not input_text:
            return None
        if is_targetless_generic_suggestion(label, input_text):
            return None
        return value.model_copy(update={"label": label, "input_text": input_text})
    if isinstance(value, dict):
        raw_label = value.get("label")
        raw_input_text = value.get("input_text")
        if not isinstance(raw_label, str) or not isinstance(raw_input_text, str):
            return None
        label = raw_label.strip()
        input_text = raw_input_text.strip()
        if not label or not input_text:
            return None
        if looks_like_json_fragment(label) or looks_like_json_fragment(input_text):
            return None
        if is_targetless_generic_suggestion(label, input_text):
            return None
        intent = value.get("intent")
        return GraphSuggestion(
            label=label,
            input_text=input_text,
            intent=intent.strip() if isinstance(intent, str) and intent.strip() else None,
            action=value.get("action")
            if isinstance(value.get("action"), dict)
            else None,
        )
    return None


def normalize_text(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def looks_like_json_fragment(text: str) -> bool:
    if text.startswith(("{", "[")):
        return True
    lowered = text.lower()
    return '"label"' in lowered or '"input_text"' in lowered or '"input_te' in lowered


def is_targetless_generic_suggestion(label: str, input_text: str) -> bool:
    generic = set(TARGETLESS_GENERIC_SUGGESTIONS)
    normalized_label = normalize_text(label)
    normalized_input = normalize_text(input_text)
    targetless_talk = targetless_talk_labels()
    if normalized_label in targetless_talk:
        return True
    if has_targeted_generic_talk_label(normalized_label, targetless_talk):
        return True
    if normalized_label in generic and normalized_input in generic:
        return True
    if normalized_label != normalized_input:
        return False
    return any(phrase in normalized_label for phrase in targetless_talk)


def targetless_talk_labels() -> set[str]:
    return {normalize_text(value) for value in TARGETLESS_TALK_LABELS}


def has_targeted_generic_talk_label(
    normalized_label: str,
    targetless_talk: set[str],
) -> bool:
    target_particles = {normalize_text(value) for value in TARGET_PARTICLES}
    return any(
        f"{particle}{phrase}" in normalized_label
        for particle in target_particles
        for phrase in targetless_talk
    )
