from __future__ import annotations

from dataclasses import dataclass

from .atoms import PLAYER, Atom, State
from .log import Delta, Event, Log, hits


@dataclass(frozen=True)
class Seen:
    t: int
    action: str
    roll: tuple[int, int, int] | None
    result: str
    witnesses: tuple[str, ...]    # W ∩ E_e
    delta: Delta                  # Δ ∩ F-rule_e
    mods: tuple[Atom, ...]        # mods ∩ F-rule_e


@dataclass(frozen=True)
class Obs:
    observer: str
    seen: frozenset
    facts: State                  # F, a sub-state of S
    beliefs: tuple[str, ...]      # B, in reveal order
    memory: tuple[Seen, ...]
    hist: frozenset

    @property
    def here(self) -> str | None:
        return self.facts.where(self.observer)


def hidden(u, x: str, o: str, s: State) -> bool:
    props = u.shows.get(x)
    return bool(props) and not any(s.has("believes", o, p) for p in props)


def seen_by(u, s: State, o: str) -> frozenset:
    here = s.where(o)
    out = {o, *s.held_by(o)}
    if here is not None:
        out.add(here)
        out.update(x for x in s.held_by(here) if not hidden(u, x, o, s))
        out.update(q for (p, q) in s.rows("link") if p == here and not hidden(u, q, o, s))
    return frozenset(out)


def fact_rule(o: str, seen: frozenset, atom: Atom) -> bool:
    """The table in ontology.md 3.2."""
    p = atom[0]
    if p == "at" or p == "link":
        return atom[1] in seen and atom[2] in seen
    if p in ("mark", "fill"):
        return atom[1] in seen
    if p in ("stat", "believes", "due", "spent"):
        return atom[1] == o
    if p in ("regards", "owes"):
        return atom[1] == o or atom[2] == o
    return False


def facts_of(u, s: State, o: str) -> State:
    seen = seen_by(u, s, o)
    return s.filter(lambda a: fact_rule(o, seen, a))


def observe(u, s: State, log: Log, o: str = PLAYER) -> Obs:
    seen = seen_by(u, s, o)
    facts = s.filter(lambda a: fact_rule(o, seen, a))
    order = {p: i for i, p in enumerate(u.props)}
    believed = [p for (g, p) in s.rows("believes") if g == o]
    believed.sort(key=lambda p: (log.believed.get((o, p), -1), order.get(p, 0)))
    return Obs(o, seen, facts, tuple(believed), tuple(log.seen.get(o, ())), log.hist)


def project(u, before: State, after: State, e: Event, o: str) -> Seen:
    seen = seen_by(u, before, o) | seen_by(u, after, o)

    def rule(a):
        return fact_rule(o, seen, a)

    return Seen(e.t, e.action, e.roll, e.result, tuple(w for w in e.witnesses if w in seen),
                Delta(frozenset(filter(rule, e.delta.add)), frozenset(filter(rule, e.delta.remove))),
                tuple(filter(rule, e.mods)))


def witnesses(u, before: State, after: State) -> tuple[str, ...]:
    out = set()
    for s in (before, after):
        here = s.where(PLAYER)
        out.update(x for x in s.held_by(here) if u.kind(x) == "agent")
        out.add(PLAYER)
    return tuple(sorted(out))


def record(u, log: Log, before: State, after: State, e: Event) -> None:
    log.events.append(e)
    log.hist = log.hist | hits(u.patterns, e.action, e.result)
    for a in sorted(e.delta.add, key=str):
        if a[0] == "believes" and (a[1], a[2]) not in log.believed:
            log.believed[(a[1], a[2])] = len(log.believed)
    mine = project(u, before, after, e, PLAYER)
    log.seen.setdefault(PLAYER, []).append(mine)
    rule_seen = seen_by(u, before, PLAYER) | seen_by(u, after, PLAYER)

    def keep(a):
        return fact_rule(PLAYER, rule_seen, a)

    for g in e.witnesses:
        if g == PLAYER:
            continue
        theirs = project(u, before, after, e, g)
        log.seen.setdefault(g, []).append(Seen(
            theirs.t, theirs.action, theirs.roll, theirs.result, theirs.witnesses,
            Delta(frozenset(filter(keep, theirs.delta.add)), frozenset(filter(keep, theirs.delta.remove))),
            tuple(filter(keep, theirs.mods))))
