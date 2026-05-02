from typing import Any, Literal

from pydantic import BaseModel, Field


class NarrateInput(BaseModel):
    world: str
    session: dict[str, Any]
    history: str
    player_view: dict[str, Any]
    target_view: dict[str, Any] | None = None
    surroundings: dict[str, Any]
    judge_result: dict[str, Any]
    grade: (
        Literal[
            "critical_success",
            "success",
            "partial_success",
            "failure",
            "critical_failure",
        ]
        | None
    ) = None
    # Engine notices from non-final chain parts; narrate must reflect them so prose can't contradict the engine.
    act_log_lines: list[str] = []
    # One-shot from previous turn (only `"downed_recovered"` today). Narrate opens with the recovery beat; flow clears it after.
    previous_phase_signal: str | None = None
    player_input: str


class NarrateOutput(BaseModel):
    turn_summary: str = ""
    state_changes: list[dict[str, Any]] = []
    memorable: bool = False
    memory_targets: list[str] = []
    memory: dict[str, str] = {}
    memory_links: dict[str, str | None] = {}
    importance: int | None = Field(default=None, ge=1, le=3)
    suggestions: list[str] = Field(default_factory=list, max_length=3)
