from pydantic import BaseModel

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


class LevelUpRequest(BaseModel):
    stat_up: str
    stat_down: str


class LevelUpResponse(BaseModel):
    game_id: str
    state: dict
    skill_candidates: list[dict] = []  # §2.3 4단계 — LLM 추천 (실패 시 빈 리스트)


class LearnSkillRequest(BaseModel):
    index: int | None = None  # None 또는 범위 밖 = 거부 (다음 레벨업까지 보류)


class LearnSkillResponse(BaseModel):
    game_id: str
    state: dict
    learned_skill_id: str | None = None


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


class UseRequest(BaseModel):
    item_id: str
    target_id: str | None = None


class UseResponse(BaseModel):
    game_id: str
    state: dict
    result: dict
