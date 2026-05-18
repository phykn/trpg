from typing import Any

from pydantic import BaseModel

from ..state import GameRuntimeState


class GraphSuggestion(BaseModel):
    label: str
    input_text: str
    intent: str | None = None
    action: dict[str, Any] | None = None


def filter_grounded_suggestions(
    runtime: GameRuntimeState,
    suggestions: list[GraphSuggestion],
) -> list[GraphSuggestion]:
    can_accept_quest = _has_quest_status(runtime, {"locked", "pending"})
    can_abandon_quest = _has_quest_status(runtime, {"active"})
    out: list[GraphSuggestion] = []
    for suggestion in suggestions:
        if suggestion.intent != "quest":
            out.append(suggestion)
            continue
        text = f"{suggestion.label} {suggestion.input_text}".lower()
        wants_accept = _ko_accept() in text or "accept" in text
        wants_abandon = _ko_abandon() in text or "abandon" in text
        if wants_accept and not can_accept_quest:
            continue
        if wants_abandon and not can_abandon_quest:
            continue
        out.append(suggestion)
    return out


def normalize_suggestion(value: object) -> GraphSuggestion | None:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        return GraphSuggestion(label=text, input_text=text)
    if isinstance(value, GraphSuggestion):
        label = value.label.strip()
        input_text = value.input_text.strip()
        if not label or not input_text:
            return None
        return value.model_copy(update={"label": label, "input_text": input_text})
    if isinstance(value, dict):
        label = str(value.get("label", "")).strip()
        input_text = str(value.get("input_text", "")).strip()
        if not label or not input_text:
            return None
        return GraphSuggestion(
            label=label,
            input_text=input_text,
            intent=str(value["intent"]).strip() if value.get("intent") else None,
            action=value.get("action")
            if isinstance(value.get("action"), dict)
            else None,
        )
    return None


def _has_quest_status(runtime: GameRuntimeState, statuses: set[str]) -> bool:
    for node in runtime.graph.nodes.values():
        if node.type != "quest":
            continue
        status = node.properties.get("status")
        if isinstance(status, str) and status in statuses:
            return True
    return False


def _ko_accept() -> str:
    return chr(0xC218) + chr(0xB77D)


def _ko_abandon() -> str:
    return chr(0xD3EC) + chr(0xAE30)
