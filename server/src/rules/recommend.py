"""Three suggested buttons: use what the scene gives, talk, and go somewhere."""

from src.content.schema import Story
from src.world.state import GameState

from .candidates import Candidate, candidates

LIMIT = 3


def recommend(story: Story, state: GameState, hint: str | None = None) -> list[Candidate]:
    cands = [c for c in candidates(story, state).values() if c.enabled]
    by_kind = {kind: [c for c in cands if c.kind == kind] for kind in {c.kind for c in cands}}
    solves = sorted(by_kind.get("solve", []), key=lambda c: hint is None or not c.id.startswith(f"solve:{hint}:"))
    picks = [
        (by_kind.get("use_tag") or solves or by_kind.get("take") or by_kind.get("inspect") or [None])[0],
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
