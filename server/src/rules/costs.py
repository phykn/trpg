from __future__ import annotations

from ..onto.atoms import PLAYER, State
from ..onto.change import Work
from ..onto.cond import holds
from .candidates import held_clock

# risk → (clock increase, complication weight) on a fail; a success costs nothing
TABLE = {
    "low": (1, None),
    "normal": (1, "light"),
    "high": (2, "heavy"),
}


def pool(u, weight: str, target: str | None, facts: State, hist: frozenset) -> list:
    here = facts.where(PLAYER)
    story = list(u.places[here].complications) if here in u.places else []
    for h, ag in u.agents.items():
        if facts.where(h) == here:
            story += ag.complications
    if target in u.obstacles:
        story += u.obstacles[target].complications
    out = [c for c in u.engine_complications.values() if c.weight == weight]
    return out + [c for c in story if c.weight == weight and holds(c.when, facts, hist)]


def settle(u, work: Work, result: str, risk: str, roll_u: int, target: str | None, world_hist: frozenset):
    """The caller applies the returned complication."""
    if result != "fail":
        return None
    n, weight = TABLE[risk]
    clock = held_clock(u, work.state())
    if clock is not None:
        work.set_("fill", (clock,), f"+{n}")
    if weight is None:
        return None
    p = pool(u, weight, target, work.state(), world_hist)
    return p[roll_u % len(p)]
