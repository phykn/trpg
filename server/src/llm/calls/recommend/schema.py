from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.entities import SkillCandidate


class SkillRecommendInput(BaseModel):
    character: dict
    existing_skills: list[dict]
    recent_turns: list[dict]
    recent_inputs: list[str]


class SkillRecommendOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[SkillCandidate] = Field(min_length=1, max_length=3)


__all__ = ["SkillCandidate", "SkillRecommendInput", "SkillRecommendOutput"]
