from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ..onto.atoms import PLAYER, Atom, State
from ..onto.view import Obs
from .acts import Action
from .candidates import held_clock, rely_atom, talk_rolls
from .costs import TABLE

RISKS = ("low", "normal", "high")
DC = {"low": 7, "normal": 8, "high": 9}   # the total to reach, by risk


def roll(seed: int, t: int) -> tuple[int, int, int]:
    b = hashlib.sha256(f"{seed}:{t}".encode()).digest()

    def n(i):
        return int.from_bytes(b[i:i + 8], "big")

    return n(0) % 6 + 1, n(8) % 6 + 1, n(16) % 60


def risk(u, a: Action) -> str:
    """Reads only U and a, so hidden atoms never change it (rule.md 3.2)."""
    if a.schema == "try":
        x, approach = a.intent
        if x == PLAYER:
            return "low"
        o = u.obstacles.get(x)
        level = RISKS.index(o.risk if o is not None else "normal")
        level += (o is not None and approach in o.clashes) + (a.get("strain") == "forced")
        return RISKS[min(level, 2)]
    if a.schema == "talk":
        return RISKS[1 + (a.get("tone") in ("threaten", "deceive"))]
    if a.schema == "choose":
        return "high"
    return "low"


def approach_of(a: Action) -> str:
    return "charm" if a.schema == "talk" else a.intent[1]


@dataclass(frozen=True)
class Mods:
    stat: Atom                        # ("stat", player, approach, n)
    help: Atom | None                 # the atom rely points at
    hinder: tuple[Atom, ...]          # every hindering atom; together they count once

    @property
    def z(self) -> int:
        return self.stat[3] + (self.help is not None) - bool(self.hinder)

    def atoms(self) -> tuple[Atom, ...]:
        """The event's mods, in rule order: stat, help, hinder."""
        return (self.stat,) + ((self.help,) if self.help else ()) + self.hinder

    def chips(self) -> list[tuple[str, tuple[Atom, ...], int]]:
        """(kind, atoms, value) chips for api.md 3: stat always, help and hinder when present."""
        out = [("stat", (self.stat,), self.stat[3])]
        if self.help:
            out.append(("help", (self.help,), 1))
        if self.hinder:
            out.append(("hinder", self.hinder, -1))
        return out


def modifiers(u, facts: State, a: Action) -> Mods:
    """Reads only the atoms in `facts`: S in R, F in the preview (rule.md 3.2)."""
    approach = approach_of(a)
    stat = ("stat", PLAYER, approach, facts.stat(PLAYER, approach) or 0)
    rely = a.get("rely")
    target = a.intent[0]
    help_ = rely_atom(u, facts, rely, target) if rely else None
    if rely and help_ is None:
        raise ValueError(f"nothing to rely on: {rely}")
    here = facts.where(PLAYER)
    hinder: list[Atom] = []
    for x in dict.fromkeys((target, here, PLAYER)):
        hinder += [("mark", x, "snag", life, i) for i, kind, life in facts.marks(x) if kind == "snag"]
    if a.schema == "talk":
        axis = "fear" if a.get("tone") == "threaten" else "trust"
        n = facts.regards(target, PLAYER, axis)
        if n is not None and n < 0:
            hinder.append(("regards", target, PLAYER, axis, n))
    return Mods(stat, help_, tuple(hinder))


def band(total: int, dc: int) -> str:
    return "success" if total >= dc else "fail"


def outcome(r: tuple[int, int, int], mods: Mods, risk_: str) -> str:
    return band(r[0] + r[1] + mods.z, DC[risk_])


def chance(z: int, dc: int) -> float:
    """P(2d6 + z >= dc)."""
    return sum(d1 + d2 + z >= dc for d1 in range(1, 7) for d2 in range(1, 7)) / 36


@dataclass(frozen=True)
class Preview:
    risk: str
    mods: Mods
    z: int
    dc: int
    stakes: dict                      # what a fail costs: {clock, weight}
    clock: dict | None                # {id, boxes, fill, fail}
    gain: dict


def rolls(u, facts: State, hist: frozenset, a: Action) -> bool:
    """Whether a rolls, judged on what the player sees (engine.md 4.2)."""
    if a.schema == "try":
        return a.intent[0] != PLAYER
    if a.schema == "talk":
        return talk_rolls(u, facts, hist, *a.intent)
    return False


def preview(u, o: Obs, a: Action) -> Preview:
    r = risk(u, a)
    mods = modifiers(u, o.facts, a)
    n, weight = TABLE[r]
    c = held_clock(u, o.facts)
    clock = None
    if c is not None:
        fill, boxes = o.facts.fill(c), u.boxes(c)
        clock = {"id": c, "boxes": boxes, "fill": fill, "fail": min(n, boxes - fill)}
    return Preview(r, mods, mods.z, DC[r], {"clock": n, "weight": weight}, clock, gain(u, o, a))


def gain(u, o: Obs, a: Action) -> dict:
    x = a.intent[0]
    if a.schema == "talk":
        h, topic = a.intent
        if topic == "favor":
            return {"kind": "favor", "effects": u.agents[h].favor.effects}
        if topic == "come":
            return {"kind": "follow"}
        return {"kind": "topic", "topic": topic}
    ob = u.obstacles.get(x)
    if ob is not None:
        fit = int(a.intent[1] in ob.fits)
        left = ob.boxes - (o.facts.fill(x) or 0)
        return {"kind": "fill", "boxes": min(1 + fit, left), "fit": min(fit, max(left - 1, 0))}
    snags = [(i, life) for i, kind, life in o.facts.marks(x) if kind == "snag"]
    return {"kind": "tag", "remove": ("mark", x, "snag", snags[0][1], snags[0][0]) if snags else None}

