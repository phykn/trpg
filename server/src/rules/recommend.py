from __future__ import annotations

from ..onto.atoms import APPROACHES, PLAYER
from ..onto.cond import atoms_of
from ..onto.view import Obs
from .acts import Action, make
from .candidates import active_threats, admits, solution_action, solution_holds


def recommend(u, o: Obs) -> list[Action]:
    picks: list[Action] = []
    for pick in (_tag(u, o), _talk(u, o), _forward(u, o)):
        if pick is not None and pick not in picks and admits(u, o, pick):
            picks.append(pick)
    return picks


def _obstacles_here(u, o: Obs) -> list[str]:
    f = o.facts
    return [x for x in sorted(o.seen, key=u.rank)
            if x in u.obstacles and u.obstacles[x].sub == "plain" and (f.fill(x) or 0) < u.boxes(x)]


def _tag(u, o: Obs) -> Action | None:
    f = o.facts
    here = f.where(PLAYER)
    edges = [(x, i) for x in (PLAYER, here) for i, kind, _ in f.marks(x) if kind == "edge"]
    targets = [x for x in _obstacles_here(u, o) if admits(u, o, make("try", (x, APPROACHES[0])))]
    if not edges or not targets:
        return None
    x = targets[0]
    owner, slot = edges[0]
    # Every plain obstacle has two or more solutions (story.md 3.6), so the first one's approach.
    return make("try", (x, u.obstacles[x].solutions[0].approach), {"rely": f"tag:{owner}:{slot}"})


def _talk(u, o: Obs) -> Action | None:
    f = o.facts
    here = f.where(PLAYER)
    for h in sorted(o.seen, key=u.rank):
        if h in u.agents and f.where(h) == here:
            for t in u.agents[h].topics:
                if not f.has("believes", PLAYER, t.prop):
                    return make("talk", (h, t.id))
    return None


def _forward(u, o: Obs) -> Action | None:
    f = o.facts
    for g in active_threats(u, f):
        ob = u.obstacles[g]
        if ob.sub == "fork":
            return make("choose", (g, ob.choices[0][0]))
    for x in _obstacles_here(u, o):
        for sol in u.obstacles[x].solutions:
            a = solution_action(x, sol)
            if solution_holds(u, o, x, sol) and admits(u, o, a):
                return a
    k = next((c.k for c in u.chapters if _chapter_is(o, c.k)), None)
    if k is None:
        return None
    goal = u.chapter_of(k).goal
    if goal is not None:
        places = {leaf[2] for leaf in atoms_of(goal) if leaf[0] == "at" and leaf[1] == PLAYER}
    else:
        # A chapter with no goal ends in an ending; head for the obstacles the endings fill, or the last chapter
        # had no button at all away from them (qa_test/runs/play-3-talker 24).
        places = {u.obstacles[leaf[1]].at for e in u.endings.values() if e.when for leaf in atoms_of(e.when)
                  if leaf[0] == "fill" and leaf[1] in u.obstacles and u.obstacles[leaf[1]].at}
    here = f.where(PLAYER)
    if here in places:
        return None
    # The first step of a shortest path over the story's exits toward a goal place; ties by story order.
    # The goal names the place, so its route is known even where the observation hides a blocked link.
    first: dict[str, str] = {}
    frontier = [here]
    while frontier:
        nxt = []
        for p in frontier:
            for q in sorted(u.places[p].exits, key=u.rank):
                if q == here or q in first:
                    continue
                first[q] = first.get(p, q)
                if q in places:
                    a = make("go", (first[q],))
                    return a if admits(u, o, a) else None
                nxt.append(q)
        frontier = nxt
    return None


def _chapter_is(o: Obs, k: int) -> bool:
    """The chapter is not a visible fact; the clock the player carries names it."""
    return o.facts.where(f"clock.{k}") == PLAYER
