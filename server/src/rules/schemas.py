from __future__ import annotations

from dataclasses import dataclass

from ..onto.atoms import PLAYER, State
from ..onto.change import Work
from ..onto.view import facts_of
from .acts import Action
from .candidates import (
    SPENDS,
    active_threats,
    blockers,
    held_clock,
    talk_rolls,
    topic_of,
)
from .costs import settle
from .roll import Mods, modifiers, outcome, risk


@dataclass
class Ctx:
    u: object
    s: State
    h: frozenset
    a: Action
    r: tuple[int, int, int] | None
    work: Work
    hstar: frozenset = frozenset()
    mods: Mods | None = None
    result: str = "none"
    risk: str = "low"

    @property
    def rolled(self) -> bool:
        return self.mods is not None


def scene_end(u, w: Work) -> None:
    w.expire("scene")
    w.set_("stat", (PLAYER, "beats"), 0)
    tick_threats(u, w)


def tick_threats(u, w: Work) -> None:
    for o in active_threats(u, w.state()):
        w.set_("fill", (o,), "+1")


def run(ctx: Ctx, effects) -> None:
    """chapter_to and end belong to triggers.apply."""
    for e in effects:
        if e[0] == "scene_end":
            scene_end(ctx.u, ctx.work)
        else:
            ctx.work.apply_effect(e)


def hidden_block(ctx: Ctx, x: str) -> bool:
    """A blocker the player could not see: believing its hidden sentence reveals it (story.md 3.6)."""
    found = blockers(ctx.u, ctx.s, x)
    for o in found:
        if f"{o}.hidden" in ctx.u.props:
            ctx.work.reveal(PLAYER, f"{o}.hidden")
    return bool(found)


def roll_now(ctx: Ctx) -> None:
    ctx.mods = modifiers(ctx.u, ctx.s, ctx.a)
    ctx.result = outcome(ctx.r, ctx.mods, ctx.risk)


def pay_costs(ctx: Ctx, target: str) -> None:
    """Consume what was relied on (rule.md 2), then the cost table (3.3)."""
    rely = ctx.a.get("rely")
    if rely and rely.startswith("tag:"):
        x, _, slot = rely[4:].rpartition(":")
        ctx.work.untag(x, int(slot))
    elif rely and rely.startswith(SPENDS):
        ctx.work.insert(("spent", PLAYER, rely.partition(":")[2]))
    comp = settle(ctx.u, ctx.work, ctx.result, ctx.risk, ctx.r[2], target, ctx.h)
    if comp is not None:
        run(ctx, comp.effects)


def delta0(ctx: Ctx) -> None:
    a, w, u = ctx.a, ctx.work, ctx.u
    ctx.risk = risk(u, a)
    # Small talk changes nothing in the world; when every greeting cost a beat, players stopped speaking (rule.md 4.1).
    small_talk = a.schema == "talk" and a.intent[1] == "chat" and a.get("tone") not in ("threaten", "deceive")
    quiet = a.schema in ("cut", "grow") or (a.schema == "try" and a.intent[0] == PLAYER) or small_talk
    if not quiet:
        w.set_("stat", (PLAYER, "beats"), "+1")
    globals()[f"_{a.schema}"](ctx, *a.intent)


def _go(ctx, q):
    if hidden_block(ctx, q):
        ctx.result = "blocked"
        return
    for h, g in ctx.s.rows("follows"):
        if g == PLAYER and q in ctx.u.agents[h].avoids:
            ctx.work.retract(("follows", h, PLAYER))
    ctx.work.move(PLAYER, q)


def _look(ctx, x):
    for p in ctx.u.props.values():
        if x in p.about:
            ctx.work.reveal(PLAYER, p.id)


def _take(ctx, x):
    if hidden_block(ctx, x):
        ctx.result = "blocked"
        return
    ctx.work.move(x, PLAYER)


def _give(ctx, x, h):
    w = ctx.work
    w.move(x, h)
    if x in ctx.u.agents[h].wants:
        w.set_("regards", (h, PLAYER, "trust"), "+1")
        w.insert(("owes", h, PLAYER, "kindness"))


def _talk(ctx, h, topic):
    u, w, a = ctx.u, ctx.work, ctx.a
    if hidden_block(ctx, h):
        ctx.result = "blocked"
        return
    if talk_rolls(u, facts_of(u, ctx.s, PLAYER), ctx.h, h, topic):
        roll_now(ctx)
    won = not ctx.rolled or ctx.result == "success"
    if topic == "favor":
        favor = u.agents[h].favor
        if not ctx.rolled:
            run(ctx, favor.effects)
            w.retract(("owes", h, PLAYER, "kindness"))
        elif won:
            run(ctx, favor.effects)
            w.insert(("owes", PLAYER, h, "promise"))
    elif topic == "come":
        if won:
            w.insert(("follows", h, PLAYER))
    elif topic == "stay":
        w.retract(("follows", h, PLAYER))
    elif topic != "chat" and won:
        w.reveal(PLAYER, topic_of(u, h, topic).prop)
    if ctx.rolled:
        pay_costs(ctx, h)
    tone = a.get("tone")
    if tone == "threaten":
        w.set_("regards", (h, PLAYER, "fear"), "+1")
        w.set_("regards", (h, PLAYER, "trust"), "-1")
    claim = a.get("claim")
    if tone == "deceive" and claim is not None and ctx.s.has("believes", h, u.claims[claim]):
        w.set_("regards", (h, PLAYER, "trust"), "-2")
        w.tag(PLAYER, "snag", "chapter", "@suspicion")


def _try(ctx, x, approach):
    if x == PLAYER:
        return
    w = ctx.work
    if hidden_block(ctx, x):
        ctx.result = "blocked"
        return
    roll_now(ctx)
    if ctx.result == "success":
        ob = ctx.u.obstacles.get(x)
        if ob is not None:
            w.set_("fill", (x,), f"+{1 + (approach in ob.fits)}")
        else:
            snags = [i for i, kind, _ in w.state().marks(x) if kind == "snag"]
            if snags:
                w.untag(x, snags[0])
            else:
                w.tag(x, "edge", "scene", None)
    pay_costs(ctx, x)


def _declare(ctx, lid):
    w = ctx.work
    w.reveal(PLAYER, lid)
    run(ctx, ctx.u.latents[lid].effects)
    clock = held_clock(ctx.u, w.state())
    if clock is not None:
        w.set_("fill", (clock,), "+1")


def _cut(ctx, how):
    scene_end(ctx.u, ctx.work)
    if how == "rest":
        ctx.work.set_("stat", (PLAYER, "wounds"), "-1")
        tick_threats(ctx.u, ctx.work)       # on top of the scene end's tick (rule.md, cut(rest))


def _choose(ctx, g, c):
    for cid, _, effects in ctx.u.obstacles[g].choices:
        if cid == c:
            run(ctx, effects)
    ctx.work.retire(g)


def _grow(ctx, *item):
    w = ctx.work
    w.set_("stat", (PLAYER, "growth"), "-1")
    if item[0] == "trait":
        w.drop_stat(PLAYER, item[1])
        w.set_("stat", (PLAYER, item[2]), 1)
    elif item[0] == "scar":
        w.untag(PLAYER, int(item[1]))
    else:
        w.set_("stat", (PLAYER, item[0]), "+1")
