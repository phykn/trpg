from __future__ import annotations

from dataclasses import dataclass, field

from .atoms import Atom, State

RESULTS = ("success", "mixed", "fail", "none", "blocked")


@dataclass(frozen=True)
class Delta:
    add: frozenset
    remove: frozenset             # add ∩ remove = ∅

    @staticmethod
    def between(before: State, after: State) -> Delta:
        a, b = before.atoms(), after.atoms()
        return Delta(b - a, a - b)

    def to_json(self) -> dict:
        return {"add": sorted(map(list, self.add), key=_key), "remove": sorted(map(list, self.remove), key=_key)}

    @staticmethod
    def from_json(d: dict) -> Delta:
        return Delta(frozenset(tuple(a) for a in d["add"]), frozenset(tuple(a) for a in d["remove"]))


def _key(a) -> tuple:
    return tuple((0, x) if isinstance(x, int) else (1, str(x)) for x in a)


@dataclass(frozen=True)
class Event:
    t: int
    action: str                   # canonical action id (story.md 3.12)
    roll: tuple[int, int, int] | None
    result: str                   # success, mixed, fail, none, blocked
    delta: Delta
    witnesses: tuple[str, ...]    # sorted
    mods: tuple[Atom, ...]        # atoms that adjusted the roll, in rule order

    def to_json(self) -> dict:
        return {"t": self.t, "action": self.action, "roll": list(self.roll) if self.roll else None,
                "result": self.result, "delta": self.delta.to_json(), "witnesses": list(self.witnesses),
                "mods": [list(m) for m in self.mods]}

    @staticmethod
    def from_json(d: dict) -> Event:
        return Event(d["t"], d["action"], tuple(d["roll"]) if d["roll"] else None, d["result"],
                     Delta.from_json(d["delta"]), tuple(d["witnesses"]), tuple(tuple(m) for m in d["mods"]))


@dataclass(frozen=True)
class Pattern:
    pieces: tuple[str, ...]       # schema and leading intent arguments
    judge: tuple[tuple[str, str], ...]
    results: frozenset | None     # None: any result


def split_action(action: str) -> tuple[tuple[str, ...], dict[str, str]]:
    head, *judge = action.split(";")
    return tuple(head.split(":")), dict(j.split("=", 1) for j in judge)


def compile_pattern(prefix: str, result: str | None, results: tuple[str, ...] | None = None) -> Pattern:
    pieces, judge = split_action(prefix)
    rs = frozenset(results) if results else (frozenset((result,)) if result else None)
    return Pattern(pieces, tuple(sorted(judge.items())), rs)


def matches(p: Pattern, action: str, result: str) -> bool:
    pieces, judge = split_action(action)
    if pieces[:len(p.pieces)] != p.pieces:
        return False
    if any(judge.get(k) != v for k, v in p.judge):
        return False
    return p.results is None or result in p.results


def hits(patterns: list[Pattern], action: str, result: str) -> frozenset:
    return frozenset(i for i, p in enumerate(patterns) if matches(p, action, result))


@dataclass
class Log:
    """h, belief order and memory projections are caches, rebuilt on load."""

    events: list[Event] = field(default_factory=list)
    hist: frozenset = frozenset()
    believed: dict[tuple[str, str], int] = field(default_factory=dict)   # (agent, prop) → order
    seen: dict[str, list] = field(default_factory=dict)                 # observer → [Seen]

    def __len__(self) -> int:
        return len(self.events)
