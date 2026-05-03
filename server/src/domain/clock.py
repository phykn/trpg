"""Turn-count → day-phase derivation.

The game has no minute/hour clock — `state.turn_count` is the sole time variable.
A day cycles through 4 phases × `RULES.time.phase_turns` turns each:
새벽 → 오전 → 오후 → 밤 → (next 새벽).
"""

from ..rules import RULES

PHASES: tuple[str, str, str, str] = ("새벽", "오전", "오후", "밤")


def day_phase(turn_count: int) -> str:
    return PHASES[(turn_count // RULES.time.phase_turns) % len(PHASES)]


def next_dawn_turn(turn_count: int) -> int:
    """Smallest turn count >= `turn_count` whose phase is 새벽. Used by sleep
    recovery — resting at the exact dawn boundary should stay on this dawn,
    not jump a full cycle (~24h) to the next one."""
    cycle = RULES.time.phase_turns * len(PHASES)
    return ((turn_count + cycle - 1) // cycle) * cycle
