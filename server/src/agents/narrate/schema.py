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
    # Per-turn engine notices from chain dispatch's non-final parts (e.g.
    # "이미 체력 가득" when a heal is skipped, "거래를 시도했지만 금화가
    # 부족합니다"). Empty for non-chain turns. Narrate must reflect these in
    # prose so the body doesn't contradict what the engine actually applied.
    act_log_lines: list[str] = []
    # One-shot signal carried over from the previous turn. Currently the
    # only value is `"downed_recovered"` (player blacked out at 0 HP last
    # combat and woke via auto death-save). None for ordinary turns. When
    # set, narrate must open the body with the recovery beat — waking,
    # disorientation, the scene re-focusing — before the player_input takes
    # over. The flow layer clears this on its way through narrate so it
    # doesn't echo across multiple turns.
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
