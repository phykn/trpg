from typing import Any

from pydantic import BaseModel


class ExtractInput(BaseModel):
    """Inputs for the metadata extraction stage. The body has already streamed
    to the client; this stage looks at body + the same context the body had,
    and emits structured metadata that must reflect what the body actually said."""

    body: str
    judge_result: dict[str, Any]
    surroundings: dict[str, Any]
    target_view: dict[str, Any] | None = None
    grade: str | None = None
    previous_phase_signal: str | None = None
