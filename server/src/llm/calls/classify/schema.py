import json
from typing import Any

from pydantic import BaseModel

from src.game.domain.action import (
    Action,
    ActionOutput,
    ActionVerb,
    RefuseCategory,
    RefuseReason,
)
from .action_builder import build_action_output


class ClassifyInput(BaseModel):
    player_input: str
    context: dict[str, Any]


def validate_action_output_json(
    answer: str,
    *,
    in_combat: bool = False,
    surroundings: dict[str, Any] | None = None,
) -> ActionOutput:
    """Parse classifier JSON into the graph action contract."""
    if not answer.strip():
        raise json.JSONDecodeError("empty answer", answer or "", 0)
    raw = json.loads(answer)
    if isinstance(raw, dict) and "intents" in raw:
        return build_action_output(raw, surroundings or {"in_combat": in_combat})
    return ActionOutput.model_validate(raw, context={"in_combat": in_combat})


__all__ = [
    "Action",
    "ActionOutput",
    "ActionVerb",
    "ClassifyInput",
    "RefuseCategory",
    "RefuseReason",
    "validate_action_output_json",
]
