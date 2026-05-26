from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.game.domain.action import Action
from src.game.domain.graph import Graph
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_debt import StoryDebtReport
from src.game.domain.story_patch import StoryWriteResponse
from src.game.domain.story_patch_ledger import StoryPatchLedgerEntry
from src.game.runtime.narration.suggestions import GraphSuggestion
from src.game.seed.player import PlayerInput


class RaceCard(BaseModel):
    id: str
    name: str
    description: str = ""


class ProfileCard(BaseModel):
    id: str
    name: str
    description: str = ""
    races: list[RaceCard] = []


class InitRequest(BaseModel):
    profile: str
    player: PlayerInput
    locale: Literal["ko", "en"] = "ko"


class InitResponse(BaseModel):
    game_id: str
    state: dict
    suggestions: list[GraphSuggestion] = Field(default_factory=list)


class GraphActionResponse(BaseModel):
    game_id: str
    state: dict
    status: str | None = None
    outcome: Literal["success", "failure", "neutral"] = "neutral"
    message: str | None = None
    suggestions: list[GraphSuggestion] = Field(default_factory=list)


class StoryPatchEntriesResponse(BaseModel):
    game_id: str
    entries: list[StoryPatchLedgerEntry]


class StoryDebtResponse(BaseModel):
    game_id: str
    debt: StoryDebtReport


class StoryGraphResponse(BaseModel):
    game_id: str
    graph: Graph


class StoryContractResponse(BaseModel):
    game_id: str
    contract: StoryContract


class StoryContractPreviewRequest(BaseModel):
    contract: dict[str, Any]


class StoryContractPreviewResponse(BaseModel):
    game_id: str
    ok: bool
    reasons: list[str] = Field(default_factory=list)
    contract: StoryContract | None = None


class StoryRollbackResponse(BaseModel):
    game_id: str
    entry: StoryPatchLedgerEntry


class StoryPatchPreviewRequest(BaseModel):
    proposal: StoryWriteResponse


class StoryPatchPreviewResponse(BaseModel):
    game_id: str
    ok: bool
    reasons: list[str] = Field(default_factory=list)
    changed_node_ids: list[str] = Field(default_factory=list)
    changed_edge_ids: list[str] = Field(default_factory=list)


class StoryPromptReplayRequest(BaseModel):
    player_input: str
    action: Action


class StoryPromptReplayResponse(BaseModel):
    game_id: str
    agent: Literal["story_write"] = "story_write"
    intent: dict[str, Any]
    system_prompt: str
    user_payload: dict[str, Any]


class GraphLevelUpChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    description: str = ""
    growth: dict[str, Any]


class GraphLevelUpChoicesResponse(BaseModel):
    choices: list[GraphLevelUpChoice]


class GraphTurnRequest(BaseModel):
    action: Action
    think: bool = False


class GraphCombatCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Literal[
        "attack",
        "defend",
        "flee",
        "talk",
    ]
    target: str | None = None
    support_id: str | None = None
    support_kind: Literal["skill"] | None = None
    think: bool = False

    @model_validator(mode="after")
    def _support_pair(self) -> "GraphCombatCommandRequest":
        if (self.support_id is None) != (self.support_kind is None):
            raise ValueError("support_id and support_kind must be provided together")
        return self


class GraphInputRequest(BaseModel):
    player_input: str
    think: bool = False


class ConfirmRequest(BaseModel):
    confirmation_id: str
    decision: Literal["confirm", "cancel"]
    think: bool = False


class GraphRollRequest(BaseModel):
    roll_id: str


class GraphLevelUpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    growth: dict[str, Any]
    think: bool = False
