from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.action import Action
from src.game.runtime.suggestions import GraphSuggestionValue
from src.game.seed.player import PlayerInput


class ChatRequest(BaseModel):
    system: str | None = None
    query: str
    think: bool = True


class ChatResponse(BaseModel):
    think: str | None = None
    answer: str | None = None


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
    suggestions: list[GraphSuggestionValue] = Field(default_factory=list)


class GraphActionResponse(BaseModel):
    game_id: str
    state: dict
    status: str | None = None
    message: str | None = None
    suggestions: list[GraphSuggestionValue] = Field(default_factory=list)


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

    command: Literal["attack", "skill", "defend", "flee"]
    target_id: str | None = None
    think: bool = False


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
