from typing import Any

from src.game.domain.action import Action


def compact_narration_payload(source: dict[str, Any]) -> dict[str, Any]:
    """Build the compact LLM contract: request, event, scene, references."""
    event = source.get("current_event")
    scene_state = {
        "current_place": source.get("current_place"),
        "scene_anchor": source.get("scene_anchor"),
        "target_view": source.get("target_view"),
    }
    payload = {
        "reference_context": {
            "world_guidance": source.get("world_guidance"),
            "current_story": source.get("current_story"),
            "previous_scene": source.get("previous_scene"),
            "subject_memories": source.get("subject_memories"),
            "recent_exchanges": source.get("recent_exchanges"),
            "discoveries": source.get("discoveries"),
        },
        "scene_state": scene_state,
        "combat_view": source.get("combat_view"),
        "engine_event": event,
        "result_cards": source.get("result_cards"),
        "user_request": {
            "player_input": source.get("player_input"),
        },
    }
    return _drop_empty_narration_values(payload)


def update_compact_narration_event(
    payload: dict[str, Any],
    event: dict[str, Any],
    *,
    player_input: str | None = None,
    result_cards: list[dict[str, Any]] | None = None,
) -> None:
    payload["engine_event"] = event
    if player_input is not None:
        payload["user_request"] = {"player_input": player_input}
    elif "user_request" in payload:
        payload.pop("user_request")
    if result_cards is not None:
        payload["result_cards"] = result_cards


def narration_action_payload(action: Action) -> dict[str, str]:
    payload = {"verb": action.verb}
    if action.how:
        payload["how"] = action.how
    if action.note:
        payload["note"] = action.note
    return payload


def _drop_empty_narration_values(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():  # ssot-allow: recursive payload cleanup
            cleaned = _drop_empty_narration_values(item)
            if cleaned is None or cleaned == [] or cleaned == {}:
                continue
            out[key] = cleaned
        return out
    if isinstance(value, list):
        return [_drop_empty_narration_values(item) for item in value]
    return value
