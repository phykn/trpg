"""sleep_encounter 시 시드 풀이 비어 있을 때 즉석 생성할 적 한 마리 (P3 §2.4)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EncounterStats(BaseModel):
    """페어 트레이드 invariant: STR+CHA = 20, DEX+WIS = 20, CON+INT = 20."""

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
    """LLM 입력. world 톤 + location 분위기 + player level + 가용 race 목록."""

    world: str
    location: dict
    player_level: int
    available_races: list[dict]


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
