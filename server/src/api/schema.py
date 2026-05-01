from pydantic import BaseModel

from ..persistence.init import PlayerInput


# --- debug ----------------------------------------------------------------


class ChatRequest(BaseModel):
    system: str | None = None
    query: str
    think: bool = True


class ChatResponse(BaseModel):
    think: str | None = None
    answer: str | None = None


# --- profiles -------------------------------------------------------------


class RaceCard(BaseModel):
    id: str
    name: str
    description: str = ""


class ProfileCard(BaseModel):
    id: str
    name: str
    description: str = ""
    races: list[RaceCard] = []


# --- session (init / turn) ------------------------------------------------


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
