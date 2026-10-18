"""What a mixed or missed check costs, picked by the risk table and never by a model."""

from random import Random

from src.content.schema import PLAYER, Cost, Grade, Risk, Story
from src.world import query
from src.world.state import Change, GameState

from . import dsl

TABLE: dict[tuple[Risk, Grade], list[tuple[str, int]]] = {
    ("low", "mixed"): [("danger", 1)],
    ("low", "miss"): [("danger", 1)],
    ("normal", "mixed"): [("danger", 1), ("snag", 0)],
    ("normal", "miss"): [("danger", 1), ("snag_or_loss", 0)],
    ("high", "mixed"): [("danger", 1), ("loss", 0)],
    ("high", "miss"): [("danger", 2), ("wound_or_loss", 0)],
}


def _payable(state: GameState, cost: Cost) -> bool:
    if cost.kind == "gold":
        return state.player.gold > 0
    if cost.kind == "item":
        return query.holder(state.graph, cost.item) == PLAYER
    return cost.kind == "wound"


def _pay(story: Story, state: GameState, cost: Cost, obstacle: str | None, out: list[Change]) -> None:
    if cost.kind == "gold":
        dsl.gold(state, -cost.value, out)
    elif cost.kind == "item":
        dsl.take(state, cost.item, out)
    elif cost.kind == "wound":
        dsl.wound(state, cost.value, out)
    else:
        dsl.add_tag(state, "snag", obstacle, out)


def pay(
    story: Story,
    state: GameState,
    risk: Risk,
    grade: Grade,
    obstacle: str | None,
    rng: Random,
    out: list[Change],
    partner: str | None = None,
) -> None:
    if grade == "hit":
        return
    costs = story.obstacles[obstacle].costs if obstacle else []
    losses = [c for c in costs if c.kind != "snag" and _payable(state, c)]
    for what, amount in TABLE[(risk, grade)]:
        if what == "danger":
            dsl.danger(story, state, amount, out)
        elif partner is not None:
            dsl.relation(state, partner, -1, out)
        elif what == "snag":
            dsl.add_tag(state, "snag", obstacle, out)
        else:
            pool: list[Cost] = list(losses)
            if what == "snag_or_loss":
                pool.append(Cost(kind="snag"))
            elif what == "wound_or_loss":
                pool.append(Cost(kind="wound"))
            if pool:
                _pay(story, state, rng.choice(pool), obstacle, out)
            else:
                dsl.danger(story, state, 1, out)
