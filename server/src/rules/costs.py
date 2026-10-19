from __future__ import annotations

from ..onto.atoms import PLAYER, State
from ..onto.change import Work
from ..onto.cond import holds
from .candidates import held_clock

# (risk, result) → (clock increase, weight, apply | choose | None)
TABLE = {
    ("low", "mixed"): (1, None, None),
    ("low", "fail"): (1, "light", "apply"),
    ("normal", "mixed"): (1, "light", "choose"),
    ("normal", "fail"): (1, "heavy", "apply"),
    ("high", "mixed"): (1, "heavy", "choose"),
    ("high", "fail"): (2, "heavy", "apply"),
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


def settle(u, work: Work, result: str, risk: str, roll_u: int, target: str | None,
           visible: tuple[State, frozenset], world_hist: frozenset):
    """The caller applies the returned complication on a fail.

    `visible` is (F, hᵥ) at the start of the step, where chosen costs are evaluated.
    """
    if result not in ("mixed", "fail"):
        return None
    n, weight, mode = TABLE[(risk, result)]
    s = work.state()
    clock = held_clock(u, s)
    if clock is not None:
        work.set_("fill", (clock,), f"+{n}")
    if mode == "apply":
        p = pool(u, weight, target, work.state(), world_hist)
        return p[roll_u % len(p)]
    if mode == "choose":
        p = pool(u, weight, target, *visible)
        start = roll_u % len(p)
        for i in range(min(3, len(p))):
            work.insert(("due", PLAYER, p[(start + i) % len(p)].id))
    return None
