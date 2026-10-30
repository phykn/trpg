from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from ..onto.atoms import APPROACHES, PLAYER, State
from ..onto.cond import holds
from ..onto.view import Obs
from .acts import JUDGE, NEUTRAL, STRAINS, TONES, Action, make

ACTIVE = ("threat", "fork", "deadline")


def blockers(u, facts: State, x: str) -> list[str]:
    return [o.id for o in u.obstacles.values()
            if x in o.blocks and facts.where(o.id) is not None and (facts.fill(o.id) or 0) < o.boxes]


def held_clock(u, facts: State) -> str | None:
    for o in u.obstacles.values():
        if o.sub == "clock" and facts.where(o.id) == PLAYER:
            return o.id
    return None


def active_threats(u, facts: State) -> list[str]:
    return [o.id for o in u.obstacles.values() if o.sub in ACTIVE and facts.where(o.id) == PLAYER]


def traits_of(u, facts: State) -> list[str]:
    return [t for t in u.traits if facts.stat(PLAYER, t) == 1]


def reach(u, facts: State, target: str) -> list[str]:
    """Whose tags count in a roll (rule.md 2, 3.2). What the player carries goes along: an edge won by readying the
    oil could only help a roll on the oil itself (qa_test/runs/play-5-explorer 34, 38, 40)."""
    return list(dict.fromkeys((target, facts.where(PLAYER), PLAYER,
                               *(t for t in u.things if facts.where(t) == PLAYER))))


# What the player has is spent until the chapter changes once leaned on; people are not, and a tag is removed instead
# (rule.md 2).
SPENDS = ("trait:", "thing:", "prop:")
# Who stands with the player raises the odds; anything spent lowers a fail's cost instead (rule.md 3.2, 3.3).
FREE = ("bond:", "with:")


def rely_atom(u, facts: State, rely: str, target: str):
    kind, _, rest = rely.partition(":")
    if kind == "tag":
        x, _, slot = rest.rpartition(":")
        if x not in reach(u, facts, target) or slot not in ("1", "2", "3"):
            return None
        mark = facts.mark_.get((x, int(slot)))
        return ("mark", x, "edge", mark[1], int(slot)) if mark and mark[0] == "edge" else None
    if kind == "trait":
        ok = facts.stat(PLAYER, rest) == 1 and rest in u.traits and not facts.has("spent", PLAYER, rest)
        return ("stat", PLAYER, rest, 1) if ok else None
    if kind in ("thing", "prop") and facts.has("spent", PLAYER, rest):
        return None
    if kind == "thing":
        return ("at", rest, PLAYER) if rest in u.things and facts.where(rest) == PLAYER else None
    if kind == "prop":
        return ("believes", PLAYER, rest) if facts.has("believes", PLAYER, rest) else None
    if kind == "bond":
        return ("regards", rest, PLAYER, "trust", 3) if rest in u.agents and facts.regards(rest, PLAYER, "trust") == 3 else None
    if kind == "with":
        return ("follows", rest, PLAYER) if rest != target and facts.has("follows", rest, PLAYER) else None
    return None


def rely_values(u, facts: State, target: str) -> list[str]:
    out = []
    for x in reach(u, facts, target):
        out += [f"tag:{x}:{i}" for i, kind, _ in facts.marks(x) if kind == "edge"]
    out += [f"trait:{t}" for t in traits_of(u, facts) if not facts.has("spent", PLAYER, t)]
    out += [f"thing:{t}" for t in u.things if facts.where(t) == PLAYER and not facts.has("spent", PLAYER, t)]
    out += [f"prop:{p}" for p in u.props if facts.has("believes", PLAYER, p) and not facts.has("spent", PLAYER, p)]
    out += [f"bond:{h}" for h in u.agents if facts.regards(h, PLAYER, "trust") == 3]
    out += [f"with:{h}" for h in u.agents if h != target and facts.has("follows", h, PLAYER)]
    return out


def avoided(u, facts: State, hist: frozenset, h: str) -> tuple[str, ...]:
    """The places h will not go into now: an avoids whose until holds has ended (story.md)."""
    a = u.agents[h]
    return tuple(q for q in a.avoids if q not in a.until or not holds(a.until[q], facts, hist))


def topic_of(u, h: str, topic: str):
    for t in u.agents[h].topics:
        if t.id == topic:
            return t
    return None


def talk_rolls(u, facts: State, hist: frozenset, h: str, topic: str) -> bool:
    """rule.md 5.1 step 2, judged on the facts given (F, or F rebuilt from S inside R)."""
    if topic in ("chat", "stay"):
        return False
    if topic == "favor":
        return not facts.has("owes", h, PLAYER, "kindness")
    if topic == "come":
        return (facts.regards(h, PLAYER, "trust") or 0) < 1
    t = topic_of(u, h, topic)
    if facts.has("believes", PLAYER, t.prop):
        return False
    return not (t.free_when is not None and holds(t.free_when, facts, hist))


def favor_open(u, facts: State, hist: frozenset, h: str) -> bool:
    ag = u.agents[h]
    return (ag.favor is not None and u.favor_patterns[h] not in hist
            and not any(g == PLAYER and k == h for g, k, _ in facts.rows("owes")))


@dataclass(frozen=True)
class Slot:
    """One intent with the judgment values allowed for it (neutral first)."""
    schema: str
    intent: tuple[str, ...]
    judge: tuple[tuple[str, tuple], ...] = ()

    def values(self, key: str) -> tuple:
        return dict(self.judge).get(key, (NEUTRAL[key],))


def space(u, o: Obs) -> list[Slot]:
    f, hist = o.facts, o.hist
    here = f.where(PLAYER)
    seen = sorted(o.seen, key=u.rank)
    tries = [Slot("try", (PLAYER, ap)) for ap in APPROACHES]

    def open_(x):
        return not blockers(u, f, x)

    out: list[Slot] = []
    out += [Slot("go", (q,)) for q in seen
            if u.kind(q) == "place" and q != here and f.has("link", here, q) and open_(q)]
    out += [Slot("look", (x,)) for x in seen if x != PLAYER]
    out += [Slot("take", (x,)) for x in seen if x in u.things and f.where(x) == here and open_(x)]
    held = [x for x in seen if x in u.things and f.where(x) == PLAYER]
    people = [h for h in seen if h in u.agents and f.where(h) == here and open_(h)]
    out += [Slot("give", (x, h)) for x in held for h in people]
    out += [Slot("show", (x, h)) for x in held for h in people]
    claims = (None, *u.claims)
    for h in people:
        topics = [t.id for t in u.agents[h].topics]
        topics += ["favor"] if favor_open(u, f, hist, h) else []
        topics += ["stay"] if f.has("follows", h, PLAYER) else ["come"]
        for topic in topics + ["chat"]:
            judge = [("tone", TONES), ("claim", claims)]
            if talk_rolls(u, f, hist, h, topic):
                judge.append(("rely", (None, *rely_values(u, f, h))))
            out.append(Slot("talk", (h, topic), tuple(judge)))
    out += tries
    for x in seen:
        if x == PLAYER or not open_(x):
            continue
        ob = u.obstacles.get(x)
        if ob is not None:
            if ob.sub != "plain" or (f.fill(x) or 0) >= ob.boxes:
                continue
        elif len(f.marks(x)) >= 3 and not any(kind == "snag" for _, kind, _ in f.marks(x)):
            continue
        judge = (("strain", STRAINS), ("rely", (None, *rely_values(u, f, x))))
        out += [Slot("try", (x, ap), judge) for ap in APPROACHES]
    out += [Slot("declare", (lid,)) for lid, lv in u.latents.items()
            if not f.has("believes", PLAYER, lid) and holds(lv.when, f, hist)]
    out.append(Slot("cut", ("pass",)))
    if here in u.places and u.places[here].rest:
        out.append(Slot("cut", ("rest",)))
    for g in active_threats(u, f):
        if u.obstacles[g].sub == "fork":
            out += [Slot("choose", (g, c)) for c, _, _ in u.obstacles[g].choices]
    if (f.stat(PLAYER, "growth") or 0) >= 1:
        out += [Slot("grow", (ap,)) for ap in APPROACHES if (f.stat(PLAYER, ap) or 0) < 3]
        mine = traits_of(u, f)
        out += [Slot("grow", ("trait", t, n)) for t in mine for n in u.traits if n not in mine]
        out += [Slot("grow", ("wound", str(i))) for i, _, life in f.marks(PLAYER) if life == "wound"]
    return out


def admits(u, o: Obs, a: Action) -> bool:
    """a ∈ K(O), without expanding K."""
    for slot in space(u, o):
        if slot.schema == a.schema and slot.intent == a.intent:
            for key in JUDGE.get(a.schema, ()):
                if a.get(key) not in slot.values(key):
                    return False
            return a.get("claim") is None or a.get("tone") == "deceive"
    return False


def expand(slot: Slot) -> list[Action]:
    keys = JUDGE.get(slot.schema, ())
    out = []
    for vals in product(*(slot.values(k) for k in keys)):
        judge = dict(zip(keys, vals, strict=True))
        if judge.get("claim") is not None and judge.get("tone") != "deceive":
            continue
        out.append(make(slot.schema, slot.intent, judge))
    return out


def candidates(u, o: Obs) -> list[Action]:
    """An ending empties K, but flags are not visible, so callers stop asking once an ending is set (triggers.ended)."""
    return [a for slot in space(u, o) for a in expand(slot)]


# Solutions name candidates; they never add any (rule.md 2).

def solution_action(o_id: str, sol) -> Action:
    return make("try", (o_id, sol.approach), {"rely": sol.rely})


def solution_label(u, o: Obs, a: Action) -> str | None:
    if a.schema != "try" or a.intent[0] not in u.obstacles:
        return None
    for sol in u.obstacles[a.intent[0]].solutions:
        if solution_action(a.intent[0], sol) == a and solution_holds(u, o, a.intent[0], sol):
            return sol.label
    return None


def solution_holds(u, o: Obs, o_id: str, sol) -> bool:
    if sol.rely and rely_atom(u, o.facts, sol.rely, o_id) is None:
        return False
    return holds(sol.when, o.facts, o.hist)
