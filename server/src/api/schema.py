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


class StoryGraphNode(BaseModel):
    id: str
    kind: str
    label: str
    detail: str = ""


class StoryGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str


class StoryGraphResponse(BaseModel):
    nodes: list[StoryGraphNode]
    edges: list[StoryGraphEdge]
    summary: str
