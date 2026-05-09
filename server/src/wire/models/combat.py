from typing import Literal

from pydantic import BaseModel

__all__ = ["CombatEndPayload", "CombatStartPayload", "CombatTurnPayload"]


class CombatStartPayload(BaseModel):
    """SSE combat_start event payload — emitted when a fight opens.
    `surprise` flags an ambush direction (player-initiated vs enemy-initiated)
    or None for a clean fight."""

    turn_order: list[str]
    round: int
    surprise: Literal["player", "enemy"] | None = None
    enemy_ids: list[str]


class CombatTurnPayload(BaseModel):
    """SSE combat_turn event payload. Two emit sites share this shape:
    auto-combat per-action turn events (full damage/grade/skill fields) and
    player passive equip/unequip during combat (only actor/action/item_id).
    All non-actor/non-action/non-round fields are optional defaults so both
    sites validate."""

    actor: str
    action: str
    round: int
    grade: str | None = None
    damage: int = 0
    killed: bool = False
    target: str | None = None
    skill_name: str | None = None
    skill_id: str | None = None
    item_id: str | None = None


class CombatEndPayload(BaseModel):
    """SSE combat_end event payload. `outcome` narrows to the 4-literal
    CombatOutcome that auto-combat produces."""

    outcome: Literal["victory", "defeat", "downed", "fled"]
