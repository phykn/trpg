from typing import Literal

from pydantic import BaseModel

from src.game.domain.action import Action
from src.game.domain.types import GraphStatKey, StatKey
from src.game.flow.init import PlayerInput


class QuestAction(BaseModel):
    kind: Literal["accept", "abandon"]
    quest_id: str


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


class TurnRequest(BaseModel):
    player_input: str
    think: bool = False
    quest_action: QuestAction | None = None


class GraphTurnRequest(BaseModel):
    action: Action


class GraphInputRequest(BaseModel):
    player_input: str
    think: bool = False


class RollRequest(BaseModel):
    think: bool = False


class ConfirmRequest(BaseModel):
    confirmation_id: str
    decision: Literal["confirm", "cancel"]
    think: bool = False


class SkillCandidatePayload(BaseModel):
    """Wire shape: adds the engine-assigned id missing from the domain SkillCandidate."""

    id: str
    name: str
    description: str
    type: Literal["attack", "heal", "buff", "debuff"]
    target: Literal["self", "single", "area"]
    primary_stat: StatKey
    special_effect: str


class LevelUpRequest(BaseModel):
    stat_up: StatKey
    skill_id: str | None = None
    think: bool = False


class GraphLevelUpRequest(BaseModel):
    stat_up: GraphStatKey
    skill_id: str | None = None
    think: bool = False


class LevelUpPreviewResponse(BaseModel):
    skill_candidates: list[SkillCandidatePayload]
