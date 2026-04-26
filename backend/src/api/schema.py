from pydantic import BaseModel

from ..state.init import PlayerInput


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


class LevelUpRequest(BaseModel):
    stat_up: str
    stat_down: str


class LevelUpResponse(BaseModel):
    game_id: str
    state: dict


class EquipRequest(BaseModel):
    item_id: str
    slot: str


class UnequipRequest(BaseModel):
    slot: str


class TradeRequest(BaseModel):
    npc_id: str
    item_id: str


class InventoryResponse(BaseModel):
    game_id: str
    state: dict
    price: int | None = None  # buy/sell 시 적용 가격


class CastRequest(BaseModel):
    skill_id: str
    targets: list[str] = []


class CastResponse(BaseModel):
    game_id: str
    state: dict
    result: dict
