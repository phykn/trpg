from __future__ import annotations

from dataclasses import dataclass

from ..onto.atoms import PLAYER, State
from ..onto.change import Work
from ..onto.view import facts_of
from .acts import Action
from .candidates import (
    FREE,
    SPENDS,
    active_threats,
    avoided,
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
    w.happen.append(("scene_end",))
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
    if ctx.mods.guard:
        ctx.work.happen.append(("guard",))      # the event's mods are atoms alone, and saves from before helped


def pay_costs(ctx: Ctx, target: str) -> None:
    """Consume what was relied on (rule.md 2), then the cost table (3.3)."""
    rely = ctx.a.get("rely")
    if rely and rely.startswith("tag:"):
        x, _, slot = rely[4:].rpartition(":")
        ctx.work.untag(x, int(slot))
    elif rely and rely.startswith(SPENDS):
        x = rely.partition(":")[2]
        if rely.startswith("thing:") and ctx.u.things[x].uses:
            # counted instead of spent for the chapter: the oil can be poured half, then all
            ctx.work.set_("flag", (f"uses.{x}",), "-1")
            if ctx.work.flag[f"uses.{x}"] == 0:
                ctx.work.consume(x)
        else:
            ctx.work.insert(("spent", PLAYER, x))
    guarded = bool(rely) and not rely.startswith(FREE)
    comp = settle(ctx.u, ctx.work, ctx.result, ctx.risk, ctx.r[2], target, ctx.h, guarded)
    if comp is not None:
        run(ctx, comp.effects)


def small_talk(a) -> bool:
    """A chat that neither threatens nor deceives: it changes nothing in the world (rule.md 4.1)."""
    return a.schema == "talk" and a.intent[1] == "chat" and a.get("tone") not in ("threaten", "deceive")


def delta0(ctx: Ctx) -> None:
    a, w, u = ctx.a, ctx.work, ctx.u
    ctx.risk = risk(u, a)
    # Beats on rolls and moves only, and a step a hidden block stopped. When looking and taking cost a beat, a player
    # who walked the map and looked at each thing once had spent 10 of the chapter's 18 before a roll;
    # when every greeting did, players stopped speaking (rule.md 4.1). The beat comes first, so a scene the step ends
    # starts at zero.
    paced = a.schema == "go" or (a.schema == "try" and a.intent[0] != PLAYER) or \
        (a.schema == "talk" and talk_rolls(u, facts_of(u, ctx.s, PLAYER), ctx.h, *a.intent))
    if paced:
        w.set_("stat", (PLAYER, "beats"), "+1")
    globals()[f"_{a.schema}"](ctx, *a.intent)
    if ctx.result == "blocked" and not paced:
        w.set_("stat", (PLAYER, "beats"), "+1")


def _go(ctx, q):
    if hidden_block(ctx, q):
        ctx.result = "blocked"
        return
    f = facts_of(ctx.u, ctx.s, PLAYER)
    for h, g in ctx.s.rows("follows"):
        if g == PLAYER and q in avoided(ctx.u, f, ctx.h, h):
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


def _show(ctx, x, h):
    """Showing is not giving: nothing moves, and a person who wants the thing warms to the sight once (rule.md 5.1)."""
    if hidden_block(ctx, h):
        ctx.result = "blocked"
        return
    if x in ctx.u.agents[h].wants and ctx.u.show_patterns[(x, h)] not in ctx.h:
        ctx.work.set_("regards", (h, PLAYER, "trust"), "+1")


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
            # Fear or a lie pays instead of a promise; both cost trust below (rule.md 5.1).
            if a.get("tone") not in ("threaten", "deceive"):
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
    # A failed talk teaches what moves the person, so the next try is informed, not the same roll (rule.md 5.1).
    if ctx.result == "fail" and f"{h}.desire" in u.props:
        w.reveal(PLAYER, f"{h}.desire")
    tone = a.get("tone")
    claim = a.get("claim")
    caught = tone == "deceive" and claim is not None and ctx.s.has("believes", h, u.claims[claim])
    if ctx.rolled and won and tone != "threaten" and not caught:
        w.set_("regards", (h, PLAYER, "trust"), "+1")
    if tone == "threaten":
        w.set_("regards", (h, PLAYER, "fear"), "+1")
        w.set_("regards", (h, PLAYER, "trust"), "-1")
    if caught:
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
            # Forcing buys a box: it costs a risk step and a heavy fail, so it must gain something.
            w.set_("fill", (x,), f"+{1 + (approach in ob.fits) + (ctx.a.get('strain') == 'forced')}")
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
        wounds = [i for i, _, life in ctx.work.state().marks(PLAYER) if life == "wound"]
        if wounds:
            ctx.work.untag(PLAYER, wounds[0])
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
    elif item[0] == "wound":
        w.untag(PLAYER, int(item[1]))
    else:
        w.set_("stat", (PLAYER, item[0]), "+1")
