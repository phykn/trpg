from .hero import _CamelModel, Equipment, InventoryItem, StatEntry

__all__ = ["SubjectPayload"]


class SubjectPayload(_CamelModel):
    """Wire shape for the `subject` slot inside the `state` payload.
    Field order matches wire/to_front.to_subject's dict insertion order.
    NPC mp/mpMax is intentionally absent — subject panel doesn't expose
    NPC mana to the player."""

    name: str
    alive: bool
    role: str
    race_job: str
    gender: str
    trust: int
    known: list[str]
    level: int
    hp: int
    hp_max: int
    stats: list[StatEntry]
    equipment: Equipment
    inventory: list[InventoryItem]
    skills: list[str]
