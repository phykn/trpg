from __future__ import annotations

import random
import re
from pathlib import Path

from ..onto.atoms import APPROACHES, PLAYER
from ..onto.change import Work
from ..onto.cond import atoms_of, holds
from ..onto.log import Log
from ..onto.universe import CreationError, Universe, conforms, initial
from ..onto.view import observe, record
from ..rules.acts import Action, parse
from ..rules.candidates import admits, candidates
from ..rules.recommend import recommend
from ..rules.resolve import Step, event_of, resolve
from ..rules.roll import outcome, preview, roll, rolls
from ..rules.schemas import Ctx
from ..rules.triggers import ENGINE, ended
from .compile import build
from .load import StoryError, read, story_files

MAX_STORY_COMPLICATIONS = 58      # u is 0…59 and the engine adds two per weight (rule.md 3.3)
FUZZ_RUNS, FUZZ_STEPS = 24, 300
CHAPTER_STEPS = 20                # F10's floor: the fewest beat-raising steps a chapter should allow (fun.md 3.3)


class Run:
    """One game in memory: admits, resolve and record, as the service does it (engine.md 7)."""

    def __init__(self, u: Universe, creation: dict, seed: int = 0):
        self.u, self.seed = u, seed
        self.s = initial(u, creation)
        self.log = Log()

    @property
    def obs(self):
        return observe(self.u, self.s, self.log)

    def step(self, a: Action, r: tuple[int, int, int] | None = None) -> Step:
        r = r or roll(self.seed, len(self.log))
        step = resolve(self.u, self.s, self.log.hist, a, r)
        record(self.u, self.log, self.s, step.after, event_of(self.u, self.s, len(self.log), a, step))
        self.s = step.after
        return step


def fail(stage: str, where: str, msg: str):
    raise StoryError(f"{stage} {where}: {msg}")


# V1 here is only the part the universe builder does not do.

def v1(u: Universe) -> None:
    raw = u.raw
    for lid, lat in u.latents.items():
        own = {lid, *lat.brings}
        for where, s in _strings(raw, "", skip={f"latents.{lid}", "witnesses"}):
            if s in own or own & set(re.split(r"[:;=]", s)):
                fail("V1", where, f"{s!r} belongs to latents.{lid} and cannot be used outside it")
        for i, e in enumerate(lat.effects):
            target = e[2][0] if e[0] == "set" else e[1]
            if e[0] not in ("move", "tag", "set") or (e[0] == "set" and e[1] != "regards") or target not in lat.brings:
                fail("V1", f"latents.{lid}.effects[{i}]", "a latent's effects only move, tag or set regards of what it brings")
    for weight in ("light", "heavy"):
        n = sum(c.weight == weight for c in _story_complications(u))
        if n > MAX_STORY_COMPLICATIONS:
            fail("V1", "complications", f"{n} {weight} complications, at most {MAX_STORY_COMPLICATIONS}")


def _strings(v, where, skip):
    if where in skip:
        return
    if isinstance(v, dict):
        for k, x in v.items():
            yield from _strings(x, f"{where}.{k}" if where else str(k), skip)
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from _strings(x, f"{where}[{i}]", skip)
    elif isinstance(v, str):
        yield where, v


def _story_complications(u: Universe):
    for table in (u.places, u.agents, u.obstacles):
        for x in table.values():
            yield from x.complications


def v2(u: Universe) -> None:
    try:
        s0 = initial(u, _creation(u))
    except CreationError as e:
        fail("V2", "witnesses.creation", str(e))
    problems = conforms(u, s0)
    if problems:
        fail("V2", "start", problems[0])
    if u.kind(s0.where(PLAYER)) != "place":
        fail("V2", "player.start", "the player is not in a place")


def _creation(u: Universe, path: dict | None = None) -> dict:
    c = (path or {}).get("creation") or u.witnesses.get("creation")
    if c is None:
        fail("V2", "witnesses.creation", "missing")
    return {"approaches": dict(c.get("approaches") or {}), "traits": list(c.get("traits") or [])}


def v3(u: Universe) -> None:
    s0 = initial(u, _creation(u))
    for t in u.triggers:
        if holds(t.when, s0, frozenset()):
            fail("V3", f"triggers.{t.id}.when", "is true at the start")
    for f in ENGINE:
        work = Work(u, s0)
        if f(Ctx(u, s0, frozenset(), parse("cut:pass"), None, work)):
            fail("V3", "start", f"engine trigger {f.__name__} fires at the start")
    for where, cond, host in _visible_conditions(u):
        for leaf in atoms_of(cond):
            if not _visible_leaf(u, leaf, host):
                fail("V3", where, f"{leaf[0]} {list(leaf[1:3])} is not always visible to the player")
    _blocking(u)
    _avoided(u)


def _visible_conditions(u: Universe):
    for o in u.obstacles.values():
        for sol in o.solutions:
            yield f"obstacles.{o.id}.solutions.{sol.id}.when", sol.when, o.id
    for lid, lat in u.latents.items():
        yield f"latents.{lid}.when", lat.when, None
    for c in _story_complications(u):
        yield f"complications.{c.id}.when", c.when, c.host
    for a in u.agents.values():
        for t in a.topics:
            if t.free_when is not None:
                yield f"characters.{a.id}.topics.{t.id}.free_when", t.free_when, a.id
        for q, c in a.until.items():
            yield f"characters.{a.id}.avoids.{q}.until", c, a.id


def _visible_leaf(u: Universe, leaf, host) -> bool:
    k = leaf[0]
    if k == "did":
        return True
    if k == "at":
        x, y = leaf[1], leaf[2]
        return (x == PLAYER and u.kind(y) == "place") or (y == PLAYER and x in u.things) or x == host
    if k == "believes":
        # a person's mind is read only where the person is: their topics, their complications, their fears
        return leaf[1] in (PLAYER, host)
    if k == "flag":
        return leaf[1] in u.texts
    if k == "mark":
        return leaf[1] in (PLAYER, host)
    if k in ("regards", "owes"):
        return PLAYER in (leaf[1], leaf[2])
    if k == "fill":
        return leaf[1] == host
    return False


def _all_effects(u: Universe):
    for t in u.triggers:
        yield from t.effects
    for c in u.chapters:
        yield from c.crisis
        yield from c.goal_effects
    for o in u.obstacles.values():
        yield from o.arrival
        for _, _, effects in o.choices:
            yield from effects
    for lat in u.latents.values():
        yield from lat.effects
    for a in u.agents.values():
        if a.favor is not None:
            yield from a.favor.effects
    for c in _story_complications(u):
        yield from c.effects


def _blocking(u: Universe) -> None:
    links = [(e[1], e[2]) for e in _all_effects(u) if e[0] == "link"]
    for o in u.obstacles.values():
        for x in o.blocks:
            where = f"obstacles.{o.id}.blocks"
            if u.kind(x) == "place":
                entries = {p.id for p in u.places.values() if x in p.exits} | {p for p, q in links if q == x}
                wrong = sorted(p for p in entries if p != o.at)
                if wrong:
                    fail("V3", where, f"{x} can be entered from {wrong[0]}, where {o.id} is not")
                continue
            start = _start_place(u, x)
            if start is not None and start != o.at:
                fail("V3", where, f"{x} starts at {start}, not with {o.id} at {o.at}")


def _avoided(u: Universe) -> None:
    moved = {(e[1], e[2]) for e in _all_effects(u) if e[0] == "move"}
    for a in u.agents.values():
        for q in a.avoids:
            # a story may bring someone past a fear that ends
            if a.at == q or ((a.id, q) in moved and q not in a.until):
                fail("V3", f"characters.{a.id}.avoids", f"the story puts {a.id} in {q}")


def _start_place(u: Universe, x: str) -> str | None:
    at = (u.things.get(x) or u.agents.get(x) or u.obstacles.get(x)).at
    if at in u.agents:
        at = u.agents[at].at
    return at


def v4(u: Universe) -> None:
    hidden = [x for x, props in u.shows.items() if any(u.props[p].source == "hidden" for p in props)]
    hidden += [b for lat in u.latents.values() for b in lat.brings]
    texts = list(_public(u))
    for x in hidden:
        for term in u.terms(x):
            for owner, where, text in texts:
                if owner != x and term in text:
                    fail("V4", where, f"names the hidden {x} ({term!r})")
    seen: dict[str, str] = {}
    for table in (u.places, u.agents, u.things, u.obstacles):
        for x in table.values():
            if x.id.startswith(("clock.", "deadline.")):
                continue
            for term in (x.name, *x.aliases):
                if term in seen and seen[term] != x.id:
                    fail("V4", f"{x.id}.aliases", f"{term!r} is also a name of {seen[term]}")
                seen[term] = x.id
    # The narrator moves anyone its context names, so a person's knows naming another brings them into the scene.
    for a in u.agents.values():
        for k in a.knows:
            for b in u.agents.values():
                if b.id != a.id and any(term in k for term in (b.name, *b.aliases)):
                    fail("V4", f"characters.{a.id}.knows", f"names {b.id}")
    labels = list(seen) + [sol.label for o in u.obstacles.values() for sol in o.solutions]
    for phrase in u.impossible:
        for text in labels:
            if phrase in text:
                fail("V4", "impossible", f"{phrase!r} is part of {text!r}")


def _public(u: Universe):
    """(owner, where, text) for every public parameter (story.md 2.1)."""
    yield None, "premise", u.premise
    yield None, "style", u.style
    for tid, (name, text) in u.traits.items():
        yield None, f"player.traits.{tid}", f"{name} {text}"
    for p in u.places.values():
        yield p.id, f"places.{p.id}", " ".join((p.name, *p.aliases, *p.senses))
    for a in u.agents.values():
        yield a.id, f"characters.{a.id}", " ".join((a.name, *a.aliases, a.voice, a.desire, a.fear, *a.knows))
        for t in a.topics:
            yield a.id, f"characters.{a.id}.topics.{t.id}.title", t.title
        if a.favor is not None:
            yield a.id, f"characters.{a.id}.favor", f"{a.favor.label} {a.favor.promise}"
    for t in u.things.values():
        yield t.id, f"things.{t.id}", " ".join((t.name, *t.aliases, t.look))
    for o in u.obstacles.values():
        parts = [o.name, *o.aliases, o.look, *(s.label for s in o.solutions), *(c[1] for c in o.choices)]
        parts += [o.default[0]] if o.default else []
        yield (None if o.sub in ("clock", "deadline") else o.id), f"obstacles.{o.id}", " ".join(parts)
    for c in _story_complications(u):
        yield c.host, f"complications.{c.id}.name", c.name
    for lid, lat in u.latents.items():
        yield lid, f"latents.{lid}.name", lat.name
    for cid in u.claims:
        yield None, f"claims.{cid}.text", u.props[cid].text
    for name, texts in u.texts.items():
        for v, text in texts.items():
            yield None, f"flags.{name}.{v}", text
    for c in u.chapters:
        yield None, f"chapters[{c.k}].title", c.title
    for e in u.endings.values():
        yield None, f"endings.{e.id}", f"{e.title} {e.frame}"


def v5(u: Universe) -> None:
    paths = u.witnesses.get("paths") or []
    reached: set[tuple[str, object]] = set()
    for i, p in enumerate(paths):
        where = f"witnesses.paths[{i}]"
        reach = p.get("reach") or {}
        if len(reach) != 1 or next(iter(reach)) not in ("goal", "ending"):
            fail("V5", where, "reach takes one goal or ending")
        (what, target), = reach.items()
        run = Run(u, _creation(u, p))
        steps = _path(paths, i, where)
        for n, st in enumerate(steps):
            aid, dice = _step(st)
            sw = f"{where}.steps[{n}]"
            if ended(run.s):
                fail("V5", sw, "the game has already ended")
            try:
                a = parse(aid)
            except ValueError as e:
                fail("V5", sw, str(e))
            o = run.obs
            if not admits(u, o, a):
                fail("V5", sw, f"{aid} is not a candidate")
            if dice is None and rolls(u, o.facts, o.hist, a):
                fail("V5", sw, f"{aid} rolls; give roll: [d1, d2, u]")
            before = _reached(run.s, what, target)
            run.step(a, dice or NO_ROLL)
            if before:
                fail("V5", sw, f"{what} {target} was reached before the last step")
        if not _reached(run.s, what, target):
            fail("V5", where, f"does not reach {what} {target}")
        reached.add((what, target))
    needed = [("goal", c.k) for c in u.chapters if c.goal is not None]
    needed += [("ending", e.id) for e in u.endings.values() if e.when is not None or e.id == "collapse"]
    for what, target in needed:
        if (what, target) not in reached:
            fail("V5", "witnesses.paths", f"no path reaches {what} {target}")


# The dice of a step that rolls nothing.
NO_ROLL = (1, 1, 0)


def _step(st) -> tuple[str, tuple | None]:
    """A witness step: an action id, or {do, roll} for one that rolls."""
    if not isinstance(st, dict):
        return st, None
    dice = st.get("roll")
    return st.get("do"), tuple(dice) if dice else None


def _path(paths, i, where, depth=0) -> list:
    p = paths[i]
    if not isinstance(p, dict) or not isinstance(p.get("steps"), list):
        fail("V5", where, "a path needs steps")
    after = p.get("after")
    if after is None:
        return list(p["steps"])
    if not isinstance(after, int) or not 0 <= after < len(paths) or depth > len(paths):
        fail("V5", where, f"after: {after!r} is not an earlier path")
    return _path(paths, after, where, depth + 1) + list(p["steps"])


def _reached(s, what, target) -> bool:
    if what == "goal":
        return s.flag(f"fired_goal.{target}") == 1
    return s.flag("ending") == target


def v6(u: Universe, runs: int = FUZZ_RUNS, steps: int = FUZZ_STEPS) -> None:
    for n in range(runs):
        rng = random.Random(n)
        creation = {"approaches": dict(zip(APPROACHES, rng.sample(list(u.approaches), 4), strict=True)),
                    "traits": rng.sample(sorted(u.traits), u.pick)}
        run = Run(u, creation, seed=n)
        for t in range(steps):
            where = f"run {n} step {t}"
            if ended(run.s):
                break
            o = run.obs
            k = candidates(u, o)
            if not k:
                fail("V6", where, "no candidates before an ending")
            buttons = recommend(u, o)
            if buttons and rng.random() < 0.5:
                a = rng.choice(buttons)
            else:
                schema = rng.choice(sorted({x.schema for x in k}))
                a = rng.choice([x for x in k if x.schema == schema])
            r = (rng.randint(1, 6), rng.randint(1, 6), rng.randrange(60))
            pv = preview(u, o, a) if rolls(u, o.facts, o.hist, a) else None
            try:
                step = run.step(a, r)
            except Exception as e:  # noqa: BLE001 - any failure here is a finding
                fail("V6", where, f"{a} raised {type(e).__name__}: {e}")
            problems = conforms(u, run.s)
            if problems:
                fail("V6", where, f"{a} breaks C: {problems[0]}")
            if step.rolled and (pv is None or (pv.risk, pv.mods.atoms()) != (step.risk, step.mods)
                                or step.result != outcome(r, pv.mods, pv.risk)):
                fail("V6", where, f"{a}: the preview differs from the execution")


STAGES = (v1, v2, v3, v4, v5, v6)


def validate(u: Universe) -> None:
    for stage in STAGES:
        stage(u)


def warnings(u: Universe) -> list[str]:
    """What the story allows but plays short; it still loads."""
    out = []
    for k in range(1, len(u.chapters) + 1):
        cap = u.beats * u.boxes(f"deadline.{k}")
        if cap < CHAPTER_STEPS:
            out.append(f"chapter {k}: beats × deadline boxes = {cap}, below the {CHAPTER_STEPS} steps of F10")
    return out


def load(path: Path) -> Universe:
    raw, digest = read(path)
    try:
        u = build(raw, digest)
    except StoryError as e:
        raise StoryError(f"V1 {e}") from None
    validate(u)
    return u


def load_all(root: Path) -> dict[str, Universe]:
    """Every story under root, validated; any failure stops the server (story.md 4)."""
    out: dict[str, Universe] = {}
    for path in story_files(root):
        try:
            u = load(path)
        except StoryError as e:
            raise StoryError(f"{path.parent.name}: {e}") from None
        if u.id in out:
            raise StoryError(f"{path.parent.name}: story id {u.id} is used twice")
        out[u.id] = u
    return out
