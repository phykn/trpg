from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .story_patch import StoryWriteIntentKind


StoryPatchLedgerStatus = Literal["accepted", "rejected", "skipped", "rolled_back"]


class StoryPatchLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn: int = Field(ge=0)
    status: StoryPatchLedgerStatus
    intent_kind: StoryWriteIntentKind
    reason: str = Field(min_length=1, max_length=240)
    patches: list[dict[str, Any]] = Field(default_factory=list)
    rejected_reasons: list[str] = Field(default_factory=list)
    changed_node_ids: list[str] = Field(default_factory=list)
    changed_edge_ids: list[str] = Field(default_factory=list)
