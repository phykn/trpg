from typing import Any, Literal

from pydantic import BaseModel, Field


class NarrateInput(BaseModel):
    world: str
    session: dict[str, Any]
    history: str
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
    player_input: str


class NarrateOutput(BaseModel):
    turn_summary: str = ""
    state_changes: list[dict[str, Any]] = []
    memorable: bool = False
    memory_targets: list[str] = []
    memory: str | None = None
    memory_links: dict[str, str | None] = {}
    importance: int | None = Field(default=None, ge=1, le=3)
