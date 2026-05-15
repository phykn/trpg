from typing import Any

from pydantic import BaseModel


class GraphSuggestion(BaseModel):
    label: str
    input_text: str
    intent: str | None = None
    action: dict[str, Any] | None = None


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
