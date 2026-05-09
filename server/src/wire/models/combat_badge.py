from .hero import _CamelModel

__all__ = ["CombatBadgePayload", "CombatEnemy"]


class CombatEnemy(_CamelModel):
    """Single enemy entry in the combat badge. `hp_max` Python field
    serializes to `hpMax` (camelCase) for the client."""

    name: str
    hp: int
    hp_max: int
    alive: bool


class CombatBadgePayload(_CamelModel):
    """Wire shape for the `combat` slot inside the `state` payload —
    surfaced when combat is active. None when no combat or empty turn order
    (gated by wire/to_front.to_combat). `turn_label` is a pre-composed
    Korean string ("내 차례" or "{name} 차례") so the client renders verbatim."""

    round: int
    turn_label: str
    enemies: list[CombatEnemy]
