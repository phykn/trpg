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


# --- growth (level-up / learn-skill) --------------------------------------


class LevelUpRequest(BaseModel):
    stat_up: str
    stat_down: str


class LevelUpResponse(BaseModel):
    game_id: str
    state: dict
    skill_candidates: list[dict] = []  # §2.3 step 4 — LLM recommendations (empty list on failure)


class LearnSkillRequest(BaseModel):
    index: int | None = None  # None or out-of-range = decline (defer to next level-up)


class LearnSkillResponse(BaseModel):
    game_id: str
    state: dict
    learned_skill_id: str | None = None


# --- inventory (equip / unequip / trade / cast / use) ---------------------


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
    price: int | None = None  # price applied at buy/sell time


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
