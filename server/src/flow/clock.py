"""Per-turn buff tick.

tick_turn_buffs walks every character at a turn boundary and decrements
each active buff's remaining duration (drop on 0). Named to avoid colliding
with engines.combat.advance_turn, which rotates initiative and is used in
the same flow modules. Time-of-day lookup lives in domain/clock.py:day_phase
since the game derives its clock from state.turn_count.
"""

from ..domain.state import GameState
from ..engines.skill import tick_active_buffs
from .dirty import Dirty


def tick_turn_buffs(state: GameState, dirty: "Dirty | None" = None) -> None:
    """One turn boundary: tick every character's active buffs (duration -1, drop on 0)."""
    entity_dirty = dirty.entities if dirty is not None else None
    for character in (
        state.characters.values()
    ):  # ssot-allow: attribute-only sweep (buff durations).
        tick_active_buffs(character, dirty=entity_dirty)
