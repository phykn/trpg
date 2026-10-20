from __future__ import annotations

from dataclasses import dataclass

from ..onto.atoms import PLAYER, Atom, State
from ..onto.change import Work
from ..onto.cond import holds
from ..onto.log import Delta, Event, hits
from ..onto.view import witnesses
from .acts import Action, format
from .schemas import Ctx, delta0
from .triggers import scan


@dataclass(frozen=True)
class Step:
    delta: Delta
    mods: tuple[Atom, ...]
    rolled: bool
    result: str                      # success, mixed, fail, none, blocked
    risk: str
    after: State
    roll: tuple[int, int, int] | None
    names: tuple[tuple[str, int, str | None], ...]   # tags placed this step: (x, slot, default name)


def resolve(u, s: State, h: frozenset, a: Action, r: tuple[int, int, int] | None) -> Step:
    ctx = Ctx(u, s, h, a, r, Work(u, s))
    start_true = [holds(t.when, s, h) for t in u.triggers]
    delta0(ctx)
    ctx.hstar = h | hits(u.patterns, format(a), ctx.result)
    if not (a.schema == "try" and a.intent[0] == PLAYER):
        scan(ctx, start_true)
    after = ctx.work.state()
    return Step(Delta.between(s, after), ctx.mods.atoms() if ctx.mods else (), ctx.rolled, ctx.result,
                ctx.risk, after, r if ctx.rolled else None, tuple(ctx.work.names))


def event_of(u, s: State, t: int, a: Action, step: Step) -> Event:
    return Event(t, format(a), step.roll, step.result, step.delta, witnesses(u, s, step.after), step.mods)
