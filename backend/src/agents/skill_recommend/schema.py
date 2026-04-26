from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...domain.types import StatKey


class SkillCandidate(BaseModel):
    """LLM 이 산출하는 스킬 후보 — 서사 부분만. 수치 (mp_cost/power/range/duration) 와
    id/level 은 엔진이 템플릿으로 채움."""

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
