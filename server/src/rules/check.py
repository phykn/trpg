"""2d6 checks: modifiers, grades, effect size, risk, and odds."""

from itertools import product
from random import Random

from src.content.schema import PLAYER, Approach, Grade, Risk, Story
from src.world import query
from src.world.state import GameState, ImproviseStep, Roll, Uses

from .dsl import here

TRACE_MODS: dict[str, tuple[str, int]] = {
    "wanted": ("finesse", -1),
    "suspicion": ("charm", -1),
    "reputation": ("charm", 1),
}
RISK_ORDER: list[Risk] = ["low", "normal", "high"]


def rng_for(state: GameState, step: int) -> Random:
    return Random(f"{state.seed}:{state.turn}:{step}")


def grade(total: int) -> Grade:
    return "hit" if total >= 10 else "mixed" if total >= 7 else "miss"


def roll(rng: Random, modifier: int) -> Roll:
    dice = (rng.randint(1, 6), rng.randint(1, 6))
    total = sum(dice) + modifier
    return Roll(dice=dice, modifier=modifier, total=total, grade=grade(total))


def odds(modifier: int) -> tuple[float, float, float]:
    totals = [a + b + modifier for a, b in product(range(1, 7), repeat=2)]
    hit = round(sum(t >= 10 for t in totals) / 36, 3)
    miss = round(sum(t <= 6 for t in totals) / 36, 3)
    return hit, round(1 - hit - miss, 3), miss


def usable(story: Story, state: GameState, target: str | None, uses: Uses) -> Uses:
    """Keep only the uses that exist in the scene and have not been spent."""
    tag_ok = any(
        t.id == uses.tag and t.kind == "edge" and t.target in (None, target)
        for t in state.tags.get(here(state), [])
    )
    things = {
        *query.carried(state.graph, PLAYER),
        *query.known(state.graph, PLAYER),
        *state.player.skills,
    }
    trait_ok = uses.trait in state.player.traits and uses.trait not in state.player.trait_used
    return Uses(
        tag=uses.tag if tag_ok else None,
        thing=uses.thing if uses.thing in things else None,
        trait=uses.trait if trait_ok else None,
    )


def modifier(
    story: Story, state: GameState, approach: Approach, target: str | None, uses: Uses, extra: int = 0
) -> int:
    snags = [
        t for t in [*state.tags.get(here(state), []), *state.traces]
        if t.kind == "snag" and not t.trace and t.target in (None, target)
    ]
    bonus = extra + (uses.tag is not None) + (uses.trait is not None) + (uses.thing is not None)
    bonus -= min(2, len(snags))
    for trace in state.traces:
        hit_approach, mod = TRACE_MODS[trace.trace] if trace.trace else ("", 0)
        if hit_approach == approach:
            bonus += mod
    return state.player.approaches[approach] + max(-3, min(3, bonus))


def effect_size(story: Story, obstacle: str, approach: Approach, used_tag: bool) -> int:
    fits = approach in story.obstacles[obstacle].fits
    return min(3, 1 + fits + used_tag)


def risk_of(story: Story, step: ImproviseStep) -> Risk:
    level = RISK_ORDER.index(step.risk)
    if step.target in story.obstacles and step.approach in story.obstacles[step.target].clashes:
        level += 1
    if step.plausibility == "stretch":
        level = 2
    return RISK_ORDER[min(2, level)]
