from __future__ import annotations

from ..onto.atoms import PLAYER, State
from ..onto.cond import holds
from .candidates import active_threats, held_clock
from .schemas import Ctx, run, scene_end


def ended(s: State) -> bool:
    return s.flag("ending") is not None


def apply(ctx: Ctx, effects) -> None:
    for e in effects:
        if e[0] == "chapter_to":
            chapter_to(ctx, e[1], e[2], *e[3:])
        elif e[0] == "end":
            end(ctx, e[1])
        else:
            run(ctx, (e,))


def promise_kept(ctx: Ctx, h: str, s: State) -> bool:
    return holds(ctx.u.agents[h].favor.keep, s, ctx.hstar)


def promise_broken(ctx: Ctx, h: str, s: State) -> bool:
    b = ctx.u.agents[h].favor.breaks
    return b is not None and holds(b, s, ctx.hstar)


def close_promise(ctx: Ctx, h: str, kept: bool) -> None:
    w = ctx.work
    w.retract(("owes", PLAYER, h, "promise"))
    if kept:
        w.set_("regards", (h, PLAYER, "trust"), "+1")
    else:
        w.set_("regards", (h, PLAYER, "trust"), "-2")
        w.tag(PLAYER, "snag", "chapter", "@broken_promise")


def player_promises(s: State) -> list[str]:
    return sorted(h for g, h, k in s.rows("owes") if g == PLAYER and k == "promise")


def chapter_to(ctx: Ctx, k: int, extra, late: bool = False) -> None:
    w = ctx.work
    w.set_("flag", ("chapter",), k)
    w.expire("chapter")
    for g, h, _ in sorted(ctx.promises):
        s = w.state()
        if s.has("owes", g, h, "promise"):
            close_promise(ctx, h, promise_kept(ctx, h, s))
    w.clear_spent(PLAYER)
    w.retire(f"clock.{k - 1}")
    w.retire(f"deadline.{k - 1}")
    w.move(f"clock.{k}", PLAYER)
    w.move(f"deadline.{k}", PLAYER)
    # A chapter its deadline ended costs time: without it a missed goal changed nothing (qa_test/runs/play-1-*).
    if late and ctx.u.boxes(f"deadline.{k}") > 1:
        w.set_("fill", (f"deadline.{k}",), "+1")
    w.set_("stat", (PLAYER, "growth"), "+1")
    apply(ctx, extra)


def end(ctx: Ctx, e: str) -> None:
    w = ctx.work
    w.set_("flag", ("ending",), e)
    for h in player_promises(w.state()):
        close_promise(ctx, h, promise_kept(ctx, h, w.state()))


# Engine triggers are level-fired, in this order.

def t_risk(ctx: Ctx) -> bool:
    s = ctx.work.state()
    c = held_clock(ctx.u, s)
    if c is None or s.fill(c) < ctx.u.boxes(c):
        return False
    apply(ctx, ctx.u.chapter_of(int(c.split(".")[1])).crisis)
    ctx.work.set_("fill", (c,), 0)
    return True


def t_fall(ctx: Ctx) -> bool:
    w = ctx.work
    if w.state().stat(PLAYER, "wounds") != ctx.u.wound_boxes:
        return False
    w.set_("stat", (PLAYER, "wounds"), 0)
    w.tag(PLAYER, "snag", "scar", "@scar")
    scene_end(ctx.u, w)
    marks = w.state().marks(PLAYER)
    if len(marks) == 3 and all(life == "scar" for _, _, life in marks):
        end(ctx, "collapse")
    return True


def t_scene(ctx: Ctx) -> bool:
    if ctx.work.state().stat(PLAYER, "beats") != ctx.u.beats:
        return False
    scene_end(ctx.u, ctx.work)
    return True


def t_arrive(ctx: Ctx) -> bool:
    s = ctx.work.state()
    full = [o for o in active_threats(ctx.u, s) if s.fill(o) >= ctx.u.boxes(o)]
    for o in full:
        apply(ctx, ctx.u.obstacles[o].arrival)
        ctx.work.retire(o)
        if ended(ctx.work.state()):
            break
    return bool(full)


def t_promise(ctx: Ctx) -> bool:
    s = ctx.work.state()
    due = [h for h in player_promises(s) if promise_kept(ctx, h, s) or promise_broken(ctx, h, s)]
    for h in due:
        close_promise(ctx, h, promise_kept(ctx, h, ctx.work.state()))
    return bool(due)


ENGINE = (t_risk, t_fall, t_scene, t_arrive, t_promise)


def bound(u) -> int:
    """m + 3 + w + q: story triggers, three engine ones, threats, favors (rule.md 8)."""
    w = sum(o.sub in ("threat", "fork", "deadline") for o in u.obstacles.values())
    q = sum(a.favor is not None for a in u.agents.values())
    return len(u.triggers) + 3 + w + q


def scan(ctx: Ctx, start_true: list[bool]) -> None:
    """Fire the first trigger that fires, back to the top; stop when none fires or an ending is set."""
    fired: set[int] = set()
    limit, n = bound(ctx.u), 0
    while not ended(ctx.work.state()):
        s = ctx.work.state()
        for i, t in enumerate(ctx.u.triggers):
            if i not in fired and not start_true[i] and holds(t.when, s, ctx.hstar):
                fired.add(i)
                apply(ctx, t.effects)
                break
        else:
            if not any(f(ctx) for f in ENGINE):
                return
        n += 1
        if n > limit:
            raise RuntimeError(f"trigger scan did not settle after {limit} firings")
