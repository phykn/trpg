from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    @model_validator(mode="before")
    @classmethod
    def _ignore_clue_only_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "title" not in data and "anchor_id" not in data:
            return data
        normalized = dict(data)
        normalized.pop("title", None)
        normalized.pop("anchor_id", None)
        return normalized


class AddCluePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["add_clue"]
    id: str = Field(pattern=r"^clue_[a-z0-9_]+$")
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=240)
    anchor_id: str | None = None
    stability: StoryStability = "scene"
    visibility: Literal["player", "private", "developer"] = "player"


class AddLocationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["add_location"]
    id: str = Field(pattern=r"^loc_[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=240)
    connect_from: str
    stability: StoryStability = "scene"

    @model_validator(mode="before")
    @classmethod
    def _accept_title_summary_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "title" not in data and "summary" not in data:
            return data
        normalized = dict(data)
        title = normalized.pop("title", None)
        summary = normalized.pop("summary", None)
        if "name" not in normalized and isinstance(title, str):
            normalized["name"] = title
        if "description" not in normalized and isinstance(summary, str):
            normalized["description"] = summary
        return normalized


class AddCharacterPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["add_character"]
    id: str = Field(pattern=r"^char_[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=80)
    role: Literal[
        "witness",
        "companion",
        "opponent",
        "merchant",
        "bystander",
        "quest_giver",
    ]
    location_id: str
    stability: StoryStability = "scene"


class AddItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["add_item"]
    id: str = Field(pattern=r"^item_[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=240)
    location_id: str | None = None
    owner_id: str | None = None
    stability: StoryStability = "scene"

    @model_validator(mode="after")
    def _has_one_placement(self) -> "AddItemPatch":
        if bool(self.location_id) == bool(self.owner_id):
            raise ValueError("add_item requires exactly one of location_id or owner_id")
        return self


class AddQuestBeatPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["add_quest_beat"]
    id: str = Field(pattern=r"^quest_[a-z0-9_]+$")
    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=240)
    stability: StoryStability = "chapter"


StoryPatch = Annotated[
    AddMemoryPatch
    | AddCluePatch
    | AddLocationPatch
    | AddCharacterPatch
    | AddItemPatch
    | AddQuestBeatPatch,
    Field(discriminator="op"),
]


class StoryWriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=240)
    patches: list[StoryPatch] = Field(default_factory=list, max_length=4)
    new_terms: list[str] = Field(default_factory=list, max_length=4)
    narration_brief: str | None = Field(default=None, max_length=240)
