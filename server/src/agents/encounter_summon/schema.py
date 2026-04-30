"""On-the-fly enemy synthesis when the seed pool is empty during sleep_encounter (P3 §2.4)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EncounterStats(BaseModel):
    """Pair-trade invariant: STR+CHA = 20, DEX+WIS = 20, CON+INT = 20."""

    model_config = ConfigDict(extra="forbid")

    STR: int = Field(ge=0, le=20)
    DEX: int = Field(ge=0, le=20)
    CON: int = Field(ge=0, le=20)
    INT: int = Field(ge=0, le=20)
    WIS: int = Field(ge=0, le=20)
    CHA: int = Field(ge=0, le=20)

    @model_validator(mode="after")
    def _pair_trade(self) -> "EncounterStats":
        if self.STR + self.CHA != 20:
            raise ValueError(
                f"pair-trade: STR+CHA must = 20, got {self.STR}+{self.CHA}"
            )
        if self.DEX + self.WIS != 20:
            raise ValueError(
                f"pair-trade: DEX+WIS must = 20, got {self.DEX}+{self.WIS}"
            )
        if self.CON + self.INT != 20:
            raise ValueError(
                f"pair-trade: CON+INT must = 20, got {self.CON}+{self.INT}"
            )
        return self


class EncounterSummonInput(BaseModel):
    """LLM input: world tone + location mood + player level + available race list.

    `requested_role` is an optional Korean hint (e.g., "경비병", "용병") that
    pins the summoned character's name and concept when the player explicitly
    references a not-yet-instanced NPC. When unset, the agent generates a
    location-appropriate generic enemy.
    """

    world: str
    location: dict
    player_level: int
    available_races: list[dict]
    requested_role: str | None = None


class EncounterSummonOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=20)
    description: str = Field(min_length=1, max_length=200)
    appearance: str = Field(min_length=1, max_length=120)
    tone_hint: str = Field(default="", max_length=80)
    race_id: str
    stats: EncounterStats
    attack_priority: Literal[
        "nearest", "lowest_hp", "highest_threat", "healer_first", "random"
    ] = "nearest"
