from __future__ import annotations

from dataclasses import dataclass, field

from .atoms import APPROACHES, AXES, KINDS, PLAYER, State
from .cond import Cond
from .log import Pattern

SHEET = ("beats", "wounds", "growth")

Effect = tuple


@dataclass(frozen=True)
class Prop:
    id: str
    text: str
    about: tuple[str, ...]
    shows: tuple[str, ...]
    against: tuple[str, ...]
    truth: bool
    source: str


@dataclass(frozen=True)
class Complication:
    id: str
    name: str
    weight: str
    when: Cond
    effects: tuple[Effect, ...]
    host: str | None          # the place, character or obstacle it hangs on; None for the engine's


@dataclass(frozen=True)
class Solution:
    id: str
    label: str
    approach: str
    rely: str | None          # kind-prefixed rely value, e.g. "thing:key"
    when: Cond


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    prop: str                 # the proposition its disclosure reveals
    free_when: Cond | None


@dataclass(frozen=True)
class Favor:
    label: str
    effects: tuple[Effect, ...]
    promise: str
    keep: Cond
    breaks: Cond | None


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    aliases: tuple[str, ...]
    senses: tuple[str, ...]
    exits: tuple[str, ...]
    rest: bool
    complications: tuple[Complication, ...]


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    aliases: tuple[str, ...]
    pronoun: str
    voice: str
    desire: str
    fear: str
    persona: str                 # a key of ko.PERSONAS
    at: str | None
    regards: dict
    beliefs: tuple[str, ...]
    wants: tuple[str, ...]
    topics: tuple[Topic, ...]
    favor: Favor | None
    complications: tuple[Complication, ...]
    latent: str | None
    avoids: tuple[str, ...] = ()   # places it will not follow the player into


@dataclass(frozen=True)
class Thing:
    id: str
    name: str
    aliases: tuple[str, ...]
    look: str
    at: str | None
    latent: str | None


@dataclass(frozen=True)
class Obstacle:
    id: str
    sub: str                  # plain, clock, deadline, threat, fork
    name: str
    aliases: tuple[str, ...] = ()
    look: str = ""
    at: str | None = None
    boxes: int = 1
    risk: str = "normal"
    fits: tuple[str, ...] = ()
    clashes: tuple[str, ...] = ()
    blocks: tuple[str, ...] = ()
    solutions: tuple[Solution, ...] = ()
    complications: tuple[Complication, ...] = ()
    arrival: tuple[Effect, ...] = ()
    choices: tuple[tuple[str, str, tuple[Effect, ...]], ...] = ()   # (id, name, effects)
    default: tuple[str, tuple[Effect, ...]] | None = None
    appears_when: Cond | None = None


@dataclass(frozen=True)
class Latent:
    id: str
    name: str
    when: Cond
    brings: tuple[str, ...]
    effects: tuple[Effect, ...]


@dataclass(frozen=True)
class Chapter:
    k: int
    title: str
    aim: str
    goal: Cond | None
    goal_effects: tuple[Effect, ...]
    clock: str
    deadline: str
    crisis: tuple[Effect, ...]


@dataclass(frozen=True)
class Ending:
    id: str
    title: str
    when: Cond | None
    frame: str


@dataclass(frozen=True)
class Trigger:
    id: str
    when: Cond
    effects: tuple[Effect, ...]
    repeat: bool
    kind: str                 # appear, story, goal, ending


@dataclass
class Universe:
    """Never changes during play."""

    id: str
    version: int
    title: str
    premise: str
    style: str
    digest: str
    beats: int
    wound_boxes: int
    impossible: tuple[str, ...]
    start: str
    approaches: tuple[int, ...]
    pick: int
    traits: dict[str, tuple[str, str]]
    places: dict[str, Place] = field(default_factory=dict)
    agents: dict[str, Agent] = field(default_factory=dict)
    things: dict[str, Thing] = field(default_factory=dict)
    obstacles: dict[str, Obstacle] = field(default_factory=dict)
    props: dict[str, Prop] = field(default_factory=dict)
    claims: dict[str, str] = field(default_factory=dict)        # claim id → the belief it is against
    latents: dict[str, Latent] = field(default_factory=dict)
    chapters: list[Chapter] = field(default_factory=list)
    endings: dict[str, Ending] = field(default_factory=dict)
    triggers: list[Trigger] = field(default_factory=list)
    patterns: list[Pattern] = field(default_factory=list)
    flags: dict[str, tuple] = field(default_factory=dict)
    engine_complications: dict[str, Complication] = field(default_factory=dict)
    shows: dict[str, tuple[str, ...]] = field(default_factory=dict)   # entity → props that show it
    favor_patterns: dict[str, int] = field(default_factory=dict)       # agent → pattern index
    witnesses: dict | None = None
    raw: dict | None = None

    def kind(self, x: str) -> str | None:
        if x == PLAYER or x in self.agents:
            return "agent"
        if x in self.places:
            return "place"
        if x in self.things:
            return "thing"
        if x in self.obstacles:
            return "obstacle"
        if x in self.props:
            return "prop"
        return None

    def name(self, x: str) -> str:
        for table in (self.places, self.agents, self.things, self.obstacles):
            if x in table:
                return table[x].name
        return x

    def aliases(self, x: str) -> tuple[str, ...]:
        for table in (self.places, self.agents, self.things, self.obstacles):
            if x in table:
                return getattr(table[x], "aliases", ())
        return ()

    def rank(self, x: str) -> int:
        """Story declaration order; ties every output order to the story (ontology.md 4)."""
        r = self.__dict__.get("_rank")
        if r is None:
            ids = [PLAYER, *self.places, *self.agents, *self.things, *self.obstacles, *self.props,
                   *self.engine_complications]
            for table in (self.places, self.agents, self.obstacles):
                ids += [c.id for x in table.values() for c in x.complications]
            r = self.__dict__["_rank"] = {i: n for n, i in enumerate(dict.fromkeys(ids))}
        return r.get(x, len(r))

    def boxes(self, o: str) -> int:
        return self.obstacles[o].boxes

    def chapter_of(self, k: int) -> Chapter:
        return self.chapters[k - 1]

    def limit(self, pred: str, key) -> tuple[int, int] | tuple | None:
        if pred == "regards":
            return (-3, 3)
        if pred == "fill":
            return (0, self.boxes(key[0]))
        if pred == "stat":
            s = key[1]
            if s in APPROACHES:
                return (0, 3)
            if s == "beats":
                return (0, self.beats)
            if s == "wounds":
                return (0, self.wound_boxes)
            if s == "growth":
                return (0, 10 ** 6)
            return (1, 1)
        if pred == "flag":
            return self.flags.get(key[0])
        return None


class CreationError(ValueError):
    """A creation the story does not allow."""


def check_creation(u: Universe, creation: dict) -> None:
    ap = creation.get("approaches") or {}
    values = list(ap.values())
    if (sorted(ap) != sorted(APPROACHES) or any(type(v) is not int or not 0 <= v <= max(u.approaches) for v in values)
            or sum(values) != sum(u.approaches)):
        raise CreationError("creation: approaches must spend the story's total, each at most its highest value")
    traits = creation.get("traits") or []
    if len(traits) != u.pick or len(set(traits)) != len(traits) or any(t not in u.traits for t in traits):
        raise CreationError(f"creation: pick {u.pick} distinct traits from the story")


def initial(u: Universe, creation: dict) -> State:
    check_creation(u, creation)
    atoms: list = [("at", PLAYER, u.start)]
    for a in u.agents.values():
        if a.at:
            atoms.append(("at", a.id, a.at))
        atoms += [("believes", a.id, b) for b in a.beliefs]
        atoms += [("regards", a.id, PLAYER, ax, a.regards.get(ax, 0)) for ax in AXES]
    for t in u.things.values():
        if t.at:
            atoms.append(("at", t.id, t.at))
    for p in u.places.values():
        atoms += [("link", p.id, q) for q in p.exits]
    for o in u.obstacles.values():
        atoms.append(("fill", o.id, 0))
        if o.at:
            atoms.append(("at", o.id, o.at))
    atoms += [("at", "clock.1", PLAYER), ("at", "deadline.1", PLAYER)]
    for ap, v in creation["approaches"].items():
        atoms.append(("stat", PLAYER, ap, v))
    atoms += [("stat", PLAYER, t, 1) for t in creation["traits"]]
    atoms += [("stat", PLAYER, s, 0) for s in SHEET]
    atoms.append(("flag", "chapter", 1))
    for name, vals in u.flags.items():
        if name not in ("chapter", "ending") and not name.startswith("fired_"):
            atoms.append(("flag", name, vals[0]))
    return State.of(atoms)


def conforms(u: Universe, s: State) -> list[str]:
    problems = []
    try:
        State.of(s.atoms())
    except ValueError as e:
        problems.append(str(e))
    for pred, index in (("regards", s.regards_), ("fill", {(o,): n for o, n in s.fill_.items()}),
                        ("stat", s.stat_), ("flag", {(f,): v for f, v in s.flag_.items()})):
        for key, v in index.items():
            lim = u.limit(pred, key)
            if lim is None:
                problems.append(f"{pred} {key} has no range")
            elif pred == "flag":
                if v not in lim:
                    problems.append(f"flag {key[0]}={v!r} is not declared")
            elif not lim[0] <= v <= lim[1]:
                problems.append(f"{pred} {key}={v} is out of range")
    for (x, i), (k, life) in s.mark_.items():
        if i not in (1, 2, 3) or k not in KINDS or life not in ("scene", "chapter", "scar"):
            problems.append(f"bad mark on {x}")
    for h, g in s.rows("follows"):
        if s.where(h) != s.where(g):
            problems.append(f"{h} follows {g} from another place")
    return problems
