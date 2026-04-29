"""Per-turn world-clock tick.

advance_time is the one place that bumps `state.world_time` and ticks
each character's active buffs. Lifted out of flow/dirty.py because the
function is about turn-boundary semantics (time + buff aging), not
about the dirty-write set.
"""
from datetime import datetime, timedelta

from ..domain.state import GameState
from ..engines.skill import tick_active_buffs
from ..rules import RULES
from .dirty import Dirty


def advance_time(state: GameState, dirty: "Dirty | None" = None) -> None:
    """One turn boundary: bump world_time by RULES.time.turn_min and tick
    every character's active buffs (duration -1, drop on 0)."""
    dt = datetime.fromisoformat(state.world_time)
    dt += timedelta(minutes=RULES.time.turn_min)
    state.world_time = dt.isoformat()

    entity_dirty = dirty.entities if dirty is not None else None
    for character in state.characters.values():
        tick_active_buffs(character, dirty=entity_dirty)
