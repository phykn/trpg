from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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
    # Engine results from the immediately preceding turn — each entry is {"type": str, "summary": str}.
    # Narrate must not contradict these (e.g. must not say "no combat" if a combat summary is present).
    recent_engine_events: list[dict] = []
    player_input: str

    @field_validator("recent_engine_events", mode="before")
    @classmethod
    def _coerce_none_to_empty(cls, v: object) -> object:
        return v if v is not None else []


class NarrateOutput(BaseModel):
    turn_summary: str = ""
    state_changes: list[dict[str, Any]] = []
    memorable: bool = False
    memory_targets: list[str] = []
    memory: dict[str, str] = {}
    memory_links: dict[str, str | None] = {}
    importance: int | None = Field(default=None, ge=1, le=3)
