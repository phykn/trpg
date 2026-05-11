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


class ClassifyInput(BaseModel):
    player_input: str
    context: dict[str, Any]


def validate_action_output_json(
    answer: str,
    *,
    in_combat: bool = False,
) -> ActionOutput:
    """Parse classifier JSON into the graph action contract."""
    if not answer.strip():
        raise json.JSONDecodeError("empty answer", answer or "", 0)
    raw = json.loads(answer)
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
