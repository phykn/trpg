from ..domain.state import GameState
from ..engines.skill import tick_active_buffs
from .dirty import Dirty


def tick_turn_buffs(state: GameState, dirty: "Dirty | None" = None) -> None:
    entity_dirty = dirty.entities if dirty is not None else None
    for character in state.characters.values():  # ssot-allow: attribute-only sweep (buff durations).
        tick_active_buffs(character, dirty=entity_dirty)
