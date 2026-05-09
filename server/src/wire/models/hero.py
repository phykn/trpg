from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    """Wire base — Python fields stay snake_case; JSON output is camelCase
    so the client sees raceJob/expMax/hpMax/mpMax/canLevelUp/reviveCoins.
    serialize_by_alias=True makes plain model_dump() emit camelCase keys
    (no per-call by_alias flag needed)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class StatEntry(_CamelModel):
    """One row of the stats display: localized label + numeric value."""

    label: str
    value: int


class EquipItem(_CamelModel):
    """Equipped item display — name only (qty implicit = 1)."""

    name: str


class Equipment(_CamelModel):
    """Hero/subject equipment slots. Mirrors domain.Equipment field set."""

    weapon: EquipItem | None = None
    armor: EquipItem | None = None
    accessory: EquipItem | None = None


class InventoryItem(_CamelModel):
    """Inventory row: item name + quantity."""

    name: str
    qty: int


class HeroPayload(_CamelModel):
    """Wire shape for the `hero` slot inside the `state` payload."""

    name: str
    alive: bool
    race_job: str
    gender: str
    level: int
    exp: int
    exp_max: int
    can_level_up: bool
    hp: int
    hp_max: int
    mp: int
    mp_max: int
    revive_coins: int
    revive_coins_max: int
    gold: int
    stats: list[StatEntry]
    equipment: Equipment
    inventory: list[InventoryItem]
    status: list[str]
    skills: list[str]
    companions: list[str]
