from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CombatActionKind = Literal["attack", "cast", "defend", "flee"]
CombatOutcome = Literal["ongoing", "victory", "defeat", "fled"]
CombatSide = Literal["player", "enemy"]


class GraphCombatTraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    actor_id: str | None = None
    target_id: str | None = None
    state: str | None = None


class GraphCombatAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CombatActionKind
    target_id: str | None = None
    skill_id: str | None = None


class GraphCombatState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: str
    player_id: str
    enemy_ids: list[str]
    participant_ids: list[str]
    sides: dict[str, CombatSide]
    round: int = Field(default=1, ge=1, le=4)
    last_action: CombatActionKind | None = None
    trace: list[GraphCombatTraceEvent] = Field(default_factory=list)
    outcome: CombatOutcome = "ongoing"
