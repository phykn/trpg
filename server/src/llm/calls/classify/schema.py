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
    """Parse JSON, then validate the JudgeOutput shape with `in_combat` context
    so each Verb's model_validator can apply modifier rules. Empty/whitespace
    answers raise JSONDecodeError so the runner's retry loop sees a structured
    failure (some models leak content=None on internal reasoning hiccups).
    Unknown modifier keys are silently dropped inside Verb.model_validator."""
    if not answer.strip():
        raise json.JSONDecodeError("empty answer", answer or "", 0)
    raw = json.loads(answer)
    if _looks_like_action_output(raw):
        return action_output_to_judge_output(
            ActionOutput.model_validate(raw),
            in_combat=in_combat,
        )
    return JudgeOutput.model_validate(raw, context={"in_combat": in_combat})


def _looks_like_action_output(raw: object) -> bool:
    if not isinstance(raw, dict):
        return False
    actions = raw.get("actions")
    if not isinstance(actions, list):
        return False
    return any(isinstance(action, dict) and "verb" in action for action in actions)
