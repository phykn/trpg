from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CombatActionKind = Literal["attack", "defend", "flee", "social"]
CombatSupportKind = Literal["skill", "item"]
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
    support_id: str | None = None
    support_kind: CombatSupportKind | None = None


class GraphCombatState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: str
    player_id: str
    active_enemy_id: str
    enemy_ids: list[str]
    participant_ids: list[str]
    sides: dict[str, CombatSide]
    player_hearts: int = Field(default=3, ge=0)
    enemy_hearts: int = Field(default=3, ge=0)
    round: int = Field(default=1, ge=1)
    last_action: CombatActionKind | None = None
    last_support_id: str | None = None
    last_support_kind: CombatSupportKind | None = None
    last_roll: int | None = None
    last_dc: int | None = None
    trace: list[GraphCombatTraceEvent] = Field(default_factory=list)
    outcome: CombatOutcome = "ongoing"
