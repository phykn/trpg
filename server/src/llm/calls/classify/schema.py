import json
from typing import Any

from pydantic import BaseModel

# Verb / RefuseReason / JudgeOutput live in domain/verb.py to break import cycle
# with domain/memory.py (PendingCheck carries Verb). Re-exported here so call sites
# can import from either location.
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
    return JudgeOutput.model_validate(raw, context={"in_combat": in_combat})
