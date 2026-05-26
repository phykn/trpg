from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


StoryPatchOp = Literal["add_memory", "add_clue"]
StoryStability = Literal["scene", "chapter", "campaign", "core"]


class StoryWorldContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    locale: Literal["ko"] = "ko"


class StoryToneContract(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    register_: str = Field(alias="register", min_length=1)
    person: Literal["second"]


class StoryBudgetContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patches_per_turn: int = Field(ge=0, le=4)
    new_terms_per_turn: int = Field(ge=0, le=4)


class StoryStabilityDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    add_memory: StoryStability = "campaign"
    add_clue: StoryStability = "scene"


class StoryContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    world: StoryWorldContract
    fixed: list[str] = Field(default_factory=list)
    forbid: list[str] = Field(default_factory=list)
    tone: StoryToneContract
    budgets: StoryBudgetContract
    allowed_ops: list[StoryPatchOp]
    stability_defaults: StoryStabilityDefaults

    @model_validator(mode="after")
    def _allowed_ops_are_mvp_only(self) -> "StoryContract":
        if not self.allowed_ops:
            raise ValueError("allowed_ops must contain at least one operation")
        if not set(self.allowed_ops).issubset({"add_memory", "add_clue"}):
            raise ValueError("generated MVP allows only add_memory and add_clue")
        return self
