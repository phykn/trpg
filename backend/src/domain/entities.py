from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .memory import Memory
from .types import StatKey, Tier


# --- character building blocks ---------------------------------------------


class Stats(BaseModel):
    STR: int = Field(default=10, ge=0, le=20)
    DEX: int = Field(default=10, ge=0, le=20)
    CON: int = Field(default=10, ge=0, le=20)
    INT: int = Field(default=10, ge=0, le=20)
    WIS: int = Field(default=10, ge=0, le=20)
    CHA: int = Field(default=10, ge=0, le=20)


class Disposition(BaseModel):
    lawful: int = Field(default=50, ge=0, le=100)
    moral: int = Field(default=50, ge=0, le=100)
    aggressive: int = Field(default=50, ge=0, le=100)


class CombatBehavior(BaseModel):
    attack_priority: (
        Literal["nearest", "lowest_hp", "highest_threat", "healer_first", "random"]
        | None
    ) = None
    flee_hp_percent: int | None = Field(default=None, ge=0, le=100)
    nearest_weight: int = 70
    random_weight: int = 30


class DeathSaveState(BaseModel):
    successes: int = 0
    failures: int = 0


class CombatState(BaseModel):
    turn_order: list[str] = []
    current_turn: int = 0
    round: int = 1
    surprise: Literal["player", "enemy"] | None = None
    enemy_ids: list[str] = []
    damage_dealt: dict[str, int] = {}  # actor_id → 누적 데미지 (highest_threat AI 용)


# --- skills / buffs --------------------------------------------------------


class Skill(BaseModel):
    id: str
    name: str
    description: str = ""
    level: int = Field(default=0, ge=0, le=20)
    type: Literal["attack", "heal", "buff", "debuff"]
    target: Literal["self", "single", "area"]
    primary_stat: StatKey
    special_effect: str = ""
    power: int = 0
    mp_cost: int = 0
    range: float = 1.5
    duration: int = 0


class ActiveBuff(BaseModel):
    description: str
    duration: int


# --- equipment / connection ------------------------------------------------


class Equipment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    head: str | None = None
    top: str | None = None
    bottom: str | None = None
    feet: str | None = None
    leftHand: str | None = None
    rightHand: str | None = None
    acc1: str | None = None
    acc2: str | None = None


EQUIPMENT_SLOTS: tuple[str, ...] = tuple(Equipment.model_fields.keys())


class Connection(BaseModel):
    target_id: str
    difficulty: Tier | None = None
    key_item_id: str | None = None
    travel_min: int | None = None


# --- items -----------------------------------------------------------------


class WeaponEffect(BaseModel):
    type: Literal["weapon"]
    weapon_dice: str
    range: float = 1.5
    two_handed: bool = False


class ArmorEffect(BaseModel):
    type: Literal["armor"]
    defense: int


class ConsumableEffect(BaseModel):
    type: Literal["consumable"]
    effect: Literal["heal", "damage", "mp_restore", "buff"]
    amount: int = 0
    description: str | None = None
    duration: int | None = None


ItemEffect = Annotated[
    WeaponEffect | ArmorEffect | ConsumableEffect,
    Field(discriminator="type"),
]


class Item(BaseModel):
    id: str
    name: str
    description: str = ""
    weight: float = 0.0
    price: int = 0
    effects: ItemEffect | None = None
    required: Stats | None = None
    consumable: bool = False
    on_use: str | None = None


# --- race / character ------------------------------------------------------


class Race(BaseModel):
    id: str
    name: str
    description: str
    racial_skills: list[Skill] = []


class Character(BaseModel):
    id: str
    name: str
    description: str = ""
    appearance: str = ""
    is_player: bool = False
    role: str = ""
    race_id: str
    job: str = ""
    level: int = Field(default=0, ge=0, le=20)

    stats: Stats = Stats()

    hp: int = 0
    max_hp: int = 0
    mp: int = 0
    max_mp: int = 0
    alive: bool = True

    location_id: str | None = None
    equipment: Equipment = Equipment()
    inventory_ids: list[str] = []
    gold: int = 0
    xp_pool: int = 0

    disposition: Disposition = Disposition()
    relations: dict[str, int] = {}
    tone_hint: str = ""
    hints: list[str] = []

    racial_skills: list[Skill] = []
    learned_skills: list[Skill] = []

    status: list[str] = []
    active_buffs: list[ActiveBuff] = []

    memories: list[Memory] = []

    combat_behavior: CombatBehavior | None = None
    death_saves: DeathSaveState | None = None
    revive_coins: int = 0
    dominant_hand: Literal["left", "right"] = "right"

    companions: list[str] = []


# --- location --------------------------------------------------------------


class Location(BaseModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = []
    item_ids: list[str] = []
    hidden_items: list[str] = []
    connections: list[Connection] = []
    hidden_connections: list[Connection] = []
    weather: list[str] = []
    sleep_risk: Literal["safe", "risky", "dangerous"] = "safe"
    sleep_encounters: list[str] = []
    difficulty: Tier | None = None


# --- quest / chapter / campaign --------------------------------------------


class QuestTrigger(BaseModel):
    id: str
    name: str
    type: str
    target_id: str


class QuestRewards(BaseModel):
    gold: int = 0
    exp: int = 0
    items: list[str] = []


class Quest(BaseModel):
    id: str
    title: str
    summary: str = ""
    giver_id: str
    difficulty: Tier
    prerequisite_ids: list[str] = []
    triggers: list[QuestTrigger] = []
    conditions: list[str] = []
    fail_triggers: list[QuestTrigger] = []
    rewards: QuestRewards = QuestRewards()
    status: Literal["locked", "active", "completed", "failed"] = "locked"
    required: bool = True

    triggers_met: list[bool] = []
    fail_triggers_met: list[bool] = []


class ChapterProgress(BaseModel):
    done: int = 0
    total: int = 0


class Chapter(BaseModel):
    id: str
    title: str
    summary: str = ""
    quest_ids: list[str] = []
    status: Literal["locked", "active", "completed"] = "locked"
    required: bool = True
    progress: ChapterProgress = ChapterProgress()


class Campaign(BaseModel):
    id: str
    title: str
    summary: str = ""
    chapter_ids: list[str] = []
