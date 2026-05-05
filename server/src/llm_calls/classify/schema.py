import json
from typing import Any

from pydantic import BaseModel

# Verb / RefuseReason / JudgeOutput live in domain/verb.py to break import cycle
# with domain/memory.py (PendingCheck carries Verb). Re-exported here so call sites
# can import from either location.
from ...domain.verb import (  # noqa: F401
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
    """Parse JSON, validate Pydantic shape, then per-verb modifier validation.
    Pydantic ValidationError → retry. ModifierValidationError → retry.
    Unknown modifier keys silently dropped (LLM hallucination tolerance)."""
    from .modifiers import validate_modifiers

    raw = json.loads(answer)
    output = JudgeOutput.model_validate(raw)
    if output.actions is not None:
        for verb in output.actions:
            validate_modifiers(verb, in_combat=in_combat)
    return output
