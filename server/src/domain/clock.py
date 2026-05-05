"""Turn-count → day-phase derivation.

The game has no minute/hour clock — `state.turn_count` is the sole time variable.
A day cycles through 4 phases × `RULES.time.phase_turns` turns each:
dawn → morning → afternoon → night → (next dawn).
"""

from typing import get_args

from .types import Phase
from ..rules import RULES

_PHASE_ORDER: tuple[Phase, ...] = get_args(Phase)


def day_phase(turn_count: int) -> Phase:
    return _PHASE_ORDER[(turn_count // RULES.time.phase_turns) % len(_PHASE_ORDER)]


def next_dawn_turn(turn_count: int) -> int:
    """Smallest turn count >= `turn_count` whose phase is dawn. Used by sleep
    recovery — resting at the exact dawn boundary should stay on this dawn,
    not jump a full cycle (~24h) to the next one."""
    cycle = RULES.time.phase_turns * len(_PHASE_ORDER)
    return ((turn_count + cycle - 1) // cycle) * cycle
