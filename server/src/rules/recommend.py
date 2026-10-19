"""Three suggested buttons: use what the scene gives, talk, and go somewhere."""

from src.content.schema import PLAYER, Story
from src.world import query
from src.world.state import GameState

from .candidates import Candidate, candidates
from .dsl import all_hold

LIMIT = 3


def _reveals_new(story: Story, state: GameState, target: str) -> bool:
    item = story.items.get(target)
    return item is not None and item.reveals is not None and not query.knows(state.graph, PLAYER, item.reveals)


def _pull(story: Story, state: GameState, move: Candidate) -> int:
    """How much a destination calls: 2 when something the player now holds opens a solution or an
    action there, 1 when an obstacle there is still open, 0 otherwise."""
    place = move.id.partition(":")[2]
    open_here = [(oid, o) for oid, o in story.obstacles.items()
                 if o.place == place and state.obstacles[oid].revealed and state.obstacles[oid].value < o.boxes]
    if any(sol.requires and all_hold(story, state, sol.requires) for _, o in open_here for sol in o.solutions):
        return 2
    # An authored action that has just appeared there (stealing the boat once Naru is free) calls as loudly.
    if any(a.place == place and a.show and all_hold(story, state, a.show) and all_hold(story, state, a.requires)
           and not (a.once and a.id in state.actions_done) for a in story.actions):
        return 2
    return 1 if open_here else 0


def recommend(story: Story, state: GameState, hint: str | None = None) -> list[Candidate]:
    cands = [c for c in candidates(story, state).values() if c.enabled]
    by_kind = {kind: [c for c in cands if c.kind == kind] for kind in {c.kind for c in cands}}
    # Go where what you carry or know opens a way: after winning the order, the prison, not the next door.
    by_kind["move"] = sorted(by_kind.get("move", []), key=lambda c: -_pull(story, state, c))
    unread = [c for c in by_kind.get("inspect", []) if _reveals_new(story, state, c.id.partition(":")[2])]
    solves = sorted(by_kind.get("solve", []), key=lambda c: hint is None or not c.id.startswith(f"solve:{hint}:"))
    # An item an obstacle guarded is what the player just fought for; a clue in hand costs a look. Both
    # used to hide behind the next obstacle's solution, so "take the ledger" never showed after winning it.
    prized = [c for c in by_kind.get("take", []) if any(c.id.partition(":")[2] in o.guards for o in story.obstacles.values())]
    picks = [
        (by_kind.get("use_tag") or prized or unread or solves or by_kind.get("take") or by_kind.get("inspect") or [None])[0],
        (by_kind.get("topic") or by_kind.get("talk") or [None])[0],
        (by_kind.get("act") or by_kind.get("move") or [None])[0],
    ]
    out: list[Candidate] = []
    for pick in picks:
        if pick is not None and pick not in out:
            out.append(pick)
    for extra in [*solves, *by_kind.get("move", [])]:
        if len(out) >= LIMIT:
            break
        if extra not in out:
            out.append(extra)
    return out[:LIMIT]
