from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...domain.types import StatKey


class SkillCandidate(BaseModel):
    """LLM-produced skill candidate — narrative fields only. Numeric fields
    (mp_cost/power/range/duration) and id/level are filled by engine templates."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=20)
    description: str = Field(min_length=1, max_length=120)
    type: Literal["attack", "heal", "buff", "debuff"]
    target: Literal["self", "single", "area"]
    primary_stat: StatKey
    special_effect: str = Field(min_length=1, max_length=120)


class SkillRecommendInput(BaseModel):
    character: dict
    recent_turns: list[dict]
    recent_inputs: list[str]


class SkillRecommendOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[SkillCandidate] = Field(min_length=3, max_length=3)
