from typing import Literal

from pydantic import BaseModel

from src.game.domain.action import Action
from src.game.domain.types import GraphStatKey
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


class GraphActionResponse(BaseModel):
    game_id: str
    state: dict
    status: str | None = None
    message: str | None = None


class GraphTurnRequest(BaseModel):
    action: Action
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
    stat_up: GraphStatKey
    skill_id: str | None = None
