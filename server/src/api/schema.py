from typing import Literal

from pydantic import BaseModel

from ..domain.types import StatKey
from ..persistence.init import PlayerInput


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


class InitResponse(BaseModel):
    game_id: str
    state: dict


class TurnRequest(BaseModel):
    player_input: str
    think: bool = False


class RollRequest(BaseModel):
    think: bool = False


class SkillCandidatePayload(BaseModel):
    """Wire-shape: includes the engine-assigned `id` so the client can echo it on POST /level_up.

    Distinct from the domain SkillCandidate (which has no id — id is assigned by
    `engines/skill.build_skill_from_candidate` after recommendation). The
    /level_up_preview endpoint builds Skill objects, then projects them down to
    this payload shape.
    """
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


class LevelUpPreviewResponse(BaseModel):
    skill_candidates: list[SkillCandidatePayload]
