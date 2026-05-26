from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .story_contract import StoryStability


StoryWriteIntentKind = Literal[
    "none",
    "memory_candidate",
    "clue_candidate",
    "both",
]


class StoryWriteIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: StoryWriteIntentKind
    reason: str | None = None


class AddMemoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["add_memory"]
    id: str = Field(pattern=r"^mem_[a-z0-9_]+$")
    summary: str = Field(min_length=1, max_length=240)
    stability: StoryStability = "campaign"
    visibility: Literal["player", "private", "developer"] = "player"


class AddCluePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["add_clue"]
    id: str = Field(pattern=r"^clue_[a-z0-9_]+$")
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=240)
    anchor_id: str | None = None
    stability: StoryStability = "scene"
    visibility: Literal["player", "private", "developer"] = "player"


StoryPatch = Annotated[AddMemoryPatch | AddCluePatch, Field(discriminator="op")]


class StoryWriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=240)
    patches: list[StoryPatch] = Field(default_factory=list, max_length=4)
    new_terms: list[str] = Field(default_factory=list, max_length=4)
    narration_brief: str | None = Field(default=None, max_length=240)
