from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from src.game.domain.memory import LogEntry

__all__ = [
    "DifficultyBadge",
    "EquipSlot",
    "GraphCombatParticipantPayload",
    "GraphCombatPayload",
    "GraphEquipmentPayload",
    "GraphFrontStatePayload",
    "GraphHeartPayload",
    "GraphHeroPayload",
    "GraphInventoryItemPayload",
    "GraphNamedPayload",
    "GraphPendingConfirmationPayload",
    "GraphPendingRollPayload",
    "GraphPlaceLinkPayload",
    "GraphPlacePayload",
    "GraphPlaceTargetPayload",
    "GraphResourcePayload",
    "QuestPayload",
    "QuestRewards",
]


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class DifficultyBadge(_CamelModel):
    label: str
    tone: Literal["neutral", "good", "exp", "accent", "bad"] | None = None


class QuestRewards(_CamelModel):
    gold: int
    exp: int


class QuestPayload(_CamelModel):
    id: str
    title: str
    summary: str
    giver: str
    difficulty: DifficultyBadge
    goals: list[str]
    progress_label: str
    rewards: QuestRewards
    status: Literal["pending", "active", "completed", "failed"]
    actions: list[Literal["accept", "abandon"]]


class GraphResourcePayload(_CamelModel):
    current: int
    maximum: int
    state: str


class GraphNamedPayload(_CamelModel):
    id: str
    name: str


EquipSlot = Literal["weapon", "armor", "accessory"]


class GraphInventoryItemPayload(_CamelModel):
    id: str
    name: str
    qty: int
    can_use: bool
    equip_slots: list[EquipSlot]


class GraphEquipmentPayload(_CamelModel):
    weapon: GraphNamedPayload | None = None
    armor: GraphNamedPayload | None = None
    accessory: GraphNamedPayload | None = None


class GraphHeroPayload(_CamelModel):
    id: str
    name: str
    level: int
    gold: int
    exp: int
    exp_max: int
    can_level_up: bool
    resources: dict[Literal["hp", "mp"], GraphResourcePayload]
    stats: dict[str, int]
    equipment: GraphEquipmentPayload
    inventory: list[GraphInventoryItemPayload]
    status: list[str]
    skills: list[str]


class GraphPlaceLinkPayload(_CamelModel):
    id: str
    name: str
    description: str


class GraphPlaceTargetPayload(_CamelModel):
    id: str
    name: str
    kind: Literal["npc"]
    alive: bool
    level: int
    race_job: str
    gender: str
    role: str
    gold: int
    stats: dict[str, int]
    equipment: GraphEquipmentPayload
    inventory: list[GraphInventoryItemPayload]
    skills: list[str]
    status: list[str]


class GraphPlacePayload(_CamelModel):
    id: str
    name: str
    description: str
    exits: list[GraphPlaceLinkPayload]
    targets: list[GraphPlaceTargetPayload]


class GraphCombatParticipantPayload(_CamelModel):
    id: str
    name: str
    side: Literal["player", "enemy"]
    hp: GraphResourcePayload | None = None
    mp: GraphResourcePayload | None = None


class GraphHeartPayload(_CamelModel):
    current: int
    maximum: int


class GraphCombatPayload(_CamelModel):
    round: int
    outcome: Literal["ongoing", "victory", "defeat", "fled"]
    player_hearts: GraphHeartPayload
    enemy_hearts: GraphHeartPayload
    active_enemy_id: str
    participants: list[GraphCombatParticipantPayload]
    escape_ready: bool = False
    enemy_pressure: int = 0
    last_roll: int | None = None
    last_dc: int | None = None


class GraphPendingConfirmationPayload(_CamelModel):
    id: str
    kind: str
    title: str
    body: str
    confirm_label: str
    cancel_label: str
    target_label: str


class GraphPendingRollPayload(_CamelModel):
    id: str
    kind: str
    title: str
    body: str
    stat: str
    stat_label: str
    required_roll: int


class GraphFrontStatePayload(_CamelModel):
    hero: GraphHeroPayload
    quest: QuestPayload | None
    quest_offers: list[QuestPayload]
    place: GraphPlacePayload | None
    combat: GraphCombatPayload | None
    pending_confirmation: GraphPendingConfirmationPayload | None
    pending_roll: GraphPendingRollPayload | None
    log: list[LogEntry]
