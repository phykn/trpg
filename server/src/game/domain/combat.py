from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CombatActionKind = Literal[
    "attack",
    "defend",
    "flee",
    "social",
    "precise",
    "guarded",
    "reckless",
    "create_distance",
    "talk",
]
CombatSupportKind = Literal["skill", "item"]
CombatOutcome = Literal[
    "ongoing",
    "victory",
    "defeat",
    "fled",
    "escaped",
    "surrendered",
    "combat_stopped",
]
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
    active_enemy_id: str = ""
    enemy_ids: list[str]
    participant_ids: list[str]
    sides: dict[str, CombatSide]
    player_hearts: int = Field(default=3, ge=0)
    enemy_hearts: int = Field(default=3, ge=0)
    escape_ready: bool = False
    enemy_pressure: int = Field(default=0, ge=0)
    round: int = Field(default=1, ge=1)
    last_action: CombatActionKind | None = None
    last_support_id: str | None = None
    last_support_kind: CombatSupportKind | None = None
    last_roll: int | None = None
    last_dc: int | None = None
    trace: list[GraphCombatTraceEvent] = Field(default_factory=list)
    outcome: CombatOutcome = "ongoing"

    @model_validator(mode="after")
    def _backfill_active_enemy(self) -> "GraphCombatState":
        if not self.active_enemy_id and self.enemy_ids:
            self.active_enemy_id = self.enemy_ids[0]
        return self
