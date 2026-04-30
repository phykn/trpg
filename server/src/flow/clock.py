"""Per-turn buff tick.

advance_turn ticks each character's active buffs at a turn boundary
(duration -1, drop on 0). Lifted out of flow/dirty.py because it's about
turn-boundary semantics, not the dirty-write set. The world clock used
to live here too, but the game now derives its time from `state.turn_count`
(see `domain/clock.py` for `day_phase`), so this hook only handles buffs.
"""
from ..domain.state import GameState
from ..engines.skill import tick_active_buffs
from .dirty import Dirty


def advance_turn(state: GameState, dirty: "Dirty | None" = None) -> None:
    """One turn boundary: tick every character's active buffs (duration -1, drop on 0)."""
    entity_dirty = dirty.entities if dirty is not None else None
    for character in state.characters.values():
        tick_active_buffs(character, dirty=entity_dirty)
