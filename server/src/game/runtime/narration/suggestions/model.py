from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GraphSuggestion(BaseModel):
    label: str
    input_text: str
    intent: str | None = None
    action: dict[str, Any] | None = None
