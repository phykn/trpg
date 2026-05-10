import json
from typing import Any

from pydantic import BaseModel

from src.game.domain.action import ActionOutput, action_output_to_judge_output
# Re-exported here so classify call sites can import all judge shapes together.
from src.game.domain.verb import (  # noqa: F401
    JudgeOutput,
    RefuseCategory,
    RefuseReason,
    Verb,
    VerbName,
)


class JudgeInput(BaseModel):
    player_input: str
    surroundings: dict[str, Any]
    # Build-up beats so judge can resolve pronouns ("그것을 든다") and detect surprise attacks.
    history: list[dict] = []
    recent_dialogue: list[dict] = []


def validate_judge_output(answer: str, *, in_combat: bool = False) -> JudgeOutput:
    """Parse classifier JSON and normalize it to the internal JudgeOutput."""
    if not answer.strip():
        raise json.JSONDecodeError("empty answer", answer or "", 0)
    raw = json.loads(answer)
    return action_output_to_judge_output(
        ActionOutput.model_validate(raw),
        in_combat=in_combat,
    )
