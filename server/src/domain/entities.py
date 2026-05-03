from collections.abc import Iterator
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .memory import Memory
from .types import StatKey, Tier


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


class SkillCandidate(BaseModel):
    """LLM-produced learn-candidate. Numeric fields filled later by `engines/skill.build_skill_from_candidate`."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=20)
    description: str = Field(min_length=1, max_length=120)
    type: Literal["attack", "heal", "buff", "debuff"]
    target: Literal["self", "single", "area"]
    primary_stat: StatKey
    special_effect: str = Field(min_length=1, max_length=120)


class Equipment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    weapon: str | None = None
    armor: str | None = None
    accessory: str | None = None

    def equipped_items(self) -> Iterator[tuple[str, str]]:
        """Iterate (slot, item_id) for filled slots only."""
        for slot in EQUIPMENT_SLOTS:
            item_id = getattr(self, slot)
            if item_id:
                yield slot, item_id


EQUIPMENT_SLOTS: tuple[str, ...] = tuple(Equipment.model_fields.keys())


class Connection(BaseModel):
    target_id: str
    difficulty: Tier | None = None
    key_item_id: str | None = None


class WeaponEffect(BaseModel):
    type: Literal["weapon"]
    weapon_dice: str
    range: float = 1.5


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


EquipSlot = Literal["weapon", "armor", "accessory"]


def allowed_slots(item: Item) -> tuple[EquipSlot, ...]:
    """Slots this item can occupy. ArmorEffect items take both armor and accessory; engine sums defense across both."""
    eff = item.effects
    if isinstance(eff, WeaponEffect):
        return ("weapon",)
    if isinstance(eff, ArmorEffect):
        return ("armor", "accessory")
    if isinstance(eff, ConsumableEffect):
        return ()
    return ("accessory",)


def item_kind(
    item: Item,
) -> Literal["weapon", "armor", "consumable", "trigger", "misc"]:
    """Judge prompt / semantics classification. Co-located with `allowed_slots` since both key off `Item.effects`."""
    eff = item.effects
    if isinstance(eff, ConsumableEffect):
        return "consumable"
    if isinstance(eff, WeaponEffect):
        return "weapon"
    if isinstance(eff, ArmorEffect):
        return "armor"
    if item.on_use:
        return "trigger"
    return "misc"


class Race(BaseModel):
    id: str
    name: str
    description: str
    playable: bool = True
    racial_skill_ids: list[str] = []


class Character(BaseModel):
    id: str
    name: str
    description: str = ""
    appearance: str = ""
    is_player: bool = False
    role: str = ""
    race_id: str
    job: str = ""
    gender: Literal["male", "female", "none"] = "none"
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
    xp_reward: int = 0

    disposition: Disposition = Disposition()
    relations: dict[str, int] = {}
    tone_hint: str = ""
    hints: list[str] = []

    racial_skill_ids: list[str] = []
    learned_skill_ids: list[str] = []
    visited_location_ids: set[str] = Field(default_factory=set)

    status: list[str] = []
    active_buffs: list[ActiveBuff] = []

    memories: list[Memory] = []

    combat_behavior: CombatBehavior | None = None
    death_saves: DeathSaveState | None = None
    revive_coins: int = 0

    companions: list[str] = []

    @property
    def known_skill_ids(self) -> tuple[str, ...]:
        return (*self.racial_skill_ids, *self.learned_skill_ids)


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
    prerequisite_ids: list[str] = []
    status: Literal["locked", "active", "completed"] = "locked"
    required: bool = True
    progress: ChapterProgress = ChapterProgress()


class Campaign(BaseModel):
    id: str
    title: str
    summary: str = ""
    chapter_ids: list[str] = []
